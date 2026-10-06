"""YouTube Metadata Translator — web interface.

Local stdlib-only server (no new dependencies): serves the SPA from
webui_static/ and exposes a JSON API over yt_metadata_translator.
Run:  python webui.py   (opens the browser automatically)
"""
import hashlib
import json
import os
import re
import shutil
import threading
import time
import webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

import yt_metadata_translator as eng

import sys

if getattr(sys, "frozen", False):
    # сборка PyInstaller: интерфейс — во временной распаковке,
    # данные (data/) — рядом с exe, чтобы переживали перезапуски
    BASE_DIR = os.path.dirname(sys.executable)
    STATIC_DIR = os.path.join(sys._MEIPASS, "webui_static")
    eng.BASE_DIR = BASE_DIR
    eng.DATA_DIR = os.path.join(BASE_DIR, "data")
else:
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    STATIC_DIR = os.path.join(BASE_DIR, "webui_static")
PORT_RANGE = range(8765, 8790)

# ---------------------------------------------------------------------------
# Shared job state (translation runs in a background thread; the UI polls)
# ---------------------------------------------------------------------------

_LOCK = threading.Lock()
CLIENTS = {}          # profile_id -> authorized youtube client
THREAD_JOB = {}       # thread ident -> job id, used by the stdout tee
JOBS = {}             # job id -> state dict
JOB_SEQ = 0
AUTH = {"running": False, "ok": None, "error": "", "channel": "", "profile_id": ""}


def new_job(kind):
    global JOB_SEQ
    with _LOCK:
        JOB_SEQ += 1
        job = {"id": JOB_SEQ, "kind": kind, "running": True, "done": False,
               "error": "", "log": [], "videos_total": 0, "videos_done": 0,
               "video_title": "", "langs": {}, "cancel": False, "started": time.time()}
        JOBS[JOB_SEQ] = job
        return job


def job_progress(job, state, code, detail=""):
    with _LOCK:
        job["langs"][code] = {"state": state, "detail": detail}


def job_log(job, text):
    with _LOCK:
        job["log"].append(str(text))
        del job["log"][:-400]  # keep the tail only


_ANSI = re.compile(r"\x1b\[[0-9;]*m")


class _JobTee:
    """sys.stdout replacement: engine prints from a job thread go to that job's log."""

    def __init__(self, origin):
        self.origin = origin
        # консоль/пайпы Windows часто в cp1251 — эмодзи убивают print
        if hasattr(origin, "reconfigure"):
            try:
                origin.reconfigure(errors="replace")
            except Exception:
                pass

    def write(self, text):
        job_id = THREAD_JOB.get(threading.get_ident())
        line = _ANSI.sub("", str(text)).strip()
        if job_id and line:
            job = JOBS.get(job_id)
            if job:
                with _LOCK:
                    job["log"].append(line)
                    del job["log"][:-400]
        return self.origin.write(text)

    def flush(self):
        self.origin.flush()


# ---------------------------------------------------------------------------
# Helpers over the engine
# ---------------------------------------------------------------------------

def get_client(profile):
    """Authorized youtube client for the profile; refreshes the token silently."""
    client = CLIENTS.get(profile["profile_id"])
    if client:
        return client
    client = eng.authenticate(profile)  # works without a browser when the token is valid
    CLIENTS[profile["profile_id"]] = client
    return client


KEY_STATUS_FILE = "api_key_status.json"
PREVIEW_CACHE = {}          # cache key -> {"data": ..., "ts": ...}
PREVIEW_TTL = 300           # seconds


def _key_hash(key):
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


def _mask_key(key):
    return (key[:3] + "…" + key[-4:]) if len(key) > 9 else "…" + key[-4:]


def _load_key_status():
    try:
        return eng.load_json_file(KEY_STATUS_FILE)
    except (FileNotFoundError, ValueError):
        return {}


def _save_key_status(status):
    eng.save_json_file(KEY_STATUS_FILE, status)


def _live_status(entry):
    """Stored status, with an expired freeze counting as working again."""
    st = entry.get("status", "ok")
    if st == "frozen" and entry.get("until", 0) <= time.time():
        return "ok"
    return st


def provider_view(provider, status_map):
    """Provider as sent to the UI: full keys never leave the server."""
    view = {k: v for k, v in provider.items() if k != "api_keys"}
    key_status = status_map.get(provider["id"], {})
    view["keys"] = [
        {"masked": _mask_key(k), "hash": _key_hash(k),
         "status": _live_status(key_status.get(_key_hash(k), {})),
         "detail": key_status.get(_key_hash(k), {}).get("detail", "")}
        for k in provider.get("api_keys", [])
    ]
    return view


def reg_view(reg):
    status = _load_key_status()
    return {
        "active": reg.get("active"),
        "backup": reg.get("backup"),
        "providers": [provider_view(p, status) for p in reg["providers"]],
    }


def profile_brief(profile):
    return {
        "id": profile["profile_id"],
        "name": profile.get("channel_title") or profile.get("display_name"),
        "client_secrets_file": profile.get("client_secrets_file", ""),
        "logo_url": profile.get("logo_url", ""),
        "ready": eng.profile_is_ready(profile),
        "authorized": bool(profile.get("channel_id")),
        "languages": eng.get_profile_languages(profile),
        "playlists": profile.get("playlists", []),
        "default_playlists": profile.get("default_playlists", []),
    }


def find_profile(profile_id):
    for profile in eng.load_channel_profiles()["profiles"]:
        if profile["profile_id"] == profile_id:
            return profile
    raise ValueError("profile not found")


def update_profile(profile_id, mutate):
    """Mutate one profile inside the loaded list and save — saving a fresh
    eng.load_channel_profiles() would silently drop the change (the engine
    re-reads the file on every call)."""
    profiles = eng.load_channel_profiles()
    for profile in profiles["profiles"]:
        if profile["profile_id"] == profile_id:
            mutate(profile)
            eng.save_channel_profiles(profiles)
            return profile
    raise ValueError("profile not found")


def active_profile():
    saved = eng._ui.get("web_active_profile")
    profiles = eng.load_channel_profiles()["profiles"]
    for profile in profiles:
        if profile["profile_id"] == saved:
            return profile
    return profiles[0] if profiles else None


def create_profile(name, secrets_filename, secrets_content):
    """New profile + client_secrets file uploaded from the browser."""
    profiles = eng.load_channel_profiles()
    profile_id = eng.profile_slug(name, {p["profile_id"] for p in profiles["profiles"]})
    secrets_name = secrets_filename if str(secrets_filename).startswith("client_secrets") \
        else f"client_secrets_{profile_id}.json"
    dest = eng.data_file_path(secrets_name)
    if not os.path.exists(dest):
        # файл уже лежит в data/ (найден сканером) — просто переиспользуем
        json.loads(secrets_content or "{}")
        with open(dest, "w", encoding="utf-8") as f:
            f.write(secrets_content)
    profile = {
        "profile_id": profile_id,
        "display_name": name,
        "channel_id": "",
        "channel_title": "",
        "token_file": f"profiles/{profile_id}/token.pickle",
        "client_secrets_file": secrets_name,
        "playlists": [],
        "default_playlists": [],
        "languages": [],
        "publ_calendar_file": f"profiles/{profile_id}/calendar.json",
    }
    profiles["profiles"].append(profile)
    eng.save_channel_profiles(profiles)
    eng.save_json_file(profile["publ_calendar_file"], {})
    return profile


def start_auth(profile):
    def worker():
        try:
            client = eng.authenticate(profile)
            # identity вносим в профиль внутри одного прочитанного списка и
            # сохраняем этот же список — иначе channel_id теряется (движок
            # перечитывает файл при каждом load_channel_profiles)
            profiles = eng.load_channel_profiles()
            target = next(p for p in profiles["profiles"]
                          if p["profile_id"] == profile["profile_id"])
            eng.refresh_profile_identity(client, target, profiles)
            CLIENTS[profile["profile_id"]] = client
            AUTH.update(running=False, ok=True, error="",
                        channel=profile.get("channel_title") or profile.get("display_name"))
        except Exception as error:
            AUTH.update(running=False, ok=False, error=str(error))
    threading.Thread(target=worker, daemon=True).start()


def start_translation(payload):
    profile = active_profile()
    if profile is None:
        raise ValueError("no profile")
    client = get_client(profile)
    job = new_job("translate")

    mode = payload.get("mode", "last")
    vtype = payload.get("type", "long")  # long | short | live
    links = [line.strip() for line in payload.get("links", []) if line.strip()]
    manual = payload.get("source") == "manual"
    manual_title = str(payload.get("manual_title", "")).strip()
    manual_desc = str(payload.get("manual_desc", "")).strip()
    parts = payload.get("parts", ("title", "description"))
    langs = [c for c in payload.get("langs", []) if c and c != "en"]
    add_playlists = bool(payload.get("add_playlists"))
    do_schedule = bool(payload.get("do_schedule"))
    schedule_date = str(payload.get("schedule_date", "")).strip()

    def progress(state, code, detail=""):
        job_progress(job, state, code, detail)

    # все языки видны в панели с самого начала — иначе прогресс-бар считал
    # проценты от уже отчитавшихся и прыгал на 100% с первым же языком
    for code in langs:
        job_progress(job, "start", code)

    def worker():
        THREAD_JOB[threading.get_ident()] = job["id"]
        try:
            job_log(job, f"🎬 {eng.t('translating').format(n=len(langs))}")
            videos, durations, shorts, lives = eng.get_channel_videos(client)
            sort_key = lambda x: x["snippet"]["publishedAt"]
            videos.sort(key=sort_key, reverse=True)
            lives.sort(key=sort_key, reverse=True)
            if mode == "specific":
                targets = [v for v in (eng.extract_video_id(link) for link in links) if v]
            else:
                targets = eng._pick_translation_targets(
                    videos, shorts, lives, ("last_" if mode == "last" else "all_") + vtype)
            if not targets:
                job_log(job, eng.t("tr_no_matches"))
                return
            with _LOCK:
                job["videos_total"] = len(targets)
            for video_id in targets:
                if job["cancel"]:
                    break
                try:
                    metadata = eng.fetch_video_source_metadata(client, video_id)
                except Exception as error:
                    job_log(job, f"❌ {error}")
                    continue
                if manual:
                    if manual_title:
                        metadata["title"] = manual_title
                    if manual_desc:
                        metadata["description"] = eng.normalize_description(manual_desc)
                eng.save_json_file(eng.METADATA_FILE, metadata)
                with _LOCK:
                    job["video_title"] = metadata["title"]
                job_log(job, f"🎬 {video_id} — {metadata['title']}")
                try:
                    eng.localize_metadata_via_llm(metadata, langs, parts, progress=progress)
                except Exception as error:
                    job_log(job, f"❌ {error}")
                    continue
                if job["cancel"]:
                    # перевод языков уже оплачен, но результат не применяем
                    continue
                localizations = eng.load_json_file(eng.LOCALIZATIONS_FILE)
                try:
                    eng.update_video_metadata(
                        client, video_id,
                        metadata.get("title"), metadata.get("description"), localizations)
                    job_log(job, eng.t("video_updated").format(id=video_id))
                except Exception as error:
                    job_log(job, f"❌ {error}")
                    continue
                if add_playlists:
                    for pl_id in profile.get("default_playlists", []):
                        try:
                            eng.add_video_to_playlist(client, video_id, pl_id)
                            job_log(job, f"➕ {pl_id}")
                        except Exception as error:
                            job_log(job, f"❌ {error}")
                if do_schedule:
                    try:
                        publish_date = eng.datetime.strptime(schedule_date, "%d%m%y")
                        publish_datetime, _ = eng.to_publish_datetime(
                            publish_date, eng.load_calendar(profile))
                        eng.set_publishAt(client, video_id, publish_datetime)
                    except ValueError:
                        job_log(job, "⚠️ ddmmyy")
                with _LOCK:
                    job["videos_done"] += 1
        except Exception as error:
            with _LOCK:
                job["error"] = str(error)
            job_log(job, f"❌ {error}")
        finally:
            THREAD_JOB.pop(threading.get_ident(), None)
            with _LOCK:
                job["running"] = False
                job["done"] = True

    threading.Thread(target=worker, daemon=True).start()
    return job


def fill_missing_logos():
    """Fetch channel avatars for profiles authorized before logos were saved.

    Runs in the background: get_client() refreshes the token silently (no
    browser), so this is quota-cheap and invisible to the user.
    """

    def worker():
        for profile in eng.load_channel_profiles()["profiles"]:
            if not profile.get("channel_id") or profile.get("logo_url"):
                continue
            try:
                client = get_client(profile)
                response = client.channels().list(
                    part="snippet", id=profile["channel_id"]).execute()
                items = response.get("items") or []
                if not items:
                    continue
                thumbnails = items[0]["snippet"].get("thumbnails", {})
                url = (thumbnails.get("medium") or thumbnails.get("default") or {}).get("url")
                if url:
                    update_profile(profile["profile_id"],
                                   lambda p, u=url: p.__setitem__("logo_url", u))
            except Exception:
                continue

    threading.Thread(target=worker, daemon=True).start()


def schedule_video(payload):
    profile = active_profile()
    client = get_client(profile)
    video_id = eng.extract_video_id(str(payload.get("link", "")))
    if not video_id:
        raise ValueError("bad link")
    publish_date = eng.datetime.strptime(str(payload.get("date", "")).strip(), "%d%m%y")
    custom_time = str(payload.get("time", "")).strip()
    if custom_time:
        # время, выбранное пользователем; без него берётся календарь публикаций
        chosen = eng.datetime.strptime(custom_time, "%H:%M")
        publish_time = custom_time
        publish_datetime = eng.local_to_utc(
            eng.datetime.combine(publish_date.date(), chosen.time()))
    else:
        publish_datetime, publish_time = eng.to_publish_datetime(
            publish_date, eng.load_calendar(profile))
    if not eng.set_publishAt(client, video_id, publish_datetime):
        raise ValueError("YouTube refused the schedule")
    return {"video_id": video_id,
            "when": publish_datetime.strftime("%d.%m.%Y %H:%M"), "time": publish_time}


# ---------------------------------------------------------------------------
# HTTP layer
# ---------------------------------------------------------------------------

MIME = {".html": "text/html", ".js": "text/javascript", ".css": "text/css",
        ".svg": "image/svg+xml", ".png": "image/png", ".ico": "image/x-icon"}


class Handler(BaseHTTPRequestHandler):
    server_version = "YTMetadataWeb/1.0"

    # --- plumbing ---

    def _send(self, code, body, content_type="application/json; charset=utf-8"):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, obj, code=200):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode("utf-8"))

    def _body(self):
        length = int(self.headers.get("Content-Length") or 0)
        if not length:
            return {}
        return json.loads(self.rfile.read(length).decode("utf-8"))

    def log_message(self, fmt, *args):
        pass  # keep the console quiet

    def do_GET(self):
        path = self.path.split("?", 1)[0]
        try:
            if path == "/":
                return self._file("index.html")
            if path.startswith("/static/"):
                return self._file(path[len("/static/"):])
            if path == "/api/bootstrap":
                return self.api_bootstrap()
            if path == "/api/job":
                return self.api_job()
            if path == "/api/auth":
                return self._json(dict(AUTH))
            if path == "/api/providers":
                return self._json(reg_view(eng.load_provider_registry()))
            return self._json({"error": "not found"}, 404)
        except Exception as error:
            self._json({"error": str(error)}, 500)

    def do_POST(self):
        path = self.path.split("?", 1)[0]
        try:
            data = self._body()
            if path == "/api/quit":
                threading.Timer(0.3, os._exit, (0,)).start()
                return self._json({"ok": True})
            if path == "/api/onboarding":
                eng._ui["language"] = data.get("language")
                eng._ui["user_name"] = str(data.get("name", "")).strip()
                eng.save_ui_settings()
                return self._json({"ok": True})
            if path == "/api/ui":
                for key in ("language", "user_name", "ask_playlists", "ask_schedule",
                            "language_presets", "web_active_profile", "theme"):
                    if key in data:
                        eng._ui[key] = data[key]
                eng.save_ui_settings()
                return self._json({"ok": True})
            if path == "/api/profiles":
                profile = create_profile(str(data.get("name", "")).strip(),
                                         str(data.get("secrets_filename", "")),
                                         str(data.get("secrets_content", "")))
                return self._json(profile_brief(profile))
            if path == "/api/profiles/delete":
                pid = data["profile_id"]
                profiles = eng.load_channel_profiles()
                profiles["profiles"] = [p for p in profiles["profiles"]
                                        if p["profile_id"] != pid]
                eng.save_channel_profiles(profiles)
                shutil.rmtree(eng.data_file_path(f"profiles/{pid}"), ignore_errors=True)
                CLIENTS.pop(pid, None)
                if eng._ui.get("web_active_profile") == pid:
                    eng._ui.pop("web_active_profile", None)
                    eng.save_ui_settings()
                return self._json({"ok": True})
            if path == "/api/auth":
                profile = find_profile(data["profile_id"])
                if AUTH["running"]:
                    return self._json({"error": "already running"}, 409)
                AUTH.update(running=True, ok=None, error="", channel="",
                            profile_id=profile["profile_id"])
                start_auth(profile)
                return self._json({"ok": True})
            if path == "/api/profile/languages":
                codes = [str(c) for c in data.get("codes", []) if eng.valid_language_code(c)]
                profile = update_profile(
                    data["profile_id"], lambda p: p.__setitem__("languages", sorted(set(codes))))
                return self._json({"ok": True})
            if path == "/api/translate":
                return self._json({"ok": True, "job": start_translation(data)["id"]})
            if path == "/api/calendar":
                profile = find_profile(data["profile_id"])
                calendar = eng.load_calendar(profile)
                return self._json({"days": {
                    day: (calendar.get(day) or [""])[0]
                    for day in ("Monday", "Tuesday", "Wednesday", "Thursday",
                                "Friday", "Saturday", "Sunday")
                }})
            if path == "/api/calendar/save":
                profile = find_profile(data["profile_id"])
                days = data.get("days", {})
                clean = {}
                for day, time_text in days.items():
                    if day not in ("Monday", "Tuesday", "Wednesday", "Thursday",
                                   "Friday", "Saturday", "Sunday"):
                        continue
                    time_text = str(time_text).strip()
                    if time_text and re.fullmatch(r"\d{1,2}:\d{2}", time_text):
                        hour, minute = time_text.split(":")
                        clean[day] = [f"{int(hour):02d}:{minute}"]
                eng.save_json_file(profile["publ_calendar_file"], clean)
                return self._json({"ok": True})
            if path == "/api/preview":
                profile = active_profile()
                client = get_client(profile)
                ptype = data.get("type") or ("short" if data.get("want_short") else "long")
                if ptype not in ("long", "short", "live"):
                    ptype = "long"
                mode = "last_" + ("live" if ptype == "live" else ptype)
                cache_key = (profile["profile_id"], mode)
                cached = PREVIEW_CACHE.get(cache_key)
                if cached and time.time() - cached["ts"] < PREVIEW_TTL:
                    return self._json(cached["data"])
                videos, durations, shorts, lives = eng.get_channel_videos(client)
                sort_key = lambda x: x["snippet"]["publishedAt"]
                videos.sort(key=sort_key, reverse=True)
                lives.sort(key=sort_key, reverse=True)
                targets = eng._pick_translation_targets(videos, shorts, lives, mode)
                if not targets:
                    return self._json({"video_id": "", "title": "", "description": ""})
                metadata = eng.fetch_video_source_metadata(client, targets[0])
                result = {"video_id": targets[0], "title": metadata["title"],
                          "description": metadata["description"]}
                PREVIEW_CACHE[cache_key] = {"data": result, "ts": time.time()}
                return self._json(result)
            if path == "/api/job/cancel":
                for candidate in sorted(JOBS.values(), key=lambda j: j["id"], reverse=True):
                    if candidate["running"]:
                        candidate["cancel"] = True
                        return self._json({"ok": True})
                return self._json({"ok": False})
            if path == "/api/schedule":
                return self._json(schedule_video(data))
            if path == "/api/playlists/add":
                playlist_id = eng.parse_playlist_id(str(data.get("link", "")))
                if not playlist_id:
                    raise ValueError("bad playlist link")

                def _add(p):
                    client = get_client(p)
                    if not any(pl["id"] == playlist_id for pl in p.setdefault("playlists", [])):
                        title = eng.fetch_playlist_title(client, playlist_id)
                        p["playlists"].append(
                            {"id": playlist_id,
                             "name": str(data.get("name", "")).strip() or title or playlist_id})

                profile = update_profile(data["profile_id"], _add)
                return self._json(profile_brief(profile))
            if path == "/api/playlists/remove":
                def _remove(p):
                    p["playlists"] = [pl for pl in p.get("playlists", [])
                                      if pl["id"] != data["playlist_id"]]
                    ds = p.setdefault("default_playlists", [])
                    if data["playlist_id"] in ds:
                        ds.remove(data["playlist_id"])
                profile = update_profile(data["profile_id"], _remove)
                return self._json(profile_brief(profile))
            if path == "/api/playlists/default":
                def _default(p):
                    ds = p.setdefault("default_playlists", [])
                    pid = data["playlist_id"]
                    if data.get("value") and pid not in ds:
                        ds.append(pid)
                    elif not data.get("value") and pid in ds:
                        ds.remove(pid)
                profile = update_profile(data["profile_id"], _default)
                return self._json(profile_brief(profile))
            if path == "/api/playlists/video":
                profile = find_profile(data["profile_id"])
                client = get_client(profile)
                video_id = eng.extract_video_id(str(data.get("link", "")))
                if not video_id:
                    raise ValueError("bad video link")
                added = 0
                for pl_id in data.get("playlist_ids", []):
                    try:
                        eng.add_video_to_playlist(client, video_id, pl_id)
                        added += 1
                    except Exception:
                        pass
                return self._json({"ok": True, "added": added})
            if path == "/api/providers/save":
                reg = eng.load_provider_registry()
                entry = data["entry"]
                keep = set(data.get("keep", []))
                new_keys = [k for k in re.split(r"[,\s]+", str(data.get("new_keys", ""))) if k]
                if entry.get("id") in {p["id"] for p in reg["providers"]}:
                    for index, old in enumerate(reg["providers"]):
                        if old["id"] == entry["id"]:
                            if old.get("auth"):
                                merged = [k for k in old.get("api_keys", [])
                                          if _key_hash(k) in keep] + new_keys
                            else:
                                merged = []
                            old.update(entry)
                            old["api_keys"] = merged
                else:
                    entry["id"] = entry.get("id") or eng.profile_slug(
                        entry["name"], {p["id"] for p in reg["providers"]})
                    entry["api_keys"] = new_keys
                    reg["providers"].append(entry)
                    reg.setdefault("active", entry["id"])
                eng.save_provider_registry(reg)
                return self._json(reg_view(reg))
            if path == "/api/providers/activate":
                reg = eng.load_provider_registry()
                if data.get("backup"):
                    reg["backup"] = data["id"] if reg.get("active") != data["id"] else None
                else:
                    reg["active"] = data["id"]
                eng.save_provider_registry(reg)
                return self._json(reg_view(reg))
            if path == "/api/providers/delete":
                reg = eng.load_provider_registry()
                reg["providers"] = [p for p in reg["providers"] if p["id"] != data["id"]]
                if reg.get("active") == data["id"] and reg["providers"]:
                    reg["active"] = reg["providers"][0]["id"]
                if reg.get("backup") == data["id"]:
                    reg["backup"] = None
                eng.save_provider_registry(reg)
                return self._json(reg_view(reg))
            if path == "/api/providers/models":
                return self._json({"models": eng.fetch_local_models(data.get("base_url", ""))})
            if path == "/api/providers/check_keys":
                reg = eng.load_provider_registry()
                provider = next((p for p in reg["providers"] if p["id"] == data["provider_id"]), None)
                if provider is None:
                    raise ValueError("provider not found")
                keys = provider.get("api_keys", [])
                base = (provider.get("base_url") or "").rstrip("/")

                def test(key):
                    try:
                        if provider.get("kind") == "gemini":
                            response = requests.get(
                                "https://generativelanguage.googleapis.com/v1beta/models",
                                params={"key": key}, timeout=10)
                        else:
                            response = requests.get(f"{base}/models",
                                headers={"Authorization": f"Bearer {key}"}, timeout=10)
                        if response.status_code == 200:
                            return "ok", ""
                        if response.status_code == 429:
                            return "frozen", "HTTP 429"
                        return "dead", f"HTTP {response.status_code}"
                    except Exception as error:
                        return "dead", str(error)[:80]

                with ThreadPoolExecutor(max_workers=min(8, max(1, len(keys)))) as pool:
                    verdicts = list(pool.map(test, keys))
                status = _load_key_status()
                per_provider = status.setdefault(provider["id"], {})
                results = []
                for key, (state, detail) in zip(keys, verdicts):
                    per_provider[_key_hash(key)] = {
                        "status": state, "detail": detail, "checked": time.time()}
                    results.append({"masked": _mask_key(key), "hash": _key_hash(key),
                                    "status": state, "detail": detail})
                _save_key_status(status)
                return self._json({"keys": results})

            if path == "/api/providers/unfreeze":
                status = _load_key_status()
                per_provider = status.get(data["provider_id"], {})
                for entry in per_provider.values():
                    if entry.get("status") in ("frozen", "dead"):
                        entry["status"] = "ok"
                        entry["until"] = 0
                _save_key_status(status)
                return self._json(reg_view(eng.load_provider_registry()))

            if path == "/api/parallel":
                config = eng.load_local_llm_config()
                raw = data.get("value", "auto")
                config["max_parallel_languages"] = "auto" if raw == "auto" else int(raw)
                eng.save_json_file("local_llm.json", config)
                return self._json({"ok": True})
            if path == "/api/presets/save":
                name = str(data.get("name", "")).strip()
                if name:
                    presets = eng._ui.setdefault("language_presets", {})
                    presets[name] = sorted(set(eng.get_profile_languages(find_profile(data["profile_id"]))))
                    eng.save_ui_settings()
                return self._json({"ok": True})
            if path == "/api/presets/delete":
                eng._ui.setdefault("language_presets", {}).pop(data.get("name"), None)
                eng.save_ui_settings()
                return self._json({"ok": True})
            if path == "/api/presets/apply":
                codes = eng._ui.get("language_presets", {}).get(data.get("name"), [])
                if codes:
                    update_profile(data["profile_id"], lambda p: p.__setitem__("languages", sorted(codes)))
                return self._json({"ok": True})
            return self._json({"error": "not found"}, 404)
        except Exception as error:
            self._json({"error": str(error)}, 400)

    def _file(self, name):
        full = os.path.abspath(os.path.join(STATIC_DIR, name))
        if not full.startswith(os.path.abspath(STATIC_DIR)) or not os.path.isfile(full):
            return self._json({"error": "not found"}, 404)
        with open(full, "rb") as f:
            body = f.read()
        ext = os.path.splitext(full)[1]
        self._send(200, body, MIME.get(ext, "application/octet-stream"))

    # --- API parts that need several engine calls ---

    def api_bootstrap(self):
        profiles = [profile_brief(p) for p in eng.load_channel_profiles()["profiles"]]
        reg = eng.load_provider_registry()
        config = eng.load_local_llm_config()
        provider = reg.get("active")
        provider = next((p for p in reg["providers"] if p["id"] == provider), None)
        self._json({
            "ui": {k: eng._ui.get(k) for k in
                   ("language", "user_name", "ask_playlists", "ask_schedule",
                    "language_presets", "web_active_profile", "theme", "ui_tr_mode", "ui_tr_type",
                    "ui_tr_source", "ui_tr_parts", "ui_add_defaults", "ui_sched")},
            "profiles": profiles,
            "secrets_found": bool(eng.find_secrets_files()),
            "secrets_files": eng.find_secrets_files(),
            "providers": reg_view(reg),
            "provider_online": bool(provider and provider.get("auth")),
            "parallel": config.get("max_parallel_languages", "auto"),
            "catalog": eng.available_language_catalog(),
            "series": eng.load_series_names(),
        })

    def api_job(self):
        job = None
        for candidate in sorted(JOBS.values(), key=lambda j: j["id"], reverse=True):
            job = candidate
            break
        if job is None:
            return self._json({"running": False, "done": False, "langs": {}, "log": []})
        with _LOCK:
            snapshot = {k: (list(v) if isinstance(v, list) else dict(v) if isinstance(v, dict) else v)
                        for k, v in job.items()}
        self._json(snapshot)


def main():
    import sys
    import io
    # windowed-сборка или pythonw не имеют stdin: интерактивные вопросы движка
    # там невозможны (RuntimeError: lost sys.stdin) — настройки читаем молча,
    # недостающее спросит веб-интерфейс
    interactive = False
    try:
        interactive = bool(sys.stdin and sys.stdin.isatty())
    except Exception:
        pass
    try:
        if interactive:
            eng.restore_ui_settings()
        else:
            saved = eng.load_json_file(eng.UI_SETTINGS_FILE)
            if saved.get("ui_language") in eng.STRINGS:
                eng._ui["language"] = saved["ui_language"]
            if saved.get("user_name"):
                eng._ui["user_name"] = saved["user_name"]
            eng._ui["ask_playlists"] = bool(saved.get("ask_playlists", True))
            eng._ui["ask_schedule"] = bool(saved.get("ask_schedule", True))
    except Exception:
        pass
    # restore_ui_settings грузит только язык/имя/флаги; веб-ключи (пресеты,
    # тема и т.д.) иначе сбрасывались бы при каждом запуске сервера
    try:
        saved = eng.load_json_file(eng.UI_SETTINGS_FILE)
        for key in ("language_presets", "theme", "web_active_profile", "ui_tr_mode",
                    "ui_tr_type", "ui_tr_source", "ui_tr_parts", "ui_add_defaults",
                    "ui_sched", "ui_sched_date"):
            if saved.get(key) is not None:
                eng._ui[key] = saved[key]
    except (FileNotFoundError, ValueError):
        pass
    # под pythonw (запуск без консоли) stdout/stderr равны None
    if sys.stdout is None:
        sys.stdout = io.StringIO()
    if sys.stderr is None:
        sys.stderr = io.StringIO()
    sys_stdout = sys.stdout
    sys.stdout = _JobTee(sys_stdout)

    server = None
    for port in PORT_RANGE:
        try:
            server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
            break
        except OSError:
            continue
    if server is None:
        raise SystemExit("Все порты 8765–8789 заняты.")
    url = f"http://127.0.0.1:{server.server_address[1]}"
    print()
    print(f"🌐 Веб-интерфейс: {url}  (закрытие — Ctrl+C здесь или кнопка в меню)")
    fill_missing_logos()

    # pywebview, если установлен, показывает интерфейс в отдельном окне;
    # без него всё открывается в браузере как обычно.
    try:
        import webview  # type: ignore[import-not-found]  # опциональный пакет
    except ImportError:
        webview = None

    if webview is not None:
        threading.Thread(target=server.serve_forever, daemon=True).start()
        webview.create_window(
            "YouTube Metadata Translator", url,
            width=1280, height=840, min_size=(420, 560))
        try:
            webview.start()
        finally:
            os._exit(0)
    else:
        if not os.environ.get("YTMT_NO_BROWSER"):
            threading.Timer(0.6, webbrowser.open, (url,)).start()
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print()
            print("Пока!")


if __name__ == "__main__":
    main()
