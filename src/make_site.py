#!/usr/bin/env python3
"""Вставляет базу ароматов в шаблон сайта.

Запуск:
  python3 -I make_site.py <site.html> <db.json> <out.html>                 # для Claude (страница-артефакт)
  python3 -I make_site.py <site.html> <db.json> <index.html> --standalone  # для хостинга (Cloudflare)

Для хостинга (--standalone) рядом с index.html пишутся ещё:
  tg/index.html, en/index.html — та же страница на таджикском и английском (у каждого языка свой адрес для поисковиков);
  sitemap.xml и robots.txt — для Google, Яндекса и Bing.
Заголовок, описание и тексты страниц берутся из переводов в site.html (I18N), поэтому всегда совпадают с сайтом.
"""
import datetime
import html
import json
import os
import re
import subprocess
import sys

SITE = "https://shoh-parfumer.com/"   # адрес сайта (для превью ссылки и поисковиков)
LANGS = {"ru": "", "tg": "tg/", "en": "en/"}            # язык → адрес страницы
LOCALE = {"ru": "ru_RU", "tg": "tg_TJ", "en": "en_US"}
# Подтверждение прав на сайт (Яндекс Вебмастер, Google Search Console): код из их кабинета. Это не секрет.
# Яндекс подтверждён ещё и файлом public/yandex_КОД.html (его отдаёт worker/index.js без перенаправления).
VERIFY = {"yandex-verification": "3075817907239567", "google-site-verification": ""}
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

if not standalone:
    open(args[2], "w", encoding="utf-8").write(out)
    print("ok", args[2], len(out.encode("utf-8")), "bytes")
    sys.exit(0)


# ---------- Переводы из site.html (выполняем сам объект I18N через node) ----------
def load_i18n(src):
    a = src.index("  var LANGS = [")
    b = src.index("\n", src.index("  LANGS.forEach(function (l) { Object.keys(I18N_X[l])"))
    code = src[a:b] + "\nprocess.stdout.write(JSON.stringify(I18N));"
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


I18N = load_i18n(tpl)
for l in LANGS:
    assert I18N[l].get("pageTitle") and I18N[l].get("metaDesc"), "нет pageTitle/metaDesc для " + l

A = lambda s: html.escape(s, quote=True)


def translate_static(page, l):
    """Тексты страницы до запуска скрипта — сразу на нужном языке (как их потом поставит applyLang)."""
    T = I18N[l]

    def ok(v):  # обычная строка без подстановок {n}
        return isinstance(v, str) and "{" not in v

    def text(m):  # <тег data-t="ключ">текст</тег> — только если внутри нет других тегов
        v = T.get(m.group(3))
        return m.group(1) + html.escape(v, quote=False) if ok(v) else m.group(0)
    page = re.sub(r'(<(\w+)\b[^<>]*\bdata-t="([A-Za-z0-9]+)"[^<>]*>)([^<]*)(?=</\2>)', text, page)

    def attr(m, data, name):
        tag, key = m.group(0), m.group(1)
        v = T.get(key)
        if not ok(v):
            return tag
        if re.search(r'\b' + name + r'="[^"]*"', tag):
            return re.sub(r'\b' + name + r'="[^"]*"', name + '="' + A(v) + '"', tag, count=1)
        return tag
    for data, name in (("data-tp", "placeholder"), ("data-ta", "aria-label"), ("data-tt", "title")):
        page = re.sub(r'<[^<>]*\b' + data + r'="([A-Za-z0-9]+)"[^<>]*>', lambda m: attr(m, data, name), page)
    return page


# ---------- Страница для каждого языка ----------
cut = out.index("<header")
head0, body0 = out[:cut], out[cut:]
head0 = head0.replace('<meta name="claude:viewport-fit-sides" content="cover">\n', "")
head0 = re.sub(r"<title>[^<]*</title>\n?", "", head0)
alts = "".join('<link rel="alternate" hreflang="%s" href="%s">\n' % (l, SITE + p) for l, p in LANGS.items()) + \
    '<link rel="alternate" hreflang="x-default" href="%s">\n' % SITE


def ld_json(l):
    T = I18N[l]
    data = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "@id": SITE + "#site", "url": SITE, "name": "Shoh Parfumer",
         "description": T["metaDesc"], "inLanguage": list(LANGS), "publisher": {"@id": SITE + "#store"}},
        # Магазин: адрес, часы и телефон добавить, когда владелец пришлёт (только настоящие данные)
        {"@type": "Store", "@id": SITE + "#store", "name": "Shoh Parfumer", "url": SITE,
         "logo": SITE + "logo.png", "image": SITE + "og.png", "description": T["metaDesc"],
         "address": {"@type": "PostalAddress", "addressLocality": "Dushanbe", "addressCountry": "TJ"}},
    ]}
    return '<script type="application/ld+json">' + json.dumps(data, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"


def page_for(l):
    T, url = I18N[l], SITE + LANGS[l]
    head = ("<!doctype html>\n<html lang=\"" + l + "\">\n<head>\n"
            "<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
            "<title>" + html.escape(T["pageTitle"], quote=False) + "</title>\n"
            "<meta name=\"description\" content=\"" + A(T["metaDesc"]) + "\">\n"
            "<meta name=\"theme-color\" content=\"#0B0B0A\">\n" +
            "".join("<meta name=\"%s\" content=\"%s\">\n" % (k, A(v)) for k, v in VERIFY.items() if v) +
            # Адрес страницы и её версии на других языках — для Google, Яндекса и Bing
            "<link rel=\"canonical\" href=\"" + url + "\">\n" + alts +
            # Превью ссылки в Telegram / WhatsApp (картинка public/og.png из src/og.html)
            "<meta property=\"og:type\" content=\"website\">\n"
            "<meta property=\"og:site_name\" content=\"Shoh Parfumer\">\n"
            "<meta property=\"og:title\" content=\"" + A(T["pageTitle"]) + "\">\n"
            "<meta property=\"og:description\" content=\"" + A(T["metaDesc"]) + "\">\n"
            "<meta property=\"og:url\" content=\"" + url + "\">\n"
            "<meta property=\"og:image\" content=\"" + SITE + "og.png\">\n"
            "<meta property=\"og:image:width\" content=\"1200\">\n"
            "<meta property=\"og:image:height\" content=\"630\">\n"
            "<meta property=\"og:image:alt\" content=\"Shoh Parfumer\">\n"
            "<meta property=\"og:locale\" content=\"" + LOCALE[l] + "\">\n" +
            "".join("<meta property=\"og:locale:alternate\" content=\"" + LOCALE[x] + "\">\n" for x in LANGS if x != l) +
            "<meta name=\"twitter:card\" content=\"summary_large_image\">\n"
            # Значки отдельными файлами (src/make_icons.py) — их видят поисковики
            "<link rel=\"icon\" href=\"/favicon.ico\" sizes=\"48x48\">\n"
            "<link rel=\"icon\" href=\"/favicon.svg\" type=\"image/svg+xml\">\n"
            "<link rel=\"icon\" href=\"/favicon-96.png\" sizes=\"96x96\" type=\"image/png\">\n"
            "<link rel=\"apple-touch-icon\" href=\"/apple-touch-icon.png\">\n" + ld_json(l) +
            "<style>:root{padding-top:env(safe-area-inset-top,0px);padding-bottom:env(safe-area-inset-bottom,0px)}"
            "body{margin:0}img{max-width:100%}[hidden]{display:none!important}</style>\n"
            + head0 + "</head>\n<body>\n")
    return head + translate_static(body0, l) + "\n</body>\n</html>\n"


root = os.path.dirname(os.path.abspath(args[2]))
changed = False
for l, p in LANGS.items():
    path = args[2] if not p else os.path.join(root, p, "index.html")
    os.makedirs(os.path.dirname(path), exist_ok=True)
    txt = page_for(l)
    try:
        changed |= open(path, encoding="utf-8").read() != txt
    except OSError:
        changed = True
    open(path, "w", encoding="utf-8").write(txt)
    print("ok", path, len(txt.encode("utf-8")), "bytes (standalone, " + l + ")")

# ---------- Карта сайта и robots.txt ----------
# Дата в карте меняется, только когда страницы действительно изменились (Worker по ней сообщает Яндексу и Bing)
smp = os.path.join(root, "sitemap.xml")
old = open(smp, encoding="utf-8").read() if os.path.exists(smp) else ""
m = re.search(r"<lastmod>([^<]+)</lastmod>", old)
today = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5)).strftime("%Y-%m-%d")   # время Душанбе
lastmod = today if changed or not m else m.group(1)
links = "".join('    <xhtml:link rel="alternate" hreflang="%s" href="%s"/>\n' % (l, SITE + p) for l, p in LANGS.items()) + \
    '    <xhtml:link rel="alternate" hreflang="x-default" href="%s"/>\n' % SITE
smx = ('<?xml version="1.0" encoding="UTF-8"?>\n'
       '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' +
       "".join("  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n%s  </url>\n" % (SITE + p, lastmod, links) for p in LANGS.values()) +
       "</urlset>\n")
open(smp, "w", encoding="utf-8").write(smx)
open(os.path.join(root, "robots.txt"), "w", encoding="utf-8").write(
    "# Shoh Parfumer — поисковикам можно всё, кроме служебного адреса Telegram-бота\n"
    "User-agent: *\nAllow: /\nDisallow: /api/tg/\n\nSitemap: " + SITE + "sitemap.xml\n")
print("ok sitemap.xml (lastmod " + lastmod + "), robots.txt")
