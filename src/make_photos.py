"""Фото ароматов Shoh Parfumer для сайта: из data/photos/<id>-<n>.(png|jpg) делает public/img/aromaty/<id>-<n>.webp
(до 800 px по ширине — для страницы аромата) и <id>-<n>-s.webp (240 px — маленькая картинка в списке).
В OWN (src/site.html) пишите путь без размера: photos: ["img/aromaty/oud-maracuja-1.webp"].
Запуск: python3 -I src/make_photos.py data/photos public/img/aromaty
"""
import os
import sys

from PIL import Image

src, out = sys.argv[1], sys.argv[2]
os.makedirs(out, exist_ok=True)
done = 0
for f in sorted(os.listdir(src)):
    base, ext = os.path.splitext(f)
    if ext.lower() not in (".png", ".jpg", ".jpeg", ".webp"):
        continue
    im = Image.open(os.path.join(src, f)).convert("RGB")
    for suffix, w, q in (("", 800, 82), ("-s", 240, 78)):
        x = im.copy()
        if x.width > w:
            x = x.resize((w, round(x.height * w / x.width)), Image.LANCZOS)
        path = os.path.join(out, base + suffix + ".webp")
        x.save(path, "WEBP", quality=q, method=6)
        print(path, x.size, os.path.getsize(path) // 1024, "KB")
    done += 1
print("фото:", done)
