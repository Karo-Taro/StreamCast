> **Language:** [Русский](README.md) · English (current)

# StreamCast

Self-hosted 24/7 streaming panel. Upload a set of videos, arrange them into a
queue, and StreamCast broadcasts them on an endless loop to YouTube (or any RTMP
target) — a "live" channel that runs forever without you touching it.

It's built for a **single owner**: you log in with one password, and every
stream is yours. No sign-up, no billing, no multi-tenant complexity.


## Dashboard Features

- **System Monitoring**: Real-time CPU and RAM usage tracking.
- **Advanced Storage Management**: Set any connected storage as the default;
  when a disk runs low, uploads and encodes spill over to the others.
- **Quality modes**: Max quality / Balanced / Max performance — the queue is
  re-encoded in the background when you switch.
- **Fast upload**: the "already encoded" checkbox skips ffmpeg — files prepared
  by the local encoder join the queue instantly.
- **Music streams**: a looping background video with an audio playlist, mixer
  and limiter.
- **Metadata localization**: automatic translation of the title and description
  into 90+ languages (see the section below).
- **Accounts & roles**: a master password plus workers scoped to their streams.
- **Self-healing**: a watchdog restarts ffmpeg; streams that were live before a
  server restart go back online automatically (with continuous uptime).


## How it works

1. **Upload** videos to a stream. Every file is queued for encoding.
2. A background worker **normalizes** each clip to one uniform format
   (1080p, 30fps, 2-second keyframes, AAC audio). This is what makes the 24/7
   loop seamless — clips are already identical, so playback needs no re-encoding.
3. **Go live** and one `ffmpeg` process concatenates the normalized clips and
   pushes them to YouTube with `-stream_loop -1 -c copy`. Low CPU, no stutter.
4. If `ffmpeg` dies (network blip, YouTube reset), a watchdog **restarts it**
   automatically so the channel self-heals.

Uploads at 60fps or higher are rejected on purpose — mixing frame rates breaks
seamless concatenation.

## Metadata translation (localization)

Built-in title & description localization powered by the
[youtube-metadata-translator](https://github.com/ErrorGone-YT/youtube-metadata-translator)
engine (vendored at `vendor/youtube-metadata-translator`, updatable right from
the admin panel).

**Features**

- On a stream's Edit page — the **Metadata localization** block: source (from
  the video or manual), what to localize (everything / titles / descriptions),
  90+ languages with presets, and a **Translate now** button with progress and
  a live log.
- Localizations are applied to the YouTube video via the Data API — viewers
  see the title and description in their language.
- Multiple connected channels: the channel owning the video is picked
  automatically for every translation.
- Autofill: pasting a video link fills the stream name, channel name and the
  translation source with the actual data.

**Setup (Admin → Translation)**

1. In Google Cloud Console (a project with **YouTube Data API v3** enabled),
   create an OAuth client of the **Web application** type and add the redirect
   URI `https://your-domain/oauth2callback` (or set `STREAMCAST_SITE_URL`).
2. Upload the downloaded `client_secrets.json` in the admin panel and click
   **Connect** — sign in with the channel's account. Repeat for other channels
   if needed.
3. Add an AI provider: LM Studio / Ollama (local, no keys) or any
   OpenAI-compatible API / Gemini (keys are verified with **Check keys**,
   including a balance check).
4. Set the parallelism ("auto" by default — one thread per API key).

Engine data (tokens, providers, presets) lives in `storage/yt_translator_data/`
and survives engine updates via the **↻ Update from GitHub** button.

## Requirements

- **Python 3.10+**
- **ffmpeg + ffprobe 5.0+** on your `PATH` (`ffmpeg -version` to check)
- A YouTube channel with **live streaming enabled**
  (enable it at <https://youtube.com/features> — takes up to 24h the first time)

---

## Run on localhost (Windows / macOS / Linux)

```bash
# 1. Get the code and enter it
cd StreamCast

# 2. Create a virtualenv
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Install dependencies
pip install -r requirements.txt
# For Linux (production): pip install gunicorn

# 4. Set your password (otherwise it defaults to "changeme")
#   Windows PowerShell:  $env:STREAMCAST_PASSWORD="my-secret"
#   macOS/Linux:         export STREAMCAST_PASSWORD=my-secret

# 5. Run
python app.py
```

Open <http://127.0.0.1:5000>, log in, and create your first stream.

> The dev server (`python app.py`) is fine for testing locally. For a real
> always-on deployment, use gunicorn + systemd as below.

---

## Get your YouTube stream key

1. Go to **YouTube Studio → Create → Go Live**.
2. Choose **Stream** (not "Webcam").
3. Under **Stream settings**, copy the **Stream key**
   (looks like `abcd-1234-efgh-5678-ijkl`).
4. Paste *only that key* into StreamCast when creating a stream. The ingest
   URL (`rtmp://a.rtmp.youtube.com/live2`) is set server-side.

---

## Deploy on a VPS (Ubuntu 22.04 / 24.04)

A $5–6/month VPS (DigitalOcean, Hetzner, Vultr) easily handles several 1080p
streams because there's no real-time transcoding.

### 1. Install system packages

```bash
sudo apt update
sudo apt install -y python3-venv ffmpeg nginx git
ffmpeg -version   # confirm it's installed
```

### 2. Get the app and set it up

```bash
sudo mkdir -p /opt/streamcast
sudo chown $USER:$USER /opt/streamcast
cd /opt/streamcast
# copy your StreamCast files here (git clone / scp / rsync)

python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 3. Configuration

Create `/opt/streamcast/.env` (see `.env.example`):

```bash
STREAMCAST_PASSWORD=a-strong-password
STREAMCAST_SECRET=$(python3 -c "import secrets;print(secrets.token_hex(32))")
STREAMCAST_STORAGE=/var/lib/streamcast
```

```bash
sudo mkdir -p /var/lib/streamcast
sudo chown $USER:$USER /var/lib/streamcast
```

### 4. Run it with systemd (always-on, auto-restart on reboot)

Create `/etc/systemd/system/streamcast.service`:

```ini
[Unit]
Description=StreamCast 24/7 streaming panel
After=network.target

[Service]
User=YOUR_USER
WorkingDirectory=/opt/streamcast
EnvironmentFile=/opt/streamcast/.env
# 2 workers is plenty; the streamer/encoder run as background threads.
# --timeout 0 so long uploads are never killed mid-transfer.
ExecStart=/opt/streamcast/venv/bin/gunicorn \
    --workers 1 --threads 8 --timeout 0 \
    --bind 127.0.0.1:5000 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

> Use **`--workers 1 --threads 8`**, not multiple workers. The streaming and
> encoding state lives in-process; multiple worker processes would each spawn
> their own ffmpeg and fight over the same streams. One threaded worker is
> correct here.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now streamcast
sudo systemctl status streamcast     # check it's running
journalctl -u streamcast -f          # live logs
```

### 5. Put nginx in front (with big upload limit)

Create `/etc/nginx/sites-available/streamcast`:

```nginx
server {
    listen 80;
    server_name your-domain-or-ip;

    client_max_body_size 8G;   # allow large video uploads

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_read_timeout 3600;
        proxy_request_buffering off;   # stream uploads straight through
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/streamcast /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 6. HTTPS (strongly recommended — you're sending a password)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## Security notes

- StreamCast has **no HTTPS and no rate limiting on its own** — always put it
  behind nginx with TLS (step 6) before exposing it to the internet. Without
  TLS, your login password travels in plaintext.
- The login is a single shared password. Choose a strong one and keep
  `STREAMCAST_SECRET` random and private (it signs session cookies).
- Treat stream keys as secrets — anyone with your YouTube stream key can
  broadcast to your channel.

## Troubleshooting

| Symptom | Fix |
|---|---|
| Video stuck on `waiting_encode` | Check `ffmpeg` is on PATH; look at logs (`journalctl -u streamcast`). |
| Video shows `error` | Hover the red tag for the ffmpeg message. 60fps files are rejected by design. |
| Stream won't go live | Needs at least one `completed` video and a stream key set. |
| Goes live then drops | Check the "Last error" banner; usually a wrong/expired YouTube key. |
| Upload fails on VPS | Raise `client_max_body_size` in nginx and `STREAMCAST_MAX_UPLOAD_MB`. |

## Configuration reference

All settings are environment variables (see `.env.example`):

| Variable | Default | Meaning |
|---|---|---|
| `STREAMCAST_PASSWORD` | `changeme` | Login password (changed on first start) |
| `STREAMCAST_REQUIRE_LOGIN` | `1` | Enable authorization (0 = disabled) |
| `STREAMCAST_SECRET` | dev value | Session cookie signing key |
| `STREAMCAST_RTMP_BASE` | YouTube live2 | RTMP ingest base URL |
| `STREAMCAST_STORAGE` | `./storage` | Where uploads, encoded files, and the DB live |
| `STREAMCAST_WIDTH` / `_HEIGHT` | 1920 / 1080 | Output resolution |
| `STREAMCAST_FPS` | 30 | Output frame rate |
| `STREAMCAST_VBITRATE` | 4500k | Video bitrate |
| `STREAMCAST_MAX_UPLOAD_MB` | 8192 | Max upload size |
| `STREAMCAST_AUTORESUME` | `1` | Auto-restart live streams after a server restart (0 to disable) |
| `STREAMCAST_MAX_FPS` | 60 | Videos at or above this fps are rejected on upload |
| `STREAMCAST_SITE_URL` | empty | Public URL of the panel (OAuth redirect base `<URL>/oauth2callback`) |

---

## Contact

For any questions about the software, reach the owner on Telegram: **<https://t.me/YT_cartell>**