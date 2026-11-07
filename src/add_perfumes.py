"""Добавляет в базу ароматы, которых в ней нет (data/perfumes_extra.jsonl).

Строка: {"b": бренд, "n": название, "copy_of": аромат того же бренда, с которого взять аккорды и вкус,
         "pc": популярность, "top"/"heart"/"base": ноты по-английски (как в словаре базы)}
Без "copy_of" (оригинала той же линейки в базе нет): вкус считается по нотам так же, как в src/build_db.py, аккордов нет,
"conc" — концентрация (1 EDT, 2 EDP, 3 экстракт…), "new_notes": {"нота по-английски": "по-русски"} — ноты, которых нет в словаре.
Повторный запуск ничего не дублирует. Запускать до add_dupes.py.
Запуск: python3 -I src/add_perfumes.py data/db.json data/perfumes_extra.jsonl
"""
import json
import sys

db_path, extra_path = sys.argv[1], sys.argv[2]
d = json.load(open(db_path, encoding="utf-8"))
B, P = d["b"], d["p"]
note_id = {e.lower(): i for i, e in enumerate(d["ne"])}
_bd = None


def build_db_funcs():   # функции вкуса из build_db.py (всё до чтения CSV) — расчёт тот же самый
    global _bd
    if _bd is None:
        src_txt = open("src/build_db.py", encoding="utf-8").read()
        _bd = {"__name__": "build_db_head"}
        exec(compile(src_txt[:src_txt.index("rows = list(csv.DictReader")].replace("SRC, OUT = sys.argv[1], sys.argv[2]", "SRC = OUT = None"), "build_db.py", "exec"), _bd)
    return _bd
have = {(B[x[1]], x[0]) for x in P}
added = 0
for line in open(extra_path, encoding="utf-8"):
    if not line.strip():
        continue
    o = json.loads(line)
    if (o["b"], o["n"]) in have:
        continue
    for en, ru in (o.get("new_notes") or {}).items():          # новая нота в словарь (в конец — номера старых не меняются)
        if en.lower() not in note_id:
            d["n"].append(ru); d["ne"].append(en); note_id[en.lower()] = len(d["ne"]) - 1
    if o.get("copy_of"):
        src = next(x for x in P if B[x[1]] == o["b"] and x[0] == o["copy_of"])
        row = list(src)
        row[0] = o["n"]
        row[4] = o.get("pc", src[4])
        row[3] = src[3] & ~(16 | 128)
    else:
        g = build_db_funcs()
        u = g["unit"](g["note_vec"](o["top"] + o["heart"] + o["base"]))
        if not any(u):
            sys.exit(f"по нотам не получается вкус: {o['n']}")
        mx = max(u)
        uu = g["unit"](u)
        diff = (uu[0] + uu[1] + 0.3 * uu[3]) - (uu[4] + uu[7] + 0.8 * uu[5] + 0.8 * uu[9] + 0.3 * uu[6])
        season = 0 if diff > 0.1 else (1 if diff < -0.3 else 2)
        if o["b"] not in B:
            B.append(o["b"])
        row = [o["n"], B.index(o["b"]), "".join(str(int(round(3 * x / mx))) for x in u), season + 8 * (o["b"] in g["PRIORITY"]),
               o.get("pc", 0), 0, [], "", o.get("year", 0), o.get("conc", 0)]
    codes = []
    for layer, key in ((1, "top"), (2, "heart"), (3, "base")):
        for name in o[key]:
            if name.lower() not in note_id:
                sys.exit(f"нет ноты в словаре: {name}")
            codes.append(note_id[name.lower()] * 4 + layer)
    row[6] = codes
    P.append(row)
    have.add((o["b"], o["n"]))
    added += 1
txt = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(db_path, "w", encoding="utf-8").write(txt)
print(f"добавлено ароматов: {added}")
