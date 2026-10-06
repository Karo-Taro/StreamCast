> **Язык:** Русский (текущий) · [English](README.en.md)

# StreamCast

Self-hosted панель для круглосуточных (24/7) стримов. Загрузи набор видео,
выстрой их в очередь — и StreamCast бесконечно крутит их в прямой эфир на YouTube
(или на любой RTMP-приёмник). Получается «живой» канал, который работает вечно и
без твоего участия.

Софт рассчитан на **одного владельца**. При первом запуске система предложит установить безопасный пароль. Все стримы принадлежат одному администратору — без лишней регистрации и биллинга.


## Особенности панели управления

- **Мониторинг ресурсов**: загрузка CPU и RAM сервера в реальном времени.
- **Гибкое управление хранилищами**: любое подключённое хранилище можно назначить
  основным; при нехватке места загрузки и энкодинг автоматически уходят на другие.
- **Режимы качества**: Max quality / Balanced / Max performance — очередь
  перезакодируется в фоне при переключении.
- **Быстрая загрузка**: чекбокс «файл уже энкодирован» пропускает ffmpeg —
  подготовленные локальным энкодером файлы попадают в очередь мгновенно.
- **Музыкальные стримы**: зацикленное видео-фоном + аудиоплейлист с миксом и
  лимитером.
- **Локализация метаданных**: автоперевод названия и описания на 90+ языков
  (см. раздел ниже).
- **Аккаунты и роли**: мастер-пароль + воркеры с правами на свои потоки.
- **Автовосстановление**: watchdog перезапускает ffmpeg; упавшие с сервером
  трансляции сами выходят в эфир после рестарта (с непрерывным аптаймом).


## Как это работает

1. **Загрузка** видео в стрим. Каждый файл встаёт в очередь на кодирование.
2. Фоновый воркер **нормализует** каждый ролик в единый формат
   (1080p, 30fps, ключевые кадры каждые 2 секунды, звук AAC). Именно это делает
   24/7-цикл бесшовным — клипы уже идентичны, и при воспроизведении их не нужно
   перекодировать.
3. **Выход в эфир** — один процесс `ffmpeg` склеивает нормализованные клипы и
   толкает их на YouTube с `-stream_loop -1 -c copy`. Низкая нагрузка на CPU, без рывков.
4. Если `ffmpeg` падает (сбой сети, сброс со стороны YouTube), watchdog
   **перезапускает его** автоматически — канал самовосстанавливается.

Файлы с 60fps и выше отклоняются намеренно — смешение частот кадров ломает
бесшовную склейку.

## Перевод метаданных (локализация)

Встроенный модуль локализации названий и описаний на базе движка
[youtube-metadata-translator](https://github.com/ErrorGone-YT/youtube-metadata-translator)
(лежит в `vendor/youtube-metadata-translator` и обновляется прямо из админки).

**Возможности**

- На странице потока (Edit) — блок **Metadata localization**: источник
  (из видео или вручную), что локализуем (всё / только названия / только описания),
  выбор языков (90+) с пресетами, кнопка **Translate now** с прогрессом и логом.
- Локализации применяются к видео на YouTube через Data API — зрители видят
  название и описание на своём языке.
- Несколько подключённых каналов: для перевода автоматически выбирается канал,
  которому принадлежит видео.
- Автозаполнение: при вставке ссылки на видео поля имени потока, канала и
  источника перевода заполняются актуальными данными.

**Настройка (Админ-панель → Translation)**

1. В Google Cloud Console (проект с включённым **YouTube Data API v3**) создай
   OAuth-клиент типа **Web application** и добавь redirect URI
   `https://твой-домен/oauth2callback` (или задай `STREAMCAST_SITE_URL`).
2. Загрузи скачанный `client_secrets.json` в админке и нажми **Connect** —
   войди в аккаунт канала. Повтори для других каналов при необходимости.
3. Добавь AI-провайдера: LM Studio / Ollama (локально, без ключей) или любой
   OpenAI-совместимый API / Gemini (ключи проверяются кнопкой **Check keys**,
   включая проверку баланса).
4. Настрой параллелизм (по умолчанию «auto» — по числу ключей).

Данные движка (токены, провайдеры, пресеты) хранятся в
`storage/yt_translator_data/` и переживают обновление движка кнопкой
**↻ Update from GitHub**.

## Требования

- **Python 3.10+**
- **ffmpeg + ffprobe 5.0+** в `PATH` (проверка: `ffmpeg -version`)
- YouTube-канал с **включёнными трансляциями**
  (включается на <https://youtube.com/features> — в первый раз активация занимает до 24 часов)

---

## Запуск на localhost (Windows / macOS / Linux)

```bash
# 1. Забрать код и зайти в папку
cd StreamCast

# 2. Создать виртуальное окружение
python -m venv venv
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# 3. Установить зависимости
pip install -r requirements.txt
# Для Linux (production): pip install gunicorn

# 4. Задать пароль (иначе по умолчанию будет "changeme")
#   Windows PowerShell:  $env:STREAMCAST_PASSWORD="my-secret"
#   macOS/Linux:         export STREAMCAST_PASSWORD=my-secret

# 5. Запустить
python app.py
```

Открой <http://127.0.0.1:5000>, войди и создай свой первый стрим.

> Dev-сервер (`python app.py`) годится для локальных тестов. Для настоящего
> постоянного развёртывания используй gunicorn + systemd (см. ниже).

---

## Где взять ключ трансляции YouTube

1. Зайди в **YouTube Studio → Создать → Начать трансляцию**.
2. Выбери **Трансляция** (не «Веб-камера»).
3. В **настройках трансляции** скопируй **Ключ трансляции**
   (вид: `abcd-1234-efgh-5678-ijkl`).
4. Вставь *только этот ключ* в StreamCast при создании стрима. Ingest-URL
   (`rtmp://a.rtmp.youtube.com/live2`) задаётся на стороне сервера.

---

## Развёртывание на VPS (Ubuntu 22.04 / 24.04)

VPS за $5–6/мес (DigitalOcean, Hetzner, Vultr) спокойно тянет несколько
1080p-стримов, потому что перекодирования в реальном времени нет.

### 1. Установить системные пакеты

```bash
sudo apt update
sudo apt install -y python3-venv ffmpeg nginx git
ffmpeg -version   # убедиться, что установлен
```

### 2. Забрать приложение и настроить

```bash
sudo mkdir -p /opt/streamcast
sudo chown $USER:$USER /opt/streamcast
cd /opt/streamcast
# скопируй сюда файлы StreamCast (git clone / scp / rsync)

python3 -m venv venv
./venv/bin/pip install -r requirements.txt
```

### 3. Конфигурация

Создай `/opt/streamcast/.env` (см. `.env.example`):

```bash
STREAMCAST_PASSWORD=надёжный-пароль
STREAMCAST_SECRET=$(python3 -c "import secrets;print(secrets.token_hex(32))")
STREAMCAST_STORAGE=/var/lib/streamcast
```

```bash
sudo mkdir -p /var/lib/streamcast
sudo chown $USER:$USER /var/lib/streamcast
```

### 4. Запуск через systemd (постоянно, автоперезапуск при перезагрузке)

Создай `/etc/systemd/system/streamcast.service`:

```ini
[Unit]
Description=StreamCast 24/7 streaming panel
After=network.target

[Service]
User=YOUR_USER
WorkingDirectory=/opt/streamcast
EnvironmentFile=/opt/streamcast/.env
# 2 воркера — уже перебор; стример/энкодер работают фоновыми потоками.
# --timeout 0, чтобы долгие загрузки не обрывались на полпути.
ExecStart=/opt/streamcast/venv/bin/gunicorn \
    --workers 1 --threads 8 --timeout 0 \
    --bind 127.0.0.1:5000 app:app
Restart=always
RestartSec=3

[Install]
WantedBy=multi-user.target
```

> Используй **`--workers 1 --threads 8`**, а не несколько воркеров. Состояние
> стриминга и кодирования живёт внутри процесса; несколько воркер-процессов
> каждый запустили бы свой ffmpeg и передрались бы за одни и те же стримы. Один
> многопоточный воркер — правильный вариант.

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now streamcast
sudo systemctl status streamcast     # проверить, что работает
journalctl -u streamcast -f          # живые логи
```

### 5. Поставить перед ним nginx (с большим лимитом загрузки)

Создай `/etc/nginx/sites-available/streamcast`:

```nginx
server {
    listen 80;
    server_name your-domain-or-ip;

    client_max_body_size 8G;   # разрешить крупные видео-загрузки

    location / {
        proxy_pass http://127.0.0.1:5000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-Proto $scheme;   # чтобы Secure-cookie включалась за HTTPS
        proxy_read_timeout 3600;
        proxy_request_buffering off;   # прокидывать загрузки напрямую
    }
}
```

```bash
sudo ln -s /etc/nginx/sites-available/streamcast /etc/nginx/sites-enabled/
sudo nginx -t && sudo systemctl reload nginx
```

### 6. HTTPS (крайне рекомендуется — ты передаёшь пароль)

```bash
sudo apt install -y certbot python3-certbot-nginx
sudo certbot --nginx -d your-domain.com
```

---

## Заметки по безопасности

- У StreamCast **нет собственного HTTPS и нет ограничения частоты запросов** —
  всегда ставь его за nginx с TLS (шаг 6), прежде чем открывать в интернет. Без
  TLS твой пароль входа идёт открытым текстом.
- Вход — один общий пароль. Выбери надёжный и держи `STREAMCAST_SECRET`
  случайным и в секрете (им подписываются cookie-сессии).
- Относись к ключам трансляции как к секретам — любой, у кого есть твой
  YouTube-ключ, может вещать на твой канал.

## Устранение неполадок

| Симптом | Что делать |
|---|---|
| Видео зависло на `waiting_encode` | Проверь, что `ffmpeg` в PATH; посмотри логи (`journalctl -u streamcast`). |
| Видео в статусе `error` | Наведи на красный тег — увидишь сообщение ffmpeg. Файлы 60fps отклоняются намеренно. |
| Стрим не выходит в эфир | Нужен хотя бы один ролик `completed` и заданный ключ трансляции. |
| Выходит в эфир и сразу отваливается | Проверь баннер «Last error» — обычно неверный/просроченный ключ YouTube. |
| Загрузка не проходит на VPS | Подними `client_max_body_size` в nginx и `STREAMCAST_MAX_UPLOAD_MB`. |

## Справочник по конфигурации

Все настройки — переменные окружения (см. `.env.example`):

| Переменная | По умолчанию | Смысл |
|---|---|---|
| `STREAMCAST_PASSWORD` | `changeme` | Пароль входа (меняется при первом старте) |
| `STREAMCAST_REQUIRE_LOGIN` | `1` | Включить авторизацию (0 — выкл) |
| `STREAMCAST_SECRET` | dev-значение | Ключ подписи cookie-сессий |
| `STREAMCAST_RTMP_BASE` | YouTube live2 | Базовый RTMP-URL приёма |
| `STREAMCAST_STORAGE` | `./storage` | Где лежат загрузки, кодированные файлы и БД |
| `STREAMCAST_WIDTH` / `_HEIGHT` | 1920 / 1080 | Разрешение на выходе |
| `STREAMCAST_FPS` | 30 | Частота кадров на выходе |
| `STREAMCAST_VBITRATE` | 4500k | Битрейт видео |
| `STREAMCAST_MAX_UPLOAD_MB` | 8192 | Максимальный размер загрузки |
| `STREAMCAST_AUTORESUME` | `1` | Автоперезапуск трансляций после рестарта сервера (0 — выкл) |
| `STREAMCAST_SITE_URL` | пусто | Публичный URL панели (база OAuth-редиректа `<URL>/oauth2callback`) |
| `STREAMCAST_MAX_FPS` | 60 | Видео с fps ≥ этого значения отклоняется при загрузке |

---

## Связь

По всем вопросам о софте обращайся к владельцу в Telegram: **<https://t.me/YT_cartell>**