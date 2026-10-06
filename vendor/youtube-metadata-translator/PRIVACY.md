# Политика конфиденциальности / Privacy Policy

**Приложение / Application:** YouTube Metadata Translator
**Разработчик / Developer:** ErrorGone-YT
**Последнее обновление / Last updated:** 2026-10-04

---

## Русский

**1. Как работает приложение.**
YouTube Metadata Translator — локальная программа, которая запускается на компьютере пользователя и через официальный YouTube Data API управляет метаданными (названиями и описаниями) видео его собственного YouTube-канала, а также плейлистами и отложенной публикацией.

**2. Какие данные доступны приложению.**
После входа через OAuth приложение получает доступ к YouTube-аккаунту пользователя в объёме, разрешённом scope `https://www.googleapis.com/auth/youtube.force-ssl`: чтение списка видео и плейлистов канала, изменение названий и описаний видео, добавление видео в плейлисты, установка времени отложенной публикации.

**3. Где хранятся данные.**
Все данные (токены доступа, профили каналов, настройки, кэш переводов) хранятся **только локально** на компьютере пользователя в папке `data/`. Приложение не имеет серверов, не ведёт баз данных и не передаёт токены или данные аккаунта каким-либо третьим лицам.

**4. Передача данных третьим лицам.**
Единственная внешняя передача — тексты названия и описания видео, которые отправляются в выбранный самим пользователем сервис искусственного интеллекта (например, Google Gemini, OpenRouter, Ollama или LM Studio) для перевода. Выбор сервиса и его ключей производит пользователь в настройках приложения. Разработчик приложения эти тексты не получает.

**5. Сбор аналитики.**
Приложение не собирает и не отправляет никакую аналитику, телеметрию или статистику использования.

**6. Отзыв доступа.**
Пользователь может в любой момент отозвать доступ приложения к своему YouTube-аккаунту на странице https://myaccount.google.com/permissions, а также удалить все локальные данные, удалив папку `data/`.

**7. Контакты.**
Вопросы по конфиденциальности: https://github.com/ErrorGone-YT/youtube-metadata-translator/issues

---

## English

**1. How the app works.**
YouTube Metadata Translator is a local application that runs on the user's computer and uses the official YouTube Data API to manage the metadata (titles and descriptions) of videos on the user's own YouTube channel, as well as playlists and deferred publishing.

**2. What data the app can access.**
After OAuth sign-in the app gets access to the user's YouTube account within the scope `https://www.googleapis.com/auth/youtube.force-ssl`: reading the channel's videos and playlists, editing video titles and descriptions, adding videos to playlists, scheduling deferred publishing.

**3. Where data is stored.**
All data (access tokens, channel profiles, settings, translation cache) is stored **locally only** on the user's computer in the `data/` folder. The app has no servers, keeps no databases, and never shares tokens or account data with any third party.

**4. Third-party data transfer.**
The only external transfer is the video title and description text, which is sent to the AI service chosen by the user (e.g. Google Gemini, OpenRouter, Ollama or LM Studio) for translation. The user configures this service and its keys in the app settings. The app developer never receives these texts.

**5. Analytics.**
The app does not collect or send any analytics, telemetry or usage statistics.

**6. Revoking access.**
The user can revoke the app's access to their YouTube account at any time at https://myaccount.google.com/permissions, and remove all local data by deleting the `data/` folder.

**7. Contact.**
Privacy questions: https://github.com/ErrorGone-YT/youtube-metadata-translator/issues
