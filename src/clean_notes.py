"""Убирает из базы испорченные ноты (data/fake_notes.txt).

Сайт-источник подмешивает в данные выдуманные слова (xylophazq, zorplox…) и «вонючие» слова-приманки
(sewer, rot, sock…), чтобы ловить копирование. Проверка показала: у таких ароматов подменён весь список нот
(например, у Tom Ford Oud Wood вместо уда и розового дерева стоят «хлор» и «томатный лист»).
Поэтому ноты такого аромата удаляются целиком, а сам аромат помечается флагом 128 — «ноты нужно внести заново».
Запуск: python3 -I src/clean_notes.py data/db.json data/fake_notes.txt
"""
import json
import sys

db_path, fake_path = sys.argv[1], sys.argv[2]
d = json.load(open(db_path, encoding="utf-8"))
fake = {l.strip().lower() for l in open(fake_path, encoding="utf-8") if l.strip() and not l.startswith("#")}
ids = {i for i, e in enumerate(d["ne"]) if e.lower() in fake}
hit = removed = 0
for x in d["p"]:
    if any((v >> 2) in ids for v in x[6]):
        hit += 1
        removed += len(x[6])
        x[6] = []
        x[3] |= 128
txt = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(db_path, "w", encoding="utf-8").write(txt)
print(f"ложных нот в словаре: {len(ids)} | испорченных ароматов: {hit} (ноты удалены, нужно внести заново) | удалено записей: {removed}")
