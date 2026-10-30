"""Вносит в базу проверенные ноты из data/notes_manual.jsonl (одна строка — один аромат).

Строка: {"b": бренд, "n": название, "top": [...], "heart": [...], "base": [...], "src": откуда взято}
Ноты пишутся по-английски, как в источнике. Скрипт находит их в словаре базы;
синонимы задаются в SAME, новые ноты (с русским названием) — в NEW_RU.
Запуск: python3 -I src/add_notes.py data/db.json data/notes_manual.jsonl
"""
import json
import sys

# Источник называет ноту иначе, чем словарь базы
SAME = {"ambrette": "ambrette seed", "bulgarian rose": "rose", "turkish rose": "rose", "carrot seeds": "carrot seed",
        "incense": "frankincense", "white flowers": "floral notes", "tiare flower": "tiare"}
# Ноты, которых в словаре ещё нет: английское → русское название
NEW_RU = {"tiare": "тиаре"}

db_path, notes_path = sys.argv[1], sys.argv[2]
d = json.load(open(db_path, encoding="utf-8"))
B, P = d["b"], d["p"]
note_id = {e.lower(): i for i, e in enumerate(d["ne"])}
by_key = {(B[x[1]], x[0]): x for x in P}


def nid(name):
    name = SAME.get(name.lower(), name.lower())
    if name not in note_id:
        if name not in NEW_RU:
            sys.exit(f"нет ноты в словаре и нет перевода в NEW_RU: {name}")
        note_id[name] = len(d["ne"])
        d["ne"].append(name)
        d["n"].append(NEW_RU[name])
        d["c"].append(-1)
    return note_id[name]


done, missing = 0, []
for line in open(notes_path, encoding="utf-8"):
    if not line.strip():
        continue
    o = json.loads(line)
    x = by_key.get((o["b"], o["n"]))
    if x is None:
        missing.append(f'{o["b"]} | {o["n"]}')
        continue
    codes, seen = [], set()
    for layer, key in ((1, "top"), (2, "heart"), (3, "base")):
        for name in o[key]:
            i = nid(name)
            if i not in seen:
                seen.add(i)
                codes.append(i * 4 + layer)
    x[6] = codes
    x[3] &= ~(16 | 128)   # ноты больше не заимствованные и не испорченные
    done += 1

txt = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(db_path, "w", encoding="utf-8").write(txt)
print(f"внесено ароматов: {done}" + ("\nНЕ НАЙДЕНЫ:\n  " + "\n  ".join(missing) if missing else ""))
