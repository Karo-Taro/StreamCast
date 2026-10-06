"""Background encoder.

Uploaded files come in every shape (different codecs, resolutions, fps). To play
them back-to-back in a seamless 24/7 stream we normalize each one to a single
target format up front. Then the streamer can concat + copy them with no
real-time transcoding, which keeps CPU low and avoids stutter at cut points.

A single worker thread pulls the oldest 'waiting_encode' video and processes it.
Status transitions: waiting_encode -> encoding -> completed | error.
"""
import json
import re
import subprocess
import threading
import time
import uuid

import config
import db
import storage

# Active encode jobs keyed by video id, so a delete request can terminate the
# running ffmpeg instead of trusting a DB-stored PID (stale/reused PIDs would
# kill an innocent process).
_jobs = {}
_jobs_lock = threading.Lock()


def terminate_job(video_id):
    """Stop the encode running for a video, if any. Safe to call anytime."""
    with _jobs_lock:
        proc = _jobs.pop(video_id, None)
    if not proc:
        return False
    if proc.poll() is None:
        proc.terminate()  # SIGTERM on POSIX, TerminateProcess on Windows
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    return True


def ffprobe_info(path):
    """Return (duration_seconds, fps, width, height) for a media file."""
    cmd = [
        config.FFPROBE, "-v", "error",
        "-select_streams", "v",
        "-show_entries", "stream=avg_frame_rate,width,height:stream_disposition=attached_pic:format=duration",
        "-of", "json", str(path),
    ]
    # utf-8 explicitly: ffmpeg always emits utf-8; on Windows the locale codec
    # (cp1251 etc.) would choke on non-ASCII output.
    out = subprocess.check_output(cmd, text=True, encoding="utf-8", errors="replace")
    data = json.loads(out)
    duration = float(data.get("format", {}).get("duration", 0) or 0)
    fps = 0.0
    width = height = None
    # Embedded album art shows up as a video stream flagged attached_pic — skip
    # it, otherwise audio tracks would report a bogus "resolution".
    streams = [s for s in data.get("streams", [])
               if not s.get("disposition", {}).get("attached_pic")]
    if streams:
        width = streams[0].get("width")
        height = streams[0].get("height")
        rate = streams[0].get("avg_frame_rate", "0/0")
        try:
            num, den = rate.split("/")
            fps = float(num) / float(den) if float(den) else 0.0
        except (ValueError, ZeroDivisionError):
            fps = 0.0
    return duration, fps, width, height


def _mode_for(video):
    """Quality mode of the stream this file belongs to."""
    stream = db.get_stream(video["stream_id"])
    mode = None
    if stream and "quality_mode" in stream.keys():
        mode = stream["quality_mode"]
    return mode if mode in config.QUALITY_MODES else "balanced"


def _transcode(video, cmd, out_path, total_duration, src_dims=(None, None), mode="balanced",
               out_storage_id=None):
    """Run an ffmpeg normalize job, streaming progress into the DB."""
    proc = subprocess.Popen(
        cmd, stderr=subprocess.PIPE, text=True,
        encoding="utf-8", errors="replace", bufsize=1,
    )
    with _jobs_lock:
        _jobs[video["id"]] = proc
    db.update_video(video["id"], encode_pid=proc.pid)  # informational only

    # Regex for 'time=00:00:00.00'
    time_pattern = re.compile(r"time=(\d{2}):(\d{2}):(\d{2})\.(\d{2})")

    last_write = 0.0  # progress is throttled to ~1 write/sec, not per stderr line

    try:
        while True:
            line = proc.stderr.readline()
            if not line:
                break

            match = time_pattern.search(line)
            if match and total_duration > 0:
                h, m, s, ms = map(int, match.groups())
                current_time = h * 3600 + m * 60 + s + ms / 100
                progress = (current_time / total_duration) * 100
                now = time.monotonic()
                if now - last_write >= 1.0:
                    last_write = now
                    db.update_video(video["id"], progress=min(100.0, progress))
    except Exception:
        # Log error or just let it fail
        pass

    proc.wait()
    with _jobs_lock:
        _jobs.pop(video["id"], None)

    if proc.returncode != 0:
        out_path.unlink(missing_ok=True)
        db.update_video(video["id"], status="error", error_msg=f"encode failed with code {proc.returncode}")
        return

    kind = video["kind"] if "kind" in video.keys() else "video"

    try:
        duration, _, _, _ = ffprobe_info(out_path)
    except Exception:
        duration = 0
    try:
        size = out_path.stat().st_size
    except OSError:
        size = None

    # Keep the previous-quality copy playable while the rest of the queue is
    # re-encoding into a new mode (see _build_playlist in streamer.py). It
    # stays wherever it was; the row records that storage explicitly.
    old_name = video["encoded_name"] if "encoded_name" in video.keys() else None
    old_preset = (video["encode_preset"] if "encode_preset" in video.keys() else None) or "balanced"
    updates = {
        "status": "completed", "encoded_name": out_path.name,
        "encoded_storage_id": out_storage_id,
        "duration": duration, "width": src_dims[0], "height": src_dims[1],
        "size": size, "encode_preset": mode, "error_msg": "", "progress": 100.0,
    }
    if old_name and old_preset != mode:
        updates["prev_encoded_name"] = old_name
        updates["prev_encode_preset"] = old_preset
        updates["prev_encoded_storage_id"] = video["encoded_storage_id"] \
            if "encoded_storage_id" in video.keys() else None
    else:
        updates["prev_encoded_name"] = None
        updates["prev_encode_preset"] = None
        updates["prev_encoded_storage_id"] = None
        if old_name and old_name != out_path.name:
            try:
                storage.video_encoded_path(video, old_name).unlink(missing_ok=True)
            except OSError:
                pass

    db.update_video(video["id"], **updates)

    if kind != "audio":
        _make_thumb(out_path)


def _make_thumb(out_path):
    """Grab a small frame for dashboard tiles (video files only)."""
    thumb = out_path.parent / (out_path.name + ".jpg")
    try:
        subprocess.run(
            [config.FFMPEG, "-y", "-ss", "1", "-i", str(out_path),
             "-frames:v", "1", "-vf", "scale=640:-2", str(thumb)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=60,
        )
    except Exception:
        pass


def _bitrate_bps(value):
    """'4500k' -> 4_500_000 (ffmpeg-style bitrate strings)."""
    m = re.match(r"^(\d+(?:\.\d+)?)\s*([kKmM]?)$", str(value or ""))
    if not m:
        return 0
    mult = {"": 1, "k": 1000, "m": 1_000_000}[m.group(2).lower()]
    return int(float(m.group(1)) * mult)


def _estimate_encoded_bytes(preset, kind, duration):
    """Rough size of the copy ffmpeg is about to write, so a storage can be
    picked that will actually hold it (duration is known from the probe)."""
    if kind == "audio":
        rate = _bitrate_bps(preset["mp3_bitrate"])
    else:
        rate = _bitrate_bps(preset["vbitrate"]) + _bitrate_bps(preset["audio_bitrate"])
    return int(duration * rate / 8 * 1.15) + 2 * 1024 ** 2


def _encode_one(video):
    src = storage.video_upload_path(video)
    if not src.exists():
        db.update_video(video["id"], status="error", error_msg="Source file missing")
        return

    kind = video["kind"] if "kind" in video.keys() else "video"

    # Enforce the 60fps block rule (video only) before spending CPU on encoding.
    try:
        src_duration, src_fps, src_w, src_h = ffprobe_info(src)
    except Exception as e:  # noqa: BLE001
        db.update_video(video["id"], status="error", error_msg=f"probe failed: {e}")
        return
    if kind != "audio" and src_fps >= config.MAX_FPS:
        db.update_video(
            video["id"], status="error",
            error_msg=f"{src_fps:.0f}fps rejected (max {config.MAX_FPS - 1}fps)",
        )
        return

    mode = _mode_for(video)
    preset = config.QUALITY_MODES[mode]

    # Where to write the encoded copy: this video's own storage when it has
    # room (keeps a re-encode's prev-copy reachable), otherwise whichever
    # storage does. The row remembers the choice via encoded_storage_id.
    prefer = storage.storage_for(video, "encoded_storage_id", "storage_id")
    targets = storage.encode_targets(prefer["id"],
                                     needed=_estimate_encoded_bytes(preset, kind, src_duration))
    if not targets:
        db.update_video(
            video["id"], status="error",
            error_msg=(f"No storage has ~{_fmt_gb(_estimate_encoded_bytes(preset, kind, src_duration))} GB "
                       f"free for the encoded copy (min free: {config.MIN_FREE_GB} GB)"),
        )
        return
    target = targets[0]
    out_dir = storage.encoded_dir(target)

    db.update_video(video["id"], status="encoding", error_msg="", progress=0.0)

    if kind == "audio":
        # Normalize to CBR MP3 so the concat playlist plays tracks seamlessly.
        out_path = out_dir / f"{uuid.uuid4().hex}.mp3"
        cmd = [
            config.FFMPEG, "-y", "-i", str(src),
            "-vn",
            "-c:a", "libmp3lame", "-b:a", preset["mp3_bitrate"],
            "-ar", "44100", "-ac", "2", "-write_xing", "0",
            str(out_path),
        ]
    else:
        w, h = preset["width"], preset["height"]
        out_path = out_dir / f"{uuid.uuid4().hex}.mp4"

        vf = (
            f"scale={w}:{h}:"
            f"force_original_aspect_ratio=decrease,"
            f"pad={w}:{h}:(ow-iw)/2:(oh-ih)/2,"
            f"fps={config.TARGET_FPS},format=yuv420p"
        )
        gop = config.TARGET_FPS * config.GOP_SECONDS
        cmd = [
            config.FFMPEG, "-y", "-i", str(src),
            "-vf", vf,
            "-c:v", "libx264", "-preset", preset["x264_preset"], "-profile:v", "high",
            "-b:v", preset["vbitrate"], "-maxrate", preset["vbitrate"],
            "-bufsize", preset["vbitrate"],
            "-g", str(gop), "-keyint_min", str(gop), "-sc_threshold", "0",
            "-c:a", "aac", "-b:a", preset["audio_bitrate"], "-ar", "48000", "-ac", "2",
            "-movflags", "+faststart",
            str(out_path),
        ]

    _transcode(video, cmd, out_path, src_duration, src_dims=(src_w, src_h), mode=mode,
               out_storage_id=target["id"])


def _fmt_gb(n_bytes):
    return round(n_bytes / 1024 ** 3, 1)


class EncoderWorker:
    """One background thread that drains the encode queue."""

    def __init__(self, poll_interval=2.0):
        self.poll_interval = poll_interval
        self._stop = threading.Event()
        self._thread = None

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._stop.clear()
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop.set()

    def _run(self):
        while not self._stop.is_set():
            job = db.next_encode_job()
            if job is None:
                time.sleep(self.poll_interval)
                continue
            try:
                _encode_one(job)
            except Exception as e:  # noqa: BLE001
                db.update_video(job["id"], status="error", error_msg=str(e))


worker = EncoderWorker()