"""Точный «Характер» ароматов (в процентах) для раздела «Сравнить».

В базе сайта характер хранится грубо (0–3 по каждому вкусу) — этого хватает для подбора. Для полосок с процентами
этот скрипт заново считает тот же вектор вкуса, что и src/build_db.py (аккорды 60% + ноты 40%), но точнее:
каждый вкус в процентах от самой сильной черты аромата (100%), с шагом 5%.

Результат — отдельный файл public/taste.json, его сайт загружает только когда открыто сравнение (главная страница
не тяжелеет). В db.json записывается метка «th»: если базу пересобрали, а taste.json — нет, сайт это заметит
и покажет полоски по грубым данным.

Запуск (последним шагом пересборки базы): python3 -I src/make_taste.py data/db.json parfumo.csv public/taste.json
"""
import csv
import hashlib
import importlib.util
import json
import sys

db_path, csv_path, out_path = sys.argv[1], sys.argv[2], sys.argv[3]

# Функции из build_db.py (всё до чтения CSV), чтобы расчёт был тем же самым
src = open("src/build_db.py", encoding="utf-8").read()
g = {"__name__": "build_db_head"}
exec(compile(src[:src.index("rows = list(csv.DictReader")].replace("SRC, OUT = sys.argv[1], sys.argv[2]", "SRC = OUT = None"), "build_db.py", "exec"), g)
clean, clean_brand, clean_name, unit = g["clean"], g["clean_brand"], g["clean_name"], g["unit"]
accord_vec, note_vec, PRIORITY = g["accord_vec"], g["note_vec"], g["PRIORITY"]
spec = importlib.util.spec_from_file_location("clean_names", "src/clean_names.py")
cn = importlib.util.module_from_spec(spec)
spec.loader.exec_module(cn)

best = {}
for r in csv.DictReader(open(csv_path, encoding="utf-8")):
    acc = clean(r["Main_Accords"])
    tops = [x.strip() for x in (clean(r["Top_Notes"]) or "").split(",") if x.strip()]
    mids = [x.strip() for x in (clean(r["Middle_Notes"]) or "").split(",") if x.strip()]
    bases = [x.strip() for x in (clean(r["Base_Notes"]) or "").split(",") if x.strip()]
    if not acc and not (tops or mids or bases):
        continue
    brand = clean_brand(r["Brand"])
    brand = cn.BRAND_FIX.get(brand, brand)
    pc = int(float(r["Rating_Count"])) if clean(r["Rating_Count"]) else 0
    if pc < 20 and brand not in PRIORITY:
        continue
    year = clean(r["Release_Year"])
    year = str(int(float(year))) if year else None
    name = clean_name(r["Name"], brand, year)
    if not name:
        continue
    a, nv = unit(accord_vec(acc)), unit(note_vec(tops + mids + bases))
    u = [0.6 * x + 0.4 * y for x, y in zip(a, nv)] if any(a) and any(nv) else (a if any(a) else nv)
    if not any(u):
        continue
    if brand == "Paco Rabanne" and name.startswith("Million"):
        name = "1 " + name            # как в src/postprocess.py (в исходных данных срезана цифра «1»)
    key = (brand.lower(), cn.fix(brand, name).lower())
    if key not in best or best[key][0] < pc:
        best[key] = (pc, u)

d = json.load(open(db_path, encoding="utf-8"))
B, P = d["b"], d["p"]
# Ароматы, добавленные вручную (data/perfumes_extra.jsonl), берут вкус у аромата той же линейки — так же, как в базе
for line in open("data/perfumes_extra.jsonl", encoding="utf-8"):
    if line.strip():
        o = json.loads(line)
        k = (o["b"].lower(), o["n"].lower())
        if k not in best and (o["b"].lower(), o["copy_of"].lower()) in best:
            best[k] = best[(o["b"].lower(), o["copy_of"].lower())]
CH = "0123456789abcdefghijk"          # 0…20 → 0%…100% с шагом 5%
out, same, miss = [], 0, 0
for x in P:
    v = best.get((B[x[1]].lower(), x[0].lower()))
    if not v:
        out.append("")                # нет в исходных данных (добавлен вручную) — сайт возьмёт грубые значения
        miss += 1
        continue
    u, mx = v[1], max(v[1])
    if "".join(str(int(round(3 * t / mx))) for t in u) != x[2]:
        out.append("")                # вкус в базе считали из других данных — точные проценты не подходят, берём грубые
        miss += 1
        continue
    same += 1
    out.append("".join(CH[int(round(20 * t / mx))] for t in u))
th = hashlib.sha1("\n".join(B[x[1]] + "|" + x[0] for x in P).encode("utf-8")).hexdigest()[:12]
d["th"] = th
open(db_path, "w", encoding="utf-8").write(json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/"))
open(out_path, "w", encoding="utf-8").write(json.dumps({"h": th, "t": out}, separators=(",", ":")))
print(f"ароматов: {len(P)}; точный характер: {same}; без него (грубые значения): {miss}; метка: {th}")
