"""Значки сайта отдельными файлами (поисковики не берут значок, встроенный в страницу).

Рисунок тот же, что во вкладке браузера: три жёлтые точки на тёмном. Запуск (один раз, файлы лежат в public/):
  python3 -I src/make_icons.py public
"""
import sys

from PIL import Image, ImageDraw

out = sys.argv[1]
BG, Y = (11, 11, 10), (255, 198, 26)
SVG = ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 32 32"><rect width="32" height="32" rx="7" fill="#0B0B0A"/>'
       '<circle cx="9" cy="16" r="4" fill="#FFC61A"/><circle cx="16" cy="16" r="4" fill="#FFC61A" fill-opacity=".65"/>'
       '<circle cx="23" cy="16" r="4" fill="#FFC61A" fill-opacity=".35"/></svg>\n')


def mix(a):  # жёлтый с прозрачностью поверх тёмного фона
    return tuple(round(BG[i] + (Y[i] - BG[i]) * a) for i in range(3))


def icon(size, rounded=True):
    k = 8                                  # рисуем крупно и уменьшаем — края получаются гладкими
    s = size * k / 32
    im = Image.new("RGBA", (size * k, size * k), (0, 0, 0, 0))
    d = ImageDraw.Draw(im)
    if rounded:
        d.rounded_rectangle([0, 0, size * k - 1, size * k - 1], radius=7 * s, fill=BG + (255,))
    else:
        d.rectangle([0, 0, size * k, size * k], fill=BG + (255,))
    for cx, a in ((9, 1), (16, .65), (23, .35)):
        d.ellipse([(cx - 4) * s, 12 * s, (cx + 4) * s, 20 * s], fill=mix(a) + (255,))
    return im.resize((size, size), Image.LANCZOS)


open(f"{out}/favicon.svg", "w").write(SVG)
icon(48).save(f"{out}/favicon.ico", sizes=[(16, 16), (32, 32), (48, 48)])
icon(96).save(f"{out}/favicon-96.png")
icon(180, rounded=False).save(f"{out}/apple-touch-icon.png")
icon(512, rounded=False).save(f"{out}/logo.png")
print("ok: favicon.svg, favicon.ico, favicon-96.png, apple-touch-icon.png, logo.png")
