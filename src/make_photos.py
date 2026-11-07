"""Фото ароматов Shoh Parfumer для сайта: из data/photos/<id>-<n>.(png|jpg) делает public/img/aromaty/<id>-<n>.webp
(для страницы аромата) и <id>-<n>-s.webp (маленькая картинка в списке). Белые поля вокруг флакона обрезаются
(остаётся небольшой отступ) — файл легче, а флакон на сайте тот же: фон под фото белый.
В OWN (src/site.html) пишите путь без размера: photos: ["img/aromaty/oud-maracuja-1.webp"].
Запуск: python3 -I src/make_photos.py data/photos public/img/aromaty
"""
import os
import sys

from PIL import Image, ImageChops

BIG_H, SMALL_H = 960, 210       # высота в пикселях: страница аромата (до 3× на экране телефона) и список (56×64 на экране)

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
done = 0
for f in sorted(os.listdir(src)):
    base, ext = os.path.splitext(f)
    if ext.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        continue
    im = Image.open(os.path.join(src, f)).convert("RGB")
    # где кончается белый фон (с отражением флакона на полу — чтобы на белом фоне сайта не было видно края обрезки)
    box = ImageChops.difference(im, Image.new("RGB", im.size, (255, 255, 255))).convert("L").point(lambda v: 255 if v > 4 else 0).getbbox()
    if box:
        mx, my = round(0.06 * (box[2] - box[0])), round(0.04 * (box[3] - box[1]))
        im = im.crop((max(0, box[0] - mx), max(0, box[1] - my), min(im.width, box[2] + mx), min(im.height, box[3] + my)))
    # края плавно уходят в чистый белый — на белом фоне сайта не видно, где фото кончается
    fade = max(1, round(0.08 * im.width))
    mask = Image.new("L", im.size, 255)
    for i in range(fade):
        v = round(255 * i / fade)
        mask.paste(v, (i, 0, i + 1, im.height)); mask.paste(v, (im.width - 1 - i, 0, im.width - i, im.height))
    im = Image.composite(im, Image.new("RGB", im.size, (255, 255, 255)), mask)
    for suffix, h, q in (("", BIG_H, 76), ("-s", SMALL_H, 72)):
        x = im.copy()
        if x.height > h:
            x = x.resize((round(x.width * h / x.height), h), Image.LANCZOS)
        path = os.path.join(out, base + suffix + ".webp")
        x.save(path, "WEBP", quality=q, method=6)
        print(path, x.size, os.path.getsize(path) // 1024, "KB")
    done += 1
print("фото:", done)
