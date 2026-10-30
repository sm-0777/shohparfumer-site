# Shoh Parfumer — Подбор Парфюма

Сайт подбора духов: клиент выбирает три любимых аромата (или любимые запахи, или подбор в подарок),
отвечает на пару вопросов и получает пять ароматов по сходству нот. Русский, тоҷикӣ, English.

## Что где лежит

| Путь | Что это |
|---|---|
| `public/index.html` | Готовый сайт. Его публикует Cloudflare. Это единственный файл, который видят клиенты. |
| `src/site.html` | Шаблон сайта (код и тексты). Правки делаются здесь. |
| `data/db.json` | База ароматов (≈17 300 духов, ноты, аккорды, пол, категория бренда). |
| `src/make_site.py` | Собирает `public/index.html` из шаблона и базы. |
| `src/build_db.py`, `src/postprocess.py` | Собирают базу из открытых данных Parfumo (TidyTuesday, 2024-12-10). |
| `public/og.png` | Картинка превью ссылки в Telegram / WhatsApp (1200×630). Собирается из `src/og.html`. |
| `public/404.html` | Неверный адрес на сайте (например `/abc`) — сразу открывает главную. |
| `wrangler.jsonc` | Настройка Cloudflare: публиковать папку `public` на shoh-parfumer.com. |

## Настройки владельца (в начале скрипта в `src/site.html`)

```js
var TELEGRAM = "sm_0777";   // куда приходят отзывы и заказы
var GOATCOUNTER = "shoh-parfumer"; // статистика: https://shoh-parfumer.goatcounter.com
var SITE_URL = "https://shoh-parfumer.com/"; // адрес сайта для «Поделиться»
var STOCK = {               // духи в наличии: "Бренд|Название": цена в сомони
  // "Creed|Aventus": 2500,
};
```

## Как обновить сайт

```bash
python3 -I src/make_site.py src/site.html data/db.json public/index.html --standalone
git add -A && git commit -m "Обновление сайта" && git push
```

Cloudflare (Workers, проект shoh-parfumer) опубликует изменения сам примерно через минуту.

Картинку превью ссылки (`public/og.png`) пересобирать только если поменялся `src/og.html`:

```bash
node -e 'const{chromium}=require("playwright");(async()=>{const b=await chromium.launch();const p=await b.newPage({viewport:{width:1200,height:630}});await p.goto("file://"+process.cwd()+"/src/og.html");await p.waitForTimeout(1500);await p.screenshot({path:"public/og.png"});await b.close()})()'
```

Telegram запоминает превью ссылки; чтобы он показал новое сразу, отправьте адрес сайта боту @WebpageBot.

## Как устроено (коротко)

- Каждый экран — запись в истории браузера: кнопка «Назад» телефона ведёт на прошлый экран или закрывает открытое окно,
  а после обновления страницы (или возврата из другого приложения) подбор не теряется.
- Ключи умного поиска готовятся в фоне маленькими порциями, популярные ароматы — первыми; пока они готовятся, поиск
  уже работает по написанию и сам обновляется, когда всё готово.
- Пять ароматов в итоге — по проценту сходства; пометка «Хит» остаётся на своём аромате.
- «Сравнить ароматы» (кнопка внизу главной, после «Найти дюп»): два парфюма рядом — сходство, известный дюп,
  сезон, пол, цена, оценка, хит, год выпуска и концентрация (только если известны), характер, аккорды, ноты общие
  и разные, по слоям. Стойкость и шлейф не показываются — данных нет. Год и концентрация — `src/add_info.py`
  (из Parfumo; ручные поправки с источниками — `data/info_manual.txt`).

## Дюпы (раздел «Найти дюп»)

Список известных дюпов — `data/dupes.txt`, одна строка на пару:
`Бренд оригинала | Название оригинала => Бренд дюпа | Название дюпа`.
После правки:

```bash
python3 -I src/add_dupes.py data/db.json data/dupes.txt
```

и пересобрать сайт. Показываются только известные дюпы из этого списка (до 5); подбор дюпов «по нотам» убран по решению владельца.

## Пересобрать базу (редко)

```bash
curl -L -o parfumo.csv https://raw.githubusercontent.com/rfordatascience/tidytuesday/main/data/2024/2024-12-10/parfumo_data_clean.csv
python3 -I src/build_db.py parfumo.csv data/db.json
python3 -I src/postprocess.py data/db.json
python3 -I src/clean_notes.py data/db.json data/fake_notes.txt     # убрать подменённые ноты
python3 -I src/add_notes.py data/db.json data/notes_manual.jsonl    # проверенные ноты
python3 -I src/add_perfumes.py data/db.json data/perfumes_extra.jsonl  # недостающие ароматы
python3 -I src/add_dupes.py data/db.json data/dupes.txt
python3 -I src/add_info.py data/db.json parfumo.csv data/info_manual.txt  # год выпуска и концентрация (для «Сравнить»)
```

Источник данных: [Parfumo Fragrance Dataset (TidyTuesday)](https://github.com/rfordatascience/tidytuesday/tree/main/data/2024/2024-12-10).
