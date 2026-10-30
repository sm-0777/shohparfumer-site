"""Убирает из названий ароматов надписи на других алфавитах (японский, китайский, арабский, тайский, греческий…).

В исходных данных у части ароматов рядом с латинским названием записано оригинальное:
«La Vallière ラヴァリエール Parfum», «Ajwad اجواد», «Ginza / 資生堂 Eau de Parfum». На сайте остаётся латиница:
«La Vallière Parfum», «Ajwad», «Ginza Eau de Parfum». Кириллицу не трогаем (её читают покупатели).
Если без такой надписи от названия не остаётся ни одной латинской буквы — название не меняется.
Арабские цифры «١٠٠١» становятся обычными «1001».

Запуск (после postprocess.py): python3 -I src/clean_names.py data/db.json
"""
import json
import re
import sys

# Алфавиты, которые убираем
FOREIGN = ("Ͱ-Ͽἀ-῿"          # греческий
           "֐-׿"                        # иврит
           "؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿"  # арабский
           "ऀ-ॿ"                        # деванагари
           "฀-๿"                        # тайский
           "က-႟"                        # мьянманский
           "ᄀ-ᇿ㄰-㆏가-힯"  # корейский
           "　-〿぀-ヿㇰ-ㇿ"  # японская пунктуация, хирагана, катакана
           "㐀-䶿一-鿿豈-﫿"  # иероглифы
           "＀-￯")                       # полноширинные знаки
F = "[" + FOREIGN + "]"
# Кусок на другом алфавите вместе с пробелами, дефисами, цифрами и «/» между такими кусками и с «/» перед ним
RUN_BODY = F + r"+(?:[\s\-–/·,.&+\d]*" + F + r"+)*"
RUN = re.compile(r"(?:\s*/\s*)?" + RUN_BODY)
# «Tomo Vetiver とも Vetiver» → «Tomo Vetiver» (то же слово до и после надписи — второе лишнее)
DUP = re.compile(r"\b([^\W\d_]+)\s+" + RUN_BODY + r"\s+\1\b")
# Полноширинные латинские знаки («Fire＋Ice») → обычные; полноширинные скобки оставляем (они внутри японских надписей)
FULLWIDTH = {c: chr(c - 0xFEE0) for c in range(0xFF01, 0xFF5F) if c not in (0xFF08, 0xFF09)}
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
BRAND_FIX = {"Kashतi": "Kashti"}     # в названии бренда буква деванагари
# В исходных данных у Hermès 24, Faubourg срезано «24» (как «1» у 1 Million)
NAME_FIX = [("Hermès", re.compile(r"^, Faubourg"), "24, Faubourg")]


def clean(name):
    n = name.translate(DIGITS).translate(FULLWIDTH)
    if not re.search(F, n):
        return n                                                 # других алфавитов нет — название не трогаем
    n = DUP.sub(r"\1", n)
    out = RUN.sub(" ", n)
    out = re.sub(r"(^|\s)[\u0300-\u036F]+", r"\1", out)       # знак ударения, оставшийся от греческой буквы
    out = re.sub(r"\s+(\.\.\.|…)", r"\1", out)
    out = re.sub(r"\(\s*\)", " ", out)
    out = re.sub(r"\s+([-–/])\s+(?=[-–/]\s)", " ", out)       # «A - - B» → «A - B»
    out = re.sub(r"\s{2,}", " ", out).strip()
    out = re.sub(r"^[\s\-–/·,:&+]+|[\s\-–/·,:&+]+$", "", out)
    if not re.search(r"[A-Za-zÀ-ɏА-Яа-яЁё]", out):
        return n                                                 # без надписи ничего не осталось — оставляем как было
    return out


def fix(brand, name):
    """Название ароматa так, как оно будет на сайте (для других скриптов, которые ищут ароматы по исходным данным)."""
    new = clean(name)
    for b, rx, rep_ in NAME_FIX:
        if brand == b:
            new = rx.sub(rep_, new)
    return new


if __name__ == "__main__":
    db = sys.argv[1]
    d = json.load(open(db, encoding="utf-8"))
    B, P = d["b"], d["p"]
    for i, b in enumerate(B):
        if b in BRAND_FIX:
            B[i] = BRAND_FIX[b]
    have = {(x[1], x[0]) for x in P}
    changed, kept = [], []
    for x in P:
        new = fix(B[x[1]], x[0])
        if new == x[0]:
            continue
        if (x[1], new) in have:                                     # такое название у бренда уже есть — не сливаем два аромата
            kept.append(f"{B[x[1]]} | {x[0]} (уже есть «{new}»)")
            continue
        have.discard((x[1], x[0])); have.add((x[1], new))
        changed.append(f"{B[x[1]]} | {x[0]}  →  {new}")
        x[0] = new
    txt = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    open(db, "w", encoding="utf-8").write(txt)
    print(f"исправлено названий: {len(changed)}; оставлено (совпало бы с другим ароматом): {len(kept)}")
    for c in changed + kept:
        print("  ", c)
