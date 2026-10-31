#!/usr/bin/env python3
"""Вставляет базу ароматов в шаблон сайта.

Запуск:
  python3 -I make_site.py <site.html> <db.json> <out.html>                 # для Claude (страница-артефакт)
  python3 -I make_site.py <site.html> <db.json> <index.html> --standalone  # для хостинга (Cloudflare)
"""
import sys

SITE = "https://shoh-parfumer.com/"   # адрес сайта (для превью ссылки и поисковиков)
args = [a for a in sys.argv[1:] if not a.startswith("--")]
standalone = "--standalone" in sys.argv
tpl = open(args[0], encoding="utf-8").read()
db = open(args[1], encoding="utf-8").read()
assert tpl.count("__DB__") == 1, "в шаблоне должна быть ровно одна метка __DB__"
assert "</script" not in db.lower(), "в базе не должно быть </script"
out = tpl.replace("__DB__", db)
# Точный «Характер» (public/taste.json из src/make_taste.py). На хостинге сайт скачивает его сам, только когда открыто
# сравнение; в странице-артефакте Claude загрузить его не откуда — вставляем прямо в страницу.
assert out.count("__TASTE__") == 1, "в шаблоне должна быть ровно одна метка __TASTE__"
taste = ""
if not standalone:
    try:
        taste = open("public/taste.json", encoding="utf-8").read()
    except OSError:
        print("нет public/taste.json — полоски «Характер» будут по грубым данным")
out = out.replace("__TASTE__", taste)

if standalone:
    # Полноценный HTML-документ: всё до <header> уходит в <head>, остальное в <body>
    cut = out.index("<header")
    head, body = out[:cut], out[cut:]
    head = head.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
    icon = ("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 32 32'%3E"
            "%3Crect width='32' height='32' rx='7' fill='%230B0B0A'/%3E"
            "%3Ccircle cx='9' cy='16' r='4' fill='%23FFC61A'/%3E"
            "%3Ccircle cx='16' cy='16' r='4' fill='%23FFC61A' fill-opacity='.65'/%3E"
            "%3Ccircle cx='23' cy='16' r='4' fill='%23FFC61A' fill-opacity='.35'/%3E%3C/svg%3E")
    out = ("<!doctype html>\n<html lang=\"ru\">\n<head>\n"
           "<meta charset=\"utf-8\">\n"
           "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
           "<meta name=\"description\" content=\"Подбор парфюма по трём любимым ароматам: 17 000+ духов, ноты и советы. Русский, тоҷикӣ, English.\">\n"
           "<meta name=\"theme-color\" content=\"#0B0B0A\">\n"
           # Адрес сайта для поисковиков и превью ссылки в Telegram / WhatsApp (картинка public/og.png из src/og.html)
           "<link rel=\"canonical\" href=\"" + SITE + "\">\n"
           "<meta property=\"og:type\" content=\"website\">\n"
           "<meta property=\"og:site_name\" content=\"Shoh Parfumer\">\n"
           "<meta property=\"og:title\" content=\"Shoh Parfumer · Подбор парфюма\">\n"
           "<meta property=\"og:description\" content=\"3 любимых аромата → 5 новых. Дюпы, ноты, советы — за минуту. Русский, тоҷикӣ, English.\">\n"
           "<meta property=\"og:url\" content=\"" + SITE + "\">\n"
           "<meta property=\"og:image\" content=\"" + SITE + "og.png\">\n"
           "<meta property=\"og:image:width\" content=\"1200\">\n"
           "<meta property=\"og:image:height\" content=\"630\">\n"
           "<meta property=\"og:image:alt\" content=\"Shoh Parfumer — подбор парфюма\">\n"
           "<meta property=\"og:locale\" content=\"ru_RU\">\n"
           "<meta name=\"twitter:card\" content=\"summary_large_image\">\n"
           "<link rel=\"icon\" href=\"" + icon + "\">\n"
           "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
           "body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n"
           + head + "</head>\n<body>\n" + body + "\n</body>\n</html>\n")

open(args[2], "w", encoding="utf-8").write(out)
print("ok", args[2], len(out.encode("utf-8")), "bytes", "(standalone)" if standalone else "")
