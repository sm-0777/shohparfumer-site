"""Добавляет в базу список известных дюпов из data/dupes.txt.

Запуск: python3 -I src/add_dupes.py data/db.json data/dupes.txt
В базе появляются ключи:
  du — [[номер оригинала, [ссылки на дюпы]], ...]; ссылка >= 0 — номер аромата в базе,
       ссылка < 0 — дюп, которого нет в базе: -(номер в xd + 1)
  xd — [[название, бренд], ...] дюпы, которых нет в базе
Скрипт можно запускать сколько угодно раз: ключи du и xd пересоздаются.
"""
import json
import sys

db_path, list_path = sys.argv[1], sys.argv[2]
d = json.load(open(db_path, encoding="utf-8"))
B, P = d["b"], d["p"]
index = {}
for i, x in enumerate(P):
    index.setdefault((B[x[1]].lower(), x[0].lower()), i)

pairs, missing = {}, []
xd, xd_index = [], {}
for ln, line in enumerate(open(list_path, encoding="utf-8"), 1):
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    left, _, right = line.partition("=>")
    ob, _, on = (s.strip() for s in left.partition("|"))
    db_, _, dn = (s.strip() for s in right.partition("|"))
    if not (ob and on and db_ and dn):
        sys.exit(f"строка {ln}: не понимаю формат: {line}")
    oi = index.get((ob.lower(), on.lower()))
    if oi is None:
        missing.append(f"{ln}: {ob} | {on}")
        continue
    di = index.get((db_.lower(), dn.lower()))
    if di is None:
        key = (db_.lower(), dn.lower())
        if key not in xd_index:
            xd_index[key] = len(xd)
            xd.append([dn, db_])
        ref = -(xd_index[key] + 1)
    else:
        ref = di
    refs = pairs.setdefault(oi, [])
    if ref not in refs:
        refs.append(ref)

d["du"] = [[oi, refs] for oi, refs in sorted(pairs.items())]
d["xd"] = xd
txt = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(db_path, "w", encoding="utf-8").write(txt)
links = sum(len(r) for r in pairs.values())
print(f"оригиналов: {len(pairs)} | дюпов: {links} (из базы: {links - sum(1 for r in pairs.values() for x in r if x < 0)}, добавлено отдельно: {len(xd)})")
if missing:
    print("НЕ НАЙДЕНЫ оригиналы (проверьте название в базе):\n  " + "\n  ".join(missing))
