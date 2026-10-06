/* YouTube Metadata Translator — web UI logic (vanilla JS, no build step) */
"use strict";

/* ------------------------------ i18n ------------------------------ */

const T = {
  ru: {
    app_title: "YouTube Metadata Translator",
    onboard_sub: "Настроим интерфейс за два шага",
    start: "Начать", your_name: "Твоё имя", your_name_ph: "Как к тебе обращаться?",
    nav_translate: "Перевод", nav_playlists: "Плейлисты", nav_schedule: "Публикация",
    nav_channels: "Каналы", nav_settings: "Настройки",
    save: "Сохранить", cancel: "Отмена", delete: "Удалить", close: "Закрыть",
    saved: "✓ Сохранено", done: "✓ Готово", error: "Ошибка",
    tr_title: "Перевод", tr_mode: "Что переводим",
    mode_last: "Последнее видео", mode_specific: "Конкретные видео", mode_all: "Все видео",
    tr_type: "Тип видео", type_long: "Лонг", type_short: "Шортс", type_live: "Активная трансляция",
    tr_links: "Ссылки на видео (по одной в строке)",
    tr_source: "Название и описание", source_video: "Из видео", source_manual: "Вписать самому",
    manual_title: "Своё название (пусто — оставить с видео)",
    manual_desc: "Своё описание (пусто — оставить с видео)",
    tr_parts: "Что локализуем", parts_all: "Всё", parts_titles: "Только названия",
    parts_descs: "Только описания",
    tr_targets: "Языки перевода", targets_empty: "Языки не выбраны — открой Настройки",
    tr_options: "После перевода", opt_playlists: "Добавлять в плейлисты по умолчанию",
    opt_schedule: "Спросить про отложенную публикацию", sched_date_ph: "Дата ddmmyy",
    tr_start: "Перевести и применить",
    prev_heading: "Что будет переведено", prev_desc: "Описание", prev_none: "Подходящее видео не найдено.",
    warn_not_authorized: "Канал ещё не авторизован — войди на вкладке «Каналы».",
    warn_no_provider: "Не настроен ни один API-провайдер — добавь его в Настройках.",
    job_title: "Идёт перевод", job_video: "Видео", job_progress: "Прогресс",
    job_new: "Новый перевод", job_running_note: "Можно переключиться на другие вкладки — перевод продолжится.",
    pl_title: "Плейлисты", pl_hint: "Плейлисты канала. Отмеченные — по умолчанию: новые видео будут попадать туда автоматически.",
    pl_name_ph: "Название (пусто — взять с YouTube)", pl_link_ph: "Ссылка на плейлист или ID",
    pl_add: "Добавить плейлист", pl_default: "По умолчанию", pl_none: "Плейлистов пока нет.",
    pl_video_title: "Добавить видео в плейлисты", pl_video_ph: "Ссылка на видео или ID",
    pl_pick: "Куда добавить", pl_added: "Добавлено в {n} плейлист(ов)",
    sch_title: "Отложенная публикация", sch_sub: "Видео станет публичным в выбранные дату и время. Если время не выбрать — оно возьмётся из календаря публикаций.",
    sch_link_ph: "Ссылка на видео или ID", sch_date_ph: "Дата ddmmyy",
    sch_set: "Запланировать", sch_ok: "Видео {id} опубликуется {when}", sch_bad: "Некорректная ссылка или дата",
    ch_title: "Каналы", ch_sub: "Выбери активный канал или добавь новый.",
    ch_add: "Добавить канал", ch_select: "Выбрать", ch_selected: "Активный",
    ch_login: "Войти", ch_logging_in: "Входим…", ch_need_langs: "Выбрать языки",
    ch_ready: "Готов", ch_no_token: "Нужен вход", ch_none: "Каналов пока нет — добавь первый.",
    ch_auth_opening: "Откроется окно браузера Google — войди в аккаунт канала…",
    ch_auth_ok: "Авторизовано: {channel}", ch_auth_failed: "Ошибка авторизации",
    ch_name_ph: "Название профиля канала", ch_secrets: "client_secrets JSON от Google Cloud",
    ch_pick_file: "Выбрать файл…", ch_found: "Найдено в data/:", ch_create: "Создать и войти",
    set_title: "Настройки", set_interface: "Интерфейс", set_ui_language: "Язык интерфейса", set_theme: "Тема",
    set_translation: "Перевод", set_parallel: "Одновременных переводов", parallel_auto: "Авто",
    set_ask_playlists: "Питаться про плейлисты после перевода",
    set_ask_schedule: "Спрашивать про отложенную публикацию после перевода",
    set_presets: "Пресеты языков", preset_apply: "Применить", preset_save: "Сохранить текущий",
    preset_delete: "Удалить", preset_name: "Название пресета", no_presets: "Пресетов ещё нет.",
    set_providers: "API-провайдеры", prov_add: "Добавить провайдера",
    prov_active: "активный", prov_backup: "резервный",
    prov_edit: "Изменить", prov_activate: "Сделать активным", prov_backup_btn: "Сделать резервным",
    prov_kind: "Тип", kind_online: "Онлайн", kind_local: "Локальный",
    prov_name: "Отображаемое имя", prov_base: "Base URL",
    prov_model: "Модель", fetch_models: "Получить модели", no_models: "Список не получен — впиши название вручную.",
    need_url: "Для онлайн-провайдера нужен base URL.", need_name: "Впиши имя провайдера.",
    prov_new: "Новый провайдер", prov_edit_title: "Настройка провайдера",
    set_langs: "Языки перевода", search_ph: "Поиск языка…", selected_n: "Выбрано: {n}",
    nothing_found: "Ничего не найдено",
    ch_delete: "Удалить", local_app: "Приложение",
    keys_add: "Добавить ключи", keys_clear: "Очистить все",
    keys_check: "Проверить ключи", keys_unfreeze: "Разморозить все",
    key_ok: "робочий", key_frozen: "в заморозке", key_dead: "сломан",
    keys_help: "Зелёный — ключ отвечает. Синий — упёрся в лимит (заморожен, оживёт сам или через «Разморозить всё»). Красный — сервер его отверг (неверный или отозван). Проверка делает реальный запрос к списку моделей.",
    keys_check_result: "Ключи: {ok} рабочих, {frozen} в заморозке, {dead} сломаны",
    keys_need_save: "Сначала сохрани провайдера",
    manual_title_s: "Название", manual_desc_s: "Описание",
    job_cancel: "Отмена", job_cancelled: "⏹ Отменено. Текущий видео-этап завершится и применение остановится.",
    cal_title: "График публикаций", cal_hint: "Время, которое по умолчанию подставится для отложенной публикации в этот день. Пусто — 10:00.",
    day_Monday: "Понедельник", day_Tuesday: "Вторник", day_Wednesday: "Среда",
    day_Thursday: "Четверг", day_Friday: "Пятница", day_Saturday: "Суббота", day_Sunday: "Воскресенье", theme_dark: "Тёмная", theme_light: "Светлая", job_cancelled: "⏹ Отменено. Текущий видео-этап завершится и применение остановится.", ch_delete_confirm: "Удалить канал «{name}»? Токен входа и календарь будут стёрты.",
    prov_keys: "API-ключи (по одному в строке или через запятую)",
    models_found: "Найдено моделей: {n}",
    quit_confirm: "Закрыть приложение?",
    pick_langs_first: "Сначала выбери языки перевода в Настройках.",
  },
  uk: {
    app_title: "YouTube Metadata Translator",
    onboard_sub: "Налаштуємо інтерфейс за два кроки",
    start: "Почати", your_name: "Ваше ім'я", your_name_ph: "Як до вас звертатися?",
    nav_translate: "Переклад", nav_playlists: "Плейлисти", nav_schedule: "Публікація",
    nav_channels: "Канали", nav_settings: "Налаштування",
    save: "Зберегти", cancel: "Скасувати", delete: "Видалити", close: "Закрити",
    saved: "✓ Збережено", done: "✓ Готово", error: "Помилка",
    tr_title: "Переклад", tr_mode: "Що перекладаємо",
    mode_last: "Останнє відео", mode_specific: "Конкретні відео", mode_all: "Усі відео",
    tr_type: "Тип відео", type_long: "Лонг", type_short: "Шортс", type_live: "Активна трансляція",
    tr_links: "Посилання на відео (по одному в рядку)",
    tr_source: "Назва та опис", source_video: "З відео", source_manual: "Вписати самому",
    manual_title: "Своя назва (порожньо — залишити з відео)",
    manual_desc: "Свій опис (порожньо — залишити з відео)",
    tr_parts: "Що локалізуємо", parts_all: "Усе", parts_titles: "Тільки назви",
    parts_descs: "Тільки описи",
    tr_targets: "Мови перекладу", targets_empty: "Мови не вибрано — відкрийте Налаштування",
    tr_options: "Після перекладу", opt_playlists: "Додавати до плейлистів за замовчуванням",
    opt_schedule: "Питати про відкладену публікацію", sched_date_ph: "Дата ddmmyy",
    tr_start: "Перекласти та застосувати",
    prev_heading: "Що буде перекладено", prev_desc: "Опис", prev_none: "Підходящого відео не знайдено.",
    warn_not_authorized: "Канал ще не авторизований — увійдіть на вкладці «Канали».",
    warn_no_provider: "Не налаштовано жодного API-провайдера — додайте його в Налаштуваннях.",
    job_title: "Триває переклад", job_video: "Відео", job_progress: "Прогрес",
    job_new: "Новий переклад", job_running_note: "Можна перемкнутися на інші вкладки — переклад триватиме.",
    pl_title: "Плейлисти", pl_hint: "Плейлисти каналу. Відмічені — за замовчуванням: нові відео потраплятимуть туди автоматично.",
    pl_name_ph: "Назва (порожньо — взяти з YouTube)", pl_link_ph: "Посилання на плейлист або ID",
    pl_add: "Додати плейлист", pl_default: "За замовчуванням", pl_none: "Плейлистів ще немає.",
    pl_video_title: "Додати відео до плейлистів", pl_video_ph: "Посилання на відео або ID",
    pl_pick: "Куди додати", pl_added: "Додано до {n} плейлист(ів)",
    sch_title: "Відкладена публікація", sch_sub: "Відео стане публічним у вибрані дату й час. Якщо час не вибрати — він візьметься з календаря публікацій.",
    sch_link_ph: "Посилання на відео або ID", sch_date_ph: "Дата ddmmyy",
    sch_set: "Запланувати", sch_ok: "Відео {id} опублікується {when}", sch_bad: "Некоректне посилання або дата",
    ch_title: "Канали", ch_sub: "Виберіть активний канал або додайте новий.",
    ch_add: "Додати канал", ch_select: "Вибрати", ch_selected: "Активний",
    ch_login: "Увійти", ch_logging_in: "Входимо…", ch_need_langs: "Вибрати мови",
    ch_ready: "Готовий", ch_no_token: "Потрібен вхід", ch_none: "Каналів ще немає — додайте перший.",
    ch_auth_opening: "Відкриється вікно браузера Google — увійдіть в акаунт каналу…",
    ch_auth_ok: "Авторизовано: {channel}", ch_auth_failed: "Помилка авторизації",
    ch_name_ph: "Назва профілю каналу", ch_secrets: "client_secrets JSON від Google Cloud",
    ch_pick_file: "Вибрати файл…", ch_found: "Знайдено в data/:", ch_create: "Створити та увійти",
    set_title: "Налаштування", set_interface: "Інтерфейс", set_ui_language: "Мова інтерфейсу", set_theme: "Тема",
    set_translation: "Переклад", set_parallel: "Одночасних перекладів", parallel_auto: "Авто",
    set_ask_playlists: "Питати про плейлисти після перекладу",
    set_ask_schedule: "Питати про відкладену публікацію після перекладу",
    set_presets: "Пресети мов", preset_apply: "Застосувати", preset_save: "Зберегти поточний",
    preset_delete: "Видалити", preset_name: "Назва пресета", no_presets: "Пресетів ще немає.",
    set_providers: "API-провайдери", prov_add: "Додати провайдера",
    prov_active: "активний", prov_backup: "резервний",
    prov_edit: "Змінити", prov_activate: "Зробити активним", prov_backup_btn: "Зробити резервним",
    prov_kind: "Тип", kind_online: "Онлайн", kind_local: "Локальний",
    prov_name: "Ім'я для показу", prov_base: "Base URL",
    prov_model: "Модель", fetch_models: "Отримати моделі", no_models: "Список не отримано — введіть назву вручну.",
    need_url: "Для онлайн-провайдера потрібен base URL.", need_name: "Впишіть ім'я провайдера.",
    prov_new: "Новий провайдер", prov_edit_title: "Налаштування провайдера",
    set_langs: "Мови перекладу", search_ph: "Пошук мови…", selected_n: "Вибрано: {n}",
    nothing_found: "Нічого не знайдено",
    ch_delete: "Видалити", local_app: "Програма",
    keys_add: "Додати ключі", keys_clear: "Очистити всі",
    keys_check: "Чи живі?", keys_unfreeze: "Розморозити всі",
    key_ok: "робочий", key_frozen: "у заморозці", key_dead: "зламаний",
    keys_help: "Зелений — ключ відповідає. Синій — вперся в ліміт (заморожений, оживе сам або через «Розморозити всі»). Червоний — сервер його відхилив (невірний або відкликаний). Перевірка робить реальний запит до списку моделей.",
    keys_check_result: "Ключі: {ok} робочих, {frozen} у заморозці, {dead} зламані",
    keys_need_save: "Спочатку збережіть провайдера",
    manual_title_s: "Назва", manual_desc_s: "Опис",
    job_cancel: "Скасувати", job_cancelled: "⏹ Скасовано. Поточний відео-етап завершиться і застосування зупиниться.",
    cal_title: "Графік публікацій", cal_hint: "Час, який за замовчуванням підставиться для відкладеної публікації в цей день. Порожньо — 10:00.",
    day_Monday: "Понеділок", day_Tuesday: "Вівторок", day_Wednesday: "Середа",
    day_Thursday: "Четвер", day_Friday: "П'ятниця", day_Saturday: "Субота", day_Sunday: "Неділя", theme_dark: "Темна", theme_light: "Світла", job_cancelled: "⏹ Скасовано. Поточний відео-етап завершиться і застосування зупиниться.", ch_delete_confirm: "Видалити канал «{name}»? Токен входу та календар буде стерто.",
    prov_keys: "API-ключі (по одному в рядку або через кому)",
    models_found: "Знайдено моделей: {n}",
    quit_confirm: "Закрити застосунок?",
    pick_langs_first: "Спочатку виберіть мови перекладу в Налаштуваннях.",
  },
  en: {
    app_title: "YouTube Metadata Translator",
    onboard_sub: "Let's set up the interface in two steps",
    start: "Start", your_name: "Your name", your_name_ph: "How should we call you?",
    nav_translate: "Translate", nav_playlists: "Playlists", nav_schedule: "Publishing",
    nav_channels: "Channels", nav_settings: "Settings",
    save: "Save", cancel: "Cancel", delete: "Delete", close: "Close",
    saved: "✓ Saved", done: "✓ Done", error: "Error",
    tr_title: "Translate", tr_mode: "What to translate",
    mode_last: "Latest video", mode_specific: "Specific videos", mode_all: "All videos",
    tr_type: "Video type", type_long: "Long", type_short: "Shorts", type_live: "Live stream",
    tr_links: "Video links (one per line)",
    tr_source: "Title and description", source_video: "From the video", source_manual: "Enter manually",
    manual_title: "Custom title (empty — keep the video's one)",
    manual_desc: "Custom description (empty — keep the video's one)",
    tr_parts: "What to localize", parts_all: "Everything", parts_titles: "Titles only",
    parts_descs: "Descriptions only",
    tr_targets: "Translation languages", targets_empty: "No languages selected — open Settings",
    tr_options: "After translation", opt_playlists: "Add to default playlists",
    opt_schedule: "Ask about deferred publishing", sched_date_ph: "Date ddmmyy",
    tr_start: "Translate and apply",
    prev_heading: "What will be translated", prev_desc: "Description", prev_none: "No matching video found.",
    warn_not_authorized: "The channel is not signed in yet — go to the «Channels» tab.",
    warn_no_provider: "No API provider configured — add one in Settings.",
    job_title: "Translation in progress", job_video: "Video", job_progress: "Progress",
    job_new: "New translation", job_running_note: "You can switch tabs — the translation keeps running.",
    pl_title: "Playlists", pl_hint: "Channel playlists. Checked ones are defaults: new videos will be added there automatically.",
    pl_name_ph: "Name (empty — take from YouTube)", pl_link_ph: "Playlist link or ID",
    pl_add: "Add playlist", pl_default: "Default", pl_none: "No playlists yet.",
    pl_video_title: "Add a video to playlists", pl_video_ph: "Video link or ID",
    pl_pick: "Where to add", pl_added: "Added to {n} playlist(s)",
    sch_title: "Deferred publishing", sch_sub: "The video goes public at the chosen date and time. Leave the time empty and it comes from the publishing calendar.",
    sch_link_ph: "Video link or ID", sch_date_ph: "Date ddmmyy",
    sch_set: "Schedule", sch_ok: "{id} will be published {when}", sch_bad: "Invalid link or date",
    ch_title: "Channels", ch_sub: "Pick the active channel or add a new one.",
    ch_add: "Add a channel", ch_select: "Select", ch_selected: "Active",
    ch_login: "Sign in", ch_logging_in: "Signing in…", ch_need_langs: "Pick languages",
    ch_ready: "Ready", ch_no_token: "Sign-in needed", ch_none: "No channels yet — add the first one.",
    ch_auth_opening: "A Google browser window will open — sign in to the channel's account…",
    ch_auth_ok: "Authorized: {channel}", ch_auth_failed: "Authorization failed",
    ch_name_ph: "Channel profile name", ch_secrets: "client_secrets JSON from Google Cloud",
    ch_pick_file: "Pick a file…", ch_found: "Found in data/:", ch_create: "Create and sign in",
    set_title: "Settings", set_interface: "Interface", set_ui_language: "Interface language", set_theme: "Theme",
    set_translation: "Translation", set_parallel: "Parallel translations", parallel_auto: "Auto",
    set_ask_playlists: "Ask about playlists after translation",
    set_ask_schedule: "Ask about deferred publishing after translation",
    set_presets: "Language presets", preset_apply: "Apply", preset_save: "Save current",
    preset_delete: "Delete", preset_name: "Preset name", no_presets: "No presets yet.",
    set_providers: "API providers", prov_add: "Add provider",
    prov_active: "active", prov_backup: "backup",
    prov_edit: "Edit", prov_activate: "Make active", prov_backup_btn: "Make backup",
    prov_kind: "Type", kind_online: "Online", kind_local: "Local",
    prov_name: "Display name", prov_base: "Base URL",
    prov_model: "Model", fetch_models: "Fetch models", no_models: "Couldn't fetch the list — type the name manually.",
    need_url: "An online provider needs a base URL.", need_name: "Enter a provider name.",
    prov_new: "New provider", prov_edit_title: "Provider settings",
    set_langs: "Translation languages", search_ph: "Search language…", selected_n: "Selected: {n}",
    nothing_found: "Nothing found",
    ch_delete: "Delete", local_app: "App",
    keys_add: "Add keys", keys_clear: "Clear all",
    keys_check: "Check keys", keys_unfreeze: "Unfreeze all",
    key_ok: "working", key_frozen: "frozen", key_dead: "dead",
    keys_help: "Green — the key answers. Blue — hit a rate limit (frozen until the limit resets or you unfreeze all). Red — the server rejected it (invalid or revoked). Checking makes a real request to the models list.",
    keys_check_result: "Keys: {ok} working, {frozen} frozen, {dead} dead",
    keys_need_save: "Save the provider first",
    manual_title_s: "Title", manual_desc_s: "Description",
    job_cancel: "Cancel", job_cancelled: "⏹ Cancelled. The current video stage finishes and nothing more will be applied.",
    cal_title: "Publishing schedule", cal_hint: "The default time for deferred publishing on that day. Empty — 10:00.",
    day_Monday: "Monday", day_Tuesday: "Tuesday", day_Wednesday: "Wednesday",
    day_Thursday: "Thursday", day_Friday: "Friday", day_Saturday: "Saturday", day_Sunday: "Sunday", theme_dark: "Dark", theme_light: "Light", job_cancelled: "⏹ Cancelled. The current video stage finishes and nothing more will be applied.", ch_delete_confirm: "Delete the channel “{name}”? Its sign-in token and calendar will be removed.",
    prov_keys: "API keys (one per line, or comma-separated)",
    models_found: "Found {n} models",
    quit_confirm: "Close the app?",
    pick_langs_first: "Pick translation languages in Settings first.",
  },
};

/* ------------------------------ state ------------------------------ */

const S = {
  ui: {}, profiles: [], catalog: {}, providers: null, provider_online: false,
  parallel: "auto", activeId: null, screen: "translate",
  tr: { mode: "last", type: "long", source: "video", parts: "title,description",
        add_playlists: false, do_schedule: false, schedule_date: "" },
  jobTimer: null, authTimer: null, langSel: new Set(),
};

const AUTH_STATE = { running: false };

const $ = (sel, root) => (root || document).querySelector(sel);
const $$ = (sel, root) => [...(root || document).querySelectorAll(sel)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g,
  (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));

function langName(code) {
  /* Language name in the interface language (like YouTube itself); native as fallback. */
  const table = LANG_LOCALIZED[S.ui.language] || {};
  return table[code] || S.catalog[code] || code;
}

const ddmmyyToISO = (s) => {
  const m = /^(\d{2})(\d{2})(\d{2})$/.exec(s || "");
  return m ? `20${m[3]}-${m[2]}-${m[1]}` : "";
};
const isoToDdmmyy = (s) => {
  const m = /^(\d{4})-(\d{2})-(\d{2})$/.exec(s || "");
  return m ? m[3] + m[2] + m[1].slice(2) : "";
};

function t(key, vars) {
  const lang = S.ui.language in T ? S.ui.language : "en";
  let text = T[lang][key] ?? T.en[key] ?? key;
  if (vars) for (const [k, v] of Object.entries(vars)) text = text.replaceAll(`{${k}}`, v);
  return text;
}

async function api(path, body, method) {
  const res = await fetch(path, {
    method: method || (body === undefined ? "GET" : "POST"),
    headers: body !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  const data = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(data.error || res.statusText);
  return data;
}

function fillAvatar(el) {
  /* Channel logo if it was fetched; the letter is the fallback. */
  const letter = el.dataset.letter || "?";
  const logo = el.dataset.logo;
  if (logo) {
    const img = document.createElement("img");
    img.src = logo;
    img.alt = "";
    img.onerror = () => { el.textContent = letter; };
    el.textContent = "";
    el.append(img);
  } else {
    el.textContent = letter;
  }
}

function toast(text, kind) {  const el = document.createElement("div");
  el.className = "toast " + (kind || "");
  el.textContent = (kind === "fail" ? "❌ " : kind === "ok" ? "" : "") + text;
  $("#toasts").append(el);
  setTimeout(() => { el.classList.add("out"); setTimeout(() => el.remove(), 320); }, 3200);
}

function modal(html) {
  const root = $("#modal_root");
  root.className = "overlay";
  root.innerHTML = `<div class="card modal-card">${html}</div>`;
  root.onclick = (e) => { if (e.target === root) closeModal(); };
  return root;
}
function closeModal() {
  const root = $("#modal_root");
  root.className = "hidden";
  root.innerHTML = "";
}

/* ------------------------------ boot ------------------------------ */

async function boot() {
  try {
    const data = await api("/api/bootstrap");
    Object.assign(S, {
      ui: data.ui, profiles: data.profiles, catalog: data.catalog,
      providers: data.providers, provider_online: data.provider_online,
      parallel: data.parallel, secretsFiles: data.secrets_files || [],
    });
  } catch (e) {
    document.body.innerHTML = `<div style="padding:40px;font-family:sans-serif">
      Backend error: ${esc(e.message)}</div>`;
    return;
  }
  S.tr.mode = S.ui.ui_tr_mode || "last";
  S.tr.type = ["long", "short", "live"].includes(S.ui.ui_tr_type) ? S.ui.ui_tr_type : "long";
  S.tr.source = S.ui.ui_tr_source || "video";
  S.tr.parts = S.ui.ui_tr_parts || "title,description";
  S.tr.add_playlists = !!S.ui.ui_add_defaults;
  S.tr.do_schedule = !!S.ui.ui_sched;

  if (!S.ui.language || !S.ui.user_name) return showOnboarding();
  startApp();
}

function showOnboarding() {
  S.ui.language = S.ui.language || "ru";
  $("#onboarding").classList.remove("hidden");
  const picker = $("#ob_langs");
  picker.innerHTML = "";
  for (const code of ["ru", "uk", "en"]) {
    const b = document.createElement("button");
    b.className = "lang-pick" + (S.ui.language === code ? " active" : "");
    b.textContent = { ru: "Русский", uk: "Українська", en: "English" }[code];
    b.onclick = () => { S.ui.language = code; showOnboarding(); };
    picker.append(b);
  }
  $("#ob_name").value = S.ui.user_name || "";
  $("#ob_name").placeholder = t("your_name_ph");
  $("#ob_start").textContent = t("start");
  $("#ob_start").onclick = async () => {
    const name = $("#ob_name").value.trim();
    if (!name) { $("#ob_name").focus(); return; }
    await api("/api/onboarding", { language: S.ui.language, name });
    S.ui.user_name = name;
    $("#onboarding").classList.add("hidden");
    await boot();
  };
}

function activeProfile() {
  return S.profiles.find((p) => p.id === S.activeId) || null;
}

function applyTheme() {
  document.body.dataset.theme = S.ui.theme === "light" ? "light" : "dark";
}

function updateHello() {
  const name = (S.ui.user_name || "").trim();
  $("#hello").textContent = name ? `👋 ${name}` : "";
}

function startApp() {
  const saved = S.ui.web_active_profile;
  const savedProfile = S.profiles.find((p) => p.id === saved);
  S.activeId = (savedProfile || S.profiles.find((p) => p.authorized) || S.profiles[0] || {}).id || null;
  if (S.activeId) api("/api/ui", { web_active_profile: S.activeId }).catch(() => {});
  applyTheme();
  updateHello();
  $("#app").classList.remove("hidden");
  buildNav();
  openScreen(S.profiles.length && S.activeId ? (S.screen === "translate" ? "translate" : S.screen) : "channels");
  pollJob(); // resume watching a job left running (e.g. after reload)
}

/* ------------------------------ nav ------------------------------ */

const NAV = [
  ["translate", "🌐"], ["playlists", "📋"], ["schedule", "📅"],
  ["channels", "📺"], ["settings", "⚙️"],
];

function buildNav() {
  const nav = $("#nav");
  nav.innerHTML = "";
  for (const [id, ico] of NAV) {
    const b = document.createElement("button");
    b.className = "nav-item" + (S.screen === id ? " active" : "");
    b.dataset.screen = id;
    b.innerHTML = `<span class="ico">${ico}</span><span class="lbl">${esc(t("nav_" + id))}</span>`;
    b.onclick = () => openScreen(id);
    nav.append(b);
  }
}

function openScreen(id) {
  S.screen = id;
  $$("#nav .nav-item").forEach((b) => b.classList.toggle("active", b.dataset.screen === id));
  const screen = $("#screen");
  screen.classList.remove("screen"); // restart the enter animation
  void screen.offsetWidth;
  screen.classList.add("screen");
  screen.scrollTop = 0;
  ({ translate: renderTranslate, playlists: renderPlaylists, schedule: renderSchedule,
     channels: renderChannels, settings: renderSettings }[id] || renderTranslate)();
}

/* ------------------------------ translate ------------------------------ */

function segControl(items, value, onPick) {
  const seg = document.createElement("div");
  seg.className = "seg";
  seg.innerHTML = `<div class="seg-thumb"></div>`;
  const thumb = $(".seg-thumb", seg);
  const btns = items.map(([val, label]) => {
    const b = document.createElement("button");
    b.textContent = label;
    b.className = String(val) === String(value) ? "active" : "";
    b.onclick = () => {
      btns.forEach((x) => (String(x.dataset.val) === String(val) ? x.classList.add("active")
                                                                : x.classList.remove("active")));
      moveThumb();
      onPick(val);
    };
    b.dataset.val = val;
    seg.append(b);
    return b;
  });
  function moveThumb() {
    const active = $(".seg button.active", seg);
    if (!active) return;
    thumb.style.left = active.offsetLeft - seg.clientLeft + "px";
    thumb.style.width = active.offsetWidth + "px";
  }
  requestAnimationFrame(moveThumb);
  seg._moveThumb = moveThumb;
  return seg;
}
window.addEventListener("resize", () => $$(".seg").forEach((s) => s._moveThumb && s._moveThumb()));

function renderTranslate() {
  const profile = activeProfile();
  const el = $("#screen");
  const selLangs = profile ? profile.languages.filter((c) => c !== "en") : [];
  const provOk = S.providers && S.providers.providers.length > 0;

  const warns = [];
  if (!profile || !profile.authorized) warns.push(t("warn_not_authorized"));
  if (!provOk) warns.push(t("warn_no_provider"));
  if (!selLangs.length) warns.push(t("pick_langs_first"));

  el.innerHTML = `
    <h1>${esc(t("tr_title"))}</h1>
    <div class="stack" style="margin-top:18px">
      ${warns.map((w) => `<div class="card" style="border-color:rgba(251,191,36,.45);
          background:rgba(251,191,36,.07);font-weight:550">⚠️ ${esc(w)}</div>`).join("")}
      <div class="card stack" style="gap:16px" id="tr_form">
        <div class="two-col">
          <div><span class="field-label">${esc(t("tr_mode"))}</span><div id="tr_mode"></div></div>
          <div id="tr_type_wrap"><span class="field-label">${esc(t("tr_type"))}</span><div id="tr_type"></div></div>
        </div>
        <div id="tr_links_wrap" class="hidden"><span class="field-label">${esc(t("tr_links"))}</span>
          <textarea id="tr_links" class="input" rows="3"></textarea></div>
        <div class="two-col">
          <div><span class="field-label">${esc(t("tr_source"))}</span><div id="tr_source"></div></div>
          <div><span class="field-label">${esc(t("tr_parts"))}</span><div id="tr_parts"></div></div>
        </div>
        <div id="tr_preview"></div>
        <div id="tr_manual" class="hidden stack" style="gap:10px">
          <div id="tr_mtitle_wrap"><span class="field-label" id="tr_mtitle_lbl">${esc(t("manual_title"))}</span>
            <input id="tr_mtitle" class="input"></div>
          <div id="tr_mdesc_wrap"><span class="field-label" id="tr_mdesc_lbl">${esc(t("manual_desc"))}</span>
            <textarea id="tr_mdesc" class="input" rows="4"></textarea></div>
        </div>
        <div><span class="field-label">${esc(t("tr_targets"))}</span>
          <div class="row">${selLangs.map((c, i) =>
            `<span class="chip" style="--i:${i}">${esc(c)} — ${esc(langName(c))}</span>`).join("")
            || `<span class="muted">${esc(t("targets_empty"))}</span>`}</div></div>
        <div><span class="field-label">${esc(t("tr_options"))}</span>
          <div class="row" style="gap:22px">
            <label class="row" style="gap:9px;cursor:pointer"><span class="switch">
              <input type="checkbox" id="tr_addpl" ${S.tr.add_playlists ? "checked" : ""}>
              <span class="track"></span><span class="knob"></span></span>
              <span style="font-weight:550">${esc(t("opt_playlists"))}</span></label>
            <label class="row" style="gap:9px;cursor:pointer"><span class="switch">
              <input type="checkbox" id="tr_sched" ${S.tr.do_schedule ? "checked" : ""}>
              <span class="track"></span><span class="knob"></span></span>
              <span style="font-weight:550">${esc(t("opt_schedule"))}</span></label>
            <input id="tr_date" type="date" class="input" style="width:auto"
              value="${esc(ddmmyyToISO(S.tr.schedule_date))}" title="${esc(t("sched_date_ph"))}">
          </div></div>
        <button id="tr_go" class="btn primary big" ${warns.length ? "disabled" : ""}>
          🚀 ${esc(t("tr_start"))}</button>
      </div>
      <div id="tr_job"></div>
    </div>`;

  const modeSeg = segControl(
    [["last", t("mode_last")], ["specific", t("mode_specific")], ["all", t("mode_all")]],
    S.tr.mode, (v) => { S.tr.mode = v; saveTrOptions(); syncMode(); fetchPreview(); });
  $("#tr_mode").append(modeSeg);
  const typeSeg = segControl([["long", t("type_long")], ["short", t("type_short")],
    ["live", t("type_live")]], S.tr.type,
    (v) => { S.tr.type = v; saveTrOptions(); fetchPreview(); });
  $("#tr_type").append(typeSeg);
  const srcSeg = segControl([["video", t("source_video")], ["manual", t("source_manual")]],
    S.tr.source, (v) => { S.tr.source = v; saveTrOptions(); syncSource(); });
  $("#tr_source").append(srcSeg);
  const partsSeg = segControl(
    [["title,description", t("parts_all")], ["title", t("parts_titles")],
     ["description", t("parts_descs")]], S.tr.parts,
    (v) => { S.tr.parts = v; saveTrOptions(); syncParts(); });
  $("#tr_parts").append(partsSeg);

  function syncMode() {
    $("#tr_links_wrap").classList.toggle("hidden", S.tr.mode !== "specific");
    // в конкретных ссылок тип видео ни на что не влияет — гасим кнопки
    // и снимаем выделение, чтобы не подсвечивать нерабочий вариант
    const off = S.tr.mode === "specific";
    $$("#tr_type button").forEach((b) => {
      b.disabled = off;
      b.classList.toggle("active", !off && b.dataset.val === S.tr.type);
    });
  }
  function syncSource() {
    $("#tr_manual").classList.toggle("hidden", S.tr.source !== "manual");
  }
  let previewSeq = 0;

  async function fetchPreview() {
    const host = $("#tr_preview");
    if (!host) return;
    if (S.tr.mode !== "last") { host.innerHTML = ""; S.previewKey = ""; return; }
    const key = S.tr.type;
    if (S.previewKey === key && host.dataset.rendered === key) return;
    S.previewKey = key;
    const seq = ++previewSeq;
    host.innerHTML = `<div class="card" style="padding:14px">
      <div class="row"><span class="spin"></span>
        <span class="muted" style="font-weight:550">${esc(t("prev_heading"))}…</span></div></div>`;
    try {
      const data = await api("/api/preview", { type: S.tr.type });
      if (seq !== previewSeq) return;
      if (!data.video_id) {
        host.innerHTML = `<div class="muted" style="font-size:13px">${esc(t("prev_none"))}</div>`;
        host.dataset.rendered = key;
        return;
      }
      host.innerHTML = `<div class="card stack" style="gap:10px;padding:16px">
        <div class="row" style="gap:8px">
          <span class="badge ok">▶ ${esc(data.video_id)}</span>
          <span class="field-label" style="margin:0">${esc(t("prev_heading"))}</span>
          <button class="btn small" id="prev_refresh" style="margin-left:auto" title="↻">↻</button>
        </div>
        <div style="font-weight:650;font-size:15px;line-height:1.35">${esc(data.title)}</div>
        <details class="prev-desc">
          <summary>${esc(t("prev_desc"))}</summary>
          <div>${esc(data.description)}</div>
        </details>
      </div>`;
      host.dataset.rendered = key;
      $("#prev_refresh", host).onclick = () => {
        host.dataset.rendered = "";
        fetchPreview();
      };
    } catch (e) {
      if (seq === previewSeq) {
        host.innerHTML = `<div class="muted" style="font-size:13px">❌ ${esc(e.message)}</div>`;
      }
    }
  }

  function syncParts() {
    // локализуем что-то одно — ручной ввод второго смысла не имеет
    const parts = S.tr.parts;
    $("#tr_mtitle_wrap").classList.toggle("hidden", parts === "description");
    $("#tr_mdesc_wrap").classList.toggle("hidden", parts === "title");
    $("#tr_mtitle_lbl").textContent = parts === "title" ? t("manual_title_s") : t("manual_title");
    $("#tr_mdesc_lbl").textContent = parts === "description" ? t("manual_desc_s") : t("manual_desc");
  }
  syncMode(); syncSource(); syncParts(); fetchPreview();

  $("#tr_addpl").onchange = (e) => { S.tr.add_playlists = e.target.checked; saveTrOptions(); };
  $("#tr_sched").onchange = (e) => { S.tr.do_schedule = e.target.checked; saveTrOptions(); };
  $("#tr_date").addEventListener("input", (e) => {
    S.tr.schedule_date = isoToDdmmyy(e.target.value);
    saveTrOptions();
  });
  $("#tr_go").onclick = startTranslation;
}

function saveTrOptions() {
  api("/api/ui", {
    ui_tr_mode: S.tr.mode, ui_tr_type: S.tr.type,
    ui_tr_source: S.tr.source, ui_tr_parts: S.tr.parts,
    ui_add_defaults: S.tr.add_playlists, ui_sched: S.tr.do_schedule,
    ui_sched_date: S.tr.schedule_date,
  }).catch(() => {});
}

async function startTranslation() {
  const profile = activeProfile();
  try {
    await api("/api/translate", {
      mode: S.tr.mode,
      type: S.tr.type,
      links: $("#tr_links").value.split("\n"),
      source: S.tr.source,
      manual_title: $("#tr_mtitle").value,
      manual_desc: $("#tr_mdesc").value,
      parts: S.tr.parts.split(","),
      langs: profile ? profile.languages : [],
      add_playlists: S.tr.add_playlists,
      do_schedule: S.tr.do_schedule,
      schedule_date: S.tr.schedule_date,
    });
    toast(t("job_title"), "ok");
    pollJob(true);
    renderJobPanel({ running: true, langs: {}, log: [] });
  } catch (e) {
    toast(e.message, "fail");
  }
}

const STATE_MARK = { ok: "✓", fail: "✗", retry: "⏳", start: "…" };

function renderJobPanel(job) {
  const host = $("#tr_job");
  if (!host) return;
  const langs = Object.entries(job.langs || {});
  const total = langs.length || 1;
  const finished = langs.filter(([, v]) => v.state === "ok" || v.state === "fail").length;
  const running = job.running;
  const hasContent = running || job.done || (job.log || []).length;

  if (!hasContent) { host.innerHTML = ""; return; }

  // структура пересобирается только при смене задачи или фазы ( running -> done ),
  // иначе каждый тик перерисовки моргали бы чипы, лог и заголовок
  const phase = running ? "running" : "done";
  if (host.dataset.jobId !== String(job.id) || host.dataset.phase !== phase) {
    const finishedPhase = host.dataset.phase === "running" && phase === "done";
    host.dataset.jobId = String(job.id);
    host.dataset.phase = phase;
    host.dataset.langsKey = "";
    host.dataset.logLines = "0";
    host.innerHTML = `
      <div class="card stack" style="gap:14px">
        <div class="row"><h2 style="margin:0">${running ? '<span class="spin"></span>' : "✅"}
          ${esc(running ? t("job_title") : t("done"))}</h2>
          ${running ? `<button id="job_cancel" class="btn small danger" style="margin-left:auto">⏹ ${esc(t("job_cancel"))}</button>`
                    : `<button class="btn small" style="margin-left:auto" onclick="openScreen('translate')">${esc(t("job_new"))}</button>`}</div>
        ${job.video_title ? `<div class="muted">${esc(t("job_video"))}: <b>${esc(job.video_title)}</b></div>` : ""}
        <div>
          <div class="row" style="justify-content:space-between;margin-bottom:6px">
            <span class="field-label" style="margin:0">${esc(t("job_progress"))}</span>
            <span class="muted" id="job_pct">0%</span></div>
          <div class="progress-track"><div class="progress-fill" style="width:0%"></div></div>
        </div>
        <div class="job-langs" id="job_langs"></div>
        ${running ? `<div class="muted" style="font-size:12.5px">${esc(t("job_running_note"))}</div>` : ""}
        <div class="log" id="job_log"></div>
      </div>`;
    if (finishedPhase && !job.error) {
      const logHost = $("#job_log", host);
      const div = document.createElement("div");
      div.textContent = "✅ " + t("done");
      logHost.append(div);
      toast(t("done"), "ok");
    }
    if (finishedPhase && job.error) toast(job.error, "fail");
    if (running) {
      $("#job_cancel", host).onclick = async () => {
        const btn = $("#job_cancel", host);
        btn.disabled = true;
        try {
          await api("/api/job/cancel", {});
          const logHost = $("#job_log", host);
          const div = document.createElement("div");
          div.textContent = "⏹ " + t("job_cancel");
          logHost.append(div);
          logHost.scrollTop = logHost.scrollHeight;
          toast(t("job_cancelled"));
        } catch (e) { toast(e.message, "fail"); }
      };
    }
  }

  // прогресс-бар: по языкам текущего видео, при нескольких видео — суммарно
  const videos = job.videos_total > 1 ? job.videos_total : 1;
  const overall = job.videos_total > 1
    ? ((job.videos_done + finished / total) / videos) * 100
    : (finished / total) * 100;
  const fill = $(".progress-fill", host);
  fill.style.width = Math.round(overall) + "%";
  $("#job_pct", host).textContent = Math.round(overall) + "%";

  // чипы языков обновляются только при реальном изменении статусов
  const langsKey = JSON.stringify(job.langs || {});
  if (host.dataset.langsKey !== langsKey) {
    host.dataset.langsKey = langsKey;
    $("#job_langs", host).innerHTML = langs.map(([code, v], i) =>
      `<span class="lang-chip ${v.state}" style="--i:${i}">${esc(code)}
        <span class="st">${v.state === "start" || v.state === "retry"
          ? '<span class="spin"></span>' : esc(STATE_MARK[v.state] || "")}</span></span>`).join("");
  }

  // лог: дописываются только новые строки, без перерисовки всего блока
  const logHost = $("#job_log", host);
  const lines = job.log || [];
  let rendered = parseInt(host.dataset.logLines || "0", 10);
  if (lines.length < rendered) { logHost.innerHTML = ""; rendered = 0; }
  const stick = logHost.scrollHeight - logHost.scrollTop - logHost.clientHeight < 40;
  for (let i = rendered; i < lines.length; i++) {
    const div = document.createElement("div");
    div.textContent = lines[i];
    logHost.append(div);
  }
  host.dataset.logLines = String(lines.length);
  if (stick) logHost.scrollTop = logHost.scrollHeight;
  if (!running) { clearInterval(S.jobTimer); S.jobTimer = null; }
}

function pollJob(force) {
  api("/api/job").then((job) => {
    $("#nav_job_dot").classList.toggle("hidden", !job.running);
    if (job.running || job.done) {
      if (S.screen === "translate" || force) renderJobPanel(job);
    }
    if (job.running && !S.jobTimer) S.jobTimer = setInterval(pollJob, 800);
    if (!job.running) { clearInterval(S.jobTimer); S.jobTimer = null; }
  }).catch(() => {});
}

/* ------------------------------ playlists ------------------------------ */

function renderPlaylists() {
  const profile = activeProfile();
  const el = $("#screen");
  if (!profile) { openScreen("channels"); return; }
  el.innerHTML = `
    <h1>${esc(t("pl_title"))}</h1>
    <p class="muted" style="max-width:640px">${esc(t("pl_hint"))}</p>
    <div class="stack" style="margin-top:18px">
      <div class="card stack" style="gap:10px">
        <div class="row">
          <input id="pl_name" class="input grow" placeholder="${esc(t("pl_name_ph"))}">
          <input id="pl_link" class="input grow" placeholder="${esc(t("pl_link_ph"))}">
          <button id="pl_add" class="btn primary">＋ ${esc(t("pl_add"))}</button>
        </div>
      </div>
      <div id="pl_rows" class="stack" style="gap:8px">
        ${profile.playlists.length ? "" : `<div class="muted">${esc(t("pl_none"))}</div>`}
      </div>
      <div class="card stack" style="gap:12px">
        <h2 style="margin:0">${esc(t("pl_video_title"))}</h2>
        <div class="row">
          <input id="plv_link" class="input grow" placeholder="${esc(t("pl_video_ph"))}">
        </div>
        <div class="row" id="plv_targets">
          ${profile.playlists.map((pl, i) => `
            <label class="chip" style="cursor:pointer;--i:${i}">
              <input type="checkbox" data-pl="${esc(pl.id)}" checked style="accent-color:#6366f1">
              ${esc(pl.name)}</label>`).join("")}
        </div>
        <button id="plv_add" class="btn primary" style="align-self:flex-start">➕ ${esc(t("pl_add"))}</button>
      </div>
    </div>`;

  $("#pl_add").onclick = async () => {
    try {
      const brief = await api("/api/playlists/add", {
        profile_id: profile.id, name: $("#pl_name").value,
        link: $("#pl_link").value,
      });
      Object.assign(profile, brief);
      toast(t("saved"), "ok");
      renderPlaylists();
    } catch (e) { toast(e.message, "fail"); }
  };
  $("#plv_add").onclick = async () => {
    const ids = $$("#plv_targets input:checked").map((x) => x.dataset.pl);
    try {
      const res = await api("/api/playlists/video", {
        profile_id: profile.id, link: $("#plv_link").value, playlist_ids: ids });
      toast(t("pl_added").format ? t("pl_added").replace("{n}", res.added) : `${res.added}`, "ok");
    } catch (e) { toast(e.message, "fail"); }
  };

  const rows = $("#pl_rows");
  for (const pl of profile.playlists) {
    const row = document.createElement("div");
    row.className = "list-row";
    row.innerHTML = `
      <div class="grow"><div class="t">${esc(pl.name)}</div><div class="s">${esc(pl.id)}</div></div>
      <label class="row" style="gap:8px;cursor:pointer;font-size:13px;color:var(--muted)">
        ${esc(t("pl_default"))}<span class="switch">
          <input type="checkbox" ${profile.default_playlists.includes(pl.id) ? "checked" : ""}>
          <span class="track"></span><span class="knob"></span></span></label>
      <button class="btn small danger">✕</button>`;
    $('input[type=checkbox]', row).onchange = async (e) => {
      const brief = await api("/api/playlists/default",
        { profile_id: profile.id, playlist_id: pl.id, value: e.target.checked }).catch((err) => {
          toast(err.message, "fail"); return null; });
      if (brief) Object.assign(profile, brief);
    };
    $(".btn", row).onclick = async () => {
      const brief = await api("/api/playlists/remove",
        { profile_id: profile.id, playlist_id: pl.id }).catch((err) => {
          toast(err.message, "fail"); return null; });
      if (brief) { Object.assign(profile, brief); renderPlaylists(); }
    };
    rows.append(row);
  }
}

/* ------------------------------ schedule ------------------------------ */

function renderSchedule() {
  const el = $("#screen");
  el.innerHTML = `
    <h1>${esc(t("sch_title"))}</h1>
    <p class="muted" style="max-width:640px">${esc(t("sch_sub"))}</p>
    <div class="card stack" style="margin-top:18px;gap:12px">
      <input id="sch_link" class="input" placeholder="${esc(t("sch_link_ph"))}">
      <div class="row" style="flex-wrap:nowrap">
        <input id="sch_date" type="datetime-local" class="input grow" title="${esc(t("sched_date_ph"))}">
        <button id="sch_go" class="btn primary" style="flex:0 0 auto">📅 ${esc(t("sch_set"))}</button>
      </div>
      <div id="sch_res" class="muted"></div>
    </div>
    <div class="card stack" style="margin-top:16px;gap:12px">
      <h2 style="margin:0">${esc(t("cal_title"))}</h2>
      <p class="muted" style="margin:0;font-size:13px">${esc(t("cal_hint"))}</p>
      <div class="stack" style="gap:8px" id="cal_rows"></div>
    </div>`;
  // график публикаций: время по дням недели, сохраняется сразу при изменении
  const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"];
  api("/api/calendar", { profile_id: activeProfile()?.id }).then(({ days }) => {
    const rows = $("#cal_rows");
    for (const day of DAYS) {
      const row = document.createElement("div");
      row.className = "list-row";
      row.innerHTML = `
        <div class="grow" style="font-weight:600">${esc(t("day_" + day))}</div>
        <input type="time" class="input" data-day="${day}" style="width:130px"
          value="${esc(days[day] || "")}">`;
      $('input', row).addEventListener("change", async (e) => {
        const times = {};
        $$("#cal_rows input").forEach((inp) => { times[inp.dataset.day] = inp.value; });
        await api("/api/calendar/save",
          { profile_id: activeProfile().id, days: times }).catch((err) => toast(err.message, "fail"));
        toast(t("saved"), "ok");
      });
      rows.append(row);
    }
  }).catch(() => {});

  $("#sch_go").onclick = async () => {
    try {
      const dt = $("#sch_date").value;
      const res = await api("/api/schedule", {
        link: $("#sch_link").value,
        date: isoToDdmmyy(dt.slice(0, 10)),
        time: dt.slice(11, 16),
      });
      $("#sch_res").innerHTML = `<span style="color:var(--ok)">✓ ${
        esc(t("sch_ok").replace("{id}", res.video_id).replace("{when}", res.when))}</span>`;
    } catch (e) {
      $("#sch_res").innerHTML = `<span style="color:var(--fail)">✗ ${esc(t("sch_bad"))}</span>`;
    }
  };
}

/* ------------------------------ channels ------------------------------ */

function renderChannels() {
  const el = $("#screen");
  el.innerHTML = `
    <div class="row"><h1 style="margin-right:auto">${esc(t("ch_title"))}</h1>
      <button id="ch_add" class="btn primary">＋ ${esc(t("ch_add"))}</button></div>
    <p class="muted">${esc(t("ch_sub"))}</p>
    ${AUTH_STATE.running ? `<div class="card" style="border-color:rgba(99,102,241,.5)">
        <div class="row"><span class="spin"></span> ${esc(t("ch_auth_opening"))}</div></div>` : ""}
    <div class="profile-grid" style="margin-top:16px" id="ch_grid">
      ${S.profiles.length ? "" : `<div class="muted">${esc(t("ch_none"))}</div>`}
    </div>`;

  const grid = $("#ch_grid");
  for (const p of S.profiles) {
    const isActive = p.id === S.activeId;
    const card = document.createElement("div");
    card.className = "card profile-card";
    card.style.setProperty("--i", 0);
    card.innerHTML = `
      <div class="row" style="flex-wrap:nowrap">
        <div class="avatar" data-letter="${esc((p.name || "?").slice(0, 1).toUpperCase())}"
             data-logo="${esc(p.logo_url || "")}"></div>
        <div class="grow" style="min-width:0">
          <div class="name" title="${esc(p.name)}" style="overflow:hidden;text-overflow:ellipsis;white-space:nowrap">${esc(p.name)}</div>
          <div class="row" style="gap:6px;margin-top:2px">
            <span class="badge ${p.authorized ? "ok" : "warn"}">${esc(p.authorized ? t("ch_ready") : t("ch_no_token"))}</span>
            ${isActive ? `<span class="badge ok">★ ${esc(t("ch_selected"))}</span>` : ""}
          </div>
        </div>
      </div>
      <div class="muted" style="font-size:12.5px">${p.languages.length
        ? esc(p.languages.slice(0, 8).join(", ")) + (p.languages.length > 8 ? "…" : "")
        : esc(t("targets_empty"))}</div>
      <div class="row ch-actions">
        ${!isActive ? `<button class="btn small" data-act="select">✓ ${esc(t("ch_select"))}</button>` : ""}
        ${!p.authorized ? `<button class="btn small primary" data-act="auth">🔑 ${esc(t("ch_login"))}</button>` : ""}
        ${!p.languages.length ? `<button class="btn small" data-act="langs">${esc(t("ch_need_langs"))}</button>` : ""}
        <button class="btn small danger" data-act="delete">🗑 ${esc(t("ch_delete"))}</button>
      </div>`;
    fillAvatar($("[data-letter]", card));
    $('[data-act=select]', card)?.addEventListener("click", async () => {
      S.activeId = p.id;
      await api("/api/ui", { web_active_profile: p.id }).catch(() => {});
      buildNav(); renderChannels();
      toast(p.name, "ok");
    });
    $('[data-act=auth]', card)?.addEventListener("click", () => startAuthFlow(p));
    $('[data-act=langs]', card)?.addEventListener("click", () => { openScreen("settings"); });
    $('[data-act=delete]', card)?.addEventListener("click", async () => {
      if (!confirm(t("ch_delete_confirm").replace("{name}", p.name))) return;
      await api("/api/profiles/delete", { profile_id: p.id }).catch((e) => toast(e.message, "fail"));
      S.profiles = (await api("/api/bootstrap")).profiles;
      if (S.activeId === p.id) {
        S.activeId = (S.profiles.find((x) => x.authorized) || S.profiles[0] || {}).id || null;
        if (S.activeId) await api("/api/ui", { web_active_profile: S.activeId }).catch(() => {});
      }
      openScreen(S.profiles.length ? "channels" : "channels");
      toast(t("done"), "ok");
    });
    grid.append(card);
  }

  $("#ch_add").onclick = () => {
    const root = modal(`
      <h2>${esc(t("ch_add"))}</h2>
      <div class="stack" style="margin-top:14px;gap:12px">
        <div><span class="field-label">${esc(t("ch_name_ph"))}</span>
          <input id="m_name" class="input"></div>
        <div id="m_found_wrap" class="hidden"><span class="field-label">${esc(t("ch_found"))}</span>
          <div class="row" id="m_found"></div></div>
        <div><span class="field-label">${esc(t("ch_secrets"))}</span>
          <div class="row">
            <button id="m_pick" class="btn">📄 ${esc(t("ch_pick_file"))}</button>
            <span id="m_file" class="muted"></span>
          </div></div>
        <div class="row" style="justify-content:flex-end">
          <button class="btn" onclick="closeModal()">${esc(t("cancel"))}</button>
          <button id="m_create" class="btn primary" disabled>${esc(t("ch_create"))}</button>
        </div>
      </div>`);
    let file = null;
    let foundName = null;
    const foundWrap = $("#m_found_wrap", root);
    const unclaimed = (S.secretsFiles || []).filter(
      (f) => !S.profiles.some((p) => p.client_secrets_file === f));
    if (unclaimed.length) {
      foundWrap.classList.remove("hidden");
      const host = $("#m_found", root);
      for (const name of unclaimed) {
        const chip = document.createElement("button");
        chip.type = "button";
        chip.className = "chip";
        chip.style.cursor = "pointer";
        chip.textContent = "🔑 " + name;
        chip.onclick = () => {
          foundName = name;
          file = null;
          $("#m_file", root).textContent = "";
          $$("#m_found .chip", root).forEach((c) => c.classList.remove("active"));
          chip.classList.add("active");
          $("#m_create", root).disabled = false;
        };
        host.append(chip);
      }
    }
    $("#m_pick", root).onclick = () => {
      const inp = document.createElement("input");
      inp.type = "file"; inp.accept = ".json,application/json";
      inp.onchange = () => {
        foundName = null;
        $$("#m_found .chip", root).forEach((c) => c.classList.remove("active"));
        file = inp.files[0];
        file.text().then((txt) => {
          try { JSON.parse(txt); } catch { toast("Invalid JSON", "fail"); file = null; return; }
          $("#m_file", root).textContent = "✓ " + file.name;
          $("#m_create", root).disabled = false;
        });
      };
      inp.click();
    };
    $("#m_create", root).onclick = async () => {
      try {
        let filename, content, fallbackName;
        if (foundName) {
          filename = foundName; content = ""; fallbackName = foundName;
        } else {
          filename = file.name;
          content = await file.text();
          fallbackName = file.name.replace(/\.json$/i, "");
        }
        const brief = await api("/api/profiles", {
          name: $("#m_name", root).value.trim() || fallbackName,
          secrets_filename: filename, secrets_content: content });
        closeModal();
        toast(t("saved"), "ok");
        const data = await api("/api/bootstrap");
        S.profiles = data.profiles;
        S.activeId = brief.id;
        startAuthFlow(brief);
      } catch (e) { toast(e.message, "fail"); }
    };
    $("#m_name", root).focus();
  };
}

function startAuthFlow(p) {
  AUTH_STATE.running = true;
  api("/api/auth", { profile_id: p.id }).then(() => {
    toast(t("ch_auth_opening"));
    renderChannels();
    clearInterval(S.authTimer);
    S.authTimer = setInterval(async () => {
      const st = await api("/api/auth").catch(() => null);
      if (!st || st.running) return;
      clearInterval(S.authTimer); S.authTimer = null;
      AUTH_STATE.running = false;
      if (st.ok) {
        toast(t("ch_auth_ok").replace("{channel}", st.channel), "ok");
        const data = await api("/api/bootstrap");
        S.profiles = data.profiles;
        S.providers = data.providers;
        S.activeId = p.id;
        await api("/api/ui", { web_active_profile: p.id }).catch(() => {});
        openScreen("translate");
      } else {
        toast(st.error || t("ch_auth_failed"), "fail");
        renderChannels();
      }
    }, 900);
  }).catch((e) => { AUTH_STATE.running = false; toast(e.message, "fail"); });
}

/* ------------------------------ settings ------------------------------ */

function renderSettings() {
  const profile = activeProfile();
  const el = $("#screen");
  const presets = S.ui.language_presets || {};
  el.innerHTML = `
    <h1>${esc(t("set_title"))}</h1>
    <div class="stack" style="margin-top:18px">

      <div class="two-col">
      <div class="card stack" style="gap:14px">
        <h2 style="margin:0">${esc(t("set_interface"))}</h2>
        <div><span class="field-label">${esc(t("set_ui_language"))}</span><div id="st_lang"></div></div>
        <div><span class="field-label">${esc(t("your_name"))}</span>
          <input id="st_name" class="input" style="max-width:340px" value="${esc(S.ui.user_name || "")}">
          <button id="st_name_save" class="btn small" style="margin-top:8px">${esc(t("save"))}</button></div>
        <div><span class="field-label">${esc(t("set_theme"))}</span><div id="st_theme"></div></div>
      </div>

      <div class="card stack" style="gap:14px">
        <h2 style="margin:0">${esc(t("set_translation"))}</h2>
        <div><span class="field-label">${esc(t("set_parallel"))}</span><div id="st_par"></div></div>
        <label class="row" style="gap:10px;cursor:pointer"><span class="switch">
          <input type="checkbox" id="st_apl" ${S.ui.ask_playlists ? "checked" : ""}>
          <span class="track"></span><span class="knob"></span></span>
          <span style="font-weight:550">${esc(t("set_ask_playlists"))}</span></label>
        <label class="row" style="gap:10px;cursor:pointer"><span class="switch">
          <input type="checkbox" id="st_asch" ${S.ui.ask_schedule ? "checked" : ""}>
          <span class="track"></span><span class="knob"></span></span>
          <span style="font-weight:550">${esc(t("set_ask_schedule"))}</span></label>
      </div>
      </div>

      <div class="two-col">
      <div class="card stack" style="gap:12px">
        <h2 style="margin:0">${esc(t("set_presets"))}</h2>
        <div class="row">
          <select id="ps_sel" class="input" style="width:auto">
            ${Object.keys(presets).map((n) => `<option>${esc(n)}</option>`).join("") ||
              `<option>—</option>`}
          </select>
          <button id="ps_apply" class="btn small">✓ ${esc(t("preset_apply"))}</button>
          <button id="ps_save" class="btn small">＋ ${esc(t("preset_save"))}</button>
          <button id="ps_del" class="btn small danger">✕ ${esc(t("preset_delete"))}</button>
        </div>
        ${Object.keys(presets).length ? "" : `<span class="muted">${esc(t("no_presets"))}</span>`}
      </div>

      <div class="card stack" style="gap:12px">
        <div class="row"><h2 style="margin:0;margin-right:auto">${esc(t("set_providers"))}</h2>
          <button id="pv_add" class="btn small primary">＋ ${esc(t("prov_add"))}</button></div>
        <div id="pv_rows" class="stack" style="gap:8px"></div>
      </div>
      </div>

      <div class="card stack" style="gap:12px">
        <div class="row"><h2 style="margin:0;margin-right:auto">${esc(t("set_langs"))}</h2>
          <span class="badge ok" id="lg_count">${esc(t("selected_n").replace("{n}", profile ? profile.languages.length : 0))}</span></div>
        <input id="lg_search" class="input" placeholder="${esc(t("search_ph"))}">
        <div class="lang-grid" id="lg_grid"></div>
        <div class="muted hidden" id="lg_empty">${esc(t("nothing_found"))}</div>
      </div>
    </div>`;

  // интерфейсный язык
  $("#st_lang").append(segControl([["ru", "Русский"], ["uk", "Українська"], ["en", "English"]],
    S.ui.language, async (v) => {
      S.ui.language = v;
      await api("/api/ui", { language: v }).catch(() => {});
      buildNav(); renderSettings();
    }));

  // тема
  $("#st_theme").append(segControl(
    [["dark", t("theme_dark")], ["light", t("theme_light")]],
    S.ui.theme === "light" ? "light" : "dark",
    (v) => {
      S.ui.theme = v;
      applyTheme();
      api("/api/ui", { theme: v }).catch((e) => toast(e.message, "fail"));
    }));

  // параллелизм
  const parSel = document.createElement("select");
  parSel.className = "input"; parSel.style.width = "auto";
  const opts = ["auto", "1", "2", "3", "4", "5", "6", "7", "8", "9", "10"];
  parSel.innerHTML = opts.map((o) =>
    `<option value="${o}" ${String(S.parallel) === o ? "selected" : ""}>${
      o === "auto" ? t("parallel_auto") : o}</option>`).join("");
  parSel.onchange = async () => {
    await api("/api/parallel", { value: parSel.value }).catch((e) => toast(e.message, "fail"));
    S.parallel = parSel.value;
    toast(t("saved"), "ok");
  };
  $("#st_par").append(parSel);

  $("#st_name_save").onclick = async () => {
    S.ui.user_name = $("#st_name").value.trim();
    await api("/api/ui", { user_name: S.ui.user_name }).catch((e) => toast(e.message, "fail"));
    updateHello();
    toast(t("saved"), "ok");
  };
  $("#st_apl").onchange = async (e) => {
    S.ui.ask_playlists = e.target.checked;
    await api("/api/ui", { ask_playlists: e.target.checked }).catch(() => {});
  };
  $("#st_asch").onchange = async (e) => {
    S.ui.ask_schedule = e.target.checked;
    await api("/api/ui", { ask_schedule: e.target.checked }).catch(() => {});
  };

  // пресеты
  $("#ps_apply").onclick = async () => {
    const name = $("#ps_sel").value;
    if (!(name in presets) || !profile) return;
    await api("/api/presets/apply", { profile_id: profile.id, name }).catch((e) => toast(e.message, "fail"));
    const data = await api("/api/bootstrap");
    S.profiles = data.profiles;
    toast(t("done"), "ok");
  };
  $("#ps_save").onclick = () => {
    if (!profile) return;
    const root = modal(`
      <h2>${esc(t("preset_name"))}</h2>
      <input id="psn" class="input" style="margin:14px 0">
      <div class="row" style="justify-content:flex-end">
        <button class="btn" onclick="closeModal()">${esc(t("cancel"))}</button>
        <button id="psn_ok" class="btn primary">${esc(t("save"))}</button></div>`);
    $("#psn", root).focus();
    $("#psn_ok", root).onclick = async () => {
      const name = $("#psn", root).value.trim();
      if (!name) return;
      await api("/api/presets/save", { profile_id: profile.id, name }).catch((e) => toast(e.message, "fail"));
      closeModal(); toast(t("saved"), "ok");
      const data = await api("/api/bootstrap");
      S.ui = data.ui; renderSettings();
    };
  };
  $("#ps_del").onclick = async () => {
    const name = $("#ps_sel").value;
    if (!(name in presets)) return;
    await api("/api/presets/delete", { name }).catch((e) => toast(e.message, "fail"));
    const data = await api("/api/bootstrap");
    S.ui = data.ui; renderSettings();
  };

  renderProviderRows();
  $("#pv_add").onclick = () => providerEditor(null);

  // сетка языков: строится один раз, поиск только скрывает ячейки
  S.langSel = new Set(profile ? profile.languages : []);
  const grid = $("#lg_grid");
  const cells = Object.keys(S.catalog).sort().map((code, i) => {
    const cell = document.createElement("div");
    cell.className = "lang-cell" + (S.langSel.has(code) ? " checked" : "");
    cell.style.setProperty("--i", Math.min(i, 40));
    cell.dataset.code = code.toLowerCase();
    cell.dataset.name = (langName(code) + " " + (S.catalog[code] || "")).toLowerCase();
    cell.title = `${code} — ${langName(code)}` +
      ((S.catalog[code] && S.catalog[code] !== langName(code)) ? ` (${S.catalog[code]})` : "");
    cell.innerHTML = `<span class="box"><svg viewBox="0 0 14 14"><path d="M2 7.5 5.5 11 12 3.5"/></svg></span>
      <span class="code">${esc(code)}</span><span class="nm">${esc(langName(code))}</span>`;
    cell.onclick = () => {
      if (S.langSel.has(code)) S.langSel.delete(code); else S.langSel.add(code);
      cell.classList.toggle("checked", S.langSel.has(code));
      $("#lg_count").textContent = t("selected_n").replace("{n}", S.langSel.size);
      if (profile) api("/api/profile/languages", { profile_id: profile.id, codes: [...S.langSel] })
        .catch((e) => toast(e.message, "fail"));
    };
    grid.append(cell);
    return cell;
  });
  $("#lg_search").addEventListener("input", (e) => {
    const q = e.target.value.trim().toLowerCase();
    let visible = 0;
    cells.forEach((cell) => {
      const show = !q || cell.dataset.code.includes(q) || cell.dataset.name.includes(q);
      cell.style.display = show ? "" : "none";
      if (show) visible++;
    });
    $("#lg_empty").classList.toggle("hidden", visible > 0);
  });
}

function renderProviderRows() {
  const host = $("#pv_rows");
  host.innerHTML = "";
  for (const p of S.providers.providers) {
    const isActive = p.id === S.providers.active;
    const isBackup = p.id === S.providers.backup;
    const row = document.createElement("div");
    row.className = "list-row provider-row";
    row.innerHTML = `
      <span class="mark ${isActive ? "active" : isBackup ? "backup" : ""}">${isActive ? "●" : isBackup ? "○" : "·"}</span>
      <div class="grow" style="min-width:0">
        <div class="t">${esc(p.name)}
          <span class="muted" style="font-weight:400;font-size:12px">
            ${isActive ? "· " + t("prov_active") : isBackup ? "· " + t("prov_backup") : ""}</span></div>
        <div class="s">${esc(p.model || "auto")} · ${p.auth ? p.keys.length + " 🔑" : esc(p.base_url || "")}</div>
      </div>
      <button class="btn small" data-a="edit">✎ ${esc(t("prov_edit"))}</button>
      ${!isActive ? `<button class="btn small" data-a="activate">● ${esc(t("prov_activate"))}</button>` : ""}
      ${!isBackup && !isActive ? `<button class="btn small" data-a="backup">○ ${esc(t("prov_backup_btn"))}</button>` : ""}
      <button class="btn small danger" data-a="del">✕</button>`;
    $('[data-a=edit]', row).onclick = () => providerEditor(p);
    $('[data-a=activate]', row)?.addEventListener("click", async () => {
      S.providers = await api("/api/providers/activate", { id: p.id }).catch((e) => {
        toast(e.message, "fail"); return null; });
      if (S.providers) { renderProviderRows(); toast(t("saved"), "ok"); }
    });
    $('[data-a=backup]', row)?.addEventListener("click", async () => {
      S.providers = await api("/api/providers/activate", { id: p.id, backup: true }).catch((e) => {
        toast(e.message, "fail"); return null; });
      if (S.providers) { renderProviderRows(); toast(t("saved"), "ok"); }
    });
    $('[data-a=del]', row).onclick = async () => {
      if (!confirm(p.name + " — " + t("delete") + "?")) return;
      S.providers = await api("/api/providers/delete", { id: p.id }).catch((e) => {
        toast(e.message, "fail"); return null; });
      if (S.providers) renderProviderRows();
    };
    host.append(row);
  }
}

function providerEditor(provider) {
  const isNew = !provider;
  const root = modal(`
    <h2>${esc(isNew ? t("prov_new") : t("prov_edit_title") + " — " + provider.name)}</h2>
    <div class="stack" style="margin-top:14px;gap:12px">
      <div><span class="field-label">${esc(t("prov_kind"))}</span><div id="pe_kind"></div></div>
      <div><span class="field-label">${esc(t("prov_name"))}</span>
        <input id="pe_name" class="input" value="${esc(provider?.name || "")}"></div>
      <div id="pe_base_wrap"><span class="field-label">${esc(t("prov_base"))}</span>
        <input id="pe_base" class="input" value="${esc(provider?.base_url || "")}"
          placeholder="https://…/v1"></div>
      <div id="pe_presets_wrap" class="hidden"><span class="field-label">${esc(t("local_app"))}</span>
        <div class="row">
          <button type="button" class="btn small" data-base="http://localhost:1234/v1">LM Studio</button>
          <button type="button" class="btn small" data-base="http://localhost:11434/v1">Ollama</button>
        </div></div>
      <div id="pe_keys_wrap">
        <span class="field-label">${esc(t("prov_keys"))}
          <span title="${esc(t("keys_help"))}" style="cursor:help;opacity:.7">ⓘ</span></span>
        <div class="row" id="pe_key_chips"></div>
        <div class="row" id="pe_key_btns" style="margin-top:8px">
          <button type="button" id="pe_add_keys" class="btn small">＋ ${esc(t("keys_add"))}</button>
          <button type="button" id="pe_clear_keys" class="btn small danger">${esc(t("keys_clear"))}</button>
          <button type="button" id="pe_check_keys" class="btn small">? ${esc(t("keys_check"))}</button>
          <button type="button" id="pe_unfreeze" class="btn small">☀ ${esc(t("keys_unfreeze"))}</button>
        </div>
        <textarea id="pe_keys" class="input" rows="3" style="margin-top:8px"
          placeholder="${esc(t("prov_keys"))}"></textarea>
      </div>
      <div><span class="field-label">${esc(t("prov_model"))}</span>
        <div class="row">
          <input id="pe_model" class="input grow" list="pe_models" value="${esc(provider?.model || "auto")}">
          <datalist id="pe_models"></datalist>
          <button id="pe_fetch" class="btn small">${esc(t("fetch_models"))}</button>
        </div></div>
      <div class="row" style="justify-content:flex-end">
        <button class="btn" onclick="closeModal()">${esc(t("cancel"))}</button>
        <button id="pe_save" class="btn primary">${esc(t("save"))}</button></div>
    </div>`);

  let online = isNew ? "online" : (provider.auth ? "online" : "local");
  $("#pe_kind", root).append(segControl(
    [["online", t("kind_online")], ["local", t("kind_local")]], online, (v) => { online = v; syncKind(); }));

  function syncKind() {
    const isLocal = online === "local";
    // локальному провайдеру ключи не нужны — вместо них пресеты приложений
    $("#pe_keys_wrap", root).classList.toggle("hidden", isLocal);
    $("#pe_presets_wrap", root).classList.toggle("hidden", !isLocal);
  }
  syncKind();

  /* --- ключи онлайн-провайдера: маскированные чипы + статусы --- */
  let keyChips = (provider?.keys || []).map((k) => ({ ...k }));
  const removedKeys = new Set();
  const DOT = { ok: "green", frozen: "blue", dead: "red" };
  let keysEditorOpen = isNew || !keyChips.length; // у нового провайдера поле открыто сразу

  function renderKeyChips() {
    const host = $("#pe_key_chips", root);
    host.innerHTML = "";
    const kept = keyChips.filter((c) => !removedKeys.has(c.hash));
    for (const chip of kept) {
      const el = document.createElement("span");
      el.className = "key-chip";
      const stText = t("key_" + (chip.status || "ok"));
      el.title = `${chip.masked} — ${stText}${chip.detail ? " (" + chip.detail + ")" : ""}`;
      el.innerHTML = `<span class="key-dot ${DOT[chip.status] || "green"}"></span>${esc(chip.masked)}
        <button type="button" class="key-x" title="${esc(t("delete"))}">×</button>`;
      $(".key-x", el).onclick = () => { removedKeys.add(chip.hash); renderKeyChips(); };
      host.append(el);
    }
    // нет ключей — ни чипов, ни кнопок, только открытое поле ввода
    const hasKeys = kept.length > 0;
    $("#pe_key_chips", root).style.display = hasKeys ? "" : "none";
    $("#pe_key_btns", root).style.display = hasKeys ? "" : "none";
    $("#pe_keys", root).classList.toggle("hidden", hasKeys && !keysEditorOpen);
    const hasFrozen = kept.some((c) => c.status === "frozen");
    $("#pe_unfreeze", root).style.display = hasFrozen ? "" : "none";
  }
  renderKeyChips();

  $("#pe_add_keys", root).onclick = () => { keysEditorOpen = !keysEditorOpen; renderKeyChips(); };
  $("#pe_clear_keys", root).onclick = () => {
    keyChips.forEach((c) => removedKeys.add(c.hash));
    keysEditorOpen = true;
    renderKeyChips();
  };
  $("#pe_check_keys", root).onclick = async () => {
    if (isNew || !provider.id) return toast(t("keys_need_save"), "fail");
    const btn = $("#pe_check_keys", root);
    btn.disabled = true;
    try {
      const res = await api("/api/providers/check_keys", { provider_id: provider.id });
      for (const fresh of res.keys) {
        const chip = keyChips.find((c) => c.hash === fresh.hash);
        if (chip) { chip.status = fresh.status; chip.detail = fresh.detail; }
      }
      renderKeyChips();
      const counts = { ok: 0, frozen: 0, dead: 0 };
      for (const fresh of res.keys) counts[fresh.status] = (counts[fresh.status] || 0) + 1;
      toast(t("keys_check_result").replace("{ok}", counts.ok)
        .replace("{frozen}", counts.frozen).replace("{dead}", counts.dead),
        counts.dead ? "fail" : "ok");
    } catch (e) { toast(e.message, "fail"); }
    finally { btn.disabled = false; }
  };
  $("#pe_unfreeze", root).onclick = async () => {
    if (isNew || !provider.id) return toast(t("keys_need_save"), "fail");
    try {
      S.providers = await api("/api/providers/unfreeze", { provider_id: provider.id });
      keyChips.forEach((c) => { if (c.status === "frozen") { c.status = "ok"; c.detail = ""; } });
      renderKeyChips();
      toast(t("saved"), "ok");
    } catch (e) { toast(e.message, "fail"); }
  };

  async function fetchModels() {
    const btn = $("#pe_fetch", root);
    btn.disabled = true;
    try {
      const models = (await api("/api/providers/models", { base_url: $("#pe_base", root).value })).models || [];
      if (!models.length) { toast(t("no_models"), "fail"); return false; }
      $("#pe_models", root).innerHTML = models.map((m) => `<option>${esc(m)}</option>`).join("");
      const current = $("#pe_model", root).value.trim();
      if (!current || current === "auto") $("#pe_model", root).value = models[0];
      toast(t("models_found").replace("{n}", models.length), "ok");
      return true;
    } catch (e) {
      toast(e.message, "fail");
      return false;
    } finally {
      btn.disabled = false;
    }
  }
  $("#pe_fetch", root).onclick = fetchModels;

  // пресет локального приложения: заполняет base URL и сразу тянет модели
  $$("#pe_presets_wrap [data-base]", root).forEach((b) => {
    b.onclick = async () => {
      $("#pe_base", root).value = b.dataset.base;
      await fetchModels();
    };
  });

  $("#pe_save", root).onclick = async () => {
    const name = $("#pe_name", root).value.trim();
    const base = $("#pe_base", root).value.trim();
    const isLocal = online === "local";
    const newKeys = $("#pe_keys", root).value.split(/[,\s]+/).filter(Boolean);
    if (!name) return toast(t("need_name"), "fail");
    if (!isLocal && !base) return toast(t("need_url"), "fail");
    const keptKeys = keyChips.filter((c) => !removedKeys.has(c.hash)).map((c) => c.hash);
    if (!isLocal && !keptKeys.length && !newKeys.length) return toast(t("prov_keys"), "fail");
    const entry = {
      id: provider?.id, name, kind: "openai", auth: !isLocal, base_url: base,
      model: $("#pe_model", root).value.trim() || "auto",
    };
    try {
      S.providers = await api("/api/providers/save",
        { entry, keep: isLocal ? [] : keptKeys, new_keys: isLocal ? "" : $("#pe_keys", root).value });
      closeModal(); renderProviderRows(); toast(t("saved"), "ok");
    } catch (e) { toast(e.message, "fail"); }
  };
}

/* ------------------------------ quit ------------------------------ */

$("#quit_btn").onclick = async () => {
  if (!confirm(t("quit_confirm"))) return;
  await api("/api/quit", {}).catch(() => {});
  document.body.innerHTML = `<div style="display:flex;height:100vh;align-items:center;
    justify-content:center;color:var(--muted);font-size:18px">👋</div>`;
};

boot();
