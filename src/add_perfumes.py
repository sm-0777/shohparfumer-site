"""Добавляет в базу ароматы, которых в ней нет (data/perfumes_extra.jsonl).

Строка: {"b": бренд, "n": название, "copy_of": аромат того же бренда, с которого взять аккорды и вкус,
         "pc": популярность, "top"/"heart"/"base": ноты по-английски (как в словаре базы)}
Повторный запуск ничего не дублирует. Запускать до add_dupes.py.
Запуск: python3 -I src/add_perfumes.py data/db.json data/perfumes_extra.jsonl
"""
import json
import sys

db_path, extra_path = sys.argv[1], sys.argv[2]
d = json.load(open(db_path, encoding="utf-8"))
B, P = d["b"], d["p"]
note_id = {e.lower(): i for i, e in enumerate(d["ne"])}
have = {(B[x[1]], x[0]) for x in P}
added = 0
for line in open(extra_path, encoding="utf-8"):
    if not line.strip():
        continue
    o = json.loads(line)
    if (o["b"], o["n"]) in have:
        continue
    src = next(x for x in P if B[x[1]] == o["b"] and x[0] == o["copy_of"])
    row = list(src)
    row[0] = o["n"]
    row[4] = o.get("pc", src[4])
    row[3] = src[3] & ~(16 | 128)
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
