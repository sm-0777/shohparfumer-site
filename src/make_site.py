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
import shutil
import subprocess
import sys
import unicodedata
import urllib.parse

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


def load_own(src):
    a = src.index("  var TELEGRAM = ")
    b = src.index("\n", src.index("  var PICKUP = "))
    na = src.index("  var NOTE_TG = {")
    nb = src.index("\n  };\n", na) + 5
    code = src[a:b] + "\n" + src[na:nb] + "\nprocess.stdout.write(JSON.stringify({OWN: OWN, NOTE_TG: NOTE_TG, TELEGRAM: TELEGRAM, WHATSAPP: WHATSAPP, PICKUP_ON: PICKUP_ON, PICKUP: PICKUP, CONTACTS: CONTACTS}));"
    r = subprocess.run(["node", "-e", code], capture_output=True, text=True, check=True)
    return json.loads(r.stdout)


SHOP = load_own(tpl)
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


def store_address():
    a = {"@type": "PostalAddress", "addressLocality": "Dushanbe", "addressCountry": "TJ"}
    street = (SHOP["CONTACTS"].get("address") or {}).get("ru")
    if street:
        a["streetAddress"] = street
    return a


def ld_json(l):
    T = I18N[l]
    data = {"@context": "https://schema.org", "@graph": [
        {"@type": "WebSite", "@id": SITE + "#site", "url": SITE, "name": "Shoh Parfumer",
         "description": T["metaDesc"], "inLanguage": list(LANGS), "publisher": {"@id": SITE + "#store"}},
        # Магазин: адрес, часы и телефон добавить, когда владелец пришлёт (только настоящие данные)
        {"@type": "Store", "@id": SITE + "#store", "name": "Shoh Parfumer", "url": SITE,
         "logo": SITE + "logo.png", "image": SITE + "og.png", "description": T["metaDesc"],
         "address": store_address()},
    ]}
    c = SHOP["CONTACTS"]
    if c.get("phone"):
        data["@graph"][1]["telephone"] = c["phone"]
    if c.get("instagram"):
        data["@graph"][1]["sameAs"] = ["https://instagram.com/" + c["instagram"]]
    if (c.get("hours") or {}).get("en"):
        data["@graph"][1]["openingHours"] = c["hours"]["en"]
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
            "<link rel=\"apple-touch-icon\" href=\"/apple-touch-icon.png\">\n"
            "<link rel=\"manifest\" href=\"/site.webmanifest\">\n" + ld_json(l) +
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

# ---------- Страницы ароматов Shoh Parfumer для поисковиков ----------
# /aromaty/ — список, /aromaty/<id>/ — аромат (и то же в /tg/ и /en/). Лёгкие страницы без скрипта: название, цена,
# ноты, описание, доставка и кнопка «Заказать» → сайт с открытой формой заказа (?a=id&z=1).
DBJ = json.loads(db)
NOTES_RU, NOTES_EN = DBJ["n"], DBJ["ne"]
CITY = {"ru": "Душанбе", "tg": "Душанбе", "en": "Dushanbe"}
LIDX = {l: i for i, l in enumerate(LANGS)}
H = lambda s: html.escape(str(s), quote=False)


def note_name(s, l):
    x = s.split("|")
    if len(x) == 3:
        return x[LIDX[l]] or x[0]
    if l == "en" and s in NOTES_RU:
        return NOTES_EN[NOTES_RU.index(s)] or s
    if l == "tg":
        return SHOP["NOTE_TG"].get(s, s)
    return s


def money(n, l):
    return "{:,}".format(n).replace(",", " ") + " " + I18N[l]["currency"]


def own_info(o):
    ob, on = (o["of"].split("|") + [""])[:2]
    vols = [v for v in o.get("vol", []) if v and v[0] > 0]
    prices = [v[1] for v in vols if v[1] > 0]
    return ob, on, o.get("name") or on, vols, prices


def own_price(o, l):
    _, _, _, vols, prices = own_info(o)
    if not prices:
        return I18N[l]["ownPriceAsk"]
    return I18N[l]["ownFrom"].replace("{p}", money(min(prices), l)) if len(vols) > 1 else money(prices[0], l)


OWN_CSS = (":root{--bg:#0B0B0A;--surface:#151513;--soft:#211F19;--line:#2E2D27;--fg:#F5F2E9;--muted:#A8A496;--accent:#FFC61A;--ink:#1A1400;--ok:#34C771;--at:#FFC61A;color-scheme:dark}"
           "@media (prefers-color-scheme:light){:root{--bg:#F6F4EE;--surface:#FFFFFF;--soft:#EFEBDF;--line:#DDD8C9;--fg:#17160F;--muted:#625E4D;--ok:#178A49;--at:#8A6A00;color-scheme:light}}"
           "*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.5 Onest,system-ui,sans-serif;overflow-wrap:break-word}"
           "a{color:inherit}header{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line)}"
           ".in{max-width:720px;margin:0 auto;padding:12px 16px;display:flex;align-items:center;justify-content:space-between;gap:12px}"
           ".brand{text-decoration:none;font-family:Unbounded,system-ui,sans-serif;font-weight:600;font-size:1.0625rem}"
           ".langs{display:flex;gap:4px}.langs a{min-width:40px;min-height:38px;display:grid;place-items:center;border:1px solid var(--line);border-radius:10px;text-decoration:none;font-size:.8125rem;font-weight:600}"
           ".langs a[aria-current]{background:var(--accent);border-color:var(--accent);color:var(--ink)}"
           "main{max-width:720px;margin:0 auto;padding:20px 16px 40px;display:flex;flex-direction:column;gap:18px}"
           "h1,h2{font-family:Unbounded,system-ui,sans-serif;font-weight:600;line-height:1.2;margin:0}h1{font-size:clamp(1.4rem,5.4vw,2rem)}h2{font-size:1.0625rem}"
           ".by,.small{color:var(--muted)}.small{font-size:.875rem}.price{font-weight:600;font-size:1.0625rem}.ok{color:var(--ok)}.out{color:var(--muted)}"
           "p{margin:0}.chips{display:flex;flex-wrap:wrap;gap:6px;margin-top:4px}.chip{font-size:.8125rem;padding:3px 10px;border-radius:999px;background:var(--soft)}"
           ".layer{display:flex;flex-direction:column;gap:2px}.stack{display:flex;flex-direction:column;gap:10px}"
           "ul{list-style:none;margin:0;padding:0}.vols li{display:flex;justify-content:space-between;gap:12px;padding:10px 14px;border-radius:12px;background:var(--surface);border:1px solid var(--line)}"
           ".info{padding:12px 14px;border-radius:14px;background:var(--soft);display:flex;flex-direction:column;gap:6px}"
           ".acts{display:flex;flex-wrap:wrap;gap:8px}.acts .btn{flex:1 1 9rem}.btn{display:inline-flex;align-items:center;justify-content:center;min-height:48px;padding:12px 22px;border-radius:12px;background:var(--accent);color:var(--ink);font-weight:600;text-decoration:none;text-align:center}"
           ".btn.ghost{background:transparent;color:var(--fg);border:1px solid var(--line)}"
           ".list{display:flex;flex-direction:column;gap:8px}.list a{display:flex;flex-direction:column;gap:2px;padding:12px 14px;border-radius:14px;background:var(--surface);border:1px solid var(--line);text-decoration:none}"
           ".photo{display:block;width:100%;height:auto;max-height:70vh;object-fit:contain;background:#fff;border-radius:16px}"
           ".ourcard{display:flex;gap:14px;align-items:center;padding:12px 14px;border-radius:14px;background:var(--surface);border:1px solid var(--accent)}"
           ".ourcard img{width:64px;height:96px;object-fit:contain;background:#fff;border-radius:10px;flex:none}"
           ".list .it{display:flex;flex-direction:column;gap:2px;padding:12px 14px;border-radius:14px;background:var(--surface);border:1px solid var(--line)}"
           ".list .it span{color:var(--muted);font-size:.875rem}"
           ".list b{font-weight:600}.list span{color:var(--muted);font-size:.875rem}.list .p{color:var(--fg);font-weight:600}")


def own_head(l, title, desc, url, alts_map, ld, image=None):
    return ("<!doctype html>\n<html lang=\"" + l + "\">\n<head>\n<meta charset=\"utf-8\">\n"
            "<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">\n"
            "<title>" + H(title) + "</title>\n<meta name=\"description\" content=\"" + A(desc) + "\">\n"
            "<meta name=\"theme-color\" content=\"#0B0B0A\">\n<link rel=\"canonical\" href=\"" + url + "\">\n" +
            "".join('<link rel="alternate" hreflang="%s" href="%s">\n' % (x, alts_map[x]) for x in LANGS) +
            '<link rel="alternate" hreflang="x-default" href="%s">\n' % alts_map["ru"] +
            "<meta property=\"og:type\" content=\"website\">\n<meta property=\"og:site_name\" content=\"Shoh Parfumer\">\n"
            "<meta property=\"og:title\" content=\"" + A(title) + "\">\n<meta property=\"og:description\" content=\"" + A(desc) + "\">\n"
            "<meta property=\"og:url\" content=\"" + url + "\">\n<meta property=\"og:image\" content=\"" + A(image or SITE + "og.png") + "\">\n"
            "<meta property=\"og:locale\" content=\"" + LOCALE[l] + "\">\n<meta name=\"twitter:card\" content=\"summary_large_image\">\n"
            "<link rel=\"icon\" href=\"/favicon.ico\" sizes=\"48x48\">\n<link rel=\"icon\" href=\"/favicon.svg\" type=\"image/svg+xml\">\n"
            "<link rel=\"apple-touch-icon\" href=\"/apple-touch-icon.png\">\n"
            "<link rel=\"preconnect\" href=\"https://fonts.googleapis.com\">\n<link rel=\"preconnect\" href=\"https://fonts.gstatic.com\" crossorigin>\n"
            "<link href=\"https://fonts.googleapis.com/css2?family=Onest:wght@400;500;600&family=Unbounded:wght@500;600&display=swap\" rel=\"stylesheet\">\n"
            '<script type="application/ld+json">' + json.dumps(ld, ensure_ascii=False).replace("</", "<\\/") + "</script>\n"
            "<style>" + OWN_CSS + "</style>\n</head>\n<body>\n")


def own_header(l, alts_map):
    return ('<header><div class="in"><a class="brand" href="/' + LANGS[l] + '">Shoh Parfumer</a><nav class="langs">' +
            "".join('<a href="%s" hreflang="%s"%s>%s</a>' % (alts_map[x].replace(SITE, "/"), x, ' aria-current="page"' if x == l else "", {"ru": "RU", "tg": "TJ", "en": "EN"}[x]) for x in LANGS) +
            "</nav></div></header>\n")


def info_list(l):
    T = I18N[l]
    a = SHOP["PICKUP"].get(l) or SHOP["PICKUP"].get("ru")
    items = [T["ownDelivery"]] + ([T["ownPickup"].replace("{a}", a) if a else T["ownPickupSoon"]] if SHOP["PICKUP_ON"] else []) + [T["ownPay"]]
    return '<ul class="info">' + "".join("<li>" + H(x) + "</li>" for x in items) + "</ul>"


def own_page(o, l):
    T, base = I18N[l], SITE + LANGS[l]
    ob, on, title, vols, prices = own_info(o)
    full = "Shoh Parfumer " + title
    dupe = T["ownDupeOf"].replace("{n}", ob + " " + on)
    url = base + "aromaty/" + o["id"] + "/"
    alts_map = {x: SITE + LANGS[x] + "aromaty/" + o["id"] + "/" for x in LANGS}
    desc = (o.get("desc") or {}).get(l) or (o.get("desc") or {}).get("ru") or ""
    ptitle = full + " — " + dupe + " · " + own_price(o, l) + ", " + CITY[l]
    pdesc = (desc + " " + T["ownDelivery"] + ".").strip()
    offers = [{"@type": "Offer", "name": T["ownMl"].replace("{n}", str(v[0])), "price": str(v[1]), "priceCurrency": "TJS", "url": url,
               "availability": "https://schema.org/" + ("InStock" if o.get("stock") else "OutOfStock"), "seller": {"@id": SITE + "#store"}}
              for v in vols if v[1] > 0]
    photos = [SITE + f.lstrip("/") for f in o.get("photos") or []]
    prod = {"@type": "Product", "name": full, "description": desc, "brand": {"@type": "Brand", "name": "Shoh Parfumer"}, "url": url}
    if photos:
        prod["image"] = photos
    if offers:
        prod["offers"] = offers if len(offers) > 1 else offers[0]
    ld = {"@context": "https://schema.org", "@graph": [prod,
          {"@type": "Store", "@id": SITE + "#store", "name": "Shoh Parfumer", "url": SITE, "address": store_address()},
          {"@type": "BreadcrumbList", "itemListElement": [
              {"@type": "ListItem", "position": 1, "name": "Shoh Parfumer", "item": base},
              {"@type": "ListItem", "position": 2, "name": T["h8"], "item": base + "aromaty/"},
              {"@type": "ListItem", "position": 3, "name": title, "item": url}]}]}
    layers = [("top", "layerTop"), ("mid", "layerHeart"), ("base", "layerBase"), ("key", "ownNotesKey")]
    notes = "".join('<div class="layer"><span class="small">' + H(T[k]) + '</span><div class="chips">' +
                    "".join('<span class="chip">' + H(note_name(n, l)) + "</span>" for n in o["notes"][f]) + "</div></div>"
                    for f, k in layers if o.get("notes", {}).get(f))
    ask = T["ownAskText"].replace("{n}", full + " (" + dupe + ")").replace("{v}", ", " + T["ownMl"].replace("{n}", str(vols[0][0])) if len(vols) == 1 else "")
    contacts = ""
    if SHOP["TELEGRAM"]:
        contacts += '<a class="btn ghost" href="https://t.me/' + A(SHOP["TELEGRAM"]) + "?text=" + A(urllib.parse.quote(ask)) + '" rel="noopener">' + H(T["ownTg"]) + "</a>"
    if SHOP["WHATSAPP"]:
        contacts += '<a class="btn ghost" href="https://wa.me/' + A(re.sub(r"\D", "", SHOP["WHATSAPP"])) + "?text=" + A(urllib.parse.quote(ask)) + '" rel="noopener">' + H(T["ownWa"]) + "</a>"
    others = [x for x in SHOP["OWN"] if x["id"] != o["id"]]
    oi = next((k for k, v in own_by_orig.items() if v is o), None)
    body = (own_header(l, alts_map) + "<main>\n" +
            ('<img class="photo" src="' + A(photos[0].replace(SITE, "/")) + '" alt="' + A(full) + '" width="800" height="1200">\n' if photos else "") +
            '<div class="stack"><h1>' + H(title) + '</h1><span class="by">' + H("Shoh Parfumer · " + dupe) + "</span>" +
            '<span><span class="price">' + H(own_price(o, l)) + '</span> · <span class="' + ("ok" if o.get("stock") else "out") + '">' + H(T["ownIn"] if o.get("stock") else T["ownOut"]) + "</span></span></div>\n" +
            ("<p>" + H(desc) + "</p>\n" if desc else "") +
            '<div class="acts"><a class="btn" href="/' + LANGS[l] + "?a=" + A(o["id"]) + '&amp;z=1">' + H(T["orderBtn"]) + "</a>" + contacts + "</div>\n" +
            ('<section class="stack"><h2>' + H(T["ownNotes"]) + "</h2>" + notes + '<p class="small">' + H(T["ownNotesSame"]) + "</p></section>\n" if notes else "") +
            ('<section class="stack"><h2>' + H(T["ownVol"]) + '</h2><ul class="stack vols" style="gap:6px">' + "".join(
                "<li><span>" + H(T["ownMl"].replace("{n}", str(v[0]))) + "</span><b>" + H(money(v[1], l) if v[1] > 0 else T["ownPriceAsk"]) + "</b></li>" for v in vols) + "</ul></section>\n" if vols else "") +
            info_list(l) + "\n" +
            ('<p class="small"><a href="/' + LANGS[l] + "dupy/" + dslug[oi] + '/">' + H(tpl_t(T["dpH"], o=ob + " " + on)) + " →</a></p>\n" if oi is not None else "") +
            '<section class="stack"><h2>' + H(T["h8"]) + '</h2><div class="list">' + "".join(
                '<a href="/' + LANGS[l] + "aromaty/" + A(x["id"]) + '/"><b>' + H(own_info(x)[2]) + "</b><span>" + H(T["ownDupeOf"].replace("{n}", own_info(x)[0] + " " + own_info(x)[1])) +
                '</span><span class="p">' + H(own_price(x, l)) + "</span></a>" for x in others) + "</div></section>\n" +
            '<a class="btn ghost" href="/' + LANGS[l] + '">' + H(T["pageTitle"].split(" — ")[0]) + " — " + H(I18N[l]["brandSub"]) + "</a>\n</main>\n</body>\n</html>\n")
    return own_head(l, ptitle, pdesc, url, alts_map, ld, photos[0] if photos else None) + body


def own_list_page(l):
    T, base = I18N[l], SITE + LANGS[l]
    url = base + "aromaty/"
    alts_map = {x: SITE + LANGS[x] + "aromaty/" for x in LANGS}
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": T["h8"], "url": url, "itemListElement": [
        {"@type": "ListItem", "position": i + 1, "url": url + x["id"] + "/", "name": "Shoh Parfumer " + own_info(x)[2]} for i, x in enumerate(SHOP["OWN"])]}
    body = (own_header(l, alts_map) + "<main>\n<h1>" + H(T["h8"]) + "</h1>\n<p class=\"by\">" + H(T["lead8"]) + "</p>\n" +
            '<div class="list">' + "".join(
                '<a href="' + A(x["id"]) + '/"><b>' + H(own_info(x)[2]) + "</b><span>" + H("Shoh Parfumer · " + T["ownDupeOf"].replace("{n}", own_info(x)[0] + " " + own_info(x)[1])) +
                '</span><span class="p">' + H(own_price(x, l)) + "</span></a>" for x in SHOP["OWN"]) + "</div>\n" + info_list(l) + "\n" +
            '<div class="acts"><a class="btn" href="/' + LANGS[l] + '?a=all">' + H(T["ownAll"]) + "</a></div>\n</main>\n</body>\n</html>\n")
    return own_head(l, T["h8"] + " · " + CITY[l], T["lead8"], url, alts_map, ld) + body


def write_if(path, txt):
    global changed
    os.makedirs(os.path.dirname(path), exist_ok=True)
    try:
        changed |= open(path, encoding="utf-8").read() != txt
    except OSError:
        changed = True
    open(path, "w", encoding="utf-8").write(txt)




# ---------- Страницы «Дюпы …» для поисковиков: /dupy/ и /dupy/<оригинал>/ (+ /tg/, /en/) ----------
# Оригиналы, у которых есть известные дюпы (data/dupes.txt → du/xd в базе) или наш дюп. Ссылки ведут в «Найти дюп» (?d=uid)
# и в «Сравнить» (?c=uidA-uidB) на сайте.
DB_B, DB_P = DBJ["b"], DBJ["p"]


def js_uid(s):   # тот же код аромата, что на сайте: hash(brand + "|" + name).toString(36) по 16-битным знакам строки
    h = 0
    b = s.encode("utf-16-le")
    for i in range(0, len(b), 2):
        h = (h * 31 + (b[i] | (b[i + 1] << 8))) & 0xFFFFFFFF
    d, out = "0123456789abcdefghijklmnopqrstuvwxyz", ""
    while True:
        h, r = divmod(h, 36)
        out = d[r] + out
        if not h:
            return out


def slug(s):
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", s).strip("-")


def pl_ru(n, f):
    n10, n100 = n % 10, n % 100
    return f[0] if n10 == 1 and n100 != 11 else (f[1] if 2 <= n10 <= 4 and not 12 <= n100 <= 14 else f[2])


def plural(n, forms, l):
    if l == "ru":
        return pl_ru(n, forms)
    if l == "en":
        return forms[0] if n == 1 else forms[2]
    return forms[0]


def tpl_t(s, **kw):
    for k, v in kw.items():
        s = s.replace("{" + k + "}", str(v))
    return s


own_by_orig = {}
for o in SHOP["OWN"]:
    ob, on = (o["of"].split("|") + [""])[:2]
    for i, x in enumerate(DB_P):
        if DB_B[x[1]] == ob and x[0] == on:
            own_by_orig[i] = o
            break
dupes_of = {i: refs for i, refs in DBJ.get("du", [])}
dorig = sorted(set(dupes_of) | set(own_by_orig), key=lambda i: (DB_B[DB_P[i][1]].lower(), DB_P[i][0].lower()))
dslug, used = {}, set()
for i in dorig:
    sl = slug(DB_B[DB_P[i][1]] + " " + DB_P[i][0]) or "x"
    k = 2
    while sl in used:
        sl = slug(DB_B[DB_P[i][1]] + " " + DB_P[i][0]) + "-" + str(k); k += 1
    used.add(sl); dslug[i] = sl


def dupe_list(i):   # [(название, бренд, номер в базе или None)]
    out = []
    for r in dupes_of.get(i, []):
        if r >= 0:
            out.append((DB_P[r][0], DB_B[DB_P[r][1]], r))
        else:
            n, b = DBJ["xd"][-r - 1]
            out.append((n, b, None))
    return out


def orig_name(i):
    return DB_B[DB_P[i][1]] + " " + DB_P[i][0]


def dupe_page(i, l):
    T, base = I18N[l], SITE + LANGS[l]
    x = DB_P[i]
    o = own_by_orig.get(i)
    ds = dupe_list(i)
    n = len(ds) + (1 if o else 0)
    oname = orig_name(i)
    url = base + "dupy/" + dslug[i] + "/"
    alts_map = {y: SITE + LANGS[y] + "dupy/" + dslug[i] + "/" for y in LANGS}
    uid = js_uid(DB_B[x[1]] + "|" + x[0])
    title = tpl_t(T["dpTitle"], o=oname, n=str(n) + " " + plural(n, T["dpSimilar"], l))
    if o:
        title = tpl_t(T["dpTitleOwn"], t=title, p=own_price(o, l))
    names = ([("Shoh Parfumer " + own_info(o)[2])] if o else []) + [b + " " + nm for nm, b, _ in ds]
    desc = tpl_t(T["dpDesc"], o=oname, list=", ".join(names[:4]) + ("…" if len(names) > 4 else "")) + (" " + tpl_t(T["dpDescOwn"], p=own_price(o, l)) if o else "")
    app = "/" + LANGS[l]
    # наш дюп — первым
    our = ""
    if o:
        ph = (o.get("photos") or [None])[0]
        our = ('<section class="stack"><h2>' + H(T["dpOur"]) + "</h2>" +
               '<div class="ourcard">' + ('<img src="/' + A(ph.replace(".webp", "-s.webp")) + '" alt="" width="80" height="120">' if ph else "") +
               '<div class="stack" style="gap:4px"><b>' + H("Shoh Parfumer " + own_info(o)[2]) + '</b><span class="price">' + H(own_price(o, l)) + "</span>" +
               '<span class="small">' + H(T["ownDelivery"]) + "</span></div></div>" +
               '<div class="acts"><a class="btn" href="' + app + "?a=" + A(o["id"]) + '&amp;z=1">' + H(T["orderBtn"]) + "</a>" +
               '<a class="btn ghost" href="' + app + "aromaty/" + A(o["id"]) + '/">' + H(T["ownMore"]) + "</a></div></section>\n")
    known = ""
    if ds:
        known = ('<section class="stack"><h2>' + H(T["dpKnown"]) + '</h2><div class="list">' + "".join(
            ('<a href="' + app + "?c=" + uid + "-" + js_uid(b + "|" + nm) + "&amp;l=" + l + '"><b>' + H(nm) + "</b><span>" + H(b) + '</span><span class="p">' + H(T["dpCompare"]) + " →</span></a>")
            if r is not None else ('<div class="it"><b>' + H(nm) + "</b><span>" + H(b) + "</span></div>")
            for nm, b, r in ds) + '</div><p class="small">' + H(T["dpSrc"]) + "</p></section>\n")
    # об оригинале: год, концентрация, ноты (только если ноты в базе надёжные)
    facts = []
    if len(x) > 8 and x[8]:
        facts.append(T["cmpYear"] + ": " + str(x[8]))
    if len(x) > 9 and x[9] and x[9] < len(T["concNames"]):
        facts.append(T["cmpConc"] + ": " + T["concNames"][x[9]])
    notes = ""
    if not (x[3] & (128 | 16)) and x[6]:
        by = {1: [], 2: [], 3: []}
        for c in x[6]:
            if (c & 3) in by:
                by[c & 3].append(note_name(NOTES_RU[c >> 2], l))
        notes = "".join('<div class="layer"><span class="small">' + H(T[k]) + '</span><div class="chips">' + "".join('<span class="chip">' + H(v) + "</span>" for v in by[ly][:10]) + "</div></div>"
                        for ly, k in ((1, "layerTop"), (2, "layerHeart"), (3, "layerBase")) if by[ly])
    about = ""
    if facts or notes:
        about = ('<section class="stack"><h2>' + H(T["dpAbout"]) + "</h2>" + ("<p class=\"by\">" + H(" · ".join(facts)) + "</p>" if facts else "") + notes + "</section>\n")
    # ещё дюпы этого бренда
    same = [j for j in dorig if j != i and DB_P[j][1] == x[1]][:8]
    more = ('<section class="stack"><h2>' + H(tpl_t(T["dpMore"], b=DB_B[x[1]])) + '</h2><div class="list">' + "".join(
        '<a href="' + app + "dupy/" + dslug[j] + '/"><b>' + H(DB_P[j][0]) + "</b><span>" + H(DB_B[DB_P[j][1]]) + "</span></a>" for j in same) + "</div></section>\n") if same else ""
    ld = {"@context": "https://schema.org", "@graph": [
        {"@type": "ItemList", "name": tpl_t(T["dpH"], o=oname), "url": url, "itemListElement": [
            {"@type": "ListItem", "position": k + 1, "name": nm} for k, nm in enumerate(names)]},
        {"@type": "BreadcrumbList", "itemListElement": [
            {"@type": "ListItem", "position": 1, "name": "Shoh Parfumer", "item": base},
            {"@type": "ListItem", "position": 2, "name": T["dpAllH"], "item": base + "dupy/"},
            {"@type": "ListItem", "position": 3, "name": oname, "item": url}]}]}
    body = (own_header(l, alts_map) + "<main>\n" +
            '<div class="stack"><h1>' + H(tpl_t(T["dpH"], o=oname)) + '</h1><p class="by">' + H(tpl_t(T["dpLead"], o=oname)) + "</p></div>\n" +
            our + known + about +
            '<div class="acts"><a class="btn' + (" ghost" if o else "") + '" href="' + app + "?d=" + uid + "&amp;l=" + l + '">' + H(T["dpOpen"]) + "</a></div>\n" +
            more +
            '<p class="small"><a href="' + app + 'dupy/">' + H(T["dpAllLink"]) + "</a> · <a href=\"" + app + '">' + H(T["dpHome"]) + "</a></p>\n</main>\n</body>\n</html>\n")
    return own_head(l, title, desc, url, alts_map, ld) + body


def dupe_list_page(l):
    T, base = I18N[l], SITE + LANGS[l]
    url = base + "dupy/"
    alts_map = {y: SITE + LANGS[y] + "dupy/" for y in LANGS}
    rows = "".join('<a href="' + dslug[i] + '/"><b>' + H(DB_P[i][0]) + "</b><span>" + H(DB_B[DB_P[i][1]]) + "</span>" +
                   ('<span class="p">' + H(T["ownHas"]) + " · " + H(own_price(own_by_orig[i], l)) + "</span>" if i in own_by_orig else "") + "</a>"
                   for i in sorted(dorig, key=lambda i: (i not in own_by_orig, DB_B[DB_P[i][1]].lower(), DB_P[i][0].lower())))
    ld = {"@context": "https://schema.org", "@type": "ItemList", "name": T["dpAllH"], "url": url, "itemListElement": [
        {"@type": "ListItem", "position": k + 1, "url": url + dslug[i] + "/", "name": orig_name(i)} for k, i in enumerate(dorig)]}
    body = (own_header(l, alts_map) + "<main>\n<h1>" + H(T["dpAllH"]) + "</h1>\n<p class=\"by\">" + H(T["dpAllLead"]) + "</p>\n" +
            '<div class="list">' + rows + "</div>\n" +
            '<div class="acts"><a class="btn" href="/' + LANGS[l] + '?d=all&amp;l=' + l + '">' + H(T["dupeBtn"]) + "</a></div>\n</main>\n</body>\n</html>\n")
    return own_head(l, T["dpAllH"] + " · Shoh Parfumer", T["dpAllLead"], url, alts_map, ld) + body


dids = [dslug[i] for i in dorig]
for l, p in LANGS.items():
    ddir = os.path.join(root, p, "dupy")
    if os.path.isdir(ddir):                            # оригинал больше не в списке — убираем его страницу
        for d in os.listdir(ddir):
            if os.path.isdir(os.path.join(ddir, d)) and d not in dids:
                shutil.rmtree(os.path.join(ddir, d)); changed = True
    write_if(os.path.join(ddir, "index.html"), dupe_list_page(l))
    for i in dorig:
        write_if(os.path.join(ddir, dslug[i], "index.html"), dupe_page(i, l))
print("ok dupy: %d оригиналов × %d языка" % (len(dorig), len(LANGS)))

# страницы ароматов пишем после «Дюпов»: на них ссылка «Дюпы <оригинал>»
ids = [o["id"] for o in SHOP["OWN"]]
assert len(ids) == len(set(ids)) and all(re.fullmatch(r"[a-z0-9-]+", i) for i in ids), "id ароматов: латиница, цифры, дефис, без повторов"
for l, p in LANGS.items():
    adir = os.path.join(root, p, "aromaty")
    if os.path.isdir(adir):                            # аромат убрали из списка — убираем и его страницу
        for d in os.listdir(adir):
            if os.path.isdir(os.path.join(adir, d)) and d not in ids:
                shutil.rmtree(os.path.join(adir, d)); changed = True
    if ids:
        write_if(os.path.join(adir, "index.html"), own_list_page(l))
        for o in SHOP["OWN"]:
            write_if(os.path.join(adir, o["id"], "index.html"), own_page(o, l))
print("ok aromaty: %d ароматов × %d языка" % (len(ids), len(LANGS)))

# ---------- Карта сайта и robots.txt ----------
# Дата в карте меняется, только когда страницы действительно изменились (Worker по ней сообщает Яндексу и Bing)
smp = os.path.join(root, "sitemap.xml")
old = open(smp, encoding="utf-8").read() if os.path.exists(smp) else ""
m = re.search(r"<lastmod>([^<]+)</lastmod>", old)
today = (datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=5)).strftime("%Y-%m-%d")   # время Душанбе
lastmod = today if changed or not m else m.group(1)
groups = [""] + (["aromaty/"] + ["aromaty/" + i + "/" for i in ids] if ids else []) + ["dupy/"] + ["dupy/" + d + "/" for d in dids]   # страница + её версии на трёх языках


def sm_group(sub):
    links = "".join('    <xhtml:link rel="alternate" hreflang="%s" href="%s"/>\n' % (l, SITE + p + sub) for l, p in LANGS.items()) + \
        '    <xhtml:link rel="alternate" hreflang="x-default" href="%s"/>\n' % (SITE + sub)
    return "".join("  <url>\n    <loc>%s</loc>\n    <lastmod>%s</lastmod>\n%s  </url>\n" % (SITE + p + sub, lastmod, links) for p in LANGS.values())


smx = ('<?xml version="1.0" encoding="UTF-8"?>\n'
       '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9" xmlns:xhtml="http://www.w3.org/1999/xhtml">\n' +
       "".join(sm_group(g) for g in groups) + "</urlset>\n")
open(smp, "w", encoding="utf-8").write(smx)
open(os.path.join(root, "robots.txt"), "w", encoding="utf-8").write(
    "# Shoh Parfumer — поисковикам можно всё, кроме служебных адресов (/api/ — отзывы, заказы, бот)\n"
    "User-agent: *\nAllow: /\nDisallow: /api/\n\nSitemap: " + SITE + "sitemap.xml\n")
open(os.path.join(root, "site.webmanifest"), "w", encoding="utf-8").write(json.dumps({
    "name": "Shoh Parfumer — " + I18N["ru"]["brandSub"], "short_name": "Shoh Parfumer", "lang": "ru", "start_url": "/", "scope": "/",
    "display": "standalone", "background_color": "#0B0B0A", "theme_color": "#0B0B0A", "description": I18N["ru"]["metaDesc"],
    "icons": [{"src": "/icon-192.png", "sizes": "192x192", "type": "image/png"}, {"src": "/logo.png", "sizes": "512x512", "type": "image/png"},
              {"src": "/logo.png", "sizes": "512x512", "type": "image/png", "purpose": "maskable"}]}, ensure_ascii=False, indent=1))
print("ok sitemap.xml (lastmod " + lastmod + "), robots.txt, site.webmanifest")
