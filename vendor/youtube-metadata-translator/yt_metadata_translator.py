"""YouTube Metadata Translator — cross-platform CLI client.

Restructuring branch: new localized UI (en/uk/ru) with first-run onboarding.
The translation engine (LLM providers, YouTube operations) is fully present
but the menu items that use it are enabled in later phases.
"""

import os
import json
import re
import sys
import time
import html
import pickle
import random
import shutil
import threading
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timedelta

import google_auth_oauthlib.flow
import googleapiclient.discovery
import google.auth.transport.requests
from googleapiclient.errors import HttpError
import isodate
import requests


BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")

SCOPES = ["https://www.googleapis.com/auth/youtube.force-ssl"]
DEFAULT_CLIENT_SECRETS_FILE = "client_secrets.json"
UI_SETTINGS_FILE = "ui_settings.json"
CHANNEL_PROFILES_FILE = "channel_profiles.json"
METADATA_FILE = "metadata.json"
LOCALIZATIONS_FILE = "localizations.json"
DEFAULT_PUBLISH_TIME = "10:00"
GEMINI_API_FILE = "gemini_api.json"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash"
DEFAULT_OLLAMA_BASE_URL = "https://ollama.com/v1"
DEFAULT_OLLAMA_MODEL = "gemma4:31b"
OLLAMA_API_FILE = "ollama_api.json"
DEFAULT_CODECRAFT_BASE_URL = "https://codecraftapi.com/v1"
DEFAULT_CODECRAFT_MODEL = "deepseek-v4-flash-0731"
CODECRAFT_API_FILE = "codecraft_api.json"
SERIES_NAMES_FILE = "series_names.json"
ALLOWED_DAYS = ["Monday", "Wednesday", "Friday", "Sunday"]

GITHUB_BASE = "https://github.com/ErrorGone-YT/youtube-metadata-translator"
# READMEs live on the working branch until merged; switch to "main" after the merge.
REPO_BRANCH = "main"
GUIDE_LINKS = {
    "en": f"{GITHUB_BASE}/blob/{REPO_BRANCH}/README.md",
    "uk": f"{GITHUB_BASE}/blob/{REPO_BRANCH}/README.uk.md",
    "ru": f"{GITHUB_BASE}/blob/{REPO_BRANCH}/README.ru.md",
}
GOOGLE_CONSOLE_LINK = "https://console.cloud.google.com/apis/credentials"

# ---------------------------------------------------------------------------
# Localized interface strings
# ---------------------------------------------------------------------------

STRINGS = {
    "en": {
        "lang_select_title": "Choose the interface language / Виберіть мову інтерфейсу / Выберите язык интерфейса:",
        "ask_name": "How should I address you?",
        "menu_greeting": "Welcome, {name}! What are we doing?",
        "menu_translation": "Translation",
        "menu_playlist": "Add to playlist",
        "menu_schedule": "Scheduled publishing",
        "menu_settings": "Settings",
        "menu_switch_profile": "Switch profile",
        "pl_menu_title": "What do we add to a playlist?",
        "pl_last_title": "Adding the latest video",
        "pl_specific_title": "Adding specific videos",
        "pl_all_title": "Adding all videos",
        "pl_target_title": "Which playlist do we add to?",
        "pl_target_default": "The default ones (★)",
        "pl_target_pick": "Pick from the list (multiple allowed)",
        "pl_none_selected": "Nothing selected.",
        "source_choice_prompt": "Where do the title and description come from?\n1) From the video\n2) Enter manually\n> ",
        "source_title_prompt": "New title (Enter — keep the video's one): ",
        "source_desc_prompt": "Paste a new description? (2 — open the editor, Enter — keep the video's one): ",
        "parts_prompt": "What do we translate?\n1) Everything\n2) Titles only\n3) Descriptions only\n> ",
        "engine_ok": "✅ {code}: title {t}, description {d}",
        "engine_failed": "❌ {code}: {error}",
        "engine_retry": "⏳ Retry {code} ({attempt}/{attempts}), waiting {wait}s: {message}",
        "no_auth_hint": "❗ YouTube authorization didn't complete — restart the script and sign in.",
        "translating": "🌐 Translating into {n} languages...",
        "localization_failed": "⚠️ Translation was not saved:",
        "last_video": "🎬 Latest video: {id} — {title}",
        "no_videos": "No videos available on the channel.",
        "metadata_fetched": "Title: {title} ({n} characters of description)",
        "translate_actual": "Translate the video's actual title/description",
        "tr_menu_title": "What do we translate?",
        "tr_last_title": "Translating the latest video",
        "tr_specific_title": "Specific videos — paste links one by one",
        "tr_all_title": "Translating all videos",
        "tr_longs": "Longs",
        "tr_shorts": "Shorts",
        "tr_last": "Latest video",
        "tr_long": "Long",
        "tr_short": "Short",
        "tr_specific": "Specific videos",
        "tr_all": "All videos",
        "tr_no_matches": "No matching videos found.",
        "tr_batch_confirm": "Found {n} videos. Translate them all? (yes/no): ",
        "tr_done": "✅ Done: {n} video(s) processed.",
        "apply_local": "Apply the local translation (metadata.json + localizations.json)",
        "localizations_missing": "❗ No saved translation yet — run a translation first (item 1).",
        "video_updated": "✅ Video {id} updated.",
        "add_to_defaults_q": "Add the video to the default playlists? (yes/no): ",
        "added_to_playlists": "✅ Added to {n} playlist(s).",
        "schedule_q": "Schedule deferred publishing? (yes/no): ",
        "schedule_done": "✅ {id} goes live {date} UTC (local {time})",
        "playlist_add_title": "▶️ Adding to the default playlists",
        "defaults_missing": "❗ No default playlists selected — set them in Settings → Playlists.",
        "video_link_prompt": "Video link or ID (0 — finish): ",
        "bad_video_link": "❌ Couldn't extract a video ID.",
        "more_videos": "Add more? (yes/no): ",
        "schedule_flow_title": "⏰ Deferred publishing — paste a video link",
        "schedule_date_prompt": "📅 Publishing date (ddmmyy): ",
        "schedule_bad_date": "❌ Invalid date.",
        "schedule_days_only": "❌ Publishing is allowed only on: {days}",
        "quota_exceeded": "⚠️ The YouTube API daily quota is exhausted. Try again tomorrow.",
        "menu_exit": "Exit",
        "menu_choice": "Your choice: ",
        "coming_soon": "🚧 This feature is being polished and will appear soon.",
        "press_enter": "Press Enter to continue...",
        "invalid_choice": "❌ Invalid choice.",
        "setup_not_finished": (
            "⚡ Setup is not finished yet, so only Settings is available.\n"
            "   Open Settings: choose translation languages and add a translator API key."
        ),
        "secrets_missing_title": "❗ No client_secrets file found — the script can't reach YouTube yet.",
        "secrets_missing_steps": (
            "Short version:\n"
            "1) Open Google Cloud Console and create a project.\n"
            "2) Enable YouTube Data API v3 for it.\n"
            "3) Configure the OAuth consent screen and add your email to Test users.\n"
            "4) Create an OAuth client ID of type 'Desktop app' and download the JSON."
        ),
        "secrets_link_guide": "📖 Full step-by-step guide: {url}",
        "secrets_link_console": "🔑 Create the keys here: {url}",
        "secrets_retry": "Save the file as client_secrets.json into the data/ folder and press Enter (or type 0 to skip for now): ",
        "auth_opening_browser": "🌐 A browser window will open — sign in to the Google account of the channel.",
        "auth_success": "✅ Authorization successful: {channel}",
        "auth_failed": "❌ Authorization failed: {error}",
        "profile_wizard_title": "— Creating a channel profile —",
        "profile_name_prompt": "Profile name (anything you like): ",
        "profile_name_empty": "The name cannot be empty.",
        "profile_secrets_auto": "🔑 Secrets file found: {file}",
        "profile_secrets_pick": "Which secrets file is yours?",
        "profile_playlist_prompt": "Playlist ID to add videos to (Enter to skip): ",
        "profile_created": "✅ Profile '{name}' created.",
        "profile_pick_title": "Your channel profiles:",
        "profile_pick_add": "N) Add a channel",
        "profile_pick_prompt": "Profile number: ",
        "settings_title": "⚙️ Settings — {channel}",
        "settings_title_no_channel": "⚙️ Settings",
        "set_language": "Interface language",
        "set_name": "How to address you",
        "settings_interface": "Interface",
        "settings_translations": "Translations",
        "settings_playlists": "Playlists",
        "playlists_title": "▶️ Playlists — {channel}",
        "playlist_current": "Current playlist ID: {id}",
        "playlist_none": "No playlist set — videos are not added to any playlist.",
        "playlist_edit": "Add a playlist",
        "playlists_defaults_item": "Default playlists",
        "playlists_remove_item": "Remove a playlist",
        "playlists_defaults_title": "Default playlists — new videos go here:",
        "playlists_defaults_hint": "Numbers separated by comma or space — toggle, Enter — done",
        "defaults_star_note": "★ = default playlist: new videos are added to these automatically.",
        "defaults_saved": "✅ Saved. New videos will be added to the selected playlists.",
        "defaults_empty_note": "⚠️ No defaults selected: adding to playlists will be skipped.",
        "playlists_add_prompt": "Playlist link or ID: ",
        "playlist_bad_link": "❌ Couldn't extract a playlist ID from that.",
        "playlist_fetched_name": "Name from YouTube: {name}",
        "playlist_name_prompt": "Playlist name (Enter — keep as is): ",
        "playlist_name_fallback": "Playlist name (Enter — use the ID): ",
        "playlist_exists": "This playlist is already in the list.",
        "playlist_added": "✅ Playlist added.",
        "remove_prompt": "Playlist number: ",
        "removed": "✅ Removed.",
        "playlist_prompt": "Playlist ID (the part after list= in the link; '-' — clear): ",
        "playlist_saved": "✅ Saved.",
        "schedule_title": "⏰ Scheduled publishing — {channel}",
        "schedule_note": "Videos go live on these weekdays at the local times below.",
        "schedule_time_prompt": "New local time (HH:MM, Enter — keep): ",
        "schedule_bad_time": "❌ Doesn't look like a HH:MM time.",
        "schedule_saved": "✅ {day}: {time}",
        "set_languages": "Translation languages",
        "set_parallel": "Number of parallel translations",
        "setup_no_languages": "No translation languages selected — Settings → Translations → Translation languages.",
        "setup_no_provider": "No translation provider with API keys — Settings → Translations → API providers.",
        "setup_fix_now": "Fix it now? (yes/no): ",
        "api_title": "API providers",
        "api_add_item": "Add a new provider",
        "api_edit_item": "Edit provider settings",
        "api_delete_item": "Delete a provider",
        "api_add_title": "— Adding a new provider —",
        "api_cancel_hint": "(type 0 at any step to cancel)",
        "api_kind_prompt": "Provider type:\n1) Local\n2) Online\n> ",
        "api_local": "Local",
        "api_online": "Online",
        "api_name_prompt": "Provider display name: ",
        "api_base_prompt": "Base URL (Enter — {default}): ",
        "api_keys_prompt": "API keys, comma-separated (Enter — skip): ",
        "api_model_prompt": "Model name: ",
        "parts_menu_title": "What do we translate?",
        "parts_all": "Everything",
        "parts_titles": "Titles only",
        "parts_descs": "Descriptions only",
        "source_menu_title": "Where do the title and description come from?",
        "source_from_video": "From the video",
        "source_manual": "Enter manually",
        "source_desc_editor": "Open the editor and paste a description",
        "source_desc_keep": "Keep the video's description",
        "set_ask_playlists": "Ask about adding to playlists after translation",
        "set_ask_schedule": "Ask about deferred publishing after translation",
        "api_local_presets": "Local servers:",
        "api_preset_lmstudio": "LM Studio",
        "api_preset_ollama": "Ollama",
        "api_preset_custom": "Custom (enter the base URL manually)",
        "api_models_found": "Available models:",
        "api_models_pick": "Pick a model (number, Enter — {default}): ",
        "api_added": "✅ Provider '{name}' added.",
        "api_make_active": "Make it the active provider? (yes/no): ",
        "api_pick": "Provider number: ",
        "api_edit_title": "— Editing provider: {name} —",
        "api_edit_name": "Name",
        "api_edit_base": "Base URL",
        "api_edit_model": "Model",
        "api_edit_addkeys": "Add API keys",
        "api_edit_delkey": "Remove a key",
        "api_edit_active": "Make active",
        "api_backup_item": "Make the backup provider",
        "api_backup_set": "✅ '{name}' is now the backup provider.",
        "api_backup_cleared": "Backup provider cleared.",
        "api_backup_same": "This provider is already the active one.",
        "api_legend": "● active · ○ backup",
        "api_keys_current": "Current keys ({n}):",
        "api_no_keys": "No keys yet.",
        "api_deleted": "✅ Provider deleted.",
        "api_canceled": "Canceled.",
        "api_need_url": "❌ A base URL is required for an online provider.",
        "api_enter_new": "New value (Enter — keep): ",
        "api_added_keys": "✅ {n} key(s) added.",
        "api_now_active": "✅ '{name}' is now the active provider.",
        "api_delete_confirm": "Delete provider '{name}'? (yes/no): ",
        "api_keys_count": "{n} keys",
        "back": "Back",
        "name_saved": "✅ Got it, {name}!",
        "languages_screen_title": "🌍 Translation languages — {channel}",
        "languages_selected": "Selected ({n}): {list}",
        "languages_none": "No languages selected: the translation item will have nothing to do.",
        "languages_menu": "1) Toggle languages from the list\n2) Add a language by code (e.g. pt-BR)\n3) Clear selection\n0) Back",
        "languages_list_title": "Languages (x = selected):",
        "languages_toggle_hint": "Numbers separated by comma or space — toggle, A — select all, N — clear all, 0 — done",
        "languages_toggle_prompt": "Selection: ",
        "languages_keys_hint": "↑/↓ move · Space toggle · A/Ф select all · N/Т clear all · Enter done",
        "languages_didnt_understand": "❌ Didn't understand the selection.",
        "languages_add_prompt": "Language code (es, pt-BR, zh-Hans): ",
        "languages_bad_code": "❌ Doesn't look like a language code.",
        "languages_already": "This language is already selected.",
        "languages_clear_confirm": "Unselect all languages? (yes/no): ",
        "parallel_current": "🧵 Parallel translations now: {n}",
        "parallel_keys_found": "Found {n} API keys — that's how many translations can run at once.",
        "parallel_local_note": "For a local LM Studio more than 2 parallel translations rarely helps.",
        "parallel_prompt": "New value (Enter to keep {n}, auto = one per key): ",
        "parallel_saved_auto": "✅ Auto mode: one translation per API key ({n} now).",
        "parallel_not_positive": "❌ Enter a positive number.",
        "parallel_over_warning": "⚠️ More than {n} won't speed things up: extra threads will just wait in line.",
        "parallel_over_confirm": "Set anyway? (yes/no): ",
        "parallel_saved": "✅ Saved: {n} parallel translations.",
    },
    "uk": {
        "lang_select_title": "Choose the interface language / Виберіть мову інтерфейсу / Выберите язык интерфейса:",
        "ask_name": "Як до вас звертатися?",
        "menu_greeting": "Вітаю, {name}! Що робитимемо?",
        "menu_translation": "Переклад",
        "menu_playlist": "Додати до плейлиста",
        "menu_schedule": "Відкладена публікація",
        "menu_settings": "Налаштування",
        "menu_switch_profile": "Змінити профіль",
        "pl_menu_title": "Що додаємо до плейлиста?",
        "pl_last_title": "Додаємо останнє відео",
        "pl_specific_title": "Додаємо конкретні відео",
        "pl_all_title": "Додаємо всі відео",
        "pl_target_title": "До якого плейлиста додати?",
        "pl_target_default": "Задані за замовчуванням (★)",
        "pl_target_pick": "Вибрати зі списку (можна кілька)",
        "pl_none_selected": "Нічого не вибрано.",
        "source_choice_prompt": "Звідки взяти назву та опис?\n1) З відео\n2) Вписати самому\n> ",
        "source_title_prompt": "Нова назва (Enter — залишити з відео): ",
        "source_desc_prompt": "Вставити новий опис? (2 — відкрити редактор, Enter — залишити з відео): ",
        "parts_prompt": "Що перекладаємо?\n1) Усе\n2) Тільки назви\n3) Тільки описи\n> ",
        "engine_ok": "✅ {code}: назва {t}, опис {d}",
        "engine_failed": "❌ {code}: {error}",
        "engine_retry": "⏳ Повтор {code} ({attempt}/{attempts}) за {wait}с: {message}",
        "no_auth_hint": "❗ Авторизація YouTube не завершена — перезапусти скрипт і увійди в акаунт.",
        "translating": "🌐 Перекладаю {n} мовами...",
        "localization_failed": "⚠️ Переклад не збережено:",
        "last_video": "🎬 Останнє відео: {id} — {title}",
        "no_videos": "На каналі немає доступних відео.",
        "metadata_fetched": "Назва: {title} ({n} символів опису)",
        "translate_actual": "Перекласти актуальні дані з відео",
        "tr_menu_title": "Що перекладаємо?",
        "tr_last_title": "Перекладаємо останнє відео",
        "tr_specific_title": "Конкретні відео — вставляй посилання по одному",
        "tr_all_title": "Перекладаємо всі відео",
        "tr_longs": "Лонги",
        "tr_shorts": "Шортси",
        "tr_last": "Останнє відео",
        "tr_long": "Лонг",
        "tr_short": "Шортс",
        "tr_specific": "Конкретні відео",
        "tr_all": "Усі відео",
        "tr_no_matches": "Підходящих відео не знайдено.",
        "tr_batch_confirm": "Знайдено {n} відео. Перекласти всі? (так/ні): ",
        "tr_done": "✅ Готово: оброблено {n} відео.",
        "apply_local": "Застосувати локальний переклад (metadata.json + localizations.json)",
        "localizations_missing": "❗ Збереженого перекладу ще немає — спочатку зроби переклад (пункт 1).",
        "video_updated": "✅ Відео {id} оновлено.",
        "add_to_defaults_q": "Додати відео до плейлистів за замовчуванням? (так/ні): ",
        "added_to_playlists": "✅ Додано до плейлистів: {n}",
        "schedule_q": "Відкладена публікація? (так/ні): ",
        "schedule_done": "✅ {id} вийде {date} UTC (локально {time})",
        "playlist_add_title": "▶️ Додавання до плейлистів за замовчуванням",
        "defaults_missing": "❗ Плейлисти за замовчуванням не вибрані — задай їх у Налаштування → Плейлисти.",
        "video_link_prompt": "Посилання на відео або ID (0 — завершити): ",
        "bad_video_link": "❌ Не вдалося витягти ID відео.",
        "more_videos": "Додати ще? (так/ні): ",
        "schedule_flow_title": "⏰ Відкладена публікація — встав посилання на відео",
        "schedule_date_prompt": "📅 Дата публікації (ddmmyy): ",
        "schedule_bad_date": "❌ Некоректна дата.",
        "schedule_days_only": "❌ Публікація лише в: {days}",
        "quota_exceeded": "⚠️ Денна квота YouTube API вичерпана. Спробуй завтра.",
        "menu_exit": "Вихід",
        "menu_choice": "Ваш вибір: ",
        "coming_soon": "🚧 Ця функція на підході — з'явиться незабаром.",
        "press_enter": "Натисніть Enter, щоб продовжити...",
        "invalid_choice": "❌ Некоректний вибір.",
        "setup_not_finished": (
            "⚡ Налаштування ще не завершено, тому доступні лише Налаштування.\n"
            "   Відкрийте їх: виберіть мови перекладу та додайте API-ключ перекладача."
        ),
        "secrets_missing_title": "❗ Не знайдено файл client_secrets — скрипт поки не має доступу до YouTube.",
        "secrets_missing_steps": (
            "Коротко:\n"
            "1) Відкрийте Google Cloud Console і створіть проєкт.\n"
            "2) Увімкніть для нього YouTube Data API v3.\n"
            "3) Налаштуйте екран згоди OAuth і додайте свою пошту до Test users.\n"
            "4) Створіть OAuth client ID типу 'Desktop app' і завантажте JSON."
        ),
        "secrets_link_guide": "📖 Повна покрокова інструкція: {url}",
        "secrets_link_console": "🔑 Створити ключі тут: {url}",
        "secrets_retry": "Збережіть файл як client_secrets.json у папку data/ і натисніть Enter (або 0 — щоб пропустити поки що): ",
        "auth_opening_browser": "🌐 Відкриється вікно браузера — увійдіть у Google-акаунт каналу.",
        "auth_success": "✅ Авторизація успішна: {channel}",
        "auth_failed": "❌ Помилка авторизації: {error}",
        "profile_wizard_title": "— Створення профілю каналу —",
        "profile_name_prompt": "Назва профілю (яка завгодно): ",
        "profile_name_empty": "Назва не може бути порожньою.",
        "profile_secrets_auto": "🔑 Знайдено файл ключів: {file}",
        "profile_secrets_pick": "Котрий з файлів ключів ваш?",
        "profile_playlist_prompt": "ID плейлиста для додавання відео (Enter — пропустити): ",
        "profile_created": "✅ Профіль '{name}' створено.",
        "profile_pick_title": "Ваші профілі каналів:",
        "profile_pick_add": "N) Додати канал",
        "profile_pick_prompt": "Номер профілю: ",
        "settings_title": "⚙️ Налаштування — {channel}",
        "settings_title_no_channel": "⚙️ Налаштування",
        "set_language": "Мова інтерфейсу",
        "set_name": "Як до вас звертатися",
        "settings_interface": "Інтерфейс",
        "settings_translations": "Переклади",
        "settings_playlists": "Плейлисти",
        "playlists_title": "▶️ Плейлисти — {channel}",
        "playlist_current": "Поточний ID плейлиста: {id}",
        "playlist_none": "Плейлист не задано — відео нікуди не додаються.",
        "playlist_edit": "Додати плейлист",
        "playlists_defaults_item": "Плейлисти за замовчуванням",
        "playlists_remove_item": "Видалити плейлист",
        "playlists_defaults_title": "Плейлисти за замовчуванням — нові відео попадатимуть сюди:",
        "playlists_defaults_hint": "Номери через кому або пробіл — перемкнути, Enter — готово",
        "defaults_star_note": "★ = плейлист за замовчуванням: нові відео додаються туди автоматично.",
        "defaults_saved": "✅ Збережено. Нові відео додаватимуться у вибрані плейлисти.",
        "defaults_empty_note": "⚠️ Не вибрано жодного: додавання до плейлистів пропускатиметься.",
        "playlists_add_prompt": "Посилання на плейлист або ID: ",
        "playlist_bad_link": "❌ Не вдалося витягти ID плейлиста.",
        "playlist_fetched_name": "Назва з YouTube: {name}",
        "playlist_name_prompt": "Назва плейлиста (Enter — залишити): ",
        "playlist_name_fallback": "Назва плейлиста (Enter — використати ID): ",
        "playlist_exists": "Цей плейлист уже у списку.",
        "playlist_added": "✅ Плейлист додано.",
        "remove_prompt": "Номер плейлиста: ",
        "removed": "✅ Видалено.",
        "playlist_prompt": "ID плейлиста (частина після list= у посиланні; '-' — прибрати): ",
        "playlist_saved": "✅ Збережено.",
        "schedule_title": "⏰ Відкладена публікація — {channel}",
        "schedule_note": "Відео виходять у ці дні тижня о вказаний локальний час.",
        "schedule_time_prompt": "Новий локальний час (HH:MM, Enter — залишити): ",
        "schedule_bad_time": "❌ Не схоже на час HH:MM.",
        "schedule_saved": "✅ {day}: {time}",
        "set_languages": "Мови перекладу",
        "set_parallel": "Кількість одночасних перекладів",
        "setup_no_languages": "Не вибрано мов перекладу — Налаштування → Переклади → Мови перекладу.",
        "setup_no_provider": "Немає провайдера перекладача з ключами — Налаштування → Переклади → API-провайдери.",
        "setup_fix_now": "Виправити зараз? (так/ні): ",
        "api_title": "API-провайдери",
        "api_add_item": "Додати нового провайдера",
        "api_edit_item": "Змінити налаштування провайдера",
        "api_delete_item": "Видалити провайдера",
        "api_add_title": "— Додавання нового провайдера —",
        "api_cancel_hint": "(0 на будь-якому кроці — скасувати)",
        "api_kind_prompt": "Тип провайдера:\n1) Локальний\n2) Онлайн\n> ",
        "api_local": "Локальний",
        "api_online": "Онлайн",
        "api_name_prompt": "Ім'я провайдера для показу: ",
        "api_base_prompt": "Base URL (Enter — {default}): ",
        "api_keys_prompt": "API-ключі через кому (Enter — пропустити): ",
        "api_model_prompt": "Назва моделі: ",
        "parts_menu_title": "Що перекладаємо?",
        "parts_all": "Усе",
        "parts_titles": "Тільки назви",
        "parts_descs": "Тільки описи",
        "source_menu_title": "Звідки взяти назву та опис?",
        "source_from_video": "З відео",
        "source_manual": "Вписати самому",
        "source_desc_editor": "Відкрити редактор і вставити опис",
        "source_desc_keep": "Залишити опис з відео",
        "set_ask_playlists": "Питати про додавання до плейлистів після перекладу",
        "set_ask_schedule": "Питати про відкладену публікацію після перекладу",
        "api_local_presets": "Локальні сервери:",
        "api_preset_lmstudio": "LM Studio",
        "api_preset_ollama": "Ollama",
        "api_preset_custom": "Свій варіант (ввести base URL вручну)",
        "api_models_found": "Доступні моделі:",
        "api_models_pick": "Вибери модель (номер, Enter — {default}): ",
        "api_added": "✅ Провайдера '{name}' додано.",
        "api_make_active": "Зробити його активним? (так/ні): ",
        "api_pick": "Номер провайдера: ",
        "api_edit_title": "— Зміна провайдера: {name} —",
        "api_edit_name": "Ім'я",
        "api_edit_base": "Base URL",
        "api_edit_model": "Модель",
        "api_edit_addkeys": "Додати API-ключі",
        "api_edit_delkey": "Видалити ключ",
        "api_edit_active": "Зробити активним",
        "api_backup_item": "Зробити резервним провайдером",
        "api_backup_set": "✅ '{name}' тепер резервний провайдер.",
        "api_backup_cleared": "Резервного провайдера скинуто.",
        "api_backup_same": "Цей провайдер уже активний.",
        "api_legend": "● активний · ○ резервний",
        "api_keys_current": "Поточні ключі ({n}):",
        "api_no_keys": "Ключів ще немає.",
        "api_deleted": "✅ Провайдера видалено.",
        "api_canceled": "Скасовано.",
        "api_need_url": "❌ Для онлайн-провайдера потрібен base URL.",
        "api_enter_new": "Нове значення (Enter — залишити): ",
        "api_added_keys": "✅ Додано ключів: {n}.",
        "api_now_active": "✅ '{name}' тепер активний провайдер.",
        "api_delete_confirm": "Видалити провайдера '{name}'? (так/ні): ",
        "api_keys_count": "ключів: {n}",
        "back": "Назад",
        "name_saved": "✅ Домовилися, {name}!",
        "languages_screen_title": "🌍 Мови перекладу — {channel}",
        "languages_selected": "Вибрано ({n}): {list}",
        "languages_none": "Мови не вибрано: пункту перекладу буде нічого робити.",
        "languages_menu": "1) Позначити мови у списку\n2) Додати мову за кодом (наприклад pt-BR)\n3) Очистити вибір\n0) Назад",
        "languages_list_title": "Мови (x = вибрано):",
        "languages_toggle_hint": "Номери через кому або пробіл — перемкнути, A — вибрати всі, N — зняти всі, 0 — готово",
        "languages_toggle_prompt": "Вибір: ",
        "languages_keys_hint": "↑/↓ рух · Пробіл — вибрати/зняти · A/Ф — вибрати всі · N/Т — зняти всі · Enter — готово",
        "languages_didnt_understand": "❌ Не зрозумів вибір.",
        "languages_add_prompt": "Код мови (es, pt-BR, zh-Hans): ",
        "languages_bad_code": "❌ Не схоже на мовний код.",
        "languages_already": "Ця мова вже вибрана.",
        "languages_clear_confirm": "Зняти всі мови? (так/ні): ",
        "parallel_current": "🧵 Одночасних перекладів зараз: {n}",
        "parallel_keys_found": "Знайдено {n} API-ключів — стільки перекладів можна вести одночасно.",
        "parallel_local_note": "Для локального LM Studio більше 2 одночасних перекладів рідко допомагає.",
        "parallel_prompt": "Нове значення (Enter — залишити {n}, auto = за кількістю ключів): ",
        "parallel_saved_auto": "✅ Авто-режим: один переклад на кожен ключ (зараз {n}).",
        "parallel_not_positive": "❌ Введіть додатне число.",
        "parallel_over_warning": "⚠️ Більше ніж {n} не прискорить: зайві потоки просто чекатимуть черги.",
        "parallel_over_confirm": "Усе одно встановити? (так/ні): ",
        "parallel_saved": "✅ Збережено: {n} одночасних перекладів.",
    },
    "ru": {
        "lang_select_title": "Choose the interface language / Виберіть мову інтерфейсу / Выберите язык интерфейса:",
        "ask_name": "Как к вам обращаться?",
        "menu_greeting": "Приветствую, {name}! Что будем делать?",
        "menu_translation": "Перевод",
        "menu_playlist": "Добавить в плейлист",
        "menu_schedule": "Отложенная публикация",
        "menu_settings": "Настройки",
        "menu_switch_profile": "Сменить профиль",
        "pl_menu_title": "Что добавляем в плейлист?",
        "pl_last_title": "Добавляем последнее видео",
        "pl_specific_title": "Добавляем конкретные видео",
        "pl_all_title": "Добавляем все видео",
        "pl_target_title": "В какой плейлист добавить?",
        "pl_target_default": "Заданные по умолчанию (★)",
        "pl_target_pick": "Выбрать из списка (можно несколько)",
        "pl_none_selected": "Ничего не выбрано.",
        "source_choice_prompt": "Откуда взять название и описание?\n1) Из видео\n2) Вписать самому\n> ",
        "source_title_prompt": "Новое название (Enter — оставить с видео): ",
        "source_desc_prompt": "Вставить новое описание? (2 — открыть редактор, Enter — оставить с видео): ",
        "parts_prompt": "Что переводим?\n1) Всё\n2) Только названия\n3) Только описания\n> ",
        "engine_ok": "✅ {code}: название {t}, описание {d}",
        "engine_failed": "❌ {code}: {error}",
        "engine_retry": "⏳ Повтор {code} ({attempt}/{attempts}) через {wait}с: {message}",
        "no_auth_hint": "❗ Авторизация YouTube не завершена — перезапусти скрипт и войди в аккаунт.",
        "translating": "🌐 Перевожу на {n} языков...",
        "localization_failed": "⚠️ Перевод не сохранён:",
        "last_video": "🎬 Последнее видео: {id} — {title}",
        "no_videos": "На канале нет доступных видео.",
        "metadata_fetched": "Название: {title} ({n} символов описания)",
        "translate_actual": "Перевести актуальные данные с видео",
        "tr_menu_title": "Что переводим?",
        "tr_last_title": "Переводим последнее видео",
        "tr_specific_title": "Конкретные видео — вставляй ссылки по одной",
        "tr_all_title": "Переводим все видео",
        "tr_longs": "Лонги",
        "tr_shorts": "Шортсы",
        "tr_last": "Последнее видео",
        "tr_long": "Лонг",
        "tr_short": "Шортс",
        "tr_specific": "Конкретные видео",
        "tr_all": "Все видео",
        "tr_no_matches": "Подходящих видео не найдено.",
        "tr_batch_confirm": "Найдено {n} видео. Переводим все? (да/нет): ",
        "tr_done": "✅ Готово: обработано {n} видео.",
        "apply_local": "Применить локальный перевод (metadata.json + localizations.json)",
        "localizations_missing": "❗ Сохранённого перевода ещё нет — сначала сделай перевод (пункт 1).",
        "video_updated": "✅ Видео {id} обновлено.",
        "add_to_defaults_q": "Добавить видео в плейлисты по умолчанию? (да/нет): ",
        "added_to_playlists": "✅ Добавлено в плейлистов: {n}",
        "schedule_q": "Отложенная публикация? (да/нет): ",
        "schedule_done": "✅ {id} выйдет {date} UTC (локально {time})",
        "playlist_add_title": "▶️ Добавление в плейлисты по умолчанию",
        "defaults_missing": "❗ Плейлисты по умолчанию не выбраны — задай их в Настройки → Плейлисты.",
        "video_link_prompt": "Ссылка на видео или ID (0 — закончить): ",
        "bad_video_link": "❌ Не удалось извлечь ID видео.",
        "more_videos": "Добавить ещё? (да/нет): ",
        "schedule_flow_title": "⏰ Отложенная публикация — вставь ссылку на видео",
        "schedule_date_prompt": "📅 Дата публикации (ddmmyy): ",
        "schedule_bad_date": "❌ Некорректная дата.",
        "schedule_days_only": "❌ Публикация только в: {days}",
        "quota_exceeded": "⚠️ Дневная квота YouTube API исчерпана. Попробуй завтра.",
        "menu_exit": "Выход",
        "menu_choice": "Ваш выбор: ",
        "coming_soon": "🚧 Эта функция в разработке и появится скоро.",
        "press_enter": "Нажмите Enter, чтобы продолжить...",
        "invalid_choice": "❌ Некорректный выбор.",
        "setup_not_finished": (
            "⚡ Настройка ещё не завершена, поэтому доступен только пункт Настройки.\n"
            "   Откройте его: выберите языки перевода и добавьте API-ключ переводчика."
        ),
        "secrets_missing_title": "❗ Не найден файл client_secrets — скрипт пока не имеет доступа к YouTube.",
        "secrets_missing_steps": (
            "Коротко:\n"
            "1) Открой Google Cloud Console и создай проект.\n"
            "2) Включи для него YouTube Data API v3.\n"
            "3) Настрой экран согласования OAuth и добавь свою почту в Test users.\n"
            "4) Создай OAuth client ID типа 'Desktop app' и скачай JSON."
        ),
        "secrets_link_guide": "📖 Полная пошаговая инструкция: {url}",
        "secrets_link_console": "🔑 Создать ключи здесь: {url}",
        "secrets_retry": "Сохрани файл как client_secrets.json в папку data/ и нажми Enter (или 0 — чтобы пропустить пока): ",
        "auth_opening_browser": "🌐 Откроется окно браузера — войди в Google-аккаунт канала.",
        "auth_success": "✅ Авторизация успешна: {channel}",
        "auth_failed": "❌ Ошибка авторизации: {error}",
        "profile_wizard_title": "— Создание профиля канала —",
        "profile_name_prompt": "Название профиля (какое угодно): ",
        "profile_name_empty": "Название не может быть пустым.",
        "profile_secrets_auto": "🔑 Найден файл ключей: {file}",
        "profile_secrets_pick": "Который из файлов ключей твой?",
        "profile_playlist_prompt": "ID плейлиста для добавления видео (Enter — пропустить): ",
        "profile_created": "✅ Профиль '{name}' создан.",
        "profile_pick_title": "Твои профили каналов:",
        "profile_pick_add": "N) Добавить канал",
        "profile_pick_prompt": "Номер профиля: ",
        "settings_title": "⚙️ Настройки — {channel}",
        "settings_title_no_channel": "⚙️ Настройки",
        "set_language": "Язык интерфейса",
        "set_name": "Как к тебе обращаться",
        "settings_interface": "Интерфейс",
        "settings_translations": "Переводы",
        "settings_playlists": "Плейлисты",
        "playlists_title": "▶️ Плейлисты — {channel}",
        "playlist_current": "Текущий ID плейлиста: {id}",
        "playlist_none": "Плейлист не задан — видео никуда не добавляются.",
        "playlist_edit": "Добавить плейлист",
        "playlists_defaults_item": "Плейлисты по умолчанию",
        "playlists_remove_item": "Удалить плейлист",
        "playlists_defaults_title": "Плейлисты по умолчанию — новые видео будут попадать сюда:",
        "playlists_defaults_hint": "Номера через запятую или пробел — переключить, Enter — готово",
        "defaults_star_note": "★ = плейлист по умолчанию: новые видео добавляются туда автоматически.",
        "defaults_saved": "✅ Сохранено. Новые видео будут добавляться в выбранные плейлисты.",
        "defaults_empty_note": "⚠️ Не выбрано ни одного: добавление в плейлисты будет пропускаться.",
        "playlists_add_prompt": "Ссылка на плейлист или ID: ",
        "playlist_bad_link": "❌ Не удалось извлечь ID плейлиста.",
        "playlist_fetched_name": "Название с YouTube: {name}",
        "playlist_name_prompt": "Название плейлиста (Enter — оставить): ",
        "playlist_name_fallback": "Название плейлиста (Enter — использовать ID): ",
        "playlist_exists": "Этот плейлист уже в списке.",
        "playlist_added": "✅ Плейлист добавлен.",
        "remove_prompt": "Номер плейлиста: ",
        "removed": "✅ Удалено.",
        "playlist_prompt": "ID плейлиста (часть после list= в ссылке; '-' — убрать): ",
        "playlist_saved": "✅ Сохранено.",
        "schedule_title": "⏰ Отложенная публикация — {channel}",
        "schedule_note": "Видео выходят в эти дни недели в указанное локальное время.",
        "schedule_time_prompt": "Новое локальное время (HH:MM, Enter — оставить): ",
        "schedule_bad_time": "❌ Не похоже на время HH:MM.",
        "schedule_saved": "✅ {day}: {time}",
        "set_languages": "Языки перевода",
        "set_parallel": "Количество одновременных переводов",
        "setup_no_languages": "Не выбраны языки перевода — Настройки → Переводы → Языки перевода.",
        "setup_no_provider": "Нет провайдера перевода с ключами — Настройки → Переводы → API-провайдеры.",
        "setup_fix_now": "Исправить сейчас? (да/нет): ",
        "api_title": "API-провайдеры",
        "api_add_item": "Добавить нового провайдера",
        "api_edit_item": "Изменить настройки провайдера",
        "api_delete_item": "Удалить провайдера",
        "api_add_title": "— Добавление нового провайдера —",
        "api_cancel_hint": "(0 на любом шаге — отмена)",
        "api_kind_prompt": "Тип провайдера:\n1) Локальный\n2) Онлайн\n> ",
        "api_local": "Локальный",
        "api_online": "Онлайн",
        "api_name_prompt": "Отображаемое имя провайдера: ",
        "api_base_prompt": "Base URL (Enter — {default}): ",
        "api_keys_prompt": "API-ключи через запятую (Enter — пропустить): ",
        "api_model_prompt": "Название модели: ",
        "parts_menu_title": "Что переводим?",
        "parts_all": "Всё",
        "parts_titles": "Только названия",
        "parts_descs": "Только описания",
        "source_menu_title": "Откуда взять название и описание?",
        "source_from_video": "Из видео",
        "source_manual": "Вписать самому",
        "source_desc_editor": "Открыть редактор и вставить описание",
        "source_desc_keep": "Оставить описание с видео",
        "set_ask_playlists": "Спрашивать про добавление в плейлисты после перевода",
        "set_ask_schedule": "Спрашивать про отложенную публикацию после перевода",
        "api_local_presets": "Локальные серверы:",
        "api_preset_lmstudio": "LM Studio",
        "api_preset_ollama": "Ollama",
        "api_preset_custom": "Свой вариант (ввести base URL вручную)",
        "api_models_found": "Доступные модели:",
        "api_models_pick": "Выбери модель (номер, Enter — {default}): ",
        "api_added": "✅ Провайдер '{name}' добавлен.",
        "api_make_active": "Сделать его активным? (да/нет): ",
        "api_pick": "Номер провайдера: ",
        "api_edit_title": "— Изменение провайдера: {name} —",
        "api_edit_name": "Имя",
        "api_edit_base": "Base URL",
        "api_edit_model": "Модель",
        "api_edit_addkeys": "Добавить API-ключи",
        "api_edit_delkey": "Удалить ключ",
        "api_edit_active": "Сделать активным",
        "api_backup_item": "Сделать резервным провайдером",
        "api_backup_set": "✅ '{name}' теперь резервный провайдер.",
        "api_backup_cleared": "Резервный провайдер сброшен.",
        "api_backup_same": "Этот провайдер уже активный.",
        "api_legend": "● активный · ○ резервный",
        "api_keys_current": "Текущие ключи ({n}):",
        "api_no_keys": "Ключей ещё нет.",
        "api_deleted": "✅ Провайдер удалён.",
        "api_canceled": "Отменено.",
        "api_need_url": "❌ Для онлайн-провайдера нужен base URL.",
        "api_enter_new": "Новое значение (Enter — оставить): ",
        "api_added_keys": "✅ Добавлено ключей: {n}.",
        "api_now_active": "✅ '{name}' теперь активный провайдер.",
        "api_delete_confirm": "Удалить провайдера '{name}'? (да/нет): ",
        "api_keys_count": "ключей: {n}",
        "back": "Назад",
        "name_saved": "✅ Договорились, {name}!",
        "languages_screen_title": "🌍 Языки перевода — {channel}",
        "languages_selected": "Выбрано ({n}): {list}",
        "languages_none": "Языки не выбраны: пункту перевода будет нечего делать.",
        "languages_menu": "1) Отметить языки в списке\n2) Добавить язык по коду (например pt-BR)\n3) Очистить выбор\n0) Назад",
        "languages_list_title": "Языки (x = выбрано):",
        "languages_toggle_hint": "Номера через запятую или пробел — переключить, A — выбрать все, N — снять все, 0 — готово",
        "languages_toggle_prompt": "Выбор: ",
        "languages_keys_hint": "↑/↓ движение · Пробел — выбрать/снять · A/Ф — выбрать все · N/Т — снять все · Enter — готово",
        "languages_didnt_understand": "❌ Не понял выбор.",
        "languages_add_prompt": "Код языка (es, pt-BR, zh-Hans): ",
        "languages_bad_code": "❌ Не похоже на языковой код.",
        "languages_already": "Этот язык уже выбран.",
        "languages_clear_confirm": "Снять все языки? (да/нет): ",
        "parallel_current": "🧵 Одновременных переводов сейчас: {n}",
        "parallel_keys_found": "Найдено {n} API-ключей — столько переводов можно вести одновременно.",
        "parallel_local_note": "Для локального LM Studio больше 2 одновременных переводов редко даёт выигрыш.",
        "parallel_prompt": "Новое значение (Enter — оставить {n}, auto = по числу ключей): ",
        "parallel_saved_auto": "✅ Авто-режим: один перевод на каждый ключ (сейчас {n}).",
        "parallel_not_positive": "❌ Введи положительное число.",
        "parallel_over_warning": "⚠️ Больше {n} не ускорит: лишние потоки просто будут ждать очереди.",
        "parallel_over_confirm": "Всё равно установить? (да/нет): ",
        "parallel_saved": "✅ Сохранено: {n} одновременных переводов.",
    },
}

_ui = {"language": None, "user_name": "", "ask_playlists": True, "ask_schedule": True}


def t(key, **kwargs):
    """Localized string with graceful fallback to English."""
    text = STRINGS.get(_ui["language"], STRINGS["en"]).get(key) or STRINGS["en"].get(key)
    if text is None:
        return key
    return text.format(**kwargs) if kwargs else text


def confirm(prompt):
    """Yes in all three interface languages."""
    return input(prompt).strip().lower() in ("y", "yes", "1", "д", "да", "т", "так")


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------


def data_file_path(filename):
    """Resolve a profile file under data/ and reject paths outside that folder."""
    full_path = os.path.abspath(os.path.join(DATA_DIR, filename))
    data_path = os.path.abspath(DATA_DIR)
    if os.path.commonpath([full_path, data_path]) != data_path:
        raise ValueError(f"Profile file must be inside {DATA_DIR}: {filename}")
    return full_path


def clear_console():
    os.system("cls" if os.name == "nt" else "clear")


def load_json_file(filename):
    with open(os.path.join(DATA_DIR, filename), "r", encoding="utf-8") as f:
        return json.load(f)


def save_json_file(filename, data):
    full_path = os.path.join(DATA_DIR, filename)
    os.makedirs(os.path.dirname(full_path), exist_ok=True)
    with open(full_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def load_ui_settings():
    if not _ui["language"]:
        choose_ui_language()
    if not _ui["user_name"]:
        ask_user_name()
    save_ui_settings()


def save_ui_settings():
    data = dict(_ui)
    data["ui_language"] = data.pop("language")
    save_json_file(UI_SETTINGS_FILE, data)


def toggle_ask_flag(flag):
    _ui[flag] = not _ui.get(flag, True)
    save_ui_settings()


def restore_ui_settings():
    """Load saved language/name before anything is printed; returns True if onboarding is needed."""
    try:
        saved = load_json_file(UI_SETTINGS_FILE)
        if saved.get("ui_language") in STRINGS:
            _ui["language"] = saved["ui_language"]
        _ui["user_name"] = str(saved.get("user_name", "")).strip()
        _ui["ask_playlists"] = bool(saved.get("ask_playlists", True))
        _ui["ask_schedule"] = bool(saved.get("ask_schedule", True))
    except (FileNotFoundError, ValueError):
        pass
    needs_onboarding = False
    if not _ui["language"]:
        choose_ui_language()
        needs_onboarding = True
    if not _ui["user_name"]:
        ask_user_name()
        needs_onboarding = True
    if needs_onboarding:
        save_ui_settings()
    return needs_onboarding


def choose_ui_language():
    """Ask for the interface language; shown before any other localized text."""
    while True:
        print(t("lang_select_title"))
        print("1) English\n2) Українська\n3) Русский")
        choice = input("> ").strip()
        if choice == "1":
            _ui["language"] = "en"
        elif choice == "2":
            _ui["language"] = "uk"
        elif choice == "3":
            _ui["language"] = "ru"
        else:
            continue
        clear_console()
        return _ui["language"]


def ask_user_name():
    while True:
        name = input(t("ask_name") + " ").strip()
        if name:
            _ui["user_name"] = name
            clear_console()
            print(t("name_saved").format(name=name))
            return name


# ---------------------------------------------------------------------------
# Google authorization and YouTube operations (engine — menu wiring comes later)
# ---------------------------------------------------------------------------


def authenticate(profile):
    full_token_path = data_file_path(profile["token_file"])
    full_secrets_path = data_file_path(profile["client_secrets_file"])

    credentials = None
    if os.path.exists(full_token_path):
        with open(full_token_path, "rb") as token:
            credentials = pickle.load(token)
    if not credentials or not credentials.valid:
        if credentials and credentials.expired and credentials.refresh_token:
            credentials.refresh(google.auth.transport.requests.Request())
        else:
            if not os.path.exists(full_secrets_path):
                raise FileNotFoundError(f"Client secrets file not found: {full_secrets_path}")
            flow = google_auth_oauthlib.flow.InstalledAppFlow.from_client_secrets_file(
                full_secrets_path, SCOPES)
            credentials = flow.run_local_server(port=0)
        os.makedirs(os.path.dirname(full_token_path), exist_ok=True)
        with open(full_token_path, "wb") as token:
            pickle.dump(credentials, token)
    return googleapiclient.discovery.build("youtube", "v3", credentials=credentials)


def refresh_profile_identity(youtube, profile, profiles):
    response = youtube.channels().list(part="id,snippet", mine=True).execute()
    if not response.get("items"):
        raise RuntimeError("The authorized Google account has no YouTube channel.")
    channel = response["items"][0]
    profile["channel_id"] = channel["id"]
    profile["channel_title"] = channel["snippet"]["title"]
    profile["logo_url"] = (channel["snippet"].get("thumbnails", {}).get("medium", {})
                           or channel["snippet"].get("thumbnails", {}).get("default", {})
                           or {}).get("url", "")
    save_channel_profiles(profiles)
    add_series_name(channel["snippet"]["title"])


def set_publishAt(youtube, video_id, publish_datetime):
    try:
        # One call: privacyStatus=private + publishAt together, 50 quota units.
        youtube.videos().update(
            part="status",
            body={
                "id": video_id,
                "status": {
                    "privacyStatus": "private",
                    "publishAt": publish_datetime.isoformat("T") + "Z",
                },
            },
        ).execute()
        print(f"✅ {video_id}: {publish_datetime.strftime('%Y-%m-%d %H:%M UTC')}")
        return True
    except Exception as e:
        print(f"set_publishAt error: {e}")
        return False


def calendar_publish_time(publ_calendar, day_name):
    times = publ_calendar.get(day_name) or []
    return times[0] if times else DEFAULT_PUBLISH_TIME


def local_to_utc(publish_datetime):
    """Shift naive local wall-clock time to naive UTC using the current DST-aware offset."""
    return publish_datetime - datetime.now().astimezone().utcoffset()


def to_publish_datetime(publish_date, publ_calendar):
    publish_time = calendar_publish_time(publ_calendar, publish_date.strftime("%A"))
    publish_datetime = datetime.strptime(
        f"{publish_date.strftime('%Y-%m-%d')} {publish_time}", "%Y-%m-%d %H:%M"
    )
    return local_to_utc(publish_datetime), publish_time


def translate_day(day_name):
    """Localized weekday name for display; comparison always uses English names."""
    days = {
        "en": ["Monday", "Wednesday", "Friday", "Sunday"],
        "uk": ["Понеділок", "Середа", "П'ятниця", "Неділя"],
        "ru": ["Понедельник", "Среда", "Пятница", "Воскресенье"],
    }
    names = days.get(_ui["language"], days["en"])
    return dict(zip(ALLOWED_DAYS, names)).get(day_name, day_name)


def next_allowed_date(start_date, days_ahead, allowed_days):
    current_date = start_date + timedelta(days=days_ahead)
    while current_date.strftime("%A") not in allowed_days:
        current_date += timedelta(days=1)
    return current_date


def ask_publish_date(publ_calendar):
    """Prompt for a ddmmyy date on an allowed weekday; returns (utc datetime, local time)."""
    while True:
        user_date = input(t("schedule_date_prompt")).strip()
        try:
            publish_date = datetime.strptime(user_date, "%d%m%y")
        except ValueError:
            print(t("schedule_bad_date"))
            continue
        if publish_date.strftime("%A") not in ALLOWED_DAYS:
            print(t("schedule_days_only").format(
                days=", ".join(translate_day(d) for d in ALLOWED_DAYS)))
            continue
        return to_publish_datetime(publish_date, publ_calendar)


def _is_short_video(video, duration):
    """Shorts = up to 3 minutes AND a vertical thumbnail (YouTube's own rule
    since 2024-10: Shorts may be 180s long; a horizontal clip is never one)."""
    if not 0 < duration <= 180:
        return False
    thumbs = video["snippet"].get("thumbnails", {})
    for key in ("maxres", "standard", "high", "medium"):
        thumb = thumbs.get(key) or {}
        width, height = thumb.get("width"), thumb.get("height")
        if width and height:
            return height > width
    return False


def get_channel_videos(youtube):
    """Uploads playlist entries for normal (non-live) videos, with their
    durations and the set of video ids that are Shorts."""
    videos = []
    next_page_token = None
    response = youtube.channels().list(part="contentDetails", mine=True).execute()
    uploads_playlist_id = response["items"][0]["contentDetails"]["relatedPlaylists"]["uploads"]

    while True:
        playlist_response = youtube.playlistItems().list(
            part="snippet",
            playlistId=uploads_playlist_id,
            maxResults=50,
            pageToken=next_page_token,
        ).execute()
        videos.extend(playlist_response["items"])
        next_page_token = playlist_response.get("nextPageToken")
        if not next_page_token:
            break

    filtered = []
    live_items = []
    durations = {}
    shorts = set()
    live_ids = set()
    video_ids = [item["snippet"]["resourceId"]["videoId"] for item in videos]
    found_ids = set()
    # videos().list accepts up to 50 ids per call; batching saves a lot of quota.
    for start in range(0, len(video_ids), 50):
        batch = video_ids[start:start + 50]
        details = youtube.videos().list(
            part="snippet,contentDetails", id=",".join(batch)
        ).execute()
        for video in details.get("items", []):
            found_ids.add(video["id"])
            durations[video["id"]] = isodate.parse_duration(
                video["contentDetails"]["duration"]
            ).total_seconds()
            if _is_short_video(video, durations[video["id"]]):
                shorts.add(video["id"])
            if video["snippet"].get("liveBroadcastContent", "none") in ("live", "upcoming"):
                live_ids.add(video["id"])
    for item in videos:
        video_id = item["snippet"]["resourceId"]["videoId"]
        if video_id not in found_ids:
            continue
        # live/upcoming — активные трансляции и запланированные премьеры
        if video_id in live_ids:
            live_items.append(item)
        else:
            filtered.append(item)
    return filtered, durations, shorts, live_items


def update_video_metadata(youtube, video_id, title, description, localizations):
    response = youtube.videos().list(part="snippet,localizations", id=video_id).execute()
    if not response["items"]:
        print(f"Video {video_id} not found")
        return False

    video = response["items"][0]
    body = {
        "id": video_id,
        "snippet": {
            "title": title[:100],
            "description": description[:5000],
            "tags": video["snippet"].get("tags", []),
            "categoryId": video["snippet"]["categoryId"],
            "defaultLanguage": "en",
        },
    }

    merged_localizations = video.get("localizations", {}).copy()
    if localizations:
        for lang_code, texts in localizations.items():
            merged_localizations[lang_code] = {
                "title": texts["title"][:100],
                "description": texts["description"][:5000],
            }
        body["localizations"] = merged_localizations

    youtube.videos().update(part="snippet,localizations", body=body).execute()
    return True


def add_video_to_playlist(youtube, video_id, playlist_id):
    if not playlist_id:
        return
    existing = youtube.playlistItems().list(
        part="snippet", playlistId=playlist_id, videoId=video_id, maxResults=1
    ).execute()
    if existing.get("items"):
        return
    youtube.playlistItems().insert(
        part="snippet",
        body={
            "snippet": {
                "playlistId": playlist_id,
                "resourceId": {"kind": "youtube#video", "videoId": video_id},
            }
        },
    ).execute()


def extract_video_id(url):
    patterns = [
        r"(?:v=|\/)([0-9A-Za-z_-]{11})",
        r"youtu\.be\/([0-9A-Za-z_-]{11})",
        r"embed\/([0-9A-Za-z_-]{11})",
    ]
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group(1)
    return None


def normalize_description(text):
    """Decode copied HTML and keep paragraph breaks as normal newline characters."""
    text = html.unescape(text)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"\n[ \t]+\n", "\n\n", text)
    return text.strip()


def get_description_from_dialog():
    """Open a multiline field so a browser description can be pasted as-is."""
    try:
        import tkinter
        from tkinter import messagebox, scrolledtext

        root = tkinter.Tk()
        root.title("Description")
        root.geometry("760x700")
        root.minsize(760, 700)

        tkinter.Label(
            root,
            text="Paste the full description below (Ctrl+V), then press Continue.",
            anchor="w", padx=12, pady=10,
        ).pack(fill="x")
        field = scrolledtext.ScrolledText(root, wrap="word", font=("Segoe UI", 11))
        field.pack(fill="both", expand=True, padx=12, pady=(0, 10))

        result = {"text": None}

        def paste_from_clipboard(event=None):
            try:
                text = root.clipboard_get()
            except tkinter.TclError:
                messagebox.showerror("Clipboard", "Could not read the clipboard.", parent=root)
                return "break"
            field.insert("insert", text)
            field.focus_set()
            return "break"

        def confirm():
            result["text"] = field.get("1.0", "end-1c")
            root.destroy()

        buttons = tkinter.Frame(root)
        buttons.pack(fill="x", padx=12, pady=(0, 12))
        tkinter.Button(buttons, text="Continue", command=confirm).pack(side="right")
        tkinter.Button(buttons, text="Paste", command=paste_from_clipboard).pack(side="left")
        root.protocol("WM_DELETE_WINDOW", root.destroy)
        field.bind("<Control-v>", paste_from_clipboard)
        field.bind("<Control-V>", paste_from_clipboard)
        field.focus_set()
        root.mainloop()

        if result["text"] is None:
            raise RuntimeError("Description entry was cancelled.")
        return result["text"]
    except Exception as error:
        raise RuntimeError(f"Could not enter the description: {error}") from error


# ---------------------------------------------------------------------------
# LLM translation engine (all providers)
# ---------------------------------------------------------------------------


def load_local_llm_config():
    try:
        return load_json_file("local_llm.json")
    except FileNotFoundError:
        return {"temperature": 0.25, "max_tokens": 2400, "timeout_seconds": 180}


def load_gemini_api_keys():
    if not os.path.exists(data_file_path(GEMINI_API_FILE)):
        raise FileNotFoundError(
            f'No data/{GEMINI_API_FILE}. Create it: {{"GEMINI_API_KEY": "key1, key2"}}'
        )
    raw = load_json_file(GEMINI_API_FILE).get("GEMINI_API_KEY", "")
    keys = [key.strip() for key in re.split(r"[,\s]+", str(raw)) if key.strip()]
    if not keys:
        raise ValueError(f"{GEMINI_API_FILE} has no GEMINI_API_KEY.")
    return keys


def load_ollama_api_keys():
    if not os.path.exists(data_file_path(OLLAMA_API_FILE)):
        raise FileNotFoundError(
            f'No data/{OLLAMA_API_FILE}. Create it: {{"OLLAMA_API_KEY": "key1, key2"}}'
        )
    raw = load_json_file(OLLAMA_API_FILE).get("OLLAMA_API_KEY", "")
    keys = [key.strip() for key in re.split(r"[,\s]+", str(raw)) if key.strip()]
    if not keys:
        raise ValueError(f"{OLLAMA_API_FILE} has no OLLAMA_API_KEY.")
    return keys


def load_codecraft_api_keys():
    if not os.path.exists(data_file_path(CODECRAFT_API_FILE)):
        raise FileNotFoundError(
            f'No data/{CODECRAFT_API_FILE}. Create it: {{"CODECRAFT_API_KEY": "cc_key1, cc_key2"}}'
        )
    raw = load_json_file(CODECRAFT_API_FILE).get("CODECRAFT_API_KEY", "")
    keys = [key.strip() for key in re.split(r"[,\s]+", str(raw)) if key.strip()]
    if not keys:
        raise ValueError(f"{CODECRAFT_API_FILE} has no CODECRAFT_API_KEY.")
    return keys


def resolve_llm_provider(config):
    """Explicit 'provider' wins; otherwise detect by which key file exists."""
    provider = str(config.get("provider", "")).lower()
    if provider in ("gemini", "lmstudio", "ollama", "codecraft"):
        return provider
    for provider_name, key_file in (
        ("codecraft", CODECRAFT_API_FILE),
        ("ollama", OLLAMA_API_FILE),
        ("gemini", GEMINI_API_FILE),
    ):
        try:
            if os.path.exists(data_file_path(key_file)):
                return provider_name
        except ValueError:
            pass
    return "lmstudio"


# ---------------------------------------------------------------------------
# API provider registry
# ---------------------------------------------------------------------------

PROVIDERS_FILE = "api_providers.json"

_openai_lock = threading.Lock()
_openai_offsets = {}


def _legacy_provider_entries():
    """Seed the registry from the legacy key files and local_llm.json."""
    llm = load_local_llm_config()
    providers = []
    try:
        providers.append({
            "id": "codecraft", "name": "CodeCraft", "kind": "openai", "auth": True,
            "base_url": llm.get("codecraft_base_url", DEFAULT_CODECRAFT_BASE_URL),
            "api_keys": load_codecraft_api_keys(),
            "model": llm.get("codecraft_model", DEFAULT_CODECRAFT_MODEL),
        })
    except (FileNotFoundError, ValueError):
        pass
    try:
        providers.append({
            "id": "gemini", "name": "Gemini", "kind": "gemini", "auth": True,
            "base_url": "",
            "api_keys": load_gemini_api_keys(),
            "model": llm.get("gemini_model", DEFAULT_GEMINI_MODEL),
        })
    except (FileNotFoundError, ValueError):
        pass
    try:
        providers.append({
            "id": "ollama", "name": "Ollama", "kind": "openai", "auth": True,
            "base_url": llm.get("ollama_base_url", DEFAULT_OLLAMA_BASE_URL),
            "api_keys": load_ollama_api_keys(),
            "model": llm.get("ollama_model", DEFAULT_OLLAMA_MODEL),
        })
    except (FileNotFoundError, ValueError):
        pass
    providers.append({
        "id": "lmstudio", "name": "LM Studio", "kind": "openai", "auth": False,
        "base_url": llm.get("base_url", "http://localhost:1234/v1"),
        "api_keys": [], "model": llm.get("model", "auto"),
    })
    return providers


def load_provider_registry():
    try:
        reg = load_json_file(PROVIDERS_FILE)
        if isinstance(reg, dict) and isinstance(reg.get("providers"), list) and reg["providers"]:
            return reg
    except (FileNotFoundError, ValueError):
        pass
    providers = _legacy_provider_entries()
    reg = {"active": providers[0]["id"], "providers": providers}
    save_json_file(PROVIDERS_FILE, reg)
    return reg


def save_provider_registry(reg):
    save_json_file(PROVIDERS_FILE, reg)


def get_active_provider(reg=None):
    reg = reg or load_provider_registry()
    active_id = reg.get("active")
    for provider in reg["providers"]:
        if provider["id"] == active_id:
            return provider
    return reg["providers"][0] if reg["providers"] else None


def get_backup_provider(reg=None):
    """The fallback provider used when the active one fails; None if unset."""
    reg = reg or load_provider_registry()
    backup_id = reg.get("backup")
    for provider in reg["providers"]:
        if provider["id"] == backup_id:
            return provider
    return None


def suggested_parallelism(config=None):
    """How many translations can safely run at once: one per cloud API key."""
    provider = get_active_provider()
    if provider and provider.get("api_keys"):
        return max(1, len(provider["api_keys"]))
    if provider and not provider.get("auth"):
        return 2  # local single model barely benefits from more threads
    return 1


def translator_ready(config=None):
    """True when the active provider is set up (keys present, or a local server)."""
    try:
        return get_active_provider() is not None
    except (FileNotFoundError, ValueError):
        return False


_gemini_key_lock = threading.Lock()
_gemini_key_offset = 0
_gemini_dead_keys = set()


def parse_retry_hint(message):
    match = re.search(r"retry in ([\d.]+)\s*(ms|s|minutes?)", message, re.IGNORECASE)
    if not match:
        return None
    value = float(match.group(1))
    unit = match.group(2).lower()
    if unit == "ms":
        seconds = value / 1000
    elif unit.startswith("min"):
        seconds = value * 60
    else:
        seconds = value
    return max(1, int(seconds) + 1)


def gemini_http_error(response):
    try:
        detail = response.json().get("error", {}).get("message", "")
    except ValueError:
        detail = ""
    return f"Gemini HTTP {response.status_code}: {detail or response.text[:300]}"


def request_gemini_completion(prompt, system_prompt, config, provider):
    """One generateContent call against the Gemini API; keys round-robin."""
    global _gemini_key_offset
    all_keys = provider.get("api_keys") or []
    keys = [key for key in all_keys if key not in _gemini_dead_keys] or all_keys
    with _gemini_key_lock:
        start = _gemini_key_offset % len(keys)
        _gemini_key_offset += 1
    model = provider.get("model", DEFAULT_GEMINI_MODEL)
    is_gemma = model.startswith("gemma")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    generation_config = {
        "temperature": config.get("temperature", 0.25),
        "maxOutputTokens": config.get("gemini_max_output_tokens", 8192),
        "responseMimeType": "application/json",
        "responseSchema": {
            "type": "OBJECT",
            "required": ["title", "description"],
            "properties": {
                "title": {"type": "STRING"},
                "description": {"type": "STRING"},
            },
        },
    }
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": generation_config,
    }
    if is_gemma:
        # Gemma rejects systemInstruction (500) and thinkingBudget (400).
        payload["contents"][0]["parts"][0]["text"] = f"{system_prompt}\n\n{prompt}"
    else:
        payload["systemInstruction"] = {"parts": [{"text": system_prompt}]}
        generation_config["thinkingConfig"] = {"thinkingBudget": 0}

    last_404 = None
    for offset in range(len(keys)):
        key = keys[(start + offset) % len(keys)]
        for patience in range(5):
            try:
                response = requests.post(
                    url, json=payload,
                    headers={"x-goog-api-key": key},
                    timeout=config.get("timeout_seconds", 180),
                )
            except requests.Timeout:
                if patience == 4:
                    raise
                time.sleep(5)
                continue
            if response.status_code not in (500, 503) or patience == 4:
                break
            time.sleep(5 + random.uniform(0, 3))
        if response.status_code == 404:
            last_404 = gemini_http_error(response)
            if key not in _gemini_dead_keys:
                _gemini_dead_keys.add(key)
                live_left = len([k for k in all_keys if k not in _gemini_dead_keys])
                print(f"⚠️ Key #{all_keys.index(key) + 1} can't see {model}. Keys left: {live_left}.")
            continue
        if response.status_code != 200:
            raise RuntimeError(gemini_http_error(response))
        data = response.json()
        candidates = data.get("candidates") or [{}]
        parts = candidates[0].get("content", {}).get("parts", [])
        text = "".join(part.get("text", "") for part in parts)
        if not text:
            raise ValueError(f"Gemini empty answer (finishReason={candidates[0].get('finishReason')})")
        return text
    raise RuntimeError(f"{last_404} — no key of {len(all_keys)} sees model {model}.")


_ollama_key_lock = threading.Lock()
_ollama_key_offset = 0


def request_openai_completion(provider, prompt, system_prompt, config):
    """One chat completion against any OpenAI-compatible provider.

    Covers online providers (Bearer key) and local ones (no auth).
    Keys rotate round-robin; dead keys (401/403/404) are skipped when
    other keys remain.
    """
    keys = provider.get("api_keys") or []
    pid = provider["id"]
    with _openai_lock:
        start = _openai_offsets.get(pid, 0) % len(keys)
        _openai_offsets[pid] = start + 1
    endpoint = provider["base_url"].rstrip("/")
    model = provider.get("model", "auto")
    if model == "auto":
        model = get_local_llm_model({"base_url": endpoint})
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
        "temperature": config.get("temperature", 0.25),
        # Reasoning models spend tokens on thinking before the answer; a tight
        # cap leaves content empty, so online providers get a generous budget.
        "max_tokens": provider.get("max_tokens") or (8192 if provider.get("auth") else 2400),
        "stream": False,
        "response_format": {"type": "json_object"},
    }
    headers = {}
    last_error = None
    for offset in range(len(keys)):
        key = keys[(start + offset) % len(keys)]
        if key:
            headers = {"Authorization": f"Bearer {key}"}
        response = requests.post(
            f"{endpoint}/chat/completions",
            json=payload,
            headers=headers,
            timeout=config.get("timeout_seconds", 180),
        )
        if response.status_code in (401, 403, 404) and offset < len(keys) - 1:
            last_error = f"HTTP {response.status_code}: {response.text[:200]}"
            print(f"⚠️ Ключ #{start + offset + 1} не работает, пробую следующий.")
            continue
        if response.status_code != 200:
            message = f"HTTP {response.status_code}: {response.text[:300]}"
            retry_after = response.headers.get("Retry-After", "")
            if response.status_code == 429 and retry_after:
                message += f" (retry in {retry_after}s)"
            raise RuntimeError(message)
        answer = response.json()
        choice = answer.get("choices", [{}])[0]
        content = choice.get("message", {}).get("content")
        if not content:
            raise ValueError(
                f"Пустой ответ (finish_reason={choice.get('finish_reason')}): {str(answer)[:150]}"
            )
        return content
    raise RuntimeError(f"{last_error} — ни один из {len(keys)} ключей провайдера не сработал.")


def get_local_llm_model(config):
    model = config.get("model", "auto")
    if model != "auto":
        return model
    endpoint = config["base_url"].rstrip("/")
    response = requests.get(f"{endpoint}/models", timeout=10)
    response.raise_for_status()
    models = response.json().get("data", [])
    if not models:
        raise RuntimeError("LM Studio is reachable, but no model is loaded.")
    return models[0]["id"]


def parse_llm_json(content):
    """Accept plain JSON and recover JSON wrapped in a code block or with trailing chatter."""
    content = content.strip()
    if content.startswith("```"):
        content = content.split("\n", 1)[1] if "\n" in content else ""
        content = content.rsplit("```", 1)[0].strip()
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        value, _ = json.JSONDecoder().raw_decode(content)
        return value


def load_series_names():
    if not os.path.exists(data_file_path(SERIES_NAMES_FILE)):
        return []
    names = load_json_file(SERIES_NAMES_FILE)
    if not isinstance(names, list):
        raise ValueError(f"{SERIES_NAMES_FILE} must contain a list of names.")
    return [str(name).strip() for name in names if str(name).strip()]


def add_series_name(name):
    name = (name or "").strip()
    if not name:
        return
    names = load_series_names()
    if any(name.casefold() == existing.casefold() for existing in names):
        return
    names.append(name)
    save_json_file(SERIES_NAMES_FILE, names)


def remove_unrequested_series_lines(description, source_description):
    """Drop LLM-invented series footer lines absent from the source description."""
    series_names = load_series_names()
    if not series_names:
        return description
    source_casefold = source_description.casefold()
    kept = []
    for line in description.split("\n"):
        invented = any(
            name.casefold() in line.casefold() and name.casefold() not in source_casefold
            for name in series_names
        )
        if not invented:
            kept.append(line)
    return "\n".join(kept).strip()


def restore_source_line_breaks(description, source_description):
    """Rebuild the source's line breaks: models often double single newlines."""
    out_content = [line.strip() for line in description.split("\n") if line.strip()]
    src_content = [line.strip() for line in source_description.split("\n") if line.strip()]
    if not out_content or len(out_content) != len(src_content):
        return description
    rebuilt = []
    out_index = 0
    for line in source_description.split("\n"):
        if not line.strip():
            if rebuilt and rebuilt[-1] != "":
                rebuilt.append("")
            continue
        rebuilt.append(out_content[out_index])
        out_index += 1
    return "\n".join(rebuilt).rstrip()


def clean_existing_series_footers(localizations, source_description):
    changed = False
    for localized_metadata in localizations.values():
        description = localized_metadata.get("description")
        if not isinstance(description, str):
            continue
        cleaned = remove_unrequested_series_lines(description, source_description)
        if cleaned != description:
            localized_metadata["description"] = cleaned
            changed = True
    return changed


def localize_language_via_llm(provider, config, language_code,
                              language_name, source_title, source_description,
                              progress=None):
    """Localize for one language; on final failure try the backup provider."""
    backup = get_backup_provider()
    try:
        return _localize_with_provider(provider, config, language_code,
                                       language_name, source_title, source_description,
                                       progress=progress)
    except Exception as error:
        if backup and backup["id"] != provider.get("id"):
            print(f"⚠️ Провайдер '{provider.get('name')}' не сработал "
                  f"({str(error).splitlines()[0][:90]}), пробую резервного '{backup['name']}'.")
            return _localize_with_provider(backup, config, language_code,
                                           language_name, source_title, source_description,
                                           progress=progress)
        raise


def _localize_with_provider(provider, config, language_code,
                            language_name, source_title, source_description,
                            progress=None):
    max_attempts = max(1, config.get("retry_attempts", 6 if provider.get("auth") else 3))
    system_prompt = "You are a precise multilingual YouTube metadata localizer."
    series_names = load_series_names()
    series_rule = ""
    if series_names:
        names_list = ", ".join(f'"{name}"' for name in series_names)
        series_rule = (
            f" Never add a line containing {names_list} "
            "unless that exact name appears in the source description."
        )
    prompt = f"""Localize the YouTube metadata below for {language_name} ({language_code}).

This is adaptive localization, not a literal translation. Preserve the scene, calm magical tone, calls to action, links, emojis, and line breaks. Use natural wording a native speaker would use. Keep Hogwarts as the locally conventional name if one exists. Do not invent facts, keywords, claims, sections, series labels, or footers.{series_rule}

Return ONLY the JSON object required by the schema.
- title: at most 100 characters, compelling and natural for YouTube.
- description: at most 5000 characters; preserve the source structure and URL exactly.
- line breaks: copy the source exactly — "\\n" for each source line break and "\\n\\n" only where the source has a blank line; never insert extra blank lines.

SOURCE TITLE:
{source_title}

SOURCE DESCRIPTION:
{source_description}"""
    for attempt in range(1, max_attempts + 1):
        try:
            if provider["kind"] == "gemini":
                content = request_gemini_completion(prompt, system_prompt, config, provider)
            else:
                content = request_openai_completion(provider, prompt, system_prompt, config)
            answer = parse_llm_json(content)
            title = answer["title"].strip()
            description = remove_unrequested_series_lines(
                answer["description"].strip(), source_description
            )
            description = restore_source_line_breaks(description, source_description)
            if not title or not description:
                raise ValueError("the model returned an empty title or description")
            if len(title) > 100 or len(description) > 5000:
                raise ValueError(f"limits exceeded: title={len(title)}, description={len(description)}")
            return {"title": title, "description": description}
        except Exception as error:
            if attempt == max_attempts:
                raise
            message = str(error)
            wait_seconds = parse_retry_hint(message)
            if wait_seconds is None:
                if "429" in message:
                    wait_seconds = 20
                elif "500" in message or "503" in message:
                    wait_seconds = 10
                else:
                    wait_seconds = 2
            retry_line = t("engine_retry").format(
                code=language_code, attempt=attempt, attempts=max_attempts - 1,
                wait=wait_seconds, message=message.splitlines()[0])
            if progress:
                progress("retry", language_code, message.splitlines()[0])
            print(retry_line)
            time.sleep(wait_seconds)


def localize_metadata_via_llm(metadata, target_languages=None, parts=("title", "description"), progress=None):
    """Create localized titles and descriptions via the active API provider."""
    config = load_local_llm_config()
    provider = get_active_provider()
    if provider is None:
        raise RuntimeError("No translation provider configured.")
    source_title = metadata.get("title", "").strip()
    source_description = metadata.get("description", "").strip()
    if not source_title or not source_description:
        raise ValueError("metadata must contain a non-empty title and description.")

    if target_languages is None:
        target_languages = []
    target_languages = list(dict.fromkeys(target_languages))
    language_names = config.get("language_names", {})
    translated = {}
    errors = []

    for language_code in target_languages:
        if language_code == "en":
            translated[language_code] = {
                "title": source_title,
                "description": source_description,
            }

    queued = [code for code in target_languages if code != "en"]
    if queued:
        max_workers = min(len(queued), resolve_parallelism(config))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            def delayed(idx, code):
                # Stagger starts so all threads don't slam the model at once.
                time.sleep(idx * 1.5)
                return localize_language_via_llm(
                    provider, config,
                    code, language_names.get(code, code), source_title, source_description,
                    progress=progress,
                )
            futures = {pool.submit(delayed, idx, code): code for idx, code in enumerate(queued)}
            for future in as_completed(futures):
                language_code = futures[future]
                try:
                    translated[language_code] = future.result()
                    result = translated[language_code]
                    if progress:
                        progress("ok", language_code,
                                 f"{len(result['title'])}/{len(result['description'])}")
                    print(t("engine_ok").format(
                        code=language_code,
                        t=len(result['title']), d=len(result['description'])))
                except Exception as error:
                    errors.append(f"{language_code}: {error}")
                    if progress:
                        progress("fail", language_code, str(error).splitlines()[0])
                    print(t("engine_failed").format(code=language_code, error=error))

    if errors:
        raise RuntimeError("Localization failed for some languages:\n" + "\n".join(errors))

    ordered = {code: translated[code] for code in target_languages if code in translated}
    for texts in ordered.values():
        # Parts outside the requested scope keep the source text untouched.
        if "title" not in parts:
            texts["title"] = source_title
        if "description" not in parts:
            texts["description"] = source_description
    save_json_file(LOCALIZATIONS_FILE, ordered)
    return ordered


def fetch_video_source_metadata(youtube, video_id):
    response = youtube.videos().list(part="snippet", id=video_id).execute()
    if not response.get("items"):
        raise ValueError(f"Video {video_id} not found.")
    snippet = response["items"][0]["snippet"]
    metadata = {
        "title": (snippet.get("title") or "").strip(),
        "description": normalize_description(snippet.get("description") or ""),
    }
    if not metadata["title"] or not metadata["description"]:
        raise ValueError(f"Video {video_id} has an empty title or description.")
    return metadata


# ---------------------------------------------------------------------------
# Channel profiles
# ---------------------------------------------------------------------------


def load_channel_profiles():
    try:
        profiles = load_json_file(CHANNEL_PROFILES_FILE)
    except FileNotFoundError:
        profiles = {"profiles": []}
        save_json_file(CHANNEL_PROFILES_FILE, profiles)
        return profiles
    if not isinstance(profiles, dict) or not isinstance(profiles.get("profiles"), list):
        raise ValueError("channel_profiles.json must contain a 'profiles' list.")
    return profiles


def save_channel_profiles(profiles):
    save_json_file(CHANNEL_PROFILES_FILE, profiles)


def migrate_playlist_model(profile):
    """Convert the legacy single playlist_id into playlists + default_playlists."""
    if profile.get("playlists"):
        return False
    legacy = (profile.get("playlist_id") or "").strip()
    if not legacy:
        return False
    profile["playlists"] = [{"id": legacy, "name": legacy}]
    profile["default_playlists"] = [legacy]
    profile["playlist_id"] = ""
    return True


def migrate_profile_paths(profile):
    """Move per-profile files into profiles/<profile_id>/ (pre-folder layout kept at data/ root)."""
    migrated = False
    for key, new_name in (("token_file", "token.pickle"), ("publ_calendar_file", "calendar.json")):
        new_rel = f"profiles/{profile['profile_id']}/{new_name}"
        old_rel = profile.get(key, "")
        if old_rel == new_rel:
            continue
        old_abs = os.path.join(DATA_DIR, old_rel)
        new_abs = os.path.join(DATA_DIR, new_rel)
        if os.path.isfile(old_abs):
            os.makedirs(os.path.dirname(new_abs), exist_ok=True)
            shutil.move(old_abs, new_abs)
            # Drop the legacy folder if the move left it empty (e.g. tokens/).
            old_dir = os.path.dirname(old_abs)
            if os.path.normpath(old_dir) != os.path.normpath(DATA_DIR) and not os.listdir(old_dir):
                os.rmdir(old_dir)
        profile[key] = new_rel
        migrated = True
    return migrated


def get_profile_languages(profile):
    languages = profile.get("languages")
    if isinstance(languages, list):
        return [str(code) for code in languages]
    return []


def valid_language_code(code):
    return bool(re.fullmatch(r"[a-z]{2,3}(?:-[A-Za-z0-9]{2,8})?", code))


def available_language_catalog():
    # Full YouTube locale list with native names.
    catalog = {
        "af": "Afrikaans", "az": "Azərbaycan", "id": "Bahasa Indonesia",
        "ms": "Bahasa Malaysia", "bs": "Bosanski", "ca": "Català", "cs": "Čeština",
        "cy": "Cymraeg", "da": "Dansk", "de": "Deutsch", "et": "Eesti",
        "en": "English", "en-CA": "English (Canada)", "en-GB": "English (UK)",
        "en-IN": "English (India)", "en-US": "English (US)", "es": "Español",
        "es-419": "Español (Latinoamérica)", "es-US": "Español (EE. UU.)",
        "eu": "Euskara", "fil": "Filipino", "fr": "Français", "fr-CA": "Français (Canada)",
        "gl": "Galego", "gu": "ગુજરાતી", "hr": "Hrvatski", "is": "Íslenska",
        "it": "Italiano", "jv": "Basa Jawa", "kn": "ಕನ್ನಡ", "la": "Latin",
        "lv": "Latviešu", "lt": "Lietuvių", "hu": "Magyar", "nl": "Nederlands",
        "ne": "नेपाली", "no": "Norsk", "or": "ଓଡ଼ିଆ", "pa": "ਪੰਜਾਬੀ",
        "pl": "Polski", "pt": "Português (Brasil)", "pt-PT": "Português (Portugal)",
        "ro": "Română", "rm": "Rumantsch", "si": "සිංහල", "sk": "Slovenčina",
        "sl": "Slovenščina", "fi": "Suomi", "sv": "Svenska", "sw": "Kiswahili",
        "tl": "Tagalog", "ta": "தமிழ்", "te": "తెలుగు", "th": "ไทย",
        "vi": "Tiếng Việt", "tr": "Türkçe", "uk": "Українська", "ur": "اردو",
        "zh-Hans": "中文（简体）", "zh-Hant": "中文（繁體）", "zh-TW": "中文（台灣）",
        "zu": "IsiZulu", "el": "Ελληνικά", "bg": "Български", "ru": "Русский",
        "sr": "Српски", "mk": "Македонски", "kk": "Қазақ тілі", "ky": "Кыргызча",
        "hy": "Հայերեն", "ka": "ქართული", "mn": "Монгол", "my": "ဗမာ",
        "km": "ខ្មែរ", "lo": "ລາວ", "he": "עברית", "ar": "العربية",
        "fa": "فارسی", "sd": "سنڌي", "am": "አማርኛ", "yo": "Yorùbá",
        "ha": "Hausa", "ig": "Igbo", "qu": "Runasimi", "nso": "Sepedi",
        "bn": "বাংলা", "hi": "हिन्दी", "ja": "日本語", "ko": "한국어",
        "so": "Soomaali", "sq": "Shqip",
    }
    try:
        catalog.update(load_local_llm_config().get("language_names", {}))
    except (FileNotFoundError, ValueError):
        pass
    return catalog


def profile_slug(display_name, existing_ids):
    # \w keeps unicode letters, so cyrillic profile/provider names stay readable.
    base = re.sub(r"[^\w]+", "_", display_name.lower(), flags=re.UNICODE).strip("_") or "channel"
    candidate = base
    number = 2
    while candidate in existing_ids:
        candidate = f"{base}_{number}"
        number += 1
    return candidate


def find_secrets_files():
    """All client_secrets*.json files in data/ (any name the user chose)."""
    if not os.path.isdir(DATA_DIR):
        return []
    return sorted(
        f for f in os.listdir(DATA_DIR)
        if f.startswith("client_secrets") and f.endswith(".json")
    )


def create_profile_wizard(profiles, secrets_files):
    clear_console()
    print(t("profile_wizard_title"))
    name = ""
    while not name:
        name = input(t("profile_name_prompt")).strip()
        if not name:
            print(t("profile_name_empty"))

    if len(secrets_files) == 1:
        secrets_file = secrets_files[0]
        print(t("profile_secrets_auto").format(file=secrets_file))
    else:
        print(t("profile_secrets_pick"))
        for index, filename in enumerate(secrets_files, start=1):
            print(f"  {index}) {filename}")
        while True:
            choice = input(t("menu_choice")).strip()
            if choice.isdigit() and 1 <= int(choice) <= len(secrets_files):
                secrets_file = secrets_files[int(choice) - 1]
                break

    # The playlist is configured later in Settings — asking here confuses new users.
    existing_ids = {p["profile_id"] for p in profiles["profiles"]}
    profile_id = profile_slug(name, existing_ids)
    # Everything a profile owns lives in its own subfolder: profiles/<profile_id>/
    token_file = f"profiles/{profile_id}/token.pickle"
    calendar_file = f"profiles/{profile_id}/calendar.json"
    save_json_file(calendar_file, {})

    profile = {
        "profile_id": profile_id,
        "display_name": name,
        "channel_id": "",
        "channel_title": "",
        "token_file": token_file,
        "client_secrets_file": secrets_file,
        "playlists": [],
        "default_playlists": [],
        "publ_calendar_file": calendar_file,
    }
    profiles["profiles"].append(profile)
    save_channel_profiles(profiles)
    print(t("profile_created").format(name=name))
    return profile


def select_profile(profiles):
    secrets_files = find_secrets_files()
    while True:
        clear_console()
        lines = []
        for index, profile in enumerate(profiles["profiles"], start=1):
            name = profile.get("channel_title") or profile.get("display_name")
            token_exists = os.path.exists(data_file_path(profile["token_file"]))
            status = "✅" if token_exists else "🔑"
            lines.append(f"{index}) {name} ({status})")
        lines.append(t("profile_pick_add"))
        show_menu(t("profile_pick_title"), lines)
        choice = input(t("profile_pick_prompt")).strip().lower()
        if choice == "0":
            return None
        if choice == "n":
            if not secrets_files:
                ensure_secrets()
                secrets_files = find_secrets_files()
                if not secrets_files:
                    continue
            return create_profile_wizard(profiles, secrets_files)
        if choice.isdigit() and 1 <= int(choice) <= len(profiles["profiles"]):
            return profiles["profiles"][int(choice) - 1]
        print(t("invalid_choice"))


def ensure_secrets():
    """Loop until a client_secrets file appears; localized instructions with links."""
    while True:
        secrets = find_secrets_files()
        if secrets:
            return secrets
        clear_console()
        print(f"{t('secrets_missing_title')}\n")
        print(t("secrets_missing_steps"))
        print()
        print(t("secrets_link_guide").format(url=GUIDE_LINKS.get(_ui["language"], GUIDE_LINKS["en"])))
        print(t("secrets_link_console").format(url=GOOGLE_CONSOLE_LINK))
        answer = input(f"\n{t('secrets_retry')}").strip().lower()
        if answer in ("0", "s", "skip", "x", "н", "х"):
            return []


def manage_profile_languages(profile, profiles):
    """Settings screen for the languages this profile translates."""
    while True:
        selected = get_profile_languages(profile)
        channel_name = profile.get("channel_title") or profile.get("display_name")
        clear_console()
        print(t("languages_screen_title").format(channel=channel_name))
        if selected:
            print(t("languages_selected").format(n=len(selected), list=", ".join(selected)))
        else:
            print(t("languages_none"))
        print(t("languages_menu"))
        choice = input(f"\n{t('menu_choice')}").strip()
        if choice == "0":
            return
        if choice == "1":
            profile["languages"] = choose_languages_from_catalog(selected)
        elif choice == "2":
            code = input(t("languages_add_prompt")).strip()
            if not valid_language_code(code):
                print(t("languages_bad_code"))
                continue
            if code in selected:
                print(t("languages_already"))
                continue
            selected.append(code)
            profile["languages"] = selected
        elif choice == "3":
            if confirm(t("languages_clear_confirm")):
                profile["languages"] = []
            else:
                continue
        else:
            print(t("invalid_choice"))
            continue
        save_channel_profiles(profiles)


def _enable_ansi_windows():
    """Enable ANSI escape codes in the classic Windows console."""
    if os.name != "nt":
        return
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32
        handle = kernel32.GetStdHandle(-11)
        mode = ctypes.c_uint32()
        if kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            kernel32.SetConsoleMode(handle, mode.value | 0x0004)
    except Exception:
        pass


def _read_key():
    """One keypress: 'up', 'down', 'space', 'enter', or the lowercase character."""
    if os.name == "nt":
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ch2 = msvcrt.getwch()
            return {"H": "up", "P": "down"}.get(ch2, "")
        if ch in ("\r", "\n"):
            return "enter"
        if ch == " ":
            return "space"
        return ch.lower()
    import termios
    import tty
    fd = sys.stdin.fileno()
    old_attrs = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            seq = ch + sys.stdin.read(2)
            return {"\x1b[A": "up", "\x1b[B": "down"}.get(seq, "")
        if ch in ("\r", "\n"):
            return "enter"
        if ch == " ":
            return "space"
        return ch.lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old_attrs)


def interactive_checkbox(title, labels, selected):
    """Checkbox list over labeled rows; returns the new set of selected indices.

    Arrows move the cursor, Space toggles, A/Ф selects all, N/Т clears,
    Enter/0/q confirms. Falls back to numbered input in non-interactive
    terminals (scripts, pipes).
    """
    selected = set(selected)
    interactive = sys.stdin.isatty() and sys.stdout.isatty()
    if not interactive:
        while True:
            clear_console()
            print(title)
            for index, label in enumerate(labels, start=1):
                mark = "x" if index - 1 in selected else " "
                print(f"  [{mark}] {index}) {label}")
            print(f"\n{t('languages_toggle_hint')}")
            answer = input(t("languages_toggle_prompt")).strip().lower()
            if answer in ("0", ""):
                return selected
            if answer in ("a", "а", "ф"):
                selected = set(range(len(labels)))
                continue
            if answer in ("n", "н", "т"):
                selected = set()
                continue
            toggled = False
            for token in re.split(r"[,\s]+", answer):
                if token.isdigit() and 1 <= int(token) <= len(labels):
                    index = int(token) - 1
                    if index in selected:
                        selected.remove(index)
                    else:
                        selected.add(index)
                    toggled = True
            if not toggled:
                print(t("languages_didnt_understand"))

    _enable_ansi_windows()
    cursor = 0

    def render(first=False):
        if not first:
            # Jump back above the list and clear it for a flicker-free redraw.
            sys.stdout.write("\x1b[%dA\x1b[J" % (len(labels) + 1))
        lines = []
        for index, label in enumerate(labels):
            arrow = "❯" if index == cursor else " "
            mark = "x" if index in selected else " "
            lines.append(f"{arrow} [{mark}] {index + 1}) {label}")
        lines.append(t("languages_keys_hint"))
        print("\n".join(lines), flush=True)

    print(title)
    sys.stdout.write("\x1b[?25l")  # hide the cursor while the list is live
    try:
        render(first=True)
        while True:
            key = _read_key()
            if key == "up":
                cursor = (cursor - 1) % len(labels)
            elif key == "down":
                cursor = (cursor + 1) % len(labels)
            elif key == "space":
                if cursor in selected:
                    selected.remove(cursor)
                else:
                    selected.add(cursor)
            elif key in ("a", "а", "ф"):
                selected = set(range(len(labels)))
            elif key in ("n", "н", "т"):
                selected = set()
            elif key in ("enter", "0", "q"):
                break
            render()
    finally:
        sys.stdout.write("\x1b[?25h")  # show the cursor back
        print()
    return selected


def choose_languages_from_catalog(selected):
    """Toggle-menu over the language catalog; returns the new selection."""
    catalog = available_language_catalog()
    codes = sorted(catalog) + [code for code in selected if code not in catalog]
    labels = [f"{code} — {catalog.get(code, code)}" for code in codes]
    chosen = interactive_checkbox(
        t("languages_list_title"), labels,
        {codes.index(code) for code in selected},
    )
    return [codes[index] for index in sorted(chosen)]


def resolve_parallelism(config):
    """'auto' (or anything unparsable) = one thread per cloud API key."""
    value = config.get("max_parallel_languages", "auto")
    try:
        return max(1, int(value))
    except (TypeError, ValueError):
        return max(1, suggested_parallelism(config))


def manage_parallelism_setting():
    config = load_local_llm_config()
    suggested = suggested_parallelism(config)
    raw_current = config.get("max_parallel_languages", "auto")
    current_display = "auto" if str(raw_current).lower() == "auto" else raw_current
    provider = resolve_llm_provider(config)
    print(f"\n{t('parallel_current').format(n=current_display)}")
    if provider in ("gemini", "ollama", "codecraft"):
        print(t("parallel_keys_found").format(n=suggested))
    else:
        print(t("parallel_local_note"))
    answer = input(t("parallel_prompt").format(n=current_display)).strip().lower()
    if not answer:
        return
    if answer in ("auto", "аuto", "а", "a"):
        config["max_parallel_languages"] = "auto"
        save_json_file("local_llm.json", config)
        print(t("parallel_saved_auto").format(n=suggested))
        return
    if not answer.isdigit() or int(answer) < 1:
        print(t("parallel_not_positive"))
        return
    value = int(answer)
    if value > suggested:
        print(t("parallel_over_warning").format(n=suggested))
        if not confirm(t("parallel_over_confirm")):
            return
    config["max_parallel_languages"] = value
    save_json_file("local_llm.json", config)
    print(t("parallel_saved").format(n=value))


def interface_menu():
    while True:
        clear_console()
        show_menu(t("settings_interface"), [
            f"1) {t('set_language')}",
            f"2) {t('set_name')}",
            f"0) {t('back')}",
        ])
        choice = input(t("menu_choice")).strip()
        if choice == "0":
            return
        if choice == "1":
            choose_ui_language()
            save_ui_settings()
        elif choice == "2":
            ask_user_name()
            save_ui_settings()
        else:
            print(t("invalid_choice"))


def translations_menu(profile, profiles):
    while True:
        clear_console()
        ask_pl = "✓" if _ui.get("ask_playlists", True) else "✗"
        ask_sc = "✓" if _ui.get("ask_schedule", True) else "✗"
        show_menu(t("settings_translations"), [
            f"1) {t('set_languages')}",
            f"2) {t('set_parallel')}",
            f"3) {t('api_title')}",
            f"4) {t('set_ask_playlists')} [{ask_pl}]",
            f"5) {t('set_ask_schedule')} [{ask_sc}]",
            f"0) {t('back')}",
        ])
        choice = input(t("menu_choice")).strip()
        if choice == "0":
            return
        if choice == "1":
            manage_profile_languages(profile, profiles)
        elif choice == "2":
            manage_parallelism_setting()
        elif choice == "3":
            api_providers_menu()
        elif choice == "4":
            toggle_ask_flag("ask_playlists")
        elif choice == "5":
            toggle_ask_flag("ask_schedule")
        else:
            print(t("invalid_choice"))


def parse_playlist_id(text):
    """Extract a playlist ID from a link (list=...) or accept a bare ID."""
    text = (text or "").strip()
    match = re.search(r"[?&]list=([A-Za-z0-9_-]+)", text)
    if match:
        return match.group(1)
    if re.fullmatch(r"[A-Za-z0-9_-]{12,}", text):
        return text
    return None


def fetch_playlist_title(youtube, playlist_id):
    """Real playlist title from YouTube; None when it can't be fetched."""
    if not youtube:
        return None
    try:
        response = youtube.playlists().list(part="snippet", id=playlist_id).execute()
        items = response.get("items", [])
        return items[0]["snippet"]["title"] if items else None
    except Exception:
        return None


def playlists_menu(profile, profiles, youtube=None):
    while True:
        clear_console()
        channel = profile.get("channel_title") or profile.get("display_name")
        playlists = profile.setdefault("playlists", [])
        defaults = profile.setdefault("default_playlists", [])

        if playlists:
            for index, pl in enumerate(playlists, start=1):
                star = "★" if pl["id"] in defaults else " "
                print(f"{index}) [{star}] {pl['name']} — {pl['id']}")
            print(t("defaults_star_note"))
        else:
            print(t("playlist_none"))

        show_menu(t("playlists_title").format(channel=channel), [
            f"1) {t('playlist_edit')}",
            *( [f"2) {t('playlists_defaults_item')}", f"3) {t('playlists_remove_item')}"]
               if playlists else [] ),
            f"0) {t('back')}",
        ])
        choice = input(t("menu_choice")).strip()

        if choice == "0":
            return
        if choice == "1":
            link = input(t("playlists_add_prompt")).strip()
            if not link:
                continue
            playlist_id = parse_playlist_id(link)
            if not playlist_id:
                print(t("playlist_bad_link"))
                continue
            if any(pl["id"] == playlist_id for pl in playlists):
                print(t("playlist_exists"))
                continue
            name = fetch_playlist_title(youtube, playlist_id) or ""
            if name:
                print(t("playlist_fetched_name").format(name=name))
                custom = input(t("playlist_name_prompt")).strip()
                name = custom or name
            else:
                name = input(t("playlist_name_fallback")).strip() or playlist_id
            playlists.append({"id": playlist_id, "name": name})
            save_channel_profiles(profiles)
            print(t("playlist_added"))
            continue
        if choice == "2" and playlists:
            labels = [f"{pl['name']} — {pl['id']}" for pl in playlists]
            chosen = interactive_checkbox(
                t("playlists_defaults_title"), labels,
                {index for index, pl in enumerate(playlists) if pl["id"] in defaults},
            )
            defaults[:] = [playlists[index]["id"] for index in sorted(chosen)]
            save_channel_profiles(profiles)
            if defaults:
                print(t("defaults_saved"))
            else:
                print(t("defaults_empty_note"))
            continue
        if choice == "3" and playlists:
            answer = input(t("remove_prompt")).strip()
            if not answer.isdigit() or not 1 <= int(answer) <= len(playlists):
                print(t("invalid_choice"))
                continue
            removed = playlists.pop(int(answer) - 1)
            if removed["id"] in defaults:
                defaults.remove(removed["id"])
            save_channel_profiles(profiles)
            print(t("removed"))
            continue
        print(t("invalid_choice"))


def schedule_menu(profile, profiles):
    """Per-profile publishing calendar: a local time for each allowed weekday."""
    while True:
        clear_console()
        channel = profile.get("channel_title") or profile.get("display_name")
        publ_calendar = load_calendar(profile)
        show_menu(t("schedule_title").format(channel=channel),
                  [t("schedule_note")] + [
            f"{index}) {translate_day(day)} — "
            f"{(publ_calendar.get(day) or [DEFAULT_PUBLISH_TIME])[0]}"
            for index, day in enumerate(ALLOWED_DAYS, start=1)
        ] + [f"0) {t('back')}"])
        choice = input(t("menu_choice")).strip()
        if choice == "0":
            return
        if choice.isdigit() and 1 <= int(choice) <= len(ALLOWED_DAYS):
            day = ALLOWED_DAYS[int(choice) - 1]
            answer = input(t("schedule_time_prompt")).strip()
            if not answer:
                continue
            try:
                datetime.strptime(answer, "%H:%M")
            except ValueError:
                print(t("schedule_bad_time"))
                continue
            publ_calendar[day] = [answer]
            save_json_file(profile["publ_calendar_file"], publ_calendar)
            print(t("schedule_saved").format(day=translate_day(day), time=answer))
        else:
            print(t("invalid_choice"))


def _ask_or_cancel(prompt, default=None):
    """Prompt where typing 0 cancels the whole flow (returns None)."""
    answer = input(prompt).strip()
    if answer == "0":
        return None
    return answer or default


def _mask_key(key):
    return key[:10] + "…" if len(key) > 12 else key


def fetch_local_models(base_url):
    """Model ids from an OpenAI-compatible server's /models; empty when unreachable."""
    try:
        response = requests.get(f"{(base_url or '').rstrip('/')}/models", timeout=5)
        response.raise_for_status()
        return [m.get("id") for m in response.json().get("data", []) if m.get("id")]
    except Exception:
        return []


def _pick_model(base_url, online):
    """Model name for a provider: fetched list for local servers, manual for online."""
    models = [] if online else fetch_local_models(base_url)
    if models:
        print(t("api_models_found"))
        for index, model_id in enumerate(models, start=1):
            print(f"  {index}) {model_id}")
        answer = input(t("api_models_pick").format(default=models[0])).strip()
        if answer == "0":
            return None
        if answer.isdigit() and 1 <= int(answer) <= len(models):
            return models[int(answer) - 1]
        return answer or models[0]
    answer = input(t("api_model_prompt")).strip()
    if answer == "0":
        return None
    return answer or "auto"


def add_provider_wizard(reg):
    clear_console()
    print(t("api_add_title"))
    print(t("api_cancel_hint"))
    kind = input(t("api_kind_prompt")).strip()
    if kind == "0":
        print(t("api_canceled"))
        return
    if kind not in ("1", "2"):
        print(t("invalid_choice"))
        return
    online = kind == "2"
    keys = []

    if online:
        name = _ask_or_cancel(t("api_name_prompt"))
        if name is None:
            print(t("api_canceled"))
            return
        if not name:
            name = t("api_online")
        base_url = ""
        while not base_url:
            base_url = _ask_or_cancel(t("api_base_prompt").format(default="")) or ""
            if base_url is None:
                print(t("api_canceled"))
                return
            if not base_url:
                print(t("api_need_url"))
        keys_raw = _ask_or_cancel(t("api_keys_prompt"), "") or ""
        keys = [key.strip() for key in re.split(r"[,\s]+", keys_raw) if key.strip()]
        model = _pick_model(base_url, online=True)
        if model is None:
            print(t("api_canceled"))
            return
    else:
        print(t("api_local_presets"))
        print(f"1) {t('api_preset_lmstudio')} — http://localhost:1234/v1")
        print(f"2) {t('api_preset_ollama')} — http://localhost:11434/v1")
        print(f"3) {t('api_preset_custom')}")
        preset = input("> ").strip()
        if preset == "0":
            print(t("api_canceled"))
            return
        if preset == "1":
            name, base_url = t("api_preset_lmstudio"), "http://localhost:1234/v1"
        elif preset == "2":
            name, base_url = t("api_preset_ollama"), "http://localhost:11434/v1"
        elif preset == "3":
            name = _ask_or_cancel(t("api_name_prompt"))
            if name is None:
                print(t("api_canceled"))
                return
            if not name:
                name = t("api_local")
            base_url = _ask_or_cancel(
                t("api_base_prompt").format(default="http://localhost:1234/v1"),
                "http://localhost:1234/v1",
            )
            if base_url is None:
                print(t("api_canceled"))
                return
        else:
            print(t("invalid_choice"))
            return
        # A local server needs no keys and usually serves exactly its loaded models.
        model = _pick_model(base_url, online=False)
        if model is None:
            print(t("api_canceled"))
            return

    provider = {
        "id": profile_slug(name, [p["id"] for p in reg["providers"]]),
        "name": name,
        "kind": "openai",
        "auth": online,
        "base_url": base_url,
        "api_keys": keys,
        "model": model or "auto",
    }
    reg["providers"].append(provider)
    save_provider_registry(reg)
    print(t("api_added").format(name=name))
    if confirm(t("api_make_active")):
        reg["active"] = provider["id"]
        save_provider_registry(reg)


def edit_provider_menu(reg, provider):
    while True:
        clear_console()
        print(t("api_edit_title").format(name=provider["name"]))
        print(f"base URL: {provider.get('base_url') or '—'}")
        print(f"{t('api_edit_model')}: {provider.get('model', 'auto')}")
        keys = provider.get("api_keys", [])
        if provider.get("auth"):
            if keys:
                print(t("api_keys_current").format(n=len(keys)))
                for index, key in enumerate(keys, start=1):
                    print(f"  {index}) {_mask_key(key)}")
            else:
                print(t("api_no_keys"))
        print(f"\n1) {t('api_edit_name')}")
        print(f"2) {t('api_edit_base')}")
        print(f"3) {t('api_edit_model')}")
        if provider.get("auth"):
            print(f"4) {t('api_edit_addkeys')}")
            print(f"5) {t('api_edit_delkey')}")
        print(f"6) {t('api_edit_active')}")
        print(f"7) {t('api_backup_item')}")
        print(f"0) {t('back')}")
        choice = input(f"\n{t('menu_choice')}").strip()

        if choice == "0":
            return
        if choice == "1":
            answer = input(t("api_enter_new")).strip()
            if answer:
                provider["name"] = answer
        elif choice == "2":
            answer = input(t("api_enter_new")).strip()
            if answer:
                provider["base_url"] = answer
        elif choice == "3":
            answer = _pick_model(provider.get("base_url"), online=bool(provider.get("auth")))
            if answer is None:
                continue
            provider["model"] = answer
        elif choice == "4" and provider.get("auth"):
            answer = input(t("api_keys_prompt")).strip()
            new_keys = [key.strip() for key in re.split(r"[,\s]+", answer) if key.strip()]
            if new_keys:
                provider.setdefault("api_keys", []).extend(new_keys)
                print(t("api_added_keys").format(n=len(new_keys)))
        elif choice == "5" and provider.get("auth"):
            if not keys:
                print(t("api_no_keys"))
                continue
            answer = input(t("remove_prompt")).strip()
            if answer.isdigit() and 1 <= int(answer) <= len(keys):
                keys.pop(int(answer) - 1)
        elif choice == "6":
            reg["active"] = provider["id"]
            print(t("api_now_active").format(name=provider["name"]))
        elif choice == "7":
            if provider["id"] == reg.get("active"):
                print(t("api_backup_same"))
            elif reg.get("backup") == provider["id"]:
                reg["backup"] = None
                print(t("api_backup_cleared"))
            else:
                reg["backup"] = provider["id"]
                print(t("api_backup_set").format(name=provider["name"]))
        else:
            print(t("invalid_choice"))
            continue
        save_provider_registry(reg)


def delete_provider_menu(reg):
    active = get_active_provider(reg)
    for index, provider in enumerate(reg["providers"], start=1):
        mark = "●" if active and provider["id"] == active["id"] else " "
        print(f"{mark} {index}) {provider['name']} — {provider.get('model', 'auto')}")
    answer = input(t("api_pick")).strip()
    if not answer.isdigit() or not 1 <= int(answer) <= len(reg["providers"]):
        print(t("invalid_choice"))
        return
    provider = reg["providers"][int(answer) - 1]
    if not confirm(t("api_delete_confirm").format(name=provider["name"])):
        return
    reg["providers"].remove(provider)
    if reg.get("active") == provider["id"] and reg["providers"]:
        reg["active"] = reg["providers"][0]["id"]
    if reg.get("backup") == provider["id"]:
        reg["backup"] = None
    save_provider_registry(reg)
    print(t("api_deleted"))


def api_providers_menu():
    while True:
        clear_console()
        reg = load_provider_registry()
        active = get_active_provider(reg)
        backup = get_backup_provider(reg)
        lines = []
        for index, provider in enumerate(reg["providers"], start=1):
            if active and provider["id"] == active["id"]:
                mark = "●"
            elif backup and provider["id"] == backup["id"]:
                mark = "○"
            else:
                mark = " "
            kind = t("api_online") if provider.get("auth") else t("api_local")
            extra = f" ({t('api_keys_count').format(n=len(provider.get('api_keys', [])))})" \
                if provider.get("auth") else ""
            lines.append(f"{mark} {index}) {provider['name']} [{kind}] — "
                         f"{provider.get('model', 'auto')}{extra}")
        show_menu(t("api_title"), lines, [t("api_legend")])
        print(f"\n1) {t('api_add_item')}")
        print(f"2) {t('api_edit_item')}")
        print(f"3) {t('api_delete_item')}")
        print(f"0) {t('back')}")
        choice = input(f"\n{t('menu_choice')}").strip()

        if choice == "0":
            return
        if choice == "1":
            add_provider_wizard(reg)
        elif choice == "2":
            print(t("api_pick"))
            for index, provider in enumerate(reg["providers"], start=1):
                print(f"  {index}) {provider['name']}")
            answer = input(t("menu_choice")).strip()
            if answer.isdigit() and 1 <= int(answer) <= len(reg["providers"]):
                edit_provider_menu(reg, reg["providers"][int(answer) - 1])
            else:
                print(t("invalid_choice"))
        elif choice == "3":
            delete_provider_menu(reg)
        else:
            print(t("invalid_choice"))


def settings_menu(profile, profiles, youtube=None):
    while True:
        clear_console()
        if profile and (profile.get("channel_title") or profile.get("display_name")):
            channel = profile.get("channel_title") or profile.get("display_name")
            title = t("settings_title").format(channel=channel)
        else:
            title = t("settings_title_no_channel")
        options = [f"1) {t('settings_interface')}"]
        if profile:
            options += [f"2) {t('settings_translations')}",
                        f"3) {t('settings_playlists')}",
                        f"4) {t('menu_schedule')}"]
        options.append(f"0) {t('back')}")
        show_menu(title, options)
        choice = input(t("menu_choice")).strip()
        if choice == "0":
            return
        if choice == "1":
            interface_menu()
        elif choice == "2" and profile:
            translations_menu(profile, profiles)
        elif choice == "3" and profile:
            playlists_menu(profile, profiles, youtube)
        elif choice == "4" and profile:
            schedule_menu(profile, profiles)
        else:
            print(t("invalid_choice"))


# ---------------------------------------------------------------------------
# Main menus
# ---------------------------------------------------------------------------


def profile_is_ready(profile):
    """A profile is configured once it has translation languages and a translator key."""
    return bool(profile) and bool(get_profile_languages(profile)) and translator_ready()


def setup_issues(profile):
    """Precise list of what blocks the Translation item: [("languages"|"provider", text)]."""
    issues = []
    if not profile or not get_profile_languages(profile):
        issues.append(("languages", t("setup_no_languages")))
    if not translator_ready():
        issues.append(("provider", t("setup_no_provider")))
    return issues


def _is_quota(error):
    return "quotaExceeded" in str(error)


def load_calendar(profile):
    """Per-profile publishing calendar; created empty when missing."""
    calendar_rel = profile["publ_calendar_file"]
    if not os.path.exists(data_file_path(calendar_rel)):
        save_json_file(calendar_rel, {})
    return load_json_file(calendar_rel)


def run_localization(metadata, profile, parts=("title", "description")):
    """Translate metadata into the profile's languages and save localizations.json."""
    try:
        localizations = load_json_file(LOCALIZATIONS_FILE)
    except FileNotFoundError:
        localizations = {}
    if clean_existing_series_footers(localizations, metadata["description"]):
        save_json_file(LOCALIZATIONS_FILE, localizations)
    target_languages = get_profile_languages(profile)
    if not target_languages:
        print(t("languages_none"))
        return False
    print(t("translating").format(n=len(target_languages)))
    try:
        localize_metadata_via_llm(metadata, target_languages, parts)
    except Exception as error:
        print(f"\n{t('localization_failed')}: {error}")
        return False
    return True


def apply_translations(youtube, profile, video_id, metadata, localizations):
    """Update the video, offer the default playlists and deferred publishing."""
    try:
        updated = update_video_metadata(
            youtube, video_id,
            metadata.get("title"), metadata.get("description"), localizations,
        )
    except HttpError as error:
        print(t("quota_exceeded") if _is_quota(error) else f"❌ {error}")
        return
    if not updated:
        return
    print(t("video_updated").format(id=video_id))
    defaults = profile.get("default_playlists", [])
    if defaults and _ui.get("ask_playlists", True) and confirm(t("add_to_defaults_q")):
        added = 0
        for pl_id in defaults:
            try:
                add_video_to_playlist(youtube, video_id, pl_id)
                added += 1
            except HttpError as error:
                print(t("quota_exceeded") if _is_quota(error) else f"❌ {error}")
                break
        print(t("added_to_playlists").format(n=added))
    if _ui.get("ask_schedule", True) and confirm(t("schedule_q")):
        try:
            publ_calendar = load_calendar(profile)
            publish_datetime, publish_time = ask_publish_date(publ_calendar)
            if set_publishAt(youtube, video_id, publish_datetime):
                print(t("schedule_done").format(
                    id=video_id,
                    date=publish_datetime.strftime("%d.%m.%Y %H:%M"),
                    time=publish_time))
        except HttpError as error:
            print(t("quota_exceeded") if _is_quota(error) else f"❌ {error}")


def _pick_translation_targets(videos, shorts, lives, mode):
    """Video ids for a translation mode: (last|all) x (long|short|live|specific).

    Shorts is the set computed by get_channel_videos: duration <= 180s AND a
    vertical thumbnail — everything else is a long video. Lives is the list of
    currently-live and scheduled stream/premiere items."""
    if mode in ("last_live", "all_live"):
        ids = [item["snippet"]["resourceId"]["videoId"] for item in lives]
        return ids[:1] if mode == "last_live" else ids
    if mode == "last_long":
        for item in videos:
            video_id = item["snippet"]["resourceId"]["videoId"]
            if video_id not in shorts:
                return [video_id]
        return []
    if mode == "last_short":
        for item in videos:
            video_id = item["snippet"]["resourceId"]["videoId"]
            if video_id in shorts:
                return [video_id]
        return []
    if mode in ("all_long", "all_short"):
        want_short = mode == "all_short"
        return [
            item["snippet"]["resourceId"]["videoId"]
            for item in videos
            if (item["snippet"]["resourceId"]["videoId"] in shorts) == want_short
        ]
    return []


def _ask_parts_screen(context):
    """Full-screen 'what do we translate' choice; None = back."""
    while True:
        clear_console()
        print(f"\n{context}\n")
        print(t("parts_menu_title"))
        print(f"1) {t('parts_all')}")
        print(f"2) {t('parts_titles')}")
        print(f"3) {t('parts_descs')}")
        print(f"0) {t('back')}")
        choice = input(f"\n{t('menu_choice')}").strip()
        if choice == "0":
            return None
        if choice == "1":
            return ("title", "description")
        if choice == "2":
            return ("title",)
        if choice == "3":
            return ("description",)
        print(t("invalid_choice"))


def _ask_source_screen(context):
    """Full-screen source choice; returns 'video' | 'manual' | None (back)."""
    while True:
        clear_console()
        print(f"\n{context}\n")
        print(t("source_menu_title"))
        print(f"1) {t('source_from_video')}")
        print(f"2) {t('source_manual')}")
        print(f"0) {t('back')}")
        choice = input(f"\n{t('menu_choice')}").strip()
        if choice == "0":
            return None
        if choice == "1":
            return "video"
        if choice == "2":
            return "manual"
        print(t("invalid_choice"))


def _ask_manual_title(context):
    """Manual title screen; None = back, empty string = keep the video's title."""
    while True:
        clear_console()
        print(f"\n{context}\n")
        answer = input(t("source_title_prompt")).strip()
        if answer == "0":
            return None
        return answer


def _ask_manual_description(context, metadata):
    """Manual description screen; None = back, otherwise metadata is updated."""
    while True:
        clear_console()
        print(f"\n{context}\n")
        print(f"1) {t('source_desc_editor')}")
        print(f"2) {t('source_desc_keep')}")
        print(f"0) {t('back')}")
        choice = input(f"\n{t('menu_choice')}").strip()
        if choice == "0":
            return None
        if choice == "1":
            try:
                desc = get_description_from_dialog()
            except Exception:
                return None
            if desc and desc.strip():
                metadata["description"] = normalize_description(desc)
            return metadata
        if choice == "2":
            return metadata
        print(t("invalid_choice"))


def _translate_one(youtube, profile, video_id, context, parts=None, ask_source=True):
    """Fetch metadata, ask parts/source on their own screens, localize, apply back."""
    try:
        metadata = fetch_video_source_metadata(youtube, video_id)
    except (ValueError, HttpError) as error:
        print(t("quota_exceeded") if _is_quota(error) else f"❌ {error}")
        return False
    print(t("metadata_fetched").format(
        title=metadata["title"], n=len(metadata["description"])))

    if parts is None:
        parts = _ask_parts_screen(context)
        if parts is None:
            return False

    if ask_source:
        source = _ask_source_screen(context)
        if source is None:
            return False
        if source == "manual":
            title = _ask_manual_title(context)
            if title is None:
                return False
            if title:
                metadata["title"] = title
            if _ask_manual_description(context, metadata) is None:
                return False

    save_json_file(METADATA_FILE, metadata)
    if not run_localization(metadata, profile, parts):
        return False
    localizations = load_json_file(LOCALIZATIONS_FILE)
    apply_translations(youtube, profile, video_id, metadata, localizations)
    return True


def translation_menu(youtube, profile, profiles):
    try:
        videos, durations, shorts, lives = get_channel_videos(youtube)
    except HttpError as error:
        print(t("quota_exceeded") if _is_quota(error) else f"❌ {error}")
        return
    if not videos:
        print(t("no_videos"))
        return
    videos.sort(key=lambda x: x["snippet"]["publishedAt"], reverse=True)
    lives.sort(key=lambda x: x["snippet"]["publishedAt"], reverse=True)

    while True:
        clear_console()
        show_menu(t("tr_menu_title"), [
            f"1) {t('tr_last')}",
            f"2) {t('tr_specific')}",
            f"3) {t('tr_all')}",
            f"0) {t('back')}",
        ])
        choice = input(t("menu_choice")).strip()

        if choice == "0":
            return
        if choice == "1":
            # Last video: pick long or short
            while True:
                clear_console()
                show_menu(t("tr_last_title"), [
                    f"1) {t('tr_long')}",
                    f"2) {t('tr_short')}",
                    f"0) {t('back')}",
                ])
                pick = input(t("menu_choice")).strip()
                if pick == "0":
                    break
                mode = "last_long" if pick == "1" else "last_short"
                targets = _pick_translation_targets(videos, shorts, lives, mode)
                if not targets:
                    print(t("tr_no_matches"))
                    continue
                context = t("tr_last_title")
                if not _translate_one(youtube, profile, targets[0], context):
                    continue
                input(t("press_enter"))
        elif choice == "2":
            clear_console()
            print(f"\n{t('tr_specific_title')}\n")
            context = t("tr_specific_title")
            while True:
                link = input(t("video_link_prompt")).strip()
                if link in ("0", ""):
                    break
                video_id = extract_video_id(link)
                if not video_id:
                    print(t("bad_video_link"))
                    continue
                _translate_one(youtube, profile, video_id, context)
        elif choice == "3":
            # All videos: longs or shorts in one batch
            while True:
                clear_console()
                show_menu(t("tr_all_title"), [
                    f"1) {t('tr_longs')}",
                    f"2) {t('tr_shorts')}",
                    f"0) {t('back')}",
                ])
                pick = input(t("menu_choice")).strip()
                if pick == "0":
                    break
                mode = "all_long" if pick == "1" else "all_short"
                targets = _pick_translation_targets(videos, shorts, lives, mode)
                if not targets:
                    print(t("tr_no_matches"))
                    continue
                if not confirm(t("tr_batch_confirm").format(n=len(targets))):
                    continue
                context = t("tr_all_title")
                parts = _ask_parts_screen(context)
                if parts is None:
                    continue
                done = 0
                for video_id in targets:
                    if _translate_one(youtube, profile, video_id, context,
                                      parts=parts, ask_source=False):
                        done += 1
                print(t("tr_done").format(n=done))
                input(t("press_enter"))
        else:
            print(t("invalid_choice"))


def add_to_playlist_menu(youtube, profile, profiles):
    defaults = profile.get("default_playlists", [])
    if not defaults:
        print(t("defaults_missing"))
        return
    names = {pl["id"]: pl["name"] for pl in profile.get("playlists", [])}
    clear_console()
    print(t("playlist_add_title"))
    for pl_id in defaults:
        print(f"  ★ {names.get(pl_id, pl_id)} — {pl_id}")
    while True:
        link = input(t("video_link_prompt")).strip()
        if link in ("0", ""):
            return
        video_id = extract_video_id(link)
        if not video_id:
            print(t("bad_video_link"))
            continue
        added = 0
        for pl_id in defaults:
            try:
                add_video_to_playlist(youtube, video_id, pl_id)
                added += 1
            except HttpError as error:
                print(t("quota_exceeded") if _is_quota(error) else f"❌ {error}")
                return
        print(t("added_to_playlists").format(n=added))
        if not confirm(t("more_videos")):
            return


def scheduled_publish_menu(youtube, profile, profiles):
    clear_console()
    print(t("schedule_flow_title"))
    while True:
        link = input(t("video_link_prompt")).strip()
        if link in ("0", ""):
            return
        video_id = extract_video_id(link)
        if not video_id:
            print(t("bad_video_link"))
            continue
        publ_calendar = load_calendar(profile)
        publish_datetime, publish_time = ask_publish_date(publ_calendar)
        if set_publishAt(youtube, video_id, publish_datetime):
            print(t("schedule_done").format(
                id=video_id,
                date=publish_datetime.strftime("%d.%m.%Y %H:%M"),
                time=publish_time))
        if not confirm(t("more_videos")):
            return


def show_menu(title, options, footers=()):
    """Uniform menu screen: air above/below the title and the option list."""
    print(f"\n{title}\n")
    for option in options:
        print(option)
    print()
    for footer in footers:
        print(footer)


def show_menu(title, options, footers=()):
    """Uniform menu screen: air above/below the title and the option list."""
    print(f"\n{title}\n")
    for option in options:
        print(option)
    print()
    for footer in footers:
        print(footer)


def _pl_target_screen(context, profile, youtube=None):
    """Full-screen 'which playlist?' choice; returns ids or None (back)."""
    while True:
        playlists = profile.setdefault("playlists", [])
        defaults = profile.get("default_playlists", [])
        names = {pl["id"]: pl["name"] for pl in playlists}
        show_menu(context, [
            f"1) {t('pl_target_default')}",
            *(f"   ★ {names.get(pl_id, pl_id)} — {pl_id}" for pl_id in defaults),
            f"2) {t('pl_target_pick')}",
            f"3) {t('playlist_edit')}",
            f"0) {t('back')}",
        ])
        choice = input(t("menu_choice")).strip()
        if choice == "0":
            return None
        if choice == "1":
            if not defaults:
                print(t("defaults_missing"))
                continue
            return list(defaults)
        if choice == "2":
            if not playlists:
                print(t("playlist_none"))
                continue
            labels = [f"{pl['name']} — {pl['id']}" for pl in playlists]
            chosen = interactive_checkbox(
                t("pl_target_pick"), labels,
                {index for index, pl in enumerate(playlists) if pl["id"] in defaults},
            )
            ids = [playlists[index]["id"] for index in sorted(chosen)]
            if not ids:
                print(t("pl_none_selected"))
                continue
            return ids
        if choice == "3":
            playlists_menu(profile, profile and {"profiles": []}, youtube)
        else:
            print(t("invalid_choice"))


def _add_video_to_playlists(youtube, video_id, pl_ids):
    """Add one video to every playlist; returns how many succeeded."""
    added = 0
    for pl_id in pl_ids:
        try:
            add_video_to_playlist(youtube, video_id, pl_id)
            added += 1
        except HttpError as error:
            print(t("quota_exceeded") if _is_quota(error) else f"❌ {error}")
            return added
    return added


def add_to_playlist_menu(youtube, profile, profiles):
    try:
        videos, durations, shorts, lives = get_channel_videos(youtube)
    except HttpError as error:
        print(t("quota_exceeded") if _is_quota(error) else f"❌ {error}")
        return
    if not videos:
        print(t("no_videos"))
        return
    videos.sort(key=lambda x: x["snippet"]["publishedAt"], reverse=True)
    lives.sort(key=lambda x: x["snippet"]["publishedAt"], reverse=True)

    while True:
        show_menu(t("pl_menu_title"), [
            f"1) {t('tr_last')}",
            f"2) {t('tr_specific')}",
            f"3) {t('tr_all')}",
            f"0) {t('back')}",
        ])
        choice = input(t("menu_choice")).strip()

        if choice == "0":
            return
        if choice == "1":
            while True:
                show_menu(t("pl_last_title"), [
                    f"1) {t('tr_long')}",
                    f"2) {t('tr_short')}",
                    f"0) {t('back')}",
                ])
                pick = input(t("menu_choice")).strip()
                if pick == "0":
                    break
                mode = "last_long" if pick == "1" else "last_short"
                targets = _pick_translation_targets(videos, shorts, lives, mode)
                if not targets:
                    print(t("tr_no_matches"))
                    continue
                pl_ids = _pl_target_screen(t("pl_last_title"), profile, youtube)
                if not pl_ids:
                    continue
                print(t("added_to_playlists").format(
                    n=_add_video_to_playlists(youtube, targets[0], pl_ids)))
        elif choice == "2":
            while True:
                link = input(t("video_link_prompt")).strip()
                if link in ("0", ""):
                    break
                video_id = extract_video_id(link)
                if not video_id:
                    print(t("bad_video_link"))
                    continue
                pl_ids = _pl_target_screen(t("pl_specific_title"), profile, youtube)
                if not pl_ids:
                    continue
                print(t("added_to_playlists").format(
                    n=_add_video_to_playlists(youtube, video_id, pl_ids)))
        elif choice == "3":
            while True:
                show_menu(t("pl_all_title"), [
                    f"1) {t('tr_longs')}",
                    f"2) {t('tr_shorts')}",
                    f"0) {t('back')}",
                ])
                pick = input(t("menu_choice")).strip()
                if pick == "0":
                    break
                mode = "all_long" if pick == "1" else "all_short"
                targets = _pick_translation_targets(videos, shorts, lives, mode)
                if not targets:
                    print(t("tr_no_matches"))
                    continue
                if not confirm(t("tr_batch_confirm").format(n=len(targets))):
                    continue
                pl_ids = _pl_target_screen(t("pl_all_title"), profile, youtube)
                if not pl_ids:
                    continue
                done = 0
                for video_id in targets:
                    done += _add_video_to_playlists(youtube, video_id, pl_ids)
                print(t("tr_done").format(n=done))
        else:
            print(t("invalid_choice"))


def profile_menu(profile, profiles, youtube=None):
    while True:
        clear_console()
        header = t("menu_greeting").format(name=_ui["user_name"])
        ready = profile_is_ready(profile)
        if youtube is None:
            header += "\n\n" + t("no_auth_hint")
        else:
            for _, issue in setup_issues(profile):
                header += f"\n\n⚡ {issue}"

        show_menu(header, [
            f"1) {t('menu_translation')}",
            f"2) {t('menu_playlist')}",
            f"3) {t('menu_schedule')}",
            f"4) {t('menu_settings')}",
            f"5) {t('menu_switch_profile')}",
            f"0) {t('menu_exit')}",
        ])
        choice = input(t("menu_choice")).strip()
        if choice == "0":
            return
        if choice == "1":
            if youtube is None:
                print(t("no_auth_hint"))
            elif not ready:
                for _, issue in setup_issues(profile):
                    print(f"⚡ {issue}")
            else:
                translation_menu(youtube, profile, profiles)
        elif choice == "2":
            if youtube is None:
                print(t("no_auth_hint"))
            else:
                add_to_playlist_menu(youtube, profile, profiles)
        elif choice == "3":
            if youtube is None:
                print(t("no_auth_hint"))
            else:
                scheduled_publish_menu(youtube, profile, profiles)
        elif choice == "4":
            settings_menu(profile, profiles, youtube)
        elif choice == "5":
            return "switch"
        else:
            print(t("invalid_choice"))


def _authorize(profile, profiles):
    """Authorize a profile; returns the youtube service or None on failure."""
    try:
        print(t("auth_opening_browser"))
        youtube = authenticate(profile)
        refresh_profile_identity(youtube, profile, profiles)
        print(t("auth_success").format(channel=profile.get("channel_title")))
        time.sleep(1.5)  # a beat to read the success line, then straight to the menu
        return youtube
    except Exception as error:
        print(t("auth_failed").format(error=error))
        input(t("press_enter"))
        return None


def main():
    restore_ui_settings()
    profiles = load_channel_profiles()
    for existing_profile in profiles["profiles"]:
        migrated_playlists = migrate_playlist_model(existing_profile)
        if migrate_profile_paths(existing_profile) or migrated_playlists:
            save_channel_profiles(profiles)
    secrets_files = ensure_secrets()

    while True:
        profile = None
        youtube = None
        if profiles["profiles"]:
            profile = select_profile(profiles)
        elif secrets_files:
            profile = create_profile_wizard(profiles, secrets_files)

        if profile is None:
            # No profile yet (secrets skipped) — settings-only menu, may come back.
            if profile_menu(None, profiles, None) != "switch":
                return
            secrets_files = ensure_secrets()
            continue

        youtube = _authorize(profile, profiles)
        if youtube is not None:
            for issue_kind, issue in setup_issues(profile):
                print(f"\n⚡ {issue}")
                if confirm(t("setup_fix_now")):
                    if issue_kind == "languages":
                        manage_profile_languages(profile, profiles)
                    else:
                        api_providers_menu()

        if profile_menu(profile, profiles, youtube) != "switch":
            return


if __name__ == "__main__":
    main()
