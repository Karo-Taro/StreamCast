"""Bridge to the vendored youtube-metadata-translator engine.

The engine lives in vendor/youtube-metadata-translator (a plain copy of
https://github.com/ErrorGone-YT/youtube-metadata-translator, replaceable at
runtime from the admin panel). Only yt_metadata_translator.py is imported —
its webui/pywebview UI stays untouched.

Everything the engine persists goes to <STORAGE_DIR>/yt_translator_data/ (the
engine's DATA_DIR is redirected at import time, so a vendored-folder update
never wipes OAuth tokens, providers or presets).
"""
import json
import os
import re
import sys
import time

import config

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VENDOR_DIR = os.path.join(BASE_DIR, "vendor", "youtube-metadata-translator")
ENGINE_MODULE = "yt_metadata_translator"
GITHUB_REPO = "ErrorGone-YT/youtube-metadata-translator"
GITHUB_BRANCH = "main"
DATA_DIRNAME = "yt_translator_data"

engine = None
load_error = None


def data_dir():
    return os.path.join(config.STORAGE_DIR, DATA_DIRNAME)


def _load():
    global engine, load_error
    if engine is not None:
        return engine
    if load_error is not None:
        return None
    if not os.path.isfile(os.path.join(VENDOR_DIR, ENGINE_MODULE + ".py")):
        load_error = "Engine not vendored (vendor/youtube-metadata-translator is missing)"
        return None
    if VENDOR_DIR not in sys.path:
        sys.path.insert(0, VENDOR_DIR)
    try:
        import yt_metadata_translator as eng
    except Exception as e:  # ImportError or a dependency blow-up
        load_error = f"Engine import failed: {e}"
        return None
    os.makedirs(data_dir(), exist_ok=True)
    eng.DATA_DIR = data_dir()  # engine resolves data files at call time
    engine = eng
    return engine


def ready():
    """True when the engine can be used (vendored + deps importable)."""
    return _load() is not None


def status():
    """What the admin tile needs: readiness, connected channels, provider."""
    eng = _load()
    if eng is None:
        return {"ready": False, "error": load_error, "channel": None,
                "channels": [], "active_provider": None, "providers": []}
    channels = []
    try:
        profiles = eng.load_channel_profiles().get("profiles", [])
        channels = [{"id": p.get("channel_id"), "title": p.get("channel_title"),
                     "logo_url": p.get("logo_url", "")} for p in profiles]
    except Exception:
        pass
    try:
        reg = eng.load_provider_registry()
        active = next((p for p in reg["providers"] if p["id"] == reg.get("active")), None)
        providers = [{"id": p["id"], "name": p.get("name"), "kind": p.get("kind"),
                      "auth": p.get("auth"), "base_url": p.get("base_url"),
                      "model": p.get("model"),
                      "keys": len(p.get("api_keys", []))} for p in reg["providers"]]
    except Exception:
        active = None
        providers = []
    return {"ready": True, "error": None,
            "channel": channels[-1] if channels else None,  # active = last connected
            "channels": channels,
            "active_provider": active.get("name") if active else None,
            "providers": providers}


def has_secrets():
    return os.path.isfile(os.path.join(data_dir(), "client_secrets.json"))


def save_secrets(raw_bytes):
    """Store an uploaded OAuth client secrets file (Desktop-app JSON)."""
    eng = _load()
    if eng is None:
        raise RuntimeError(load_error)
    data = json.loads(raw_bytes.decode("utf-8-sig"))
    if "installed" not in data and "web" not in data:
        raise ValueError("Not an OAuth client secrets file (no 'installed'/'web' key)")
    path = os.path.join(data_dir(), "client_secrets.json")
    with open(path, "wb") as f:
        f.write(raw_bytes)
    return path


_EN_NAMES = {
    "af": "Afrikaans", "az": "Azerbaijani", "id": "Indonesian", "ms": "Malay",
    "bs": "Bosnian", "ca": "Catalan", "cs": "Czech", "cy": "Welsh", "da": "Danish",
    "de": "German", "et": "Estonian", "en": "English", "en-CA": "English (Canada)",
    "en-GB": "English (UK)", "en-IN": "English (India)", "en-US": "English (US)",
    "es": "Spanish", "es-419": "Spanish (Latin America)", "es-US": "Spanish (US)",
    "eu": "Basque", "fil": "Filipino", "fr": "French", "fr-CA": "French (Canada)",
    "gl": "Galician", "gu": "Gujarati", "hr": "Croatian", "is": "Icelandic",
    "it": "Italian", "jv": "Javanese", "kn": "Kannada", "la": "Latin",
    "lv": "Latvian", "lt": "Lithuanian", "hu": "Hungarian", "nl": "Dutch",
    "ne": "Nepali", "no": "Norwegian", "or": "Odia", "pa": "Punjabi",
    "pl": "Polish", "pt": "Portuguese (Brazil)", "pt-PT": "Portuguese (Portugal)",
    "ro": "Romanian", "rm": "Romansh", "si": "Sinhala", "sk": "Slovak",
    "sl": "Slovenian", "fi": "Finnish", "sv": "Swedish", "sw": "Swahili",
    "tl": "Tagalog", "ta": "Tamil", "te": "Telugu", "th": "Thai",
    "vi": "Vietnamese", "tr": "Turkish", "uk": "Ukrainian", "ur": "Urdu",
    "zh-Hans": "Chinese (Simplified)", "zh-Hant": "Chinese (Traditional)",
    "zh-TW": "Chinese (Taiwan)", "zu": "Zulu", "el": "Greek", "bg": "Bulgarian",
    "ru": "Russian", "sr": "Serbian", "mk": "Macedonian", "kk": "Kazakh",
    "ky": "Kyrgyz", "hy": "Armenian", "ka": "Georgian", "mn": "Mongolian",
    "my": "Burmese", "km": "Khmer", "lo": "Lao", "he": "Hebrew", "ar": "Arabic",
    "fa": "Persian", "sd": "Sindhi", "am": "Amharic", "yo": "Yoruba",
    "ha": "Hausa", "ig": "Igbo", "qu": "Quechua", "nso": "Sepedi",
    "bn": "Bengali", "hi": "Hindi", "ja": "Japanese", "ko": "Korean",
    "so": "Somali", "sq": "Albanian",
}


def language_catalog():
    """{code: English display name} — falls back to the engine's native name
    for codes not in the English map."""
    eng = _load()
    if eng is None:
        return dict(_EN_NAMES)
    try:
        native = eng.available_language_catalog()
    except Exception:
        native = {}
    return {code: _EN_NAMES.get(code, name) for code, name in native.items()}


def language_presets():
    """Named language presets saved in the translator's settings UI."""
    path = os.path.join(data_dir(), "ui_settings.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            return (json.load(f).get("language_presets") or {})
    except (OSError, ValueError):
        return {}


def save_preset(name, codes):
    """Create/update a named language preset in ui_settings.json."""
    if not name:
        raise ValueError("Preset name is required")
    path = os.path.join(data_dir(), "ui_settings.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        data = {}
    data.setdefault("language_presets", {})[name] = sorted(set(codes))
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def delete_preset(name):
    path = os.path.join(data_dir(), "ui_settings.json")
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (OSError, ValueError):
        return
    (data.get("language_presets") or {}).pop(name, None)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def parallelism():
    eng = _load()
    if eng is None:
        return {"value": "auto", "suggested": 1}
    cfg = eng.load_local_llm_config()
    return {"value": cfg.get("max_parallel_languages", "auto"),
            "suggested": eng.suggested_parallelism(cfg)}


def set_parallelism(value):
    eng = _load()
    if eng is None:
        raise RuntimeError(load_error)
    cfg = eng.load_local_llm_config()
    cfg["max_parallel_languages"] = "auto" if str(value) == "auto" else max(1, int(value))
    eng.save_json_file("local_llm.json", cfg)
    return cfg["max_parallel_languages"]


def provider_registry():
    eng = _load()
    return eng.load_provider_registry() if eng else {"active": None, "providers": []}


def provider_registry_view():
    """Registry with masked keys, safe to send to the browser."""
    reg = provider_registry()
    view = {"active": reg.get("active"), "backup": reg.get("backup"), "providers": []}
    for p in reg.get("providers", []):
        item = dict(p)
        item.pop("api_keys", None)
        item["key_count"] = len(p.get("api_keys", []))
        item["keys_masked"] = [_mask_key(k) for k in p.get("api_keys", [])]
        view["providers"].append(item)
    return view


def _mask_key(key):
    key = str(key)
    if len(key) <= 8:
        return key[:2] + "***"
    return key[:4] + "***" + key[-4:]


def save_provider_registry(reg):
    eng = _load()
    if eng is None:
        raise RuntimeError(load_error)
    eng.save_provider_registry(reg)


_provider_alerts = {}  # provider_id -> {"status", "detail", "seen"} raised by live jobs


def set_provider_alert(provider_id, status, detail):
    """Record a live problem seen during an actual translation (e.g. HTTP 402):
    a key can pass the models list and even a tiny probe while having no
    balance for a real workload."""
    _provider_alerts[provider_id] = {"status": status, "detail": str(detail)[:160],
                                     "seen": time.strftime("%Y-%m-%d %H:%M")}


def clear_provider_alert(provider_id):
    _provider_alerts.pop(provider_id, None)


def get_provider_alerts():
    return dict(_provider_alerts)


def check_provider_keys(provider_id):
    """Validate each API key of a provider (ok / frozen / dead / no balance).

    A GET /models probe alone passes for keys with no money left, so for
    OpenAI-compatible providers a 1-token completion is sent as well — it
    costs a fraction of a cent and catches HTTP 402."""
    import requests
    from concurrent.futures import ThreadPoolExecutor
    eng = _load()
    if eng is None:
        raise RuntimeError(load_error)
    reg = eng.load_provider_registry()
    provider = next((p for p in reg["providers"] if p["id"] == provider_id), None)
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
                if response.status_code == 200:
                    return "ok", ""
                if response.status_code == 429:
                    return "frozen", "HTTP 429"
                return "dead", f"HTTP {response.status_code}"
            response = requests.get(f"{base}/models",
                                    headers={"Authorization": f"Bearer {key}"}, timeout=10)
            if response.status_code != 200:
                if response.status_code == 429:
                    return "frozen", "HTTP 429"
                return "dead", f"HTTP {response.status_code}"
            # The key exists — now check it can actually run a completion
            # (catches accounts with no balance: HTTP 402).
            completion = requests.post(
                f"{base}/chat/completions",
                headers={"Authorization": f"Bearer {key}",
                         "Content-Type": "application/json"},
                json={"model": provider.get("model") or "gpt-4o-mini",
                      "max_tokens": 64,
                      "messages": [{"role": "user", "content": "hi"}]},
                timeout=20)
            if completion.status_code == 200:
                return "ok", ""
            if completion.status_code == 402:
                return "nobalance", "HTTP 402 — insufficient balance"
            if completion.status_code == 429:
                return "frozen", "HTTP 429"
            return "dead", f"HTTP {completion.status_code}"
        except Exception as error:
            return "dead", str(error)[:80]

    with ThreadPoolExecutor(max_workers=min(8, max(1, len(keys)))) as pool:
        verdicts = list(pool.map(test, keys))
    return [{"masked": _mask_key(k), "status": s, "detail": d}
            for k, (s, d) in zip(keys, verdicts)]


_yt_clients = {}  # channel_id -> authorized client (credentials refresh themselves)


def _authenticate_profile(profile):
    eng = _load()
    if eng is None:
        raise RuntimeError(load_error)
    return eng.authenticate(profile)


def _profile_for_channel(channel_id):
    eng = _load()
    if eng is None:
        return None
    profiles = eng.load_channel_profiles().get("profiles", [])
    if channel_id:
        match = next((p for p in profiles if p.get("channel_id") == channel_id), None)
        if match:
            return match
    return profiles[-1] if profiles else None  # fall back to the active one


def get_youtube_client(channel_id=None):
    """Authorized client for the channel owning the video when channel_id is
    given, otherwise for the active (last connected) channel. None when the
    channel isn't authorized."""
    cache_key = channel_id or "__active__"
    if cache_key in _yt_clients:
        return _yt_clients[cache_key]
    if _load() is None:
        return None
    profile = _profile_for_channel(channel_id)
    if profile is None:
        return None
    try:
        client = _authenticate_profile(profile)
        _yt_clients[cache_key] = client
        return client
    except Exception:
        return None


def fetch_video_meta(video_id):
    """Current title/description of a video (for the 'from video' source)."""
    eng = _load()
    youtube = get_youtube_client()
    if youtube is None:
        raise RuntimeError("YouTube channel is not connected")
    meta = eng.fetch_video_source_metadata(youtube, video_id)
    if meta is None:
        raise ValueError("Video not found")
    return meta


def video_lookup(video_id):
    """Lightweight snippet lookup (title / channel / description) for the
    stream-name autofill. Works for live broadcasts and regular videos."""
    youtube = get_youtube_client()
    if youtube is None:
        raise RuntimeError("YouTube channel is not connected")
    response = youtube.videos().list(part="snippet", id=video_id).execute()
    if not response.get("items"):
        raise ValueError("Video not found")
    snippet = response["items"][0]["snippet"]
    return {"title": snippet.get("title", ""),
            "channel_title": snippet.get("channelTitle", ""),
            "channel_id": snippet.get("channelId", ""),
            "description": snippet.get("description", "")}


def fetch_video_meta(video_id):
    """Current title/description of a video (for the 'from video' source).
    Resolves the video's owning channel automatically."""
    meta = video_lookup(video_id)
    return {"title": meta["title"], "description": meta["description"]}


def update_video_localizations(video_id, source_title, source_description,
                               source_language, localizations):
    """Write localized title/description back to the YouTube video. The client
    is picked by the video's owning channel, so translations land on the right
    channel even when several are connected."""
    eng = _load()
    if eng is None:
        raise RuntimeError(load_error)
    channel_id = ""
    try:
        # One extra 1-unit videos.list to learn the owner; if it fails we let
        # the fallback channel try and surface the real API error instead.
        response = get_youtube_client().videos().list(part="snippet", id=video_id).execute()
        if response.get("items"):
            channel_id = response["items"][0]["snippet"].get("channelId", "")
    except Exception:
        pass
    youtube = get_youtube_client(channel_id or None)
    if youtube is None:
        raise RuntimeError("YouTube channel is not connected")
    merged = dict(localizations)
    if source_language:
        merged[source_language] = {"title": source_title,
                                   "description": source_description}
    return eng.update_video_metadata(youtube, video_id,
                                     source_title, source_description, merged)


def run_translation(source_title, source_description, languages, parts,
                    progress=None):
    """Blocking translation — run from a background thread.

    Unlike the engine's all-or-nothing localize_metadata_via_llm(), this keeps
    every language that completed and returns partial failures instead of
    raising. parts: 'all' | 'title' | 'description'.
    Returns {"localizations": {lang: {title, description}}, "errors": [str]}."""
    eng = _load()
    if eng is None:
        raise RuntimeError(load_error)
    import time as _time
    from concurrent.futures import ThreadPoolExecutor, as_completed

    cfg = eng.load_local_llm_config()
    provider = eng.get_active_provider()
    if provider is None:
        raise RuntimeError("No translation provider configured.")
    names = cfg.get("language_names", {})
    # 'en' is the assumed source language: pass the source text through.
    localizations = {"en": {"title": source_title, "description": source_description}} \
        if "en" in languages else {}
    queued = [c for c in dict.fromkeys(languages) if c and c != "en"]
    errors = []

    if queued:
        workers = min(len(queued), eng.resolve_parallelism(cfg))

        def one(idx, code):
            # Stagger starts so all threads don't slam the model at once.
            _time.sleep(idx * 1.5)
            return eng.localize_language_via_llm(
                provider, cfg, code, names.get(code, code),
                source_title, source_description, progress=progress)

        with ThreadPoolExecutor(max_workers=workers) as pool:
            futures = {pool.submit(one, i, c): c for i, c in enumerate(queued)}
            for future in as_completed(futures):
                code = futures[future]
                try:
                    localizations[code] = future.result()
                except Exception as error:
                    errors.append(f"{code}: {str(error).splitlines()[0]}")

    if parts == "title":
        for texts in localizations.values():
            texts["description"] = source_description
    elif parts == "description":
        for texts in localizations.values():
            texts["title"] = source_title

    return {"localizations": localizations, "errors": errors}


def _vendored_marker():
    """Version marker of the vendored copy, if recorded."""
    try:
        with open(os.path.join(data_dir(), "vendored_version.json"),
                  encoding="utf-8") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def vendored_version():
    marker = _vendored_marker()
    if marker:
        return marker
    return {"sha": None, "date": None}


def latest_version(timeout=10):
    """Latest commit (sha short + date) of the translator's main branch."""
    import requests
    response = requests.get(
        f"https://api.github.com/repos/{GITHUB_REPO}/commits/{GITHUB_BRANCH}",
        timeout=timeout,
        headers={"Accept": "application/vnd.github+json"})
    response.raise_for_status()
    data = response.json()
    return {"sha": data["sha"][:7],
            "date": data["commit"]["committer"]["date"]}


def update_vendor(progress=None):
    """Replace the vendored folder with the latest main-branch zip. Runtime
    data is untouched (it lives in storage/yt_translator_data)."""
    global engine, load_error
    import io
    import shutil
    import tempfile
    import zipfile
    import requests

    def note(msg):
        if progress:
            progress(msg)

    url = f"https://codeload.github.com/{GITHUB_REPO}/zip/refs/heads/{GITHUB_BRANCH}"
    note(f"Downloading {url}")
    response = requests.get(url, timeout=120)
    response.raise_for_status()
    info = latest_version()

    note("Extracting")
    with tempfile.TemporaryDirectory() as tmp:
        with zipfile.ZipFile(io.BytesIO(response.content)) as zf:
            zf.extractall(tmp)
        extracted = next(
            os.path.join(tmp, name) for name in os.listdir(tmp)
            if name.startswith(GITHUB_REPO.split("/")[1] + "-"))
        parent = os.path.dirname(VENDOR_DIR)
        os.makedirs(parent, exist_ok=True)
        staging = os.path.join(parent, ".vendor-staging")
        shutil.rmtree(staging, ignore_errors=True)
        shutil.copytree(extracted, staging)
        shutil.rmtree(VENDOR_DIR, ignore_errors=True)
        os.replace(staging, VENDOR_DIR)

    with open(os.path.join(data_dir(), "vendored_version.json"), "w",
              encoding="utf-8") as f:
        json.dump(info, f)
    note(f"Updated to {info['sha']}")
    return info
