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

## Дюпы (раздел «Найти дюп»)

Список известных дюпов — `data/dupes.txt`, одна строка на пару:
`Бренд оригинала | Название оригинала => Бренд дюпа | Название дюпа`.
После правки:

```bash
python3 -I src/add_dupes.py data/db.json data/dupes.txt
```

и пересобрать сайт. Остальные места в пятёрке подбираются по формуле среди брендов дюпов (Armaf, Lattafa, Afnan, Rasasi, Al Haramain, Swiss Arabian, Zara…).

## Пересобрать базу (редко)

```bash
curl -L -o parfumo.csv https://raw.githubusercontent.com/rfordatascience/tidytuesday/main/data/2024/2024-12-10/parfumo_data_clean.csv
python3 -I src/build_db.py parfumo.csv data/db.json
python3 -I src/postprocess.py data/db.json
python3 -I src/add_dupes.py data/db.json data/dupes.txt
```

Источник данных: [Parfumo Fragrance Dataset (TidyTuesday)](https://github.com/rfordatascience/tidytuesday/tree/main/data/2024/2024-12-10).
