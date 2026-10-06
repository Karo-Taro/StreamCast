"""
StreamCast configuration.

Everything is driven by environment variables so the same code runs on your
laptop (localhost) and on a VPS without edits. Copy .env.example to .env and
adjust, or export the variables in your shell / systemd unit.
"""
import os
from pathlib import Path


def _env(name, default=None):
    val = os.environ.get(name)
    return val if val not in (None, "") else default


BASE_DIR = Path(__file__).resolve().parent


def _load_dotenv():
    """Tiny .env loader so the panel behaves the same everywhere (VS Code,
    plain terminal, systemd). KEY=VALUE lines, '#' comments, quotes stripped.
    Real environment variables always win over .env values."""
    env_file = BASE_DIR / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        os.environ.setdefault(key.strip(), val.strip().strip('"').strip("'"))


_load_dotenv()

STORAGE_DIR = Path(_env("STREAMCAST_STORAGE", str(BASE_DIR / "storage")))
UPLOAD_DIR = STORAGE_DIR / "uploads"      # raw user uploads
ENCODED_DIR = STORAGE_DIR / "encoded"     # normalized, ready-to-stream files
DB_PATH = Path(_env("STREAMCAST_DB", str(STORAGE_DIR / "streamcast.db")))

# --- Auth (single owner, no registration) -----------------------------------
# Login page checks this single password. On first start with the default
# value the app shows a one-time setup screen asking for a new password.
OWNER_PASSWORD = _env("STREAMCAST_PASSWORD", "changeme")
SECRET_KEY = _env("STREAMCAST_SECRET", "dev-secret-change-me")

# Set STREAMCAST_REQUIRE_LOGIN=1 to always require the password. It is also
# turned on automatically (and stored in the DB) by the first-start setup.
# With login not required anonymous visitors can look around read-only; every
# mutating action still needs a signed-in account.
REQUIRE_LOGIN = _env("STREAMCAST_REQUIRE_LOGIN", "0") == "1"

# Trust X-Real-IP / CF-Connecting-IP / X-Forwarded-Proto headers from a reverse
# proxy (nginx, Cloudflare). Leave on when the app sits behind a proxy; set 0
# when it is exposed directly, or clients could spoof these headers.
TRUST_PROXY = _env("STREAMCAST_TRUST_PROXY", "1") == "1"

# Where the dev server binds (gunicorn users set their own -b instead).
HOST = _env("STREAMCAST_HOST", "127.0.0.1")
PORT = int(_env("STREAMCAST_PORT", "5000"))

# Public base URL of this instance (no trailing slash). Used as the OAuth
# redirect base: <SITE_URL>/oauth2callback must be registered in the Google
# Cloud console. Empty = derived from the incoming request.
SITE_URL = _env("STREAMCAST_SITE_URL", "").rstrip("/")

# --- Streaming --------------------------------------------------------------
# Default YouTube ingest endpoint. Users only paste their stream KEY in the UI.
RTMP_BASE = _env("STREAMCAST_RTMP_BASE", "rtmp://a.rtmp.youtube.com/live2")

# Target format all uploads are normalized to (keeps the 24/7 stream seamless).
TARGET_WIDTH = int(_env("STREAMCAST_WIDTH", "1920"))
TARGET_HEIGHT = int(_env("STREAMCAST_HEIGHT", "1080"))
TARGET_FPS = int(_env("STREAMCAST_FPS", "30"))
VIDEO_BITRATE = _env("STREAMCAST_VBITRATE", "4500k")
AUDIO_BITRATE = _env("STREAMCAST_ABITRATE", "128k")
GOP_SECONDS = 2  # keyframe interval; YouTube recommends 2s

# Quality modes: per-stream encoding presets. A stream's queue is re-encoded
# into its mode's parameters (once, in the background); playback itself always
# stays -c copy, so the mode costs nothing at air time.
QUALITY_MODES = {
    "quality": {
        "label": "Max quality",
        "x264_preset": "medium",
        "width": 1920, "height": 1080,
        "vbitrate": "6000k",
        "audio_bitrate": "192k",   # AAC audio of video files
        "mp3_bitrate": "192k",     # normalized audio tracks (music streams)
    },
    "balanced": {
        "label": "Balanced",
        "x264_preset": "veryfast",
        "width": TARGET_WIDTH, "height": TARGET_HEIGHT,
        "vbitrate": VIDEO_BITRATE,
        "audio_bitrate": AUDIO_BITRATE,
        "mp3_bitrate": "128k",
    },
    "performance": {
        "label": "Max performance",
        "x264_preset": "superfast",
        "width": 1280, "height": 720,
        "vbitrate": "2500k",
        "audio_bitrate": "128k",
        "mp3_bitrate": "128k",
    },
}

# Uploads at or above this fps are rejected (matches the "blocks 60fps!" rule).
MAX_FPS = int(_env("STREAMCAST_MAX_FPS", "60"))

# Restart streams that were live when the server stopped (1/0).
AUTO_RESUME = _env("STREAMCAST_AUTORESUME", "1") == "1"

MAX_UPLOAD_MB = int(_env("STREAMCAST_MAX_UPLOAD_MB", "8192"))  # 8 GB
ALLOWED_EXT = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".flv", ".m4v"}

# Audio formats accepted for music streams. Tracks are normalized to MP3 so
# the concat playlist plays them back-to-back without glitches.
ALLOWED_AUDIO_EXT = {".mp3", ".wav", ".flac", ".ogg", ".oga", ".m4a", ".aac", ".opus", ".wma"}

# When a stream is live, queue edits are picked up at the end of the current
# playback block. Short queues are repeated inside one block up to this many
# seconds so we don't reconnect to YouTube too often. Lower = faster pickup of
# queue changes but more frequent reconnects.
RELOAD_BLOCK_SECONDS = int(_env("STREAMCAST_RELOAD_BLOCK_SECONDS", "900"))

# Extra storages (admin panel) and the main one stop accepting new files when
# their disk has less than this much free space — the DB/WAL and ffmpeg share
# those disks too, and a 100%-full disk breaks everything on it.
MIN_FREE_GB = int(_env("STREAMCAST_MIN_FREE_GB", "5"))

# How long YouTube keeps a broadcast alive without incoming data before it
# finalizes it and saves it as a video (~1 minute in practice, undocumented).
# If ffmpeg keeps crashing and the supervisor can't get it back up within this
# window, the runner gives up (stream goes offline) so YouTube archives the
# broadcast cleanly instead of splitting it into pieces.
YOUTUBE_GRACE_SECONDS = int(_env("STREAMCAST_YOUTUBE_GRACE_SECONDS", "60"))

# ffmpeg / ffprobe binaries (override if not on PATH)
FFMPEG = _env("STREAMCAST_FFMPEG", "ffmpeg")
FFPROBE = _env("STREAMCAST_FFPROBE", "ffprobe")


def ensure_dirs():
    for d in (STORAGE_DIR, UPLOAD_DIR, ENCODED_DIR):
        d.mkdir(parents=True, exist_ok=True)
