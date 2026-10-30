"""Добавляет в базу год выпуска и концентрацию (для раздела «Сравнить») из исходных данных Parfumo.

Аромат ищется так же, как его выбирала сборка базы (src/build_db.py): бренд + очищенное название,
из нескольких строк — та, у которой больше оценок. Концентрация берётся из названия аромата
(«… Eau de Parfum»), а если там её нет — из столбца Concentration. Неизвестное не придумывается.
Ручные поправки (официальные данные брендов) — в data/info_manual.txt: «Бренд | Название | год | концентрация».

В строку аромата дописываются два поля: [8] год (0 — неизвестен), [9] концентрация (код ниже, 0 — неизвестна).
Запуск: python3 -I src/add_info.py data/db.json parfumo.csv data/info_manual.txt
"""
import csv
import importlib.util
import json
import re
import sys

# Названия на сайте очищены src/clean_names.py — исходные названия приводим к тому же виду
_spec = importlib.util.spec_from_file_location("clean_names", "src/clean_names.py")
cn = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cn)

# Коды концентраций (на сайте — CONC_NAMES в src/site.html, три языка)
CONC = {"EDT": 1, "EDP": 2, "EXT": 3, "PAR": 4, "EDC": 5, "OIL": 6}
FROM_COLUMN = {"eau de toilette": "EDT", "eau de parfum": "EDP", "eau de parfum intense": "EDP", "extrait de parfum": "EXT",
               "extrait": "EXT", "parfum": "PAR", "perfume": "PAR", "pure perfume": "PAR", "eau de cologne": "EDC",
               "cologne": "EDC", "perfume oil": "OIL"}
PRIORITY = None  # берётся из build_db.py, чтобы правила отбора строк совпадали


def conc_from_name(n):
    n = " " + n.lower().replace("’", "'") + " "
    if re.search(r"[\s']eau de parfum", n):        # и «L'Eau de Parfum»
        return "EDP"
    if re.search(r"[\s']eau de toilette", n):
        return "EDT"
    if " extrait de parfum" in n or n.rstrip().endswith(" extrait"):
        return "EXT"
    if " eau de cologne" in n:
        return "EDC"
    if n.rstrip().endswith(" parfum") and not n.rstrip().endswith(" le parfum"):
        return "PAR"
    return None


def clean(x):
    x = (x or "").strip()
    return "" if x in ("", "NA") else x


def clean_brand(b):
    return b.split(" / ")[0].strip()


def clean_name(name, brand, year):
    n = name.strip()
    if year:
        n = re.sub(r"\s+%s\b" % re.escape(year), "", n)
    m = re.search(r"(?<=\S)\s+%s\b" % re.escape(brand), n, flags=re.I)
    if m and m.start() > 0:
        n2 = (n[:m.start()] + n[m.end():]).strip()
        if n2:
            n = n2
    return re.sub(r"\s{2,}", " ", n)


db_path, csv_path = sys.argv[1], sys.argv[2]
manual_path = sys.argv[3] if len(sys.argv) > 3 else None
src = open("src/build_db.py", encoding="utf-8").read()
PRIORITY = set(re.search(r'PRIORITY = set\("""(.*?)"""', src, re.S).group(1).split("|"))

best = {}
for r in csv.DictReader(open(csv_path, encoding="utf-8")):
    if not clean(r["Main_Accords"]) and not (clean(r["Top_Notes"]) or clean(r["Middle_Notes"]) or clean(r["Base_Notes"])):
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
    key = (brand.lower(), cn.fix(brand, name).lower())
    if key not in best or best[key][0] < pc:
        best[key] = (pc, int(year) if year else 0, clean(r["Concentration"]).lower())

manual = {}
if manual_path:
    for line in open(manual_path, encoding="utf-8"):
        line = line.split("#", 1)[0].strip()
        if not line:
            continue
        b, n, y, c = [x.strip() for x in line.split("|")]
        manual[(b, n)] = (int(y) if y else 0, c or None)

d = json.load(open(db_path, encoding="utf-8"))
B, P = d["b"], d["p"]
n_year = n_conc = n_conflict = 0
conflicts = []
for x in P:
    b = B[x[1]]
    info = best.get((b.lower(), x[0].lower()))
    if info is None and x[0].startswith("1 "):          # «1 Million»: в данных без «1»
        info = best.get((b.lower(), x[0][2:].lower()))
    year = info[1] if info else 0
    if year and not (1700 <= year <= 2026):
        year = 0
    # В «испорченных» строках Parfumo (флаг 128 — подменённые ноты) год тоже бывает неверным (Oud Wood 2009 вместо 2007)
    if x[3] & 128:
        year = 0
    # В названии есть другой год («Koh-Kong 2015», а в данных 1991) — не верим
    m = re.search(r"\b(19|20)\d\d\b", x[0])
    if year and m and int(m.group(0)) != year:
        year = 0
    by_name, by_col = conc_from_name(x[0]), FROM_COLUMN.get(info[2]) if info else None
    if by_name and by_col and by_name != by_col:
        n_conflict += 1
        conflicts.append(f"{b} | {x[0]}: в названии {by_name}, в столбце {by_col}")
    conc = by_name or by_col
    if (b, x[0]) in manual:
        my, mc = manual[(b, x[0])]
        year = my or year
        conc = mc or conc
    del x[8:]
    if year or conc:
        x.extend([year, CONC.get(conc, 0)])
    n_year += bool(year)
    n_conc += bool(conc)

txt = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(db_path, "w", encoding="utf-8").write(txt)
print(f"ароматов: {len(P)}; год известен: {n_year}; концентрация известна: {n_conc}; "
      f"расхождений название/столбец: {n_conflict} (верим названию); ручных поправок: {len(manual)}")
for c in conflicts[:15]:
    print("  ", c)
