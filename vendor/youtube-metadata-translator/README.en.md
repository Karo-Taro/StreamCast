# YouTube Metadata Translator

A tool for YouTube creators: it localizes video titles and descriptions into 90+ languages with an AI model, updates video metadata, adds videos to playlists and schedules deferred publishing. Managed from a **web interface** that runs locally on your machine and opens in your browser.

Works on Windows and macOS. Everything it needs is free or nearly free.

> 🇷🇺 Инструкция на русском: [README.md](README.md)
> 🇺🇦 Інструкція українською: [README.uk.md](README.uk.md)

## What you need (~30 minutes of one-time setup)

1. **Python 3.10 or newer** — the language the tool is written in.
2. A **Google account** that owns the YouTube channel.
3. A **translation provider** — any one of:
   - a local app: **LM Studio** or **Ollama** (free, runs on your machine);
   - an **online OpenAI-compatible API** with keys (e.g. OpenRouter or any aggregator);
   - Google **Gemini** keys from AI Studio (free, used by the console version).
4. Everything else installs itself from `requirements.txt` — including the app window.

## Step 1. Install Python

### Windows

1. Go to https://www.python.org/downloads/ and press the yellow **Download Python 3.x.x** button.
2. Run the installer.
3. **MOST IMPORTANT:** on the first screen check **"Add python.exe to PATH"** (at the bottom).
4. Press **Install Now**.
5. Check: press `Win + R`, type `cmd`, press Enter, then type `python --version`. It should print something like `Python 3.13.1`.

### macOS

1. Go to https://www.python.org/downloads/ — the site offers the right version for Mac. Install it like a normal app.
2. Check: open **Terminal** (Cmd + Space, type "Terminal"), type `python3 --version`.

## Step 2. Install the libraries

Open a terminal in the project folder and run:

```
pip install -r requirements.txt
```

(macOS: `pip3 install -r requirements.txt`)

## Step 3. Create your Google keys (client_secrets) — the longest step

These keys let the tool manage **your** YouTube channel. Done once.

### 3.1. Create a Google Cloud project

1. Go to https://console.cloud.google.com with the Google account of your channel.
2. Top bar → project selector → **New Project**.
3. Name it anything, e.g. `youtube-translator` → **Create**.

### 3.2. Enable the YouTube Data API

1. Menu (☰) → **APIs & Services** → **Library**.
2. Search for `YouTube Data API v3` → open it → press **Enable**.

### 3.3. Configure the OAuth consent screen

1. Menu → **APIs & Services** → **OAuth consent screen** (may be called **Google Auth Platform**).
2. **User Type**: **External** → **Create**.
3. Fill in the minimum: **App name** (anything), **User support email** (your email), **Developer contact email**.
4. Press **Save and Continue** on every step (Scopes can be skipped).

### 3.4. Add emails to Test users — REQUIRED

While the app is in **Testing** mode, Google only lets in **users whose emails you explicitly added**. Otherwise you'll get `Access blocked: access_denied`.

1. In **OAuth consent screen** (or **Google Auth Platform → Audience**) find **Test users**.
2. Press **+ Add Users**.
3. Enter **the email of your channel's Google account** (and the email of anyone else who will use the tool).
4. **Save**.

> ⚠️ In Testing mode the access token lives **7 days**, then you'll be asked to sign in again. Tired of that? Press **Publish App** (on the Audience screen): sign-in then works indefinitely (Google may show an "unverified app" warning; for personal use just press Advanced → Go to the app). Google may ask for a home page and privacy policy — use this repository's links: home page — `https://github.com/ErrorGone-YT/youtube-metadata-translator`, policy — [PRIVACY.md](PRIVACY.md).

### 3.5. Download client_secrets

1. Menu → **APIs & Services** → **Credentials**.
2. **+ Create Credentials** → **OAuth client ID**.
3. **Application type**: **Desktop app** (not Web, not Android!).
4. Name it anything → **Create** → **Download JSON**.
5. Keep the downloaded file — you will pick it in the web interface when adding a channel. No need to rename or move it anywhere.

> 💡 Managing **several channels**? You need **one client_secrets file for all of them** — it belongs to the app, not to a channel. Just add a profile per channel on the **Channels** screen, signing in with the corresponding Google account (its email must be in Test users on the Branding screen). The Google quota is shared across the project.

## Step 4. First run

### Windows

Double-click **Запустить веб-интерфейс (Windows).cmd** — the interface opens in its own app window.

### macOS

1. Open Terminal, type `chmod +x ` (with a trailing space), drag **Запустить веб-интерфейс (Mac).command** into the window, press Enter. One-time only.
2. After that just double-click the file.

### First-launch wizard

1. **Interface language** — Русский / Українська / English.
2. **Your name** — how the tool greets you.
3. On the **Channels** screen press **Add a channel**: enter a name and pick the client_secrets JSON file downloaded in step 3.5.
4. A Google window opens — **sign in to the channel's account**. If Google warns about an unverified app: Advanced → Go to the app.
5. Done — the token is saved in `data/profiles/<channel>/`, no repeated sign-ins.

> The interface lives in its own window (the pywebview engine is already in requirements.txt). Prefer a browser tab? Open `http://127.0.0.1:8765` manually — the server prints the address to the console.

## Step 5. Connect a translation provider

Open **Settings → API providers → Add provider**.

- **Local** — pick the app preset (**LM Studio** or **Ollama**): the address fills in automatically and the model list is fetched from the running app. No keys needed.
- **Online** — enter the base URL (e.g. `https://openrouter.ai/api/v1`), paste your keys (one per line) and choose a model. Keys are stored masked, and the **Check keys** button shows which ones are alive, rate-limited or rejected.

Translations run in parallel across languages; the number of simultaneous translations is set in Settings (Auto works for most cases).

## The screens

| Screen | What it does |
|---|---|
| **Translate** | Takes the actual title/description of a video (latest, specific or all), localizes them into the selected languages with a live progress bar and log, and applies them back. |
| **Playlists** | Manage the channel's playlists and default playlists; add a video to several playlists at once. |
| **Publishing** | Deferred publishing with date and time; edit the per-weekday publishing schedule below. |
| **Channels** | Add channels (with client_secrets upload), sign in, switch the active channel, delete profiles. |
| **Settings** | Interface language, your name, parallel translations, language presets, API providers, translation languages (searchable, localized like on YouTube). |

A translation can be cancelled — already finished languages are kept, nothing further is applied.

## Packaging into a ready app (optional)

Want a single exe without installing Python?

1. `pip install pyinstaller`
2. Windows: run **«Собрать приложение (Windows).cmd»** — the ready file appears in `dist/`.
3. macOS: `pyinstaller --noconfirm --clean --onefile --windowed --name "YouTube Metadata Translator" --icon webui_static/app_icon.icns --add-data "webui_static:webui_static" webui.py` (convert the icon to icns: `sips -s format icns webui_static/app_icon_512.png --out app_icon.icns`).

Data (`data/`) lives next to the built file, so the exe can be copied and moved together with the `data` folder.

## Console version

Prefer the terminal? **Запустить (Windows).cmd** / **Запустить (Mac).command** run the classic console version with the same engine and the same data.

## Files and folders

```
youtube-metadata-translator/
├── yt_metadata_translator.py        ← the engine (console version)
├── webui.py                         ← web interface server
├── webui_static/                    ← web interface files
├── Запустить веб-интерфейс (Windows).cmd  ← launch the web interface (Windows)
├── Запустить веб-интерфейс (Mac).command  ← launch the web interface (macOS)
├── Запустить (Windows).cmd          ← launch the console version (Windows)
├── Запустить (Mac).command          ← launch the console version (macOS)
├── requirements.txt                 ← library list
├── README.md                        ← this guide
└── data/                            ← all data (auto-created)
    ├── local_llm.json               ← translator settings
    ├── api_providers.json           ← translation providers and keys (masked in the UI)
    ├── api_key_status.json          ← key liveness results
    ├── channel_profiles.json        ← channel profiles
    ├── client_secrets*.json         ← Google keys (step 3.5)
    ├── metadata.json                ← last translated title/description
    ├── localizations.json           ← last set of translations
    ├── ui_settings.json             ← interface language, your name, presets
    └── profiles/<channel>/          ← Google token and publishing calendar per channel
```

Enjoy! 🧙

---

License: [MIT](LICENSE) — free to use, modify and distribute.
