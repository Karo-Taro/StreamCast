"""24/7 streaming engine.

For each live stream we run one ffmpeg process that reads a concat playlist of
the already-normalized clips and pushes it to YouTube via RTMP. Because every
clip shares the same codec/resolution/fps/GOP, we stream with `-c copy` (no
re-encode) — cheap on CPU and seamless between clips.

Hot reload: instead of looping one fixed playlist forever, the supervisor plays
the queue in "blocks" (a playlist that repeats the current queue up to
RELOAD_BLOCK_SECONDS). When a block ends, it rebuilds the playlist from the
*current* database state and starts the next block. So adding videos or
reordering the queue while live is picked up automatically at the next block —
no manual stop/start. `apply_now()` forces an immediate block restart.

A watchdog restarts ffmpeg if it dies (network blip, YouTube reset), so the
channel self-heals.
"""
import logging
import random
import subprocess
import threading
import time
import uuid
from collections import deque

import config
import db
import storage


def _has_audio_stream(path):
    """True if the media file carries at least one audio stream."""
    try:
        out = subprocess.check_output(
            [config.FFPROBE, "-v", "error", "-select_streams", "a:0",
             "-show_entries", "stream=index", "-of", "csv=p=0", str(path)],
            text=True, encoding="utf-8", errors="replace",
        )
        return bool(out.strip())
    except Exception:
        return False


class _Runner:
    """Owns one ffmpeg process + watchdog for a single stream."""

    def __init__(self, stream_id, live_since=None):
        self.stream_id = stream_id
        self.proc = None
        self.playlist_path = None
        self.loop_video_path = None     # music mode: video looped as the background
        self._mix_video_audio = False   # music mode: mix the background's own sound
        self._video_volume = 0.5        # music mode: background sound level (0..2)
        self._music_volume = 1.0        # music mode: playlist audio level (0..2)
        self._stream_volume = 1.0       # video mode: playback audio level (0..2)
        self._stop = threading.Event()
        self._reload = threading.Event()   # set to force an immediate block restart
        self._thread = None
        self.last_error = ""

        # ffmpeg stderr is drained continuously by a helper thread (a full pipe
        # would block ffmpeg itself); the tail is kept for error reporting.
        self._stderr_tail = deque(maxlen=20)

        # Live-session uptime (wall clock). Set once per runner start; block
        # rebuilds and watchdog restarts don't reset it. Reset on next start.
        # _live_since keeps a resumed session's original start (auto-resume).
        self.session_started = None
        self.session_stopped = None
        self._live_since = live_since

        # now-playing tracking (computed from wall-clock, since -re plays realtime)
        self._block_started = 0.0          # monotonic time the current block began
        self._block_videos = []            # {id, duration} in actual play order
        self._block_total = 0.0            # summed duration of the whole block

    # -- playlist ------------------------------------------------------------
    def _build_playlist(self):
        """Rebuild from current DB state.

        Returns (path, play_order, block_total): play_order is the flattened
        list of {id, duration} in the exact order the block plays them, and
        block_total is its summed duration. For music streams the entries are
        audio tracks; the visual is one looped video (self.loop_video_path).
        Sets self.last_error and returns (None, [], 0.0) when nothing is
        ready to play.

        While a quality-mode switch re-encodes the queue, the playlist is
        built from the previous-quality copies (kept in prev_* columns) so
        the broadcast never mixes parameters mid-stream.
        """
        stream = db.get_stream(self.stream_id)
        stream_type = stream["stream_type"] if stream and "stream_type" in stream.keys() else "video"
        is_music = stream_type == "music"
        is_shuffle = bool(stream["shuffle"]) if stream else False
        loop = bool(stream["loop_queue"]) if stream else False

        videos_all = db.list_videos(self.stream_id)
        # Pending = an existing copy is being re-encoded for a mode switch.
        pending = any(
            v["status"] == "waiting_encode" and v["encoded_name"]
            for v in videos_all
        )
        if not pending:
            # Transition finished (or never started): drop previous copies.
            for v in videos_all:
                if v["prev_encoded_name"]:
                    try:
                        storage.video_encoded_path(v, v["prev_encoded_name"]).unlink(missing_ok=True)
                    except OSError:
                        pass
                    db.update_video(v["id"], prev_encoded_name=None, prev_encode_preset=None,
                                    prev_encoded_storage_id=None)
            videos_all = db.list_videos(self.stream_id)

        def copy_name(v):
            """The copy this row should play right now."""
            if pending and v["status"] == "completed":
                return v["prev_encoded_name"]  # keep the whole block uniform
            return v["encoded_name"]

        if is_music:
            videos_base = [v for v in videos_all if v["kind"] == "audio" and copy_name(v)]
            if not videos_base:
                self.last_error = "No ready audio files in queue"
                return None, [], 0.0
            loop_video = None
            loop_id = stream["loop_video_id"] if stream and "loop_video_id" in stream.keys() else None
            if loop_id:
                lv = next((v for v in videos_all if v["id"] == loop_id and copy_name(v)), None)
                if lv:
                    loop_video = lv
            if loop_video is None:
                self.last_error = "No loop video selected — upload a video and set it as the background"
                return None, [], 0.0
            self.loop_video_path = storage.video_encoded_path(
                loop_video, copy_name(loop_video)).resolve()
            self._mix_video_audio = bool(
                stream["mix_video_audio"] if "mix_video_audio" in stream.keys() else False
            )
            self._video_volume = min(2.0, max(0.0, float(
                stream["video_volume"] if "video_volume" in stream.keys() and
                stream["video_volume"] is not None else 0.5
            )))
            self._music_volume = min(2.0, max(0.0, float(
                stream["music_volume"] if "music_volume" in stream.keys() and
                stream["music_volume"] is not None else 1.0
            )))
            self._stream_volume = 1.0
            if self._mix_video_audio and not _has_audio_stream(self.loop_video_path):
                # Background has no sound to mix — fall back to playlist-only audio.
                self._mix_video_audio = False
        else:
            videos_base = [v for v in videos_all if v["kind"] != "audio" and copy_name(v)]
            if not videos_base:
                self.last_error = "No ready videos in queue"
                return None, [], 0.0
            self.loop_video_path = None
            self._mix_video_audio = False
            self._music_volume = 1.0
            self._stream_volume = min(2.0, max(0.0, float(
                stream["stream_volume"] if "stream_volume" in stream.keys() and
                stream["stream_volume"] is not None else 1.0
            )))
            self._video_volume = 0.5

        one_pass = sum((v["duration"] or 0) for v in videos_base)
        repeats = 1
        if loop and one_pass > 0:
            repeats = max(1, int(config.RELOAD_BLOCK_SECONDS // one_pass) or 1)

        lines = ["ffconcat version 1.0"]
        play_order = []
        prev_ids = None
        for _ in range(repeats):
            cycle = list(videos_base)
            if is_shuffle and len(cycle) > 1:
                # Fresh order every pass; never repeat the previous pass's order.
                for _ in range(10):
                    random.shuffle(cycle)
                    ids = [v["id"] for v in cycle]
                    if ids != prev_ids:
                        break
            prev_ids = [v["id"] for v in cycle] if is_shuffle else None
            for v in cycle:
                # copy_name: while a mode switch re-encodes the queue, every
                # entry plays its previous-quality copy (uniform block).
                path = storage.video_encoded_path(v, copy_name(v)).resolve()
                # Use a simpler replacement to avoid JS escaping issues
                safe_path = str(path).replace('\\', '/').replace("'", "'\\''")
                lines.append(f"file '{safe_path}'")
                play_order.append({"id": v["id"], "duration": v["duration"] or 0})

        pl = config.STORAGE_DIR / f"playlist_{self.stream_id}_{uuid.uuid4().hex}.txt"
        pl.write_text("\n".join(lines) + "\n", encoding="utf-8")
        block_total = sum(v["duration"] for v in play_order)
        return pl, play_order, block_total

    def _cleanup_playlist(self):
        if self.playlist_path is None:
            return
        try:
            self.playlist_path.unlink(missing_ok=True)
        except Exception:
            pass
        self.playlist_path = None

    def _ffmpeg_cmd(self, stream):
        rtmp_url = f"{config.RTMP_BASE}/{stream['rtmp_key']}"
        limiter = "alimiter=limit=0.98:level=false"  # keep boosts from clipping
        if self.loop_video_path is not None:
            # Music stream: one video loops forever as the visual, its audio is
            # replaced (or mixed, see below) with the block's audio playlist.
            # -shortest ends the block when the playlist finishes, same block
            # cycle as video streams.
            if self._mix_video_audio:
                return [
                    config.FFMPEG, "-hide_banner", "-loglevel", "warning",
                    "-stream_loop", "-1", "-re",  # loop the background video forever
                    "-i", str(self.loop_video_path),
                    "-f", "concat", "-safe", "0", "-re",
                    "-i", str(self.playlist_path),
                    "-filter_complex",
                    # Independent gain per source; normalize=0 keeps our explicit
                    # levels; duration=shortest ends the mix with the playlist (the
                    # looped background never ends). The limiter catches sums > 1.
                    "[0:a]aformat=sample_rates=44100:channel_layouts=stereo,"
                    f"volume={self._video_volume:.2f}[bg];"
                    "[1:a]aformat=sample_rates=44100:channel_layouts=stereo,"
                    f"volume={self._music_volume:.2f}[pl];"
                    f"[bg][pl]amix=inputs=2:duration=shortest:normalize=0,{limiter}[mix]",
                    "-map", "0:v:0", "-map", "[mix]",
                    "-c:v", "copy",           # background video is pre-normalized
                    "-c:a", "aac", "-b:a", config.AUDIO_BITRATE, "-ar", "44100", "-ac", "2",
                    "-shortest",
                    "-f", "flv",
                    "-flvflags", "no_duration_filesize",
                    rtmp_url,
                ]
            cmd = [
                config.FFMPEG, "-hide_banner", "-loglevel", "warning",
                "-stream_loop", "-1", "-re",  # loop the background video forever
                "-i", str(self.loop_video_path),
                "-f", "concat", "-safe", "0", "-re",
                "-i", str(self.playlist_path),
                "-map", "0:v:0", "-map", "1:a:0",
                "-c:v", "copy",           # background video is pre-normalized
            ]
            if abs(self._music_volume - 1.0) > 1e-6:
                # Playlist gain requires re-encoding its audio.
                cmd += [
                    "-filter:a", f"volume={self._music_volume:.2f},{limiter}",
                    "-c:a", "aac", "-b:a", config.AUDIO_BITRATE, "-ar", "44100", "-ac", "2",
                ]
            else:
                cmd += ["-c:a", "aac", "-b:a", config.AUDIO_BITRATE, "-ar", "44100", "-ac", "2"]
            cmd += ["-shortest", "-f", "flv", "-flvflags", "no_duration_filesize", rtmp_url]
            return cmd
        cmd = [
            config.FFMPEG, "-hide_banner", "-loglevel", "warning",
            "-re",                      # read at native rate = real-time push
            "-f", "concat", "-safe", "0",
            "-i", str(self.playlist_path),
        ]
        if abs(self._stream_volume - 1.0) > 1e-6:
            # Playback gain: video stays a stream copy, only audio re-encodes.
            cmd += [
                "-c:v", "copy",
                "-filter:a", f"volume={self._stream_volume:.2f},{limiter}",
                "-c:a", "aac", "-b:a", config.AUDIO_BITRATE, "-ar", "44100", "-ac", "2",
            ]
        else:
            cmd += ["-c", "copy"]       # no re-encode: clips are pre-normalized
        cmd += ["-f", "flv", "-flvflags", "no_duration_filesize", rtmp_url]
        return cmd

    # -- lifecycle -----------------------------------------------------------
    def start(self):
        stream = db.get_stream(self.stream_id)
        if not stream or not stream["rtmp_key"]:
            self.last_error = "No RTMP key set"
            return False
        # Validate there is at least one ready file before spawning a thread.
        pl, play_order, block_total = self._build_playlist()
        if pl is None:
            # _build_playlist already set a specific last_error message.
            return False
        self.playlist_path, self._block_videos, self._block_total = pl, play_order, block_total
        self._stop.clear()
        self._reload.clear()
        self.session_started = self._live_since or time.time()
        self.session_stopped = None
        self._thread = threading.Thread(target=self._supervise, daemon=True)
        self._thread.start()
        return True

    def _drain_stderr(self):
        """Read ffmpeg's stderr in the background until the process exits.

        Without a reader the pipe buffer (~64 KB) fills up on warning-heavy
        runs (e.g. repeated 'Non-monotonous DTS' with concat) and ffmpeg
        blocks on write — looking exactly like a hung stream.
        """
        try:
            for line in self.proc.stderr:
                self._stderr_tail.append(line.rstrip())
        except Exception:
            pass
        finally:
            try:
                self.proc.stderr.close()
            except Exception:
                pass

    def _spawn(self, stream):
        self.proc = subprocess.Popen(
            self._ffmpeg_cmd(stream),
            stdout=subprocess.DEVNULL, stderr=subprocess.PIPE, text=True,
            encoding="utf-8", errors="replace",
        )
        threading.Thread(target=self._drain_stderr, daemon=True).start()
        self._block_started = time.monotonic()
        db.set_live(self.stream_id, True, pid=self.proc.pid,
                    live_since=self.session_started)

    def _supervise(self):
        """Play the queue block by block, rebuilding between blocks."""
        backoff = 2
        first_failure = None   # start of the current crash streak (grace window)
        spawned_at = None
        while not self._stop.is_set():
            stream = db.get_stream(self.stream_id)
            if not stream:
                break

            # (Re)build the playlist from current queue state for this block.
            if self.playlist_path is None:
                pl, play_order, block_total = self._build_playlist()
                if pl is None:
                    # queue emptied while live — wait and retry, don't die
                    self.last_error = "Queue is empty"
                    time.sleep(5)
                    continue
                self.playlist_path, self._block_videos, self._block_total = pl, play_order, block_total

            self._spawn(stream)
            spawned_at = time.time()

            # Wait for ffmpeg to finish this block, but wake early on reload.
            killed_by_us = False
            while True:
                try:
                    self.proc.wait(timeout=1)
                    break  # ffmpeg exited (block done or crashed)
                except subprocess.TimeoutExpired:
                    if self._stop.is_set() or self._reload.is_set():
                        killed_by_us = True
                        self.proc.terminate()
                        try:
                            self.proc.wait(timeout=8)
                        except subprocess.TimeoutExpired:
                            self.proc.kill()
                        break

            rc = self.proc.returncode
            block_was_reload = self._reload.is_set()
            self._reload.clear()
            self._cleanup_playlist()  # force rebuild next iteration

            if self._stop.is_set():
                break

            if block_was_reload:
                backoff = 2
                first_failure = None  # clean block switch — healthy again
                continue  # user changed the queue -> straight into a fresh block

            # ffmpeg exited on its own. A clean exit (rc 0) is a normal block/loop
            # boundary; a non-zero code means it faulted (network, bad key, etc).
            if not killed_by_us and rc not in (0, None):
                # The drain thread kept the tail for us (the pipe reader can't
                # block here — the process has already exited).
                self.last_error = (" | ".join(self._stderr_tail) or "").strip()[-300:]
                now = time.time()
                if first_failure is None or now - spawned_at >= config.YOUTUBE_GRACE_SECONDS:
                    # It ran healthy since the last spawn — start a new streak.
                    first_failure = now
                if now - first_failure + backoff >= config.YOUTUBE_GRACE_SECONDS:
                    # YouTube has finalized (or is about to finalize) the broadcast;
                    # keep retrying and we'd only split it into multiple videos.
                    self.last_error = ("Stream kept failing — YouTube grace window "
                                       "exceeded; stopped. Restart when ready.")
                    break
                time.sleep(backoff)
                backoff = min(backoff * 2, 30)
            else:
                first_failure = None
                self.last_error = ""
                backoff = 2
                # Looping disabled + queue finished cleanly -> end the broadcast.
                stream = db.get_stream(self.stream_id)
                if stream and not stream["loop_queue"]:
                    break

        self._cleanup_playlist()
        if self.session_started:
            self.session_stopped = time.time()
        db.set_live(self.stream_id, False, pid=None)
        # Persist the reason the session ended so it survives an app restart.
        db.update_stream(self.stream_id, last_error=self.last_error)

    def apply_now(self):
        """Force the current block to end and rebuild from the latest queue."""
        self._reload.set()

    def stop(self):
        self._stop.set()
        self.last_error = ""  # manual stop is not an error
        if self.proc and self.proc.poll() is None:
            self.proc.terminate()
            try:
                self.proc.wait(timeout=8)
            except subprocess.TimeoutExpired:
                self.proc.kill()
                try:
                    self.proc.wait(timeout=3)
                except subprocess.TimeoutExpired:
                    pass
        self._cleanup_playlist()
        db.set_live(self.stream_id, False, pid=None)

    def is_running(self):
        return self._thread is not None and self._thread.is_alive()

    def now_playing(self):
        """Which video is on air right now, and progress through it.

        Position is derived from elapsed wall-clock (ffmpeg -re plays in real
        time), walked through the block's actual play order — so it stays
        correct with shuffle on. No ffmpeg log parsing needed.
        """
        if not self._block_videos or self._block_total <= 0:
            return None
        elapsed = (time.monotonic() - self._block_started) % self._block_total
        acc = 0.0
        for v in self._block_videos:
            dur = v["duration"] or 0
            if elapsed < acc + dur:
                return {
                    "video_id": v["id"],
                    "offset": round(elapsed - acc, 1),
                    "duration": round(dur, 1),
                }
            acc += dur
        return None


class StreamManager:
    """Registry of running streams, keyed by stream id."""

    def __init__(self):
        self._runners = {}
        self._lock = threading.Lock()
        self._sched_thread = None
        self._sched_stop = threading.Event()

    def start_stream(self, stream_id, live_since=None):
        with self._lock:
            existing = self._runners.get(stream_id)
            if existing and existing.is_running():
                return True, "Already live"
            runner = _Runner(stream_id, live_since=live_since)
            ok = runner.start()
            if ok:
                self._runners[stream_id] = runner
                return True, "Started"
            return False, runner.last_error or "Failed to start"

    def stop_stream(self, stream_id):
        with self._lock:
            runner = self._runners.pop(stream_id, None)
        if runner:
            runner.stop()
            return True, "Stopped"
        # Not tracked in memory (e.g. after app restart) — just clear the flag.
        db.set_live(stream_id, False, pid=None)
        return True, "Stopped"

    def apply_now(self, stream_id):
        runner = self._runners.get(stream_id)
        if runner and runner.is_running():
            runner.apply_now()
            return True, "Applying new queue"
        return False, "Stream is not live"

    def is_live(self, stream_id):
        runner = self._runners.get(stream_id)
        return bool(runner and runner.is_running())

    def uptime(self, stream_id):
        """Seconds since the current session started, or None when offline."""
        runner = self._runners.get(stream_id)
        if runner and runner.is_running() and runner.session_started:
            return round(time.time() - runner.session_started, 1)
        return None

    def status(self, stream_id):
        runner = self._runners.get(stream_id)
        if runner and runner.is_running():
            uptime = None
            if runner.session_started:
                uptime = round(time.time() - runner.session_started, 1)
            return {
                "live": True,
                "error": runner.last_error,
                "now_playing": runner.now_playing(),
                "uptime": uptime,
            }
        return {
            "live": False,
            "error": runner.last_error if runner else "",
            "now_playing": None,
            "uptime": None,
        }

    # -- scheduler -----------------------------------------------------------
    def resume_interrupted(self):
        """Restart streams that were live when the server went down.

        The runner registry is memory-only, but streams.is_live is persisted:
        a flag still set at boot means the user wanted that stream live. Only
        call once, from bootstrap. Returns (resumed_ids, failed[(id, msg)]).
        """
        resumed, failed = [], []
        for s in db.list_streams():
            if not s.get("is_live"):
                continue
            live_since = s.get("live_since")
            last_seen = s.get("last_seen")
            if live_since and last_seen and live_since < last_seen <= time.time():
                # The stream kept a heartbeat, so we know how long it actually
                # streamed before the crash: shift the session start forward by
                # the downtime instead of counting it as uptime.
                live_since = time.time() - (last_seen - live_since)
            # None (pre-feature flag) → start the uptime from now.
            ok, msg = self.start_stream(s["id"], live_since=live_since or time.time())
            if ok:
                resumed.append(s["id"])
            else:
                # Clear the flag so a permanently broken stream doesn't linger
                # as phantom-live; a transient failure just needs one click.
                db.set_live(s["id"], False, pid=None)
                failed.append((s["id"], msg, live_since))
        if failed:
            self._schedule_resume_retry(failed)
        return resumed, failed

    def _schedule_resume_retry(self, failed, delay=45.0):
        """One background retry for streams that failed to resume — the usual
        cause is the network not being up yet at boot. The is_live flag stays
        cleared meanwhile, so the UI shows the stream as offline until it
        actually starts."""
        def _retry():
            time.sleep(delay)
            log = logging.getLogger("streamcast")
            for sid, _first_msg, live_since in failed:
                ok, msg = self.start_stream(sid, live_since=live_since or time.time())
                if ok:
                    log.info("Resumed stream %d on retry", sid)
                else:
                    log.warning("Stream %d still failed to resume: %s", sid, msg)
        threading.Thread(target=_retry, daemon=True).start()

    def start_scheduler(self):
        if self._sched_thread and self._sched_thread.is_alive():
            return
        self._sched_stop.clear()
        self._sched_thread = threading.Thread(target=self._sched_loop, daemon=True)
        self._sched_thread.start()

    def _sched_loop(self):
        while not self._sched_stop.is_set():
            now = time.time()
            for s in db.list_streams():
                if self.is_live(s["id"]):
                    # Live heartbeat: lets a post-crash resume tell streamed
                    # time from server downtime (see resume_interrupted).
                    db.update_stream(s["id"], last_seen=now)
                sched = s.get("scheduled_at")
                if sched and sched <= now and not self.is_live(s["id"]):
                    db.update_stream(s["id"], scheduled_at=None)
                    self.start_stream(s["id"])
            time.sleep(10)

    def shutdown(self):
        self._sched_stop.set()
        for sid in list(self._runners.keys()):
            self.stop_stream(sid)


manager = StreamManager()