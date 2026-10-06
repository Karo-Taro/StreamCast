"""StreamCast — single-owner 24/7 YouTube streaming panel."""
import json
import logging
import psutil
import threading
from logging.handlers import RotatingFileHandler
import re
import secrets
import subprocess
import time
import shutil
import uuid
from functools import wraps
from pathlib import Path
from urllib.parse import urlsplit

from flask import (
    Flask, abort, flash, g, jsonify, redirect, render_template,
    request, send_file, session, url_for,
)
from werkzeug.security import check_password_hash, generate_password_hash
from werkzeug.utils import secure_filename

import config
import db
import storage
import translator_bridge
from encoder import ffprobe_info, terminate_job, worker as encoder_worker
from streamer import manager

# --- Display helpers ---------------------------------------------------------
def _fmt_size(n):
    """Human-readable file size, e.g. 1.4 GB."""
    if not n or n <= 0:
        return ""
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024 or unit == "TB":
            return f"{int(n)} {unit}" if unit == "B" else f"{n:.1f} {unit}"
        n /= 1024.0


def _fmt_runtime(seconds):
    """Compact runtime label, e.g. 3h 12m / 45m 03s / 42s. '' when empty."""
    sec = int(seconds or 0)
    if sec <= 0:
        return ""
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h}h {m:02d}m"
    if m:
        return f"{m}m {s:02d}s"
    return f"{s}s"


def _res_label(width, height):
    """Resolution badge from source dimensions: 4K / 1440p / 1080p / ..."""
    if not width or not height:
        return ""
    m = min(width, height)  # portrait videos still report their height class
    if m >= 2160:
        return "4K"
    if m >= 1440:
        return "1440p"
    if m >= 1080:
        return "1080p"
    if m >= 720:
        return "720p"
    if m >= 480:
        return "480p"
    return f"{m}p"


# Encoding target of the whole app (per-stream selection is not wired up yet).
def _mode_resolution(mode):
    """Resolution badge for a quality mode, e.g. 1080p."""
    preset = config.QUALITY_MODES.get(mode or "balanced", config.QUALITY_MODES["balanced"])
    return _res_label(preset["width"], preset["height"])


def _youtube_id(url):
    """Video ID from common YouTube link shapes, or None."""
    if not url:
        return None
    m = re.search(r"(?:youtu\.be/|watch\?v=|/live/|/shorts/|/embed/)([\w-]{11})", url)
    return m.group(1) if m else None


def _thumb_path(video):
    """Thumbnail sits next to the encoded file: xxx.mp4 -> xxx.mp4.jpg."""
    return storage.video_thumb_path(video)


def _ensure_thumb(video):
    """Grab a frame from an encoded video if its thumbnail doesn't exist yet."""
    if not video["encoded_name"] or video["kind"] == "audio":
        return
    thumb = _thumb_path(video)
    if thumb.exists():
        return
    src = storage.video_encoded_path(video)
    if not src.exists():
        return
    try:
        subprocess.run(
            [config.FFMPEG, "-y", "-ss", "1", "-i", str(src),
             "-frames:v", "1", "-vf", "scale=640:-2", str(thumb)],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=30,
        )
    except Exception:
        pass


def _stream_thumb_url(stream):
    """Local frame URL representing a stream on the dashboard tile, or None.

    Music streams are represented by their loop background video; video
    streams by the first ready video in the queue.
    """
    videos = db.list_videos(stream["id"])
    loop_id = stream["loop_video_id"] if "loop_video_id" in stream.keys() else None
    pick = None
    if loop_id:
        pick = next(
            (v for v in videos
             if v["id"] == loop_id and v["kind"] != "audio" and v["encoded_name"]),
            None,
        )
    if pick is None:
        pick = next(
            (v for v in videos
             if v["kind"] != "audio" and v["status"] == "completed" and v["encoded_name"]),
            None,
        )
    if pick is None:
        return None
    _ensure_thumb(pick)
    return url_for("video_thumb", video_id=pick["id"])


def _hydrate_media_meta(v):
    """Backfill size/resolution for files encoded before those columns existed."""
    if v["status"] != "completed" or not v["encoded_name"]:
        return
    updates = {}
    if v.get("kind") == "audio" and (v["width"] or v["height"]):
        # Old rows may carry the embedded album-art dimensions as "resolution".
        updates["width"] = None
        updates["height"] = None
    if not v["size"]:
        p = storage.video_encoded_path(v)
        if p.exists():
            updates["size"] = p.stat().st_size
    if not v["width"] and v.get("kind") != "audio":
        src = storage.video_upload_path(v)
        if src.exists():
            try:
                _, _, w, h = ffprobe_info(src)
                if w and h:
                    updates["width"], updates["height"] = w, h
            except Exception:
                pass
    if updates:
        db.update_video(v["id"], **updates)
        v.update(updates)


app = Flask(__name__)
@app.route('/api/system_load')
def api_system_load():
    """Current system-wide CPU and RAM usage."""
    try:
        import psutil
        return jsonify({'cpu': psutil.cpu_percent(interval=0.1), 'ram': psutil.virtual_memory().percent})
    except Exception as e:
        return jsonify({'cpu': 0, 'ram': 0, 'error': str(e)}), 500
app.config["SECRET_KEY"] = config.SECRET_KEY
app.config["MAX_CONTENT_LENGTH"] = config.MAX_UPLOAD_MB * 1024 * 1024
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
# SESSION_COOKIE_SECURE is toggled per request by _harden_session_cookie()
# below: on over plain HTTP it stays off so LAN/localhost logins work, and
# flips on automatically as soon as the request arrived over HTTPS.
# Reload templates on change so UI edits show up without a restart.
app.config["TEMPLATES_AUTO_RELOAD"] = True
app.jinja_env.auto_reload = True


def _client_ip():
    """Best-effort client IP for logging and brute-force throttling.
    Proxied headers are only honored behind a reverse proxy (STREAMCAST_TRUST_PROXY);
    exposed directly they could be spoofed to dodge the login throttle."""
    if config.TRUST_PROXY:
        return (request.headers.get("X-Real-IP")
                or request.headers.get("CF-Connecting-IP")
                or request.remote_addr or "?")
    return request.remote_addr or "?"


@app.before_request
def _harden_session_cookie():
    secure = request.is_secure
    if not secure and config.TRUST_PROXY:
        secure = request.headers.get("X-Forwarded-Proto") == "https"
    app.config["SESSION_COOKIE_SECURE"] = secure


@app.before_request
def _force_first_start_setup():
    """Fresh install with the default password: walk the owner through creating
    a real admin password before anything else is reachable."""
    if request.endpoint in ("setup", "static"):
        return None
    if _setup_pending():
        return redirect(url_for("setup"))
    return None


@app.before_request
def _reject_cross_origin_posts():
    """CSRF guard for form POSTs (the JSON APIs already use ajax_required).
    Browsers always attach Origin/Referer on cross-site POSTs, so only a
    mismatched header is proof of an attack; requests with neither header
    (curl, scripts, API clients) are allowed through."""
    if request.method not in ("POST", "PUT", "PATCH", "DELETE"):
        return None
    for header in ("Origin", "Referer"):
        val = request.headers.get(header)
        if not val:
            continue
        if urlsplit(val).netloc != request.host:
            abort(400)
        return None
    return None


def _fmt_hms(seconds):
    """HH:MM:SS uptime label, same format as the stream page timer."""
    sec = max(0, int(seconds or 0))
    h, rem = divmod(sec, 3600)
    m, s = divmod(rem, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"


app.jinja_env.filters["hms"] = _fmt_hms


# --- Auth & roles ------------------------------------------------------------
# The master password (env or a DB-stored override) is the owner/admin. Extra
# accounts live in the `users` table, passwordless-login style:
#   admin  — full rights (created in the admin panel, rarely needed)
#   worker — can create streams and manage only the ones they created
#   viewer — read-only
# With login not required (STREAMCAST_REQUIRE_LOGIN unset and setup not done)
# anonymous visitors can look around read-only; mutations need an account.
# The /admin panel always asks for an explicit master login.
ROLES = ("admin", "worker", "viewer")


def _check_master_password(password):
    stored = db.get_setting("master_password_hash")
    if stored:
        return check_password_hash(stored, password)
    return password == config.OWNER_PASSWORD


def _setup_pending():
    """True until the owner replaces the default master password: no DB-stored
    hash yet and the environment still carries the shipped default."""
    return (db.get_setting("master_password_hash") is None
            and config.OWNER_PASSWORD == "changeme")


def _require_login():
    """Login wall: the env flag, or the flag stored by first-start setup."""
    return config.REQUIRE_LOGIN or db.get_setting("require_login") == "1"


def current_user():
    """(user_id, role) for this request, or (None, None) when locked out."""
    if getattr(g, "_user_resolved", False):
        return g._user_id, g._user_role
    uid = role = None
    if session.get("authed"):
        uid = session.get("user_id")
        role = session.get("role", "viewer")
        if uid is not None and not db.get_user(uid):
            # Account deleted while the session was alive — treat as logged out.
            uid = role = None
    elif not _require_login():
        # Open access = read-only: anonymous visitors can look around,
        # but everything that mutates needs a signed-in account.
        role = "viewer"
    g._user_resolved = True
    g._user_id, g._user_role = uid, role
    return uid, role


def current_role():
    return current_user()[1]


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if current_role() is None:
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def admin_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if not (session.get("authed") and session.get("role") == "admin"):
            return redirect(url_for("login", next=request.path))
        return view(*args, **kwargs)
    return wrapped


def ajax_required(view):
    """Light CSRF guard for the JSON APIs: a cross-site form/fetch cannot set
    this custom header without a CORS preflight, which we never grant."""
    @wraps(view)
    def wrapped(*args, **kwargs):
        if request.headers.get("X-Requested-With") != "XMLHttpRequest":
            abort(400)
        return view(*args, **kwargs)
    return wrapped


def _owns_stream(stream):
    """May the current user edit / delete / run this stream?"""
    uid, role = current_user()
    if role == "admin":
        return True
    if role != "worker" or uid is None:
        return False
    if stream["owner_id"] == uid:
        return True
    shared = getattr(g, "_shared_ids", None)
    if shared is None:
        shared = set(db.list_shared_stream_ids(uid))
        g._shared_ids = shared
    return stream["id"] in shared


def _owned_stream(stream_id):
    """Fetch a stream for a mutating action; 403 unless admin or the owner."""
    stream = db.get_stream(stream_id)
    if not stream:
        abort(404)
    if current_role() == "viewer" or not _owns_stream(stream):
        abort(403)
    return stream


@app.context_processor
def _inject_user():
    uid, role = current_user()
    return {"u_id": uid, "u_role": role}


# Brute-force throttle for password entry: 5 bad attempts put the client IP on
# a timeout that doubles with every further failure (30s ... 15 min). In-memory
# only — resetting on restart is fine, this is a speed bump, not an audit log.
_LOGIN_FAILS = {}  # ip -> {"fails": n, "until": monotonic}
_LOGIN_LOCK_THRESHOLD = 5
_LOGIN_LOCK_BASE = 30       # seconds
_LOGIN_LOCK_CAP = 15 * 60


def _login_lock_remaining():
    rec = _LOGIN_FAILS.get(_client_ip())
    if not rec:
        return 0
    left = rec["until"] - time.monotonic()
    return max(0, left)


def _login_record_fail():
    ip = _client_ip()
    rec = _LOGIN_FAILS.setdefault(ip, {"fails": 0, "until": 0.0})
    rec["fails"] += 1
    if rec["fails"] >= _LOGIN_LOCK_THRESHOLD:
        delay = min(_LOGIN_LOCK_CAP,
                    _LOGIN_LOCK_BASE * 2 ** (rec["fails"] - _LOGIN_LOCK_THRESHOLD))
        rec["until"] = time.monotonic() + delay
    if len(_LOGIN_FAILS) > 10000:  # keep the table bounded
        cutoff = time.monotonic()
        for k in [k for k, v in _LOGIN_FAILS.items() if v["until"] < cutoff]:
            _LOGIN_FAILS.pop(k, None)


def _login_record_success():
    _LOGIN_FAILS.pop(_client_ip(), None)


@app.route("/setup", methods=["GET", "POST"])
def setup():
    """One-time first-start screen: create the admin password."""
    if not _setup_pending():
        return redirect(url_for("dashboard"))
    if request.method == "POST":
        pw = request.form.get("password", "")
        confirm = request.form.get("confirm", "")
        if len(pw) < 8:
            flash("Password must be at least 8 characters", "error")
        elif pw != confirm:
            flash("Passwords do not match", "error")
        elif pw == "changeme":
            flash("Please pick something other than the default password", "error")
        else:
            db.set_setting("master_password_hash", generate_password_hash(pw))
            db.set_setting("require_login", "1")
            session.clear()
            session["authed"] = True
            session["user_id"] = None
            session["role"] = "admin"
            session.permanent = True
            flash("Password saved — welcome to StreamCast!", "ok")
            return redirect(url_for("dashboard"))
    return render_template("setup.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("authed"):
        return redirect(url_for("dashboard"))
    nxt = request.args.get("next") or url_for("dashboard")
    # Only same-app paths; "//host" is protocol-relative and would leave the site.
    if not nxt.startswith("/") or nxt.startswith("//"):
        nxt = url_for("dashboard")
    if request.method == "POST":
        wait = _login_lock_remaining()
        if wait:
            flash(f"Too many attempts — try again in {int(wait // 60) + 1} min", "error")
            return render_template("login.html"), 429
        pw = request.form.get("password", "")
        if _check_master_password(pw):
            _login_record_success()
            session["authed"] = True
            session["user_id"] = None
            session["role"] = "admin"
            session.permanent = True
            return redirect(nxt)
        user = db.find_user_by_password(pw, check_password_hash)
        if user:
            _login_record_success()
            session["authed"] = True
            session["user_id"] = user["id"]
            session["role"] = user["role"]
            session.permanent = True
            return redirect(nxt)
        _login_record_fail()
        flash("Wrong password", "error")
    return render_template("login.html")


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


# --- Own account -------------------------------------------------------------
@app.route("/password", methods=["GET", "POST"])
@login_required
def change_password():
    uid, _ = current_user()
    if request.method == "POST":
        cur = request.form.get("current", "")
        new = request.form.get("new", "")
        confirm = request.form.get("confirm", "")
        if len(new) < 6:
            flash("New password must be at least 6 characters", "error")
        elif new != confirm:
            flash("New passwords do not match", "error")
        elif uid is None:
            # Master password (DB override; env fallback keeps working until set).
            if not _check_master_password(cur):
                flash("Current password is wrong", "error")
            else:
                db.set_setting("master_password_hash", generate_password_hash(new))
                flash("Master password updated", "ok")
                return redirect(url_for("dashboard"))
        else:
            u = db.get_user(uid)
            if not u or not check_password_hash(u["password_hash"], cur):
                flash("Current password is wrong", "error")
            else:
                db.update_user_password(uid, generate_password_hash(new))
                flash("Password updated", "ok")
                return redirect(url_for("dashboard"))
    return render_template("password.html")


# --- Admin panel -------------------------------------------------------------
def _gen_password():
    return secrets.token_urlsafe(9)  # ~12 chars, URL-safe, no lookalikes trimmed


@app.route("/admin")
@admin_required
def admin_panel():
    users = db.list_users()
    created = session.pop("created_password", None)
    streams = db.list_streams()
    shared = {u["id"]: set(db.list_shared_stream_ids(u["id"])) for u in users}
    storages_ui = []
    for row in db.list_storages():
        st = storage.disk_status(row)
        storages_ui.append({
            "id": row["id"], "name": row["name"],
            "path": str(storage.root(row)),
            "is_main": row["path"] is None,
            "is_default": bool(row["is_default"]),
            "files": db.count_videos_on_storage(row["id"]),
            **st,
        })
    return render_template("admin.html", users=users, created=created,
                           roles=ROLES, streams=streams, shared=shared,
                           storages=storages_ui,
                           min_free_gb=config.MIN_FREE_GB)


@app.route("/admin/users", methods=["POST"])
@admin_required
def admin_create_user():
    note = request.form.get("note", "").strip()
    role = request.form.get("role", "worker")
    if role not in ROLES:
        role = "worker"
    password = _gen_password()
    db.create_user(note, role, generate_password_hash(password))
    # The plaintext password is shown once, right after creation.
    session["created_password"] = {"password": password, "note": note, "role": role}
    return redirect(url_for("admin_panel"))


@app.route("/admin/users/<int:user_id>", methods=["POST"])
@admin_required
def admin_update_user(user_id):
    if not db.get_user(user_id):
        abort(404)
    role = request.form.get("role")
    db.update_user(user_id,
                   note=request.form.get("note", ""),
                   role=role if role in ROLES else None)
    # Shared streams (worker extra access); harmless for other roles.
    try:
        shared_ids = [int(x) for x in request.form.getlist("shared")]
    except ValueError:
        shared_ids = []
    db.set_shared_streams(user_id, shared_ids)
    flash("Account updated", "ok")
    return redirect(url_for("admin_panel"))


@app.route("/admin/users/<int:user_id>/regenerate", methods=["POST"])
@admin_required
def admin_regenerate_user(user_id):
    user = db.get_user(user_id)
    if not user:
        abort(404)
    password = _gen_password()
    db.update_user_password(user_id, generate_password_hash(password))
    session["created_password"] = {"password": password, "note": user["note"],
                                   "role": user["role"], "regenerated": True}
    return redirect(url_for("admin_panel"))


@app.route("/admin/users/<int:user_id>/delete", methods=["POST"])
@admin_required
def admin_delete_user(user_id):
    db.delete_user(user_id)
    flash("Account removed", "ok")
    return redirect(url_for("admin_panel"))


# --- Storages (admin: extra upload targets, e.g. an external SSD) ------------
@app.route("/admin/storages/scan", methods=["GET"])
@admin_required
def admin_scan_storages():
    """Scan system for available disks/mounts to help the admin pick a path."""
    disks = storage.scan_available_disks()
    return jsonify(disks)


@app.route("/admin/storages", methods=["POST"])
@admin_required
def admin_add_storage():
    try:
        path = storage.validate_new_storage(
            request.form.get("name", ""), request.form.get("path", ""))
    except storage.StorageError as e:
        flash(str(e), "error")
        return redirect(url_for("admin_panel"))
    db.create_storage(request.form.get("name", "").strip(), path)
    flash(f"Storage added: {path}", "ok")
    return redirect(url_for("admin_panel"))


@app.route("/admin/storages/<int:storage_id>/default", methods=["POST"])
@admin_required
def admin_default_storage(storage_id):
    if not db.get_storage(storage_id):
        abort(404)
    db.set_default_storage(storage_id)
    flash("Default storage updated — new uploads go there while it has room", "ok")
    return redirect(url_for("admin_panel"))


@app.route("/admin/storages/<int:storage_id>/delete", methods=["POST"])
@admin_required
def admin_delete_storage(storage_id):
    row = db.get_storage(storage_id)
    if not row:
        abort(404)
    if row["path"] is None:
        flash("The main storage cannot be removed", "error")
        return redirect(url_for("admin_panel"))
    used = db.count_videos_on_storage(storage_id)
    if used:
        flash(f"Storage «{row['name']}» still holds {used} file(s) — "
              f"delete them from the queue first", "error")
        return redirect(url_for("admin_panel"))
    db.delete_storage(storage_id)
    # The files stay on disk; re-adding the same path brings everything back.
    flash(f"Storage «{row['name']}» removed (files on disk were not touched)", "ok")
    return redirect(url_for("admin_panel"))


# --- Dashboard --------------------------------------------------------------
@app.route("/")
@login_required
def dashboard():
    streams = db.list_streams()
    for s in streams:
        s["live"] = manager.is_live(s["id"])
        # Runtime = the bigger of the two: video total vs audio total.
        runtime = max(s["video_duration"], s["audio_duration"])
        s["runtime_label"] = _fmt_runtime(runtime)
        s["size_label"] = _fmt_size(s["total_size"])
        s["resolution"] = _mode_resolution(s["quality_mode"])
        s["uptime"] = manager.uptime(s["id"]) if s["live"] else None
        s["yt_id"] = _youtube_id(s["youtube_url"])
        s["thumb_url"] = _stream_thumb_url(s)
        s["can_manage"] = _owns_stream(s)
    # Per-storage free/total for the dashboard strip (main storage first).
    storages_ui = []
    for row in db.list_storages():
        st = storage.disk_status(row)
        storages_ui.append({
            "id": row["id"], "name": row["name"],
            "path": str(storage.root(row)),
            "is_default": bool(row["is_default"]),
            **st,
        })
    return render_template("dashboard.html", streams=streams, storages=storages_ui,
                           encoding_count=db.count_encoding_videos())


# --- Stream CRUD -------------------------------------------------------------
@app.route("/stream/create", methods=["GET", "POST"])
@login_required
def stream_create():
    if request.method == "POST":
        if current_role() not in ("admin", "worker"):
            abort(403)
        name = request.form.get("name", "").strip() or "Untitled stream"
        stream_type = request.form.get("stream_type", "video")
        if stream_type not in ("video", "music"):
            stream_type = "video"
        quality_mode = request.form.get("quality_mode", "balanced")
        if quality_mode not in config.QUALITY_MODES:
            quality_mode = "balanced"
        uid, _ = current_user()
        channel_name = request.form.get("channel_name", "").strip()
        languages = [l for l in request.form.getlist("translate_languages") if l]
        parts = request.form.get("translate_parts", "all")
        source = request.form.get("translate_source", "video")
        sid = db.create_stream(
            name,
            channel_name=channel_name,
            rtmp_key=request.form.get("rtmp_key", "").strip(),
            youtube_url=request.form.get("youtube_url", "").strip(),
            stream_type=stream_type,
            quality_mode=quality_mode,
            owner_id=uid,  # None for the master/admin: owned by the panel itself
            translate_enabled=1 if request.form.get("translate_enabled") else 0,
            translate_parts=parts if parts in ("all", "title", "description") else "all",
            translate_source=source if source in ("video", "manual") else "video",
            translate_title=request.form.get("translate_title", "").strip(),
            translate_description=request.form.get("translate_description", "").strip(),
            translate_languages=json.dumps(languages),
        )
        return redirect(url_for("stream_detail", stream_id=sid))
    return render_template("stream_edit.html", stream=None, current_mode="balanced",
                           **_translate_page_data(None))


@app.route("/stream/<int:stream_id>")
@login_required
def stream_detail(stream_id):
    stream = db.get_stream(stream_id)
    if not stream:
        abort(404)
    videos = [dict(v) for v in db.list_videos(stream_id)]
    for v in videos:
        _hydrate_media_meta(v)
        v["res_label"] = _res_label(v.get("width"), v.get("height"))
        v["size_label"] = _fmt_size(v.get("size"))
        # Full name: the client-side fitQueueNames() mid-truncates with the
        # extension visible; CSS ellipsis is the no-JS fallback.
        v["display_name"] = v["orig_name"]
    status = manager.status(stream_id)
    if not status["live"] and not status["error"]:
        # In-memory error is gone after a restart — fall back to the persisted one.
        last = stream["last_error"] if "last_error" in stream.keys() else ""
        status["error"] = last or ""
    vd, ad, sz = db.stream_totals(stream_id)
    totals_label = " · ".join(
        x for x in (_fmt_runtime(max(vd, ad)), _fmt_size(sz)) if x
    )
    return render_template(
        "stream.html", stream=stream, videos=videos, status=status,
        totals_label=totals_label, resolution=_mode_resolution(stream["quality_mode"]),
        can_manage=_owns_stream(stream),
    )


@app.route("/stream/edit/<int:stream_id>", methods=["GET", "POST"])
@login_required
def stream_edit(stream_id):
    stream = db.get_stream(stream_id)
    if not stream:
        abort(404)
    # The edit page itself is manage-only: viewers don't even see the form,
    # workers only for streams they own or were granted.
    if not _owns_stream(stream):
        abort(403)
    if request.method == "POST":
        quality_mode = request.form.get("quality_mode", stream["quality_mode"] or "balanced")
        if quality_mode not in config.QUALITY_MODES:
            quality_mode = stream["quality_mode"] or "balanced"
        languages = [l for l in request.form.getlist("translate_languages") if l]
        parts = request.form.get("translate_parts", "all")
        source = request.form.get("translate_source", "video")
        db.update_stream(
            stream_id,
            name=request.form.get("name", "").strip() or stream["name"],
            channel_name=request.form.get("channel_name", "").strip() or stream.get("channel_name", ""),
            rtmp_key=request.form.get("rtmp_key", "").strip(),
            youtube_url=request.form.get("youtube_url", "").strip(),
            loop_queue=1 if request.form.get("loop_queue") else 0,
            quality_mode=quality_mode,
            translate_enabled=1 if request.form.get("translate_enabled") else 0,
            translate_parts=parts if parts in ("all", "title", "description") else "all",
            translate_source=source if source in ("video", "manual") else "video",
            translate_title=request.form.get("translate_title", "").strip(),
            translate_description=request.form.get("translate_description", "").strip(),
            translate_languages=json.dumps(languages),
        )
        if quality_mode != (stream["quality_mode"] or "balanced"):
            # Re-encode the queue into the new mode in the background; files
            # keep playing their previous-quality copies until each is done.
            for v in db.list_videos(stream_id):
                if v["status"] == "completed" and (v["encode_preset"] or "balanced") != quality_mode:
                    # Fast-imported files have no source upload — nothing to
                    # re-encode; they stay as they are.
                    if not storage.video_upload_path(v).exists():
                        continue
                    db.update_video(v["id"], status="waiting_encode", progress=0.0, error_msg="")
            manager.apply_now(stream_id)
            flash("Quality mode changed — the queue is being re-encoded in the background", "ok")
        else:
            flash("Saved", "ok")
        return redirect(url_for("stream_detail", stream_id=stream_id))
    return render_template(
        "stream_edit.html", stream=stream,
        current_mode=stream["quality_mode"] or "balanced",
        **_translate_page_data(stream),
    )


# --- Metadata localization (vendored youtube-metadata-translator) -----------

def _translate_page_data(stream):
    """Template context for the localization section of the edit page."""
    languages = []
    if stream:
        try:
            languages = json.loads(stream["translate_languages"] or "[]")
        except ValueError:
            pass
    data = {
        "tr_ready": translator_bridge.ready(),
        "tr_error": translator_bridge.load_error,
        "tr_channel": None,
        "tr_catalog": {},
        "tr_presets": {},
        "tr_languages": languages,
    }
    if data["tr_ready"]:
        status = translator_bridge.status()
        data["tr_channel"] = status["channel"]
        data["tr_catalog"] = translator_bridge.language_catalog()
        data["tr_presets"] = translator_bridge.language_presets()
    return data


def _is_auth_error(message):
    """YouTube API 'Forbidden' — the connected account can't manage this video
    (or the API isn't enabled for the project). Needs (re-)authorization."""
    message = str(message)
    return "403" in message and "forbidden" in message.lower()


def _translation_video_id(stream):
    return _youtube_id(stream["youtube_url"] or "")


@app.route("/stream/translate_preview/<int:stream_id>")
@login_required
@ajax_required
def translate_preview(stream_id):
    """Current source title/description the translation would start from."""
    _owned_stream(stream_id)
    stream = db.get_stream(stream_id)
    if not stream:
        abort(404)
    if (stream["translate_source"] or "video") == "manual":
        return jsonify({"source": "manual",
                        "title": stream["translate_title"] or "",
                        "description": stream["translate_description"] or ""})
    video_id = _translation_video_id(stream)
    if not video_id:
        return jsonify({"error": "No YouTube URL on this stream"}), 400
    try:
        meta = translator_bridge.fetch_video_meta(video_id)
    except Exception as e:
        logging.getLogger("streamcast").warning("Preview fetch for stream %d failed: %s",
                                                stream_id, e)
        return jsonify({"error": str(e)[:200], "needs_auth": _is_auth_error(e)}), 502
    return jsonify({"source": "video", "video_id": video_id,
                    "title": meta.get("title", ""),
                    "description": meta.get("description", "")})


_TRANSLATION_JOBS = {}          # stream_id -> job dict
_TRANSLATION_JOBS_LOCK = threading.Lock()


def _translation_worker(stream_id, video_id, title, description, languages, parts):
    job = _TRANSLATION_JOBS[stream_id]
    log = logging.getLogger("streamcast")
    catalog = translator_bridge.language_catalog()
    provider_id = None
    try:
        provider_id = ((translator_bridge.engine.get_active_provider() or {}) .get("id"))
    except Exception:
        pass

    def progress(kind, lang, detail=""):
        name = catalog.get(lang, lang) if lang else ""
        with _TRANSLATION_JOBS_LOCK:
            if kind == "ok":
                job["done"] += 1
                line = f"✓ {lang} — {name}: translation applied"
            elif kind == "fail":
                line = f"✗ {lang} — {name}: failed — {str(detail)[:120]}"
            elif kind == "retry":
                is_balance = "402" in str(detail) or "insufficient" in str(detail).lower()
                if is_balance and provider_id:
                    translator_bridge.set_provider_alert(
                        provider_id, "nobalance", f"HTTP 402 during translation ({lang})")
                marker = "⚠" if is_balance else "⟳"
                line = f"{marker} {lang} — {name}: {str(detail)[:100]} — retrying…"
            else:
                line = str(detail)[:160]
            job["log"].append({"kind": kind, "lang": lang, "detail": line})
            job["log"] = job["log"][-200:]

    try:
        result = translator_bridge.run_translation(
            title, description, languages, parts, progress=progress)
        if result["localizations"]:
            with _TRANSLATION_JOBS_LOCK:
                job["log"].append({"kind": "info", "lang": "",
                                   "detail": f"▸ Applying {len(result['localizations'])} "
                                             f"localization(s) to the video…"})
            translator_bridge.update_video_localizations(
                video_id, title, description, "en", result["localizations"])
        applied = list(result["localizations"])
        with _TRANSLATION_JOBS_LOCK:
            job["done"] = len(applied)
            job["running"] = False
            job["error"] = "; ".join(result["errors"]) if result["errors"] else ""
            job["applied"] = len(applied)
            for code in applied:
                job["log"].append({"kind": "ok", "lang": code,
                                   "detail": f"✓ {code} — {catalog.get(code, code)}: "
                                             f"applied to the video"})
            if result["errors"]:
                job["log"].append({"kind": "fail", "lang": "",
                                   "detail": f"✗ {len(result['errors'])} language(s) failed — "
                                             f"the rest were applied"})
        log.info("Translation for stream %d applied %d/%d language(s)",
                 stream_id, len(applied), len(languages))
    except Exception as e:
        log.warning("Translation for stream %d failed: %s", stream_id, e)
        with _TRANSLATION_JOBS_LOCK:
            job["running"] = False
            job["error"] = str(e)[:300]
            job["needs_auth"] = _is_auth_error(e)
            job["log"].append({"kind": "fail", "lang": "",
                               "detail": f"✗ failed — {str(e)[:140]}"})


@app.route("/stream/translate/<int:stream_id>", methods=["POST"])
@login_required
@ajax_required
def stream_translate(stream_id):
    _owned_stream(stream_id)
    stream = db.get_stream(stream_id)
    if not stream:
        abort(404)
    if not translator_bridge.ready():
        return jsonify({"ok": False, "message": translator_bridge.load_error}), 400
    video_id = _translation_video_id(stream)
    if not video_id:
        return jsonify({"ok": False, "message": "No YouTube URL on this stream"}), 400
    if (stream["translate_source"] or "video") == "manual":
        title = (stream["translate_title"] or "").strip()
        description = (stream["translate_description"] or "").strip()
        if not title:
            return jsonify({"ok": False, "message": "Manual source title is empty"}), 400
    else:
        try:
            meta = translator_bridge.fetch_video_meta(video_id)
        except Exception as e:
            return jsonify({"ok": False, "message": f"Cannot fetch video: {e}",
                            "needs_auth": _is_auth_error(e)}), 502
        title = meta.get("title", "")
        description = meta.get("description", "")
    try:
        languages = json.loads(stream["translate_languages"] or "[]")
    except ValueError:
        languages = []
    if not languages:
        return jsonify({"ok": False, "message": "No target languages selected"}), 400

    with _TRANSLATION_JOBS_LOCK:
        old = _TRANSLATION_JOBS.get(stream_id)
        if old and old["running"]:
            return jsonify({"ok": False, "message": "A translation is already running"}), 409
        provider_name = None
        try:
            provider_name = (translator_bridge.engine.get_active_provider() or {}).get("name")
        except Exception:
            pass
        _TRANSLATION_JOBS[stream_id] = {
            "running": True, "done": 0, "total": len(languages),
            "applied": 0, "error": "", "started": time.time(),
            "video_id": video_id,
            "log": [{"kind": "info", "lang": "",
                     "detail": f"▸ Starting translation into {len(languages)} language(s): "
                               f"{', '.join(languages)}"
                               + (f" — provider: {provider_name}" if provider_name else "")}],
        }
        job = _TRANSLATION_JOBS[stream_id]
    parts = stream["translate_parts"] or "all"
    threading.Thread(target=_translation_worker,
                     args=(stream_id, video_id, title, description, languages, parts),
                     daemon=True).start()
    return jsonify({"ok": True, "total": len(languages)})


@app.route("/api/translate_status/<int:stream_id>")
@login_required
@ajax_required
def translate_status(stream_id):
    _owned_stream(stream_id)
    with _TRANSLATION_JOBS_LOCK:
        job = _TRANSLATION_JOBS.get(stream_id)
        return jsonify(job or {"running": False, "done": 0, "total": 0,
                               "applied": 0, "error": "", "log": []})


@app.route("/api/yt_lookup")
@login_required
@ajax_required
def yt_lookup():
    """Title/channel/description lookup for a YouTube URL. Default mode is
    best-effort ({} on any failure) for the form autofill; ?strict=1 returns
    real errors so the localization Fetch button can show and route them."""
    video_id = _youtube_id(request.args.get("url", ""))
    strict = request.args.get("strict") == "1"
    if not video_id:
        if strict:
            return jsonify({"error": "Not a YouTube video URL"}), 400
        return jsonify({})
    if not translator_bridge.ready() or translator_bridge.get_youtube_client() is None:
        if strict:
            return jsonify({"error": "YouTube channel is not connected",
                            "needs_auth": True}), 502
        return jsonify({})
    try:
        return jsonify(translator_bridge.video_lookup(video_id))
    except Exception as e:
        if strict:
            return jsonify({"error": str(e)[:200],
                            "needs_auth": _is_auth_error(e)}), 502
        return jsonify({})


def _admin_guard():
    if current_role() != "admin":
        abort(403)


@app.route("/admin/translator/secrets", methods=["POST"])
@login_required
def admin_translator_secrets():
    _admin_guard()
    file = request.files.get("secrets")
    if not file or not file.filename:
        flash("Choose a client_secrets file first", "error")
        return redirect(url_for("admin_panel"))
    try:
        translator_bridge.save_secrets(file.read())
        flash("OAuth client secrets saved", "ok")
    except Exception as e:
        flash(f"Rejected: {e}", "error")
    return redirect(url_for("admin_panel") + "#translator")


@app.route("/admin/translator/connect")
@login_required
def admin_translator_connect():
    """Start the Google OAuth flow with a redirect back to this site."""
    _admin_guard()
    if not translator_bridge.ready():
        flash(translator_bridge.load_error or "Translator engine unavailable", "error")
        return redirect(url_for("admin_panel"))
    if not translator_bridge.has_secrets():
        flash("Upload the OAuth client secrets JSON first", "error")
        return redirect(url_for("admin_panel") + "#translator")
    try:
        from google_auth_oauthlib.flow import Flow
    except ImportError:
        flash("google-auth-oauthlib is not installed (see requirements.txt)", "error")
        return redirect(url_for("admin_panel"))
    eng = translator_bridge.engine
    with open(translator_bridge.os.path.join(
            translator_bridge.data_dir(), "client_secrets.json"), encoding="utf-8") as f:
        client_config = json.load(f)
    redirect_uri = (config.SITE_URL or request.url_root.rstrip("/")) + "/oauth2callback"
    flow = Flow.from_client_config(client_config, scopes=eng.SCOPES,
                                   redirect_uri=redirect_uri)
    auth_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="false", prompt="consent")
    session["oauth_state"] = state
    return redirect(auth_url)


@app.route("/oauth2callback")
@login_required
def oauth2callback():
    _admin_guard()
    eng = translator_bridge.engine
    if eng is None:
        abort(404)
    if request.args.get("error"):
        flash(f"Google returned: {request.args['error']}", "error")
        return redirect(url_for("admin_panel") + "#translator")
    if request.args.get("code") is None or "oauth_state" not in session:
        abort(400)
    try:
        from google_auth_oauthlib.flow import Flow
        import googleapiclient.discovery
        import pickle
        redirect_uri = (config.SITE_URL or request.url_root.rstrip("/")) + "/oauth2callback"
        with open(translator_bridge.os.path.join(
                translator_bridge.data_dir(), "client_secrets.json"), encoding="utf-8") as f:
            client_config = json.load(f)
        flow = Flow.from_client_config(client_config, scopes=eng.SCOPES,
                                       redirect_uri=redirect_uri, state=session["oauth_state"])
        flow.fetch_token(authorization_response=request.url)
        credentials = flow.credentials
        # A token file per connect, so several channels can stay authorized.
        token_file = f"oauth_token_{uuid.uuid4().hex[:8]}.pickle"
        with open(translator_bridge.os.path.join(
                translator_bridge.data_dir(), token_file), "wb") as f:
            pickle.dump(credentials, f)
        profiles = eng.load_channel_profiles()
        profile = {"id": f"channel_{uuid.uuid4().hex[:6]}", "name": "Channel",
                   "token_file": token_file,
                   "client_secrets_file": "client_secrets.json",
                   "playlists": [], "default_playlists": []}
        profiles["profiles"].append(profile)
        youtube = googleapiclient.discovery.build("youtube", "v3", credentials=credentials)
        eng.refresh_profile_identity(youtube, profile, profiles)
        # One profile per channel: reconnecting the same channel replaces its
        # old entry instead of piling up duplicates.
        profiles["profiles"] = [p for p in profiles["profiles"]
                                if p is profile or p.get("channel_id") != profile.get("channel_id")]
        eng.save_channel_profiles(profiles)
        translator_bridge._yt_clients.clear()  # force client rebuilds for new tokens
        flash(f"YouTube channel connected: {profile.get('channel_title', '')}", "ok")
    except Exception as e:
        logging.getLogger("streamcast").warning("OAuth connect failed: %s", e)
        flash(f"YouTube connect failed: {str(e)[:200]}", "error")
    session.pop("oauth_state", None)
    return redirect(url_for("admin_panel") + "#translator")


def _translator_api(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        _admin_guard()
        if not translator_bridge.ready():
            return jsonify({"ok": False, "message": translator_bridge.load_error}), 400
        return view(*args, **kwargs)
    return wrapped


@app.route("/api/translator/settings")
@login_required
@ajax_required
def translator_settings():
    _admin_guard()
    vendored = translator_bridge.vendored_version()
    return jsonify({
        "ok": True,
        "status": translator_bridge.status(),
        "has_secrets": translator_bridge.has_secrets(),
        "registry": translator_bridge.provider_registry_view(),
        "parallel": translator_bridge.parallelism(),
        "vendored": vendored,
        "alerts": translator_bridge.get_provider_alerts(),
    })


@app.route("/api/translator/provider/save", methods=["POST"])
@login_required
@ajax_required
@_translator_api
def translator_provider_save():
    data = request.get_json() or {}
    entry = data.get("entry") or {}
    if not entry.get("name"):
        return jsonify({"ok": False, "message": "Provider name is required"}), 400
    import hashlib
    reg = translator_bridge.provider_registry()
    keep = set(data.get("keep", []))
    new_keys = [k for k in re.split(r"[,\s]+", str(data.get("new_keys", ""))) if k]
    clean = {k: v for k, v in entry.items()
             if k in ("id", "name", "kind", "base_url", "model", "auth")}
    existing = next((p for p in reg["providers"] if p["id"] == clean.get("id")), None)
    if existing:
        if existing.get("auth"):
            merged = [k for k in existing.get("api_keys", [])
                      if hashlib.sha1(k.encode()).hexdigest()[:10] in keep] + new_keys
        else:
            merged = []
        existing.update(clean)
        existing["api_keys"] = merged
    else:
        eng = translator_bridge.engine
        clean["id"] = eng.profile_slug(clean["name"], {p["id"] for p in reg["providers"]})
        clean["api_keys"] = new_keys
        reg["providers"].append(clean)
        reg.setdefault("active", clean["id"])
    translator_bridge.save_provider_registry(reg)
    return jsonify({"ok": True, "registry": translator_bridge.provider_registry_view()})


@app.route("/api/translator/provider/activate", methods=["POST"])
@login_required
@ajax_required
@_translator_api
def translator_provider_activate():
    data = request.get_json() or {}
    reg = translator_bridge.provider_registry()
    if data.get("id") not in {p["id"] for p in reg["providers"]}:
        return jsonify({"ok": False, "message": "Unknown provider"}), 400
    reg["active"] = data["id"]
    translator_bridge.save_provider_registry(reg)
    return jsonify({"ok": True, "registry": translator_bridge.provider_registry_view()})


@app.route("/api/translator/provider/delete", methods=["POST"])
@login_required
@ajax_required
@_translator_api
def translator_provider_delete():
    data = request.get_json() or {}
    reg = translator_bridge.provider_registry()
    reg["providers"] = [p for p in reg["providers"] if p["id"] != data.get("id")]
    if reg.get("active") not in {p["id"] for p in reg["providers"]}:
        reg["active"] = reg["providers"][0]["id"] if reg["providers"] else None
    translator_bridge.save_provider_registry(reg)
    return jsonify({"ok": True, "registry": translator_bridge.provider_registry_view()})


@app.route("/api/translator/provider/check_keys", methods=["POST"])
@login_required
@ajax_required
@_translator_api
def translator_provider_check_keys():
    provider_id = (request.get_json() or {}).get("provider_id")
    try:
        keys = translator_bridge.check_provider_keys(provider_id)
    except ValueError as e:
        return jsonify({"ok": False, "message": str(e)}), 400
    # A fully healthy check clears a live "out of balance" alert for the provider.
    if keys and all(k["status"] == "ok" for k in keys):
        translator_bridge.clear_provider_alert(provider_id)
    return jsonify({"ok": True, "keys": keys})


@app.route("/api/translator/parallel", methods=["POST"])
@login_required
@ajax_required
@_translator_api
def translator_parallel():
    value = (request.get_json() or {}).get("value", "auto")
    try:
        saved = translator_bridge.set_parallelism(value)
    except ValueError:
        return jsonify({"ok": False, "message": "Invalid value"}), 400
    return jsonify({"ok": True, "parallel": translator_bridge.parallelism(),
                    "saved": saved})


@app.route("/api/translator/preset/save", methods=["POST"])
@login_required
@ajax_required
@_translator_api
def translator_preset_save():
    data = request.get_json() or {}
    name = str(data.get("name") or "").strip()
    codes = [c for c in (data.get("codes") or []) if c]
    if not name or not codes:
        return jsonify({"ok": False, "message": "Name and at least one language are required"}), 400
    translator_bridge.save_preset(name, codes)
    return jsonify({"ok": True, "presets": translator_bridge.language_presets()})


@app.route("/api/translator/preset/delete", methods=["POST"])
@login_required
@ajax_required
@_translator_api
def translator_preset_delete():
    name = str((request.get_json() or {}).get("name") or "").strip()
    translator_bridge.delete_preset(name)
    return jsonify({"ok": True, "presets": translator_bridge.language_presets()})


@app.route("/admin/translator/update", methods=["POST"])
@login_required
def admin_translator_update():
    _admin_guard()
    try:
        info = translator_bridge.update_vendor()
        flash(f"Translator engine updated to {info['sha']}", "ok")
    except Exception as e:
        logging.getLogger("streamcast").warning("Vendor update failed: %s", e)
        flash(f"Update failed: {str(e)[:200]}", "error")
    return redirect(url_for("admin_panel") + "#translator")


@app.route("/stream/delete/<int:stream_id>", methods=["POST"])
@login_required
def stream_delete(stream_id):
    stream = db.get_stream(stream_id)
    if not stream:
        abort(404)
    if current_role() == "viewer" or not _owns_stream(stream):
        abort(403)
    manager.stop_stream(stream_id)
    for v in db.list_videos(stream_id):
        _remove_video_files(v)
    db.delete_stream(stream_id)
    flash("Stream deleted", "ok")
    return redirect(url_for("dashboard"))


# --- Start / stop / schedule ------------------------------------------------
def _post_action_redirect(stream_id):
    # Tile buttons on the dashboard pass next=dashboard to stay there;
    # every other caller lands back on the stream page.
    if request.args.get("next") == "dashboard":
        return redirect(url_for("dashboard"))
    return redirect(url_for("stream_detail", stream_id=stream_id))


def _post_action_result(stream_id, ok, msg):
    # Tile switches fetch this with X-Requested-With and read JSON, so a
    # failed start (e.g. unconfigured stream) can be reported in place
    # instead of the switch blindly flipping on a redirect response.
    if request.headers.get("X-Requested-With") == "XMLHttpRequest":
        return jsonify({"ok": ok, "message": msg})
    flash(msg, "ok" if ok else "error")
    return _post_action_redirect(stream_id)


@app.route("/stream/start/<int:stream_id>", methods=["POST"])
@login_required
def stream_start(stream_id):
    _owned_stream(stream_id)
    ok, msg = manager.start_stream(stream_id)
    return _post_action_result(stream_id, ok, msg)


@app.route("/stream/stop/<int:stream_id>", methods=["POST"])
@login_required
def stream_stop(stream_id):
    _owned_stream(stream_id)
    ok, msg = manager.stop_stream(stream_id)
    return _post_action_result(stream_id, ok, msg)


@app.route("/stream/apply/<int:stream_id>", methods=["POST"])
@login_required
def stream_apply(stream_id):
    stream = _owned_stream(stream_id)
    ok, msg = manager.apply_now(stream_id)
    flash(msg, "ok" if ok else "error")
    return redirect(url_for("stream_detail", stream_id=stream_id))


@app.route("/stream/schedule/<int:stream_id>", methods=["POST"])
@login_required
def stream_schedule(stream_id):
    _owned_stream(stream_id)
    when = request.form.get("scheduled_at", "").strip()
    if when:
        # HTML datetime-local -> unix ts (server local time).
        try:
            ts = time.mktime(time.strptime(when, "%Y-%m-%dT%H:%M"))
            db.update_stream(stream_id, scheduled_at=ts)
            flash("Scheduled", "ok")
        except ValueError:
            flash("Bad date", "error")
    else:
        db.update_stream(stream_id, scheduled_at=None)
        flash("Schedule cleared", "ok")
    return redirect(url_for("stream_detail", stream_id=stream_id))


# --- Upload / delete video --------------------------------------------------
def _unlink_retry(path, attempts=3, delay=0.4):
    """Windows: a file with an open handle (e.g. an open preview player) can't
    be unlinked — retry briefly, then give up so the row still goes away
    (the startup sweep will clean the orphaned file later)."""
    for _ in range(attempts):
        try:
            path.unlink(missing_ok=True)
            return True
        except PermissionError:
            time.sleep(delay)
    logging.getLogger("streamcast").warning("Could not delete %s (file in use)", path)
    return False


def _remove_video_files(video):
    if video["stored_name"]:
        _unlink_retry(storage.video_upload_path(video))
    if video["encoded_name"]:
        _unlink_retry(storage.video_encoded_path(video))
        _unlink_retry(_thumb_path(video))


def _do_save_file(fileobj, stored_name, targets):
    """Save an upload to the first storage that works. The pre-checked order
    is default-first; if a disk still runs out mid-write (stale free-space
    numbers, concurrent uploads), the partial file is dropped and the next
    storage gets the whole file from the start. Returns the storage row."""
    last_err = None
    for row in targets:
        try:
            fileobj.stream.seek(0)  # a previous attempt may have consumed part of it
            fileobj.save(storage.upload_dir(row) / stored_name)
            return row
        except OSError as e:
            last_err = e
            try:
                (storage.upload_dir(row) / stored_name).unlink(missing_ok=True)
            except OSError:
                pass
    raise last_err if last_err else OSError("no storage available")


@app.route("/upload/<int:stream_id>", methods=["POST"])
@login_required
def upload(stream_id):
    _owned_stream(stream_id)
    curr_stream = db.get_stream(stream_id)
    if not curr_stream:
        abort(404)
    
    is_music = curr_stream["stream_type"] == "music"
    files = request.files.getlist("video")
    
    # Лимит места
    needed_space = (request.content_length or 0) * 2
    storage_targets = storage.upload_targets(needed=needed_space)
    
    added_count = 0
    # Проверяем флаг быстрого импорта
    is_fast = request.form.get("already_encoded") == "on"
    stream_quality_mode = curr_stream["quality_mode"] or "balanced"
    
    for f in files:
        if not f or not f.filename:
            continue
        
        ext = Path(f.filename).suffix.lower()
        if ext in config.ALLOWED_EXT:
            kind = "video"
        elif is_music and ext in config.ALLOWED_AUDIO_EXT:
            kind = "audio"
        else:
            flash(f"{f.filename}: unsupported type", "error")
            continue
            
        stored_name = f"{uuid.uuid4().hex}{ext}"
        
        try:
            if is_fast:
                # БЫСТРЫЙ ПУТЬ: файл уже нормализован локальным энкодером —
                # пишем сразу в encoded/ без ffmpeg. Тот же fallback по дискам,
                # что и у обычной загрузки.
                if not storage_targets:
                    raise OSError("no storage available")
                res_row = storage_targets[0]
                target_path = storage.encoded_dir(res_row) / stored_name
                with open(target_path, "wb") as out_f:
                    shutil.copyfileobj(f.stream, out_f)
                status_val = "completed"
                encoded_name_val = stored_name
                if kind == "video" and ext != ".mp4":
                    flash(f"{f.filename}: not an .mp4 — the stream expects files "
                          f"pre-encoded by the local encoder", "error")
            else:
                # ОБЫЧНЫЙ ПУТЬ: через _do_save_file (бывший _save_upload)
                res_row = _do_save_file(f, stored_name, storage_targets)
                status_val = "waiting_encode"
                encoded_name_val = None

            # Метаданные, которые при обычном энкодинге проставляет encoder.py,
            # — иначе у тайла нет размера, бейджа и длительности.
            duration, fps, w, h = 0, 0.0, None, None
            try:
                duration, fps, w, h = ffprobe_info(target_path)
            except Exception:
                pass
            if is_fast and kind == "video" and fps and fps >= config.MAX_FPS:
                target_path.unlink(missing_ok=True)
                flash(f"{f.filename}: {fps:.0f}fps rejected (max {config.MAX_FPS - 1}fps)", "error")
                continue

            video_id = db.add_video(stream_id, f.filename, stored_name, kind=kind,
                         storage_id=res_row["id"], status=status_val,
                         encoded_name=encoded_name_val, encode_preset=stream_quality_mode)
            added_count += 1

            updates = {"duration": duration}
            try:
                updates["size"] = target_path.stat().st_size
            except OSError:
                pass
            if kind == "video":
                updates["width"], updates["height"] = w, h
            db.update_video(video_id, **updates)
            if is_fast:
                _ensure_thumb(db.get_video(video_id))

        except Exception as e:
            logging.getLogger("streamcast").exception(f"Upload error: {e}")
            flash(f"{f.filename}: upload failed", "error")
            continue
            
    if added_count:
        msg = f"{added_count} file(s) ready" if is_fast else f"{added_count} file(s) queued for encoding"
        flash(msg, "ok")
        
    return redirect(url_for("stream_detail", stream_id=stream_id))

@app.route("/video/set_loop/<int:video_id>", methods=["POST"])
@login_required
def video_set_loop(video_id):
    """Music streams: pick which uploaded video loops as the visual background."""
    video = db.get_video(video_id)
    if not video:
        abort(404)
    _owned_stream(video["stream_id"])
    kind = video["kind"] if "kind" in video.keys() else "video"
    if kind == "audio" or video["status"] != "completed":
        flash("Only an encoded video can be set as the loop background", "error")
        return redirect(url_for("stream_detail", stream_id=video["stream_id"]))
    db.update_stream(video["stream_id"], loop_video_id=video_id)
    manager.apply_now(video["stream_id"])  # takes effect immediately when live
    flash("Loop background video updated", "ok")
    return redirect(url_for("stream_detail", stream_id=video["stream_id"]))


def _delete_video_row(video):
    """Terminate a running encode, clear loop references, delete the row and
    remove files (best effort — the startup sweep cleans any orphans)."""
    terminate_job(video["id"])
    stream = db.get_stream(video["stream_id"])
    if stream and "loop_video_id" in stream.keys() and stream["loop_video_id"] == video["id"]:
        db.update_stream(video["stream_id"], loop_video_id=None)
    db.delete_video(video["id"])
    _remove_video_files(video)


@app.route("/video/delete/<int:video_id>", methods=["POST"])
@login_required
def video_delete(video_id):
    video = db.get_video(video_id)
    if not video:
        abort(404)
    # Deleting videos is owner-level: workers may manage their streams' queues
    # but never remove the files themselves.
    if current_role() != "admin":
        abort(403)
    _delete_video_row(video)
    return redirect(url_for("stream_detail", stream_id=video["stream_id"]))


@app.route("/videos/delete/<int:stream_id>", methods=["POST"])
@login_required
@ajax_required
def videos_delete_batch(stream_id):
    """Batch delete selected queue files (admins only)."""
    stream = db.get_stream(stream_id)
    if not stream:
        abort(404)
    if current_role() != "admin":
        abort(403)
    data = request.get_json(silent=True) or {}
    try:
        ids = [int(i) for i in data.get("ids", [])]
    except (TypeError, ValueError):
        ids = []
    deleted = 0
    for vid in ids:
        video = db.get_video(vid)
        if video and video["stream_id"] == stream_id:
            _delete_video_row(video)
            deleted += 1
    return jsonify({"ok": True, "deleted": deleted})


@app.route("/video/file/<int:video_id>")
@login_required
def video_file(video_id):
    """Owner-only preview player for the normalized file (no YouTube needed)."""
    video = db.get_video(video_id)
    if not video or not video["encoded_name"]:
        abort(404)
    _owned_stream(video["stream_id"])
    path = storage.video_encoded_path(video)
    if not path.exists():
        abort(404)
    mime = "audio/mpeg" if video["kind"] == "audio" else "video/mp4"
    return send_file(path, mimetype=mime, conditional=True)


# --- JSON API (live polling) ------------------------------------------------
@app.route("/api/video_statuses/<int:stream_id>")
@login_required
def api_video_statuses(stream_id):
    videos = []
    for v in db.list_videos(stream_id):
        d = dict(v)
        _hydrate_media_meta(d)
        videos.append({
            "id": v["id"], "status": v["status"], "error": v["error_msg"],
            "duration": round(v["duration"] or 0, 1),
            "progress": v["progress"] if "progress" in v.keys() else 0,
            "res": _res_label(d.get("width"), d.get("height")),
            "size_label": _fmt_size(d.get("size")),
        })
    return jsonify(videos)


@app.route("/thumb/<int:video_id>")
@login_required
def video_thumb(video_id):
    """Tile thumbnail: a frame grabbed from the encoded video."""
    video = db.get_video(video_id)
    if not video or not video["encoded_name"] or video["kind"] == "audio":
        abort(404)
    thumb = _thumb_path(video)
    if not thumb.exists():
        _ensure_thumb(video)
        if not thumb.exists():
            abort(404)
    return send_file(thumb, mimetype="image/jpeg", max_age=3600)


@app.route('/api/stream_status/<int:stream_id>')
@login_required
def api_stream_status(stream_id):
    runner_status = manager.status(stream_id)
    stream = db.get_stream(stream_id)
    shuffle = False
    if stream:
        try:
            shuffle = bool(stream["shuffle"])
        except (KeyError, TypeError):
            shuffle = False
    vd, ad, sz = db.stream_totals(stream_id)
    res = {
        "live": runner_status.get("live", False),
        "error": runner_status.get("error", ""),
        "now_playing": runner_status.get("now_playing"),
        "shuffle": shuffle,
        "uptime": runner_status.get("uptime"),
        "totals": {
            "runtime": _fmt_runtime(max(vd, ad)),
            "size": _fmt_size(sz),
        },
    }
    return jsonify(res)


@app.route("/api/encode_count")
@login_required
def api_encode_count():
    """Live count of queued/running encodes for the dashboard chip."""
    return jsonify({"count": db.count_encoding_videos()})


@app.route('/api/stream_mix/<int:stream_id>', methods=['POST'])
@login_required
@ajax_required
def stream_mix(stream_id):
    """Music streams: mix the background video's own sound under the playlist."""
    _owned_stream(stream_id)
    try:
        data = request.get_json() or {}
        enabled = bool(data.get('enabled', False))
        fields = {'mix_video_audio': 1 if enabled else 0}
        if 'volume' in data:
            vol = max(0, min(200, int(data['volume'])))
            fields['video_volume'] = vol / 100.0
        db.update_stream(stream_id, **fields)
        manager.apply_now(stream_id)
        return jsonify({'status': 'ok', 'enabled': enabled})
    except Exception:
        logging.getLogger("streamcast").exception("API error in %s", request.path)
        return jsonify({'status': 'error', 'message': 'Internal error'}), 500


@app.route('/api/stream_volume/<int:stream_id>', methods=['POST'])
@login_required
@ajax_required
def stream_volume(stream_id):
    """Playback loudness: video-stream audio or the music playlist (0..200%)."""
    _owned_stream(stream_id)
    try:
        data = request.get_json() or {}
        vol = max(0, min(200, int(data.get('volume', 100))))
        stream = db.get_stream(stream_id)
        if not stream:
            return jsonify({'status': 'error', 'message': 'Stream not found'}), 404
        field = 'music_volume' if stream["stream_type"] == "music" else 'stream_volume'
        db.update_stream(stream_id, **{field: vol / 100.0})
        manager.apply_now(stream_id)
        return jsonify({'status': 'ok', 'volume': vol})
    except Exception:
        logging.getLogger("streamcast").exception("API error in %s", request.path)
        return jsonify({'status': 'error', 'message': 'Internal error'}), 500


@app.route("/api/reorder", methods=["POST"])
@login_required
@ajax_required
def api_reorder():
    data = request.get_json(silent=True) or {}
    stream_id = data.get("stream_id")
    order = data.get("order", [])
    if stream_id is None:
        return jsonify({"ok": False}), 400
    _owned_stream(int(stream_id))
    db.reorder_videos(int(stream_id), [int(i) for i in order])
    return jsonify({"ok": True})




# --- Boot -------------------------------------------------------------------
def _setup_logging():
    """File + console logging so a VPS has something to inspect after a crash."""
    fmt = logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s")
    root = logging.getLogger()
    root.setLevel(logging.INFO)
    file_h = RotatingFileHandler(
        config.STORAGE_DIR / "streamcast.log",
        maxBytes=2_000_000, backupCount=3, encoding="utf-8",
    )
    file_h.setFormatter(fmt)
    root.addHandler(file_h)
    console_h = logging.StreamHandler()
    console_h.setFormatter(fmt)
    root.addHandler(console_h)


def _sweep_orphan_files():
    """Delete storage files no longer referenced by any video row — leftovers
    from deletes that hit the Windows 'file in use' race on a previous run."""
    referenced = set()
    for v in db.list_all_videos():
        if v["stored_name"]:
            referenced.add(v["stored_name"])
        for name in (v["encoded_name"], v["prev_encoded_name"]):
            if name:
                referenced.add(name)
                referenced.add(name + ".jpg")
    removed = 0
    dirs = []
    for row in db.list_storages():
        dirs += (storage.upload_dir(row), storage.encoded_dir(row))
    for d in dirs:
        if not d.exists():
            continue
        for f in d.iterdir():
            if f.is_file() and f.name not in referenced:
                try:
                    f.unlink(missing_ok=True)
                    removed += 1
                except OSError:
                    pass
    if removed:
        logging.getLogger("streamcast").info("Swept %d orphaned storage file(s)", removed)


@login_required
@app.route('/admin/storage/default/<int:storage_id>', methods=['POST'])
@login_required
def admin_set_default_storage(storage_id):
    if current_role() != 'admin':
        abort(403)
    db.set_default_storage(storage_id)
    flash('Default storage updated', 'ok')
    return redirect(url_for('admin'))

def bootstrap():
    config.ensure_dirs()
    _setup_logging()
    db.init_db()
    storage.ensure_all()
    if config.SECRET_KEY == "dev-secret-change-me":
        # Safe default for self-hosters who never set STREAMCAST_SECRET: mint a
        # random key once and keep it in the DB so sessions survive restarts.
        stored = db.get_setting("session_secret")
        if not stored:
            stored = secrets.token_hex(32)
            db.set_setting("session_secret", stored)
            logging.getLogger("streamcast").info(
                "STREAMCAST_SECRET not set — generated a random session key (stored in the DB)")
        app.config["SECRET_KEY"] = stored
    _sweep_orphan_files()
    encoder_worker.start()
    manager.start_scheduler()
    if config.AUTO_RESUME:
        log = logging.getLogger("streamcast")
        resumed, failed = manager.resume_interrupted()
        for sid in resumed:
            log.info("Resumed stream %d (was live before restart)", sid)
        for sid, msg in failed:
            log.warning("Could not resume stream %d: %s", sid, msg)
    logging.getLogger("streamcast").info("StreamCast started")


@app.route('/api/stream_shuffle/<int:stream_id>', methods=['POST'])
@login_required
@ajax_required
def toggle_shuffle(stream_id):
    _owned_stream(stream_id)
    try:
        data = request.get_json() or {}
        enabled = data.get('enabled', False)
        db.update_stream(stream_id, shuffle=1 if enabled else 0)
        manager.apply_now(stream_id)
        return jsonify({'status': 'ok', 'shuffle': enabled})
    except Exception:
        logging.getLogger("streamcast").exception("API error in %s", request.path)
        return jsonify({'status': 'error', 'message': 'Internal error'}), 500
bootstrap()

if __name__ == "__main__":
    # Dev server. Use gunicorn in production (see README).
    app.run(host=config.HOST, port=config.PORT, debug=False, threaded=True)