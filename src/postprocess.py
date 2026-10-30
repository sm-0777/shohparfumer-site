#!/usr/bin/env python3
"""Ручные поправки к базе: 1 Million и известные ароматы без числа оценок.

Запуск: python3 -I postprocess.py <db.json>
"""
import json, sys

p = sys.argv[1]
d = json.load(open(p, encoding="utf-8"))
B, P = d["b"], d["p"]
bi = {b: i for i, b in enumerate(B)}

# В исходных данных у 1 Million срезана цифра "1"
for x in P:
    if B[x[1]] == "Paco Rabanne" and x[0].startswith("Million"):
        x[0] = "1 " + x[0]

# Знаменитые ароматы, у которых в данных нет числа оценок: поднимаем в списках и отмечаем как хит
FAMOUS = {
    "Creed": ["Aventus", "Silver Mountain Water", "Green Irish Tweed", "Viking"],
    "Maison Francis Kurkdjian": ["Baccarat Rouge 540 Eau de Parfum", "Baccarat Rouge 540 Extrait de Parfum", "Grand Soir"],
    "Chanel": ["Bleu de Chanel Eau de Parfum", "Bleu de Chanel Eau de Toilette"],
    "Tom Ford": ["Tobacco Vanille Eau de Parfum", "Black Orchid Eau de Parfum", "Ombré Leather Eau de Parfum",
                 "Tuscan Leather Eau de Parfum", "Oud Wood Eau de Parfum"],
    "Parfums de Marly": ["Layton", "Herod", "Pegasus", "Delina Eau de Parfum"],
    "Louis Vuitton": ["Imagination", "Ombre Nomade", "Afternoon Swim"],
    "Initio": ["Side Effect", "Oud for Greatness", "Rehab"],
    "XerJoff": ["Erba Pura", "Naxos"],
    "Maison Margiela": ["Replica - By the Fireplace", "Replica - Jazz Club"],
    "Hermès": ["Terre d'Hermès Eau de Toilette"],
    "Nishane": ["Hacivat"],
    "Dior": ["Bois d'Argent", "Sauvage Eau de Toilette", "Sauvage Eau de Parfum", "Sauvage Elixir"],
    "Rasasi": ["Hawas for Him"],
    "Azzaro": ["Wanted Eau de Parfum"],
    "Paco Rabanne": ["1 Million Eau de Toilette"],
}
miss = []
for b, names in FAMOUS.items():
    for n in names:
        m = [x for x in P if x[1] == bi.get(b) and x[0] == n]
        if not m:
            miss.append((b, n))
        for x in m:
            x[4] = max(x[4], 3000)
            x[3] |= 4

P.sort(key=lambda x: -x[4])
txt = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(p, "w", encoding="utf-8").write(txt)
print("postprocess ok; not found:", miss, "bytes", len(txt.encode("utf-8")))


# ---------- 2. Ноты для знаменитых ароматов, у которых в данных их нет ----------
import re, unicodedata
from collections import defaultdict

d = json.load(open(p, encoding="utf-8"))
B, N, P = d["b"], d["n"], d["p"]
note_id = {t: i for i, t in enumerate(N)}


EN_MANUAL = {"пихтовая смола": "fir resin", "табачный лист": "tobacco leaf", "цветок табака": "tobacco blossom",
             "сухофрукты": "dried fruits", "пряные ноты": "spicy notes", "амбровое дерево": "amberwood", "элеми": "elemi",
             "древесные ноты": "woody notes", "сычуаньский перец": "sichuan pepper", "перец": "pepper"}


def nid(t):
    if t not in note_id:
        note_id[t] = len(N)
        N.append(t)
        d["ne"].append(EN_MANUAL.get(t, t))
    return note_id[t]


# Официальные пирамиды, сверены с магазинами (lessenteurs.com, venbafragrance.com)
MANUAL = {
    ("Maison Francis Kurkdjian", "Baccarat Rouge 540 Eau de Parfum"):
        [(1, "жасмин"), (1, "шафран"), (2, "амбровое дерево"), (2, "серая амбра"), (3, "пихтовая смола"), (3, "кедр")],
    ("Tom Ford", "Tobacco Vanille Eau de Parfum"):
        [(1, "табачный лист"), (1, "пряные ноты"), (2, "ваниль"), (2, "какао"), (2, "тонка"), (2, "цветок табака"),
         (3, "сухофрукты"), (3, "древесные ноты")],
    ("Dior", "Sauvage Eau de Toilette"):
        [(1, "бергамот"), (1, "перец"), (2, "сычуаньский перец"), (2, "лаванда"), (2, "розовый перец"), (2, "ветивер"),
         (2, "пачули"), (2, "герань"), (2, "элеми"), (3, "амброксан"), (3, "кедр"), (3, "лабданум")],
}
for x in P:
    key = (B[x[1]], x[0])
    if key in MANUAL and not x[6]:
        x[6] = [nid(t) * 4 + layer for layer, t in MANUAL[key]]
        x[3] |= 16          # ноты добавлены вручную


def norm(s):
    s = unicodedata.normalize("NFD", s.lower())
    return "".join(c for c in s if unicodedata.category(c) != "Mn")


def line_key(x):
    w = re.split(r"[\s\-–]+", norm(x[0]).strip())
    return B[x[1]] + "|" + (w[0] if w else "")


# Нет нот: берём у ближайшего родственника той же линейки (например, Sauvage EDT ← Sauvage Parfum)
lines = defaultdict(list)
for x in P:
    lines[line_key(x)].append(x)
borrowed = 0
for x in P:
    if x[6]:
        continue
    # родственник с самыми похожими аккордами (Sauvage EDT ближе к Sauvage Parfum, чем к Elixir)
    def acc_sim(a, b):
        W = [1.0, 0.85, 0.7, 0.6, 0.5, 0.4, 0.35, 0.3]
        wa = {ch: W[k] if k < len(W) else 0.2 for k, ch in enumerate(a)}
        wb = {ch: W[k] if k < len(W) else 0.2 for k, ch in enumerate(b)}
        num = sum(wa[c] * wb.get(c, 0) for c in wa)
        den = (sum(v * v for v in wa.values()) * sum(v * v for v in wb.values())) ** 0.5
        return num / den if den else 0
    mates = sorted([m for m in lines[line_key(x)] if m[6] and not (m[3] & 16)], key=lambda m: (-acc_sim(x[7], m[7]), -m[4]))
    if mates:
        x[6] = list(mates[0][6])
        x[3] |= 16
        borrowed += 1

# ---------- 3. Общие ключи нот: «перечная мята» и «мята» считаются родственными ----------
BASES = ("мята амбра мускус жасмин роза кедр сандал ваниль пачули ветивер ирис лаванда бергамот лимон апельсин мандарин "
         "перец чай уд ладан смородина яблоко груша персик вишня кожа табак кофе шоколад какао мёд карамель тонка корица "
         "кардамон имбирь шафран фиалка пион лилия тубероза гардения орхидея магнолия нероли грейпфрут лайм юдзу кокос "
         "малина клубника слива инжир миндаль гвоздика герань мох пихта сосна кипарис можжевельник шалфей розмарин базилик "
         "мирра бензоин лабданум гваяк берёза фрезия ландыш ананас манго личи абрикос гранат ром коньяк замша").split()
coarse_names, coarse_id, C = [], {}, []
for t in N:
    toks = t.split()
    key = None
    if not (toks and toks[0] in ("лист", "листья", "листьев")):
        for b in BASES:
            if b in toks:
                key = b
                break
        if key is None and t.startswith("амбр"):
            key = "амбра"
    if key is None:
        C.append(-1)
        continue
    if key not in coarse_id:
        coarse_id[key] = len(coarse_names)
        coarse_names.append(key)
    C.append(coarse_id[key])
d["c"], d["cn"] = C, coarse_names

P.sort(key=lambda x: -x[4])
txt = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(p, "w", encoding="utf-8").write(txt)
print("borrowed notes:", borrowed, "| manual:", len(MANUAL), "| coarse groups:", len(coarse_names),
      "| notes mapped to a group:", sum(1 for c in C if c >= 0), "| bytes", len(txt.encode("utf-8")))


# ---------- 4. Пол аромата и ценовая категория бренда ----------
# Пол: по словам в названии (pour Homme, for Her ...), затем по списку известных линеек. Остальные — «для всех».
# Категория бренда (приблизительно): 1 доступный, 2 средний, 3 люкс, 4 нишевый. 0 — неизвестно.
d = json.load(open(p, encoding="utf-8"))
B, P = d["b"], d["p"]

MALE_RX = re.compile(r"\b(pour homme|homme|for men|men|man|for him|him|masculin|uomo|hombre|male|boy|gentleman|monsieur|pour lui)\b")
FEMALE_RX = re.compile(r"\b(pour femme|femme|for women|women|woman|for her|her|donna|mujer|lady|girl|pour elle|elle|feminin|feminine|madame|mademoiselle|princess|miss)\b")
MALE_LINES = [("dior", "sauvage"), ("dior", "dior homme"), ("dior", "fahrenheit"), ("dior", "eau sauvage"), ("creed", "aventus"),
              ("creed", "green irish tweed"), ("creed", "viking"), ("chanel", "bleu de chanel"), ("chanel", "egoiste"), ("chanel", "platinum egoiste"),
              ("giorgio armani", "acqua di gio"), ("giorgio armani", "armani code"), ("giorgio armani", "emporio armani - stronger with you"),
              ("versace", "eros"), ("versace", "dylan blue"), ("paco rabanne", "1 million"), ("paco rabanne", "invictus"), ("paco rabanne", "phantom"),
              ("paco rabanne", "pure xs"), ("hermes", "terre d'hermes"), ("prada", "luna rossa"), ("montblanc", "explorer"), ("montblanc", "legend"),
              ("azzaro", "wanted"), ("azzaro", "the most wanted"), ("azzaro", "chrome"), ("yves saint laurent", "y"), ("yves saint laurent", "l'homme"),
              ("yves saint laurent", "la nuit de l'homme"), ("yves saint laurent", "kouros"), ("hugo boss", "boss bottled"), ("viktor & rolf", "spicebomb"),
              ("jean paul gaultier", "le beau"), ("davidoff", "cool water"), ("rasasi", "hawas"), ("ralph lauren", "polo"), ("afnan perfumes", "supremacy"),
              ("lattafa", "asad"), ("armaf", "club de nuit intense"), ("armaf", "club de nuit sillage"), ("armaf", "club de nuit iconic"),
              ("guerlain", "l'homme ideal"), ("valentino", "uomo"), ("dolce & gabbana", "the one for men"), ("dolce & gabbana", "k"),
              ("bvlgari", "aqva"), ("issey miyake", "l'eau d'issey pour homme"), ("calvin klein", "eternity for men"), ("lacoste", "l'homme")]
FEMALE_LINES = [("lancome", "la vie est belle"), ("lancome", "idole"), ("lancome", "tresor"), ("lancome", "la nuit tresor"),
                ("yves saint laurent", "black opium"), ("yves saint laurent", "libre"), ("yves saint laurent", "mon paris"), ("yves saint laurent", "opium"),
                ("dior", "j'adore"), ("dior", "poison"), ("dior", "hypnotic poison"), ("dior", "addict"), ("chanel", "coco"), ("chanel", "chance"),
                ("chanel", "n°5"), ("chanel", "n°19"), ("chanel", "gabrielle"), ("viktor & rolf", "flowerbomb"), ("mugler", "angel"), ("mugler", "alien"),
                ("giorgio armani", "si"), ("giorgio armani", "my way"), ("giorgio armani", "acqua di gioia"), ("dolce & gabbana", "light blue"),
                ("versace", "bright crystal"), ("versace", "crystal noir"), ("marc jacobs", "daisy"), ("gucci", "bloom"), ("gucci", "flora"),
                ("paco rabanne", "olympea"), ("parfums de marly", "delina"), ("prada", "candy"), ("prada", "paradoxe"), ("jean paul gaultier", "scandal"),
                ("jean paul gaultier", "so scandal"), ("jean paul gaultier", "classique"), ("hermes", "twilly"), ("calvin klein", "euphoria"),
                ("givenchy", "l'interdit"), ("givenchy", "irresistible"), ("guerlain", "shalimar"), ("guerlain", "mon guerlain"),
                ("guerlain", "la petite robe noire"), ("carolina herrera", "good girl"), ("carolina herrera", "very good girl"),
                ("narciso rodriguez", "for her"), ("valentino", "donna"), ("burberry", "her"), ("kenzo", "flower")]
FEMALE_BRANDS = {"chloe", "victoria's secret", "juicy couture", "kayali", "escada", "elie saab"}


def nm(s):
    return norm(s).strip()


def line_match(name, prefix):
    return name == prefix or name.startswith(prefix + " ")


male_l = [(nm(b), nm(x)) for b, x in MALE_LINES]
female_l = [(nm(b), nm(x)) for b, x in FEMALE_LINES]
import collections
gcount = collections.Counter()
for x in P:
    name, brand = nm(x[0]), nm(B[x[1]])
    m, f = bool(MALE_RX.search(name)), bool(FEMALE_RX.search(name))
    g = 1 if m and not f else (2 if f and not m else 0)
    if g == 0 and not (m and f):
        if any(b == brand and line_match(name, l) for b, l in female_l) or brand in FEMALE_BRANDS:
            g = 2
        elif any(b == brand and line_match(name, l) for b, l in male_l):
            g = 1
    x[3] = (x[3] & ~96) | (32 if g == 1 else 64 if g == 2 else 0)
    gcount[g] += 1

TIERS = {
    1: "Zara|Armaf|Rasasi|Al Haramain|Afnan Perfumes|Avon|Yves Rocher|Bath & Body Works|Davidoff|Swiss Arabian|Nabeel|Lattafa|L'Erbolario|Lush|"
       "The Body Shop|Bruno Banani|Jaguar|4711|Mäurer & Wirtz|Rammstein|Nautica|Adidas|Playboy|s.Oliver|Mexx|Superdry|Hollister|Oriflame|"
       "Antonio Banderas|Police|Jacques Bogart|Paris Corner|Maison Alhambra|Fragrance World|French Avenue|Khadlaj|Zimaya|Ard Al Zaafaran|"
       "Tesori d'Oriente|Ted Lapidus|Grès|Nikos|Victoria's Secret",
    2: "Giorgio Armani|Yves Saint Laurent|Paco Rabanne|Prada|Hugo Boss|Calvin Klein|Mugler|Lancôme|Dolce & Gabbana|Gucci|Givenchy|Jil Sander|"
       "Jean Paul Gaultier|Burberry|Versace|Issey Miyake|Kenzo|Narciso Rodriguez|Valentino|Estēe Lauder|Estée Lauder|Azzaro|Montblanc|Carolina Herrera|"
       "Chloé|Marc Jacobs|Elizabeth Arden|Lacoste|Rochas|Cacharel|Salvatore Ferragamo|Elie Saab|Diesel|Trussardi|Escada|Ralph Lauren|DKNY|"
       "Laura Biagiotti|Dsquared²|Zadig & Voltaire|Lolita Lempicka|Roberto Cavalli|Karl Lagerfeld|Viktor & Rolf|Lanvin|Moschino|Dunhill|Aigner|"
       "Joop!|Cerruti|Nina Ricci|Tommy Hilfiger|Juicy Couture|Shiseido|Jimmy Choo|Clinique|Bvlgari|Lalique|Chopard|John Varvatos|Kayali|Clean|"
       "Abercrombie & Fitch|Bentley|Ajmal|Rituals|L'Occitane en Provence|Fragonard|Annayake|Réminiscence|Molinard|Berdoues|Comptoir Sud Pacifique|"
       "Le Couvent|Boucheron|Corday|Birkholz|Parfum-Individual Harry Lehmann|Duftanker MGO Duftmanufaktur|Mancera|Montale",
    3: "Dior|Chanel|Hermès|Guerlain|Tom Ford|Cartier|Acqua di Parma|Jo Malone|Maison Margiela|Diptyque|Penhaligon's|Comme des Garçons|"
       "Van Cleef & Arpels|Loewe|Bottega Veneta|Etro|Goutal|Caron|Juliette Has A Gun|Etat Libre d'Orange|Atkinsons|Floris|Escentric Molecules|"
       "Jean Patou|Lubin|Miller Harris|Carthusia|Santa Maria Novella|Histoires de Parfums|L'Artisan Parfumeur|The Different Company|Zoologist|"
       "Imaginary Authors|Laboratorio Olfattivo|Lorenzo Villoresi|Pierre Guillaume|Nicolaï|Keiko Mecheri|Heeley|Olfactive Studio|D.S. & Durga|"
       "Liquides Imaginaires|Parfum d'Empire|Masque|Il Profvmo|Gritti|The House of Oud|Sisley|Balmain|Houbigant|Les Parfums de Rosine|"
       "Farmacia SS. Annunziata|Maître Parfumeur et Gantier|Oriza L. Legrand|Maison Mona di Orio|Zarkoperfume|Kerosene|Rogue|Floraïku|Bois 1920|"
       "Une Nuit Nomade|Perris Monte Carlo|Nobile 1942|Pana Dora|Goldfield & Banks|Fragrance One|Olympic Orchids Artisan Perfumes|Matière Première|"
       "Tauer Perfumes|Francesca Bianchi|Jovoy|Robert Piguet|Simone Andreoli|Gisada|Marc Gebauer|Serge Lutens|J.F. Schwarzlose Berlin|Aaron Terence Hughes",
    4: "Creed|Maison Francis Kurkdjian|Parfums de Marly|Initio|XerJoff|Amouage|Nishane|Kilian|Louis Vuitton|Roja Parfums|Clive Christian|"
       "Editions de Parfums Frédéric Malle|Byredo|Le Labo|Maison Crivelli|Memo Paris|Tiziana Terenzi|Orto Parisi|Nasomatto|Ex Nihilo|Bond No. 9|"
       "Vilhelm Parfumerie|bdk Parfums|Profumum Roma|Stéphane Humbert Lucas|M. Micallef|Ormonde Jayne|Boadicea the Victorious|"
       "The Merchant Of Venice|Parfums MDCI|Ensar Oud|Widian|Moresque|Electimuss|Dusita|Areej Le Doré|Carner|Celine|Filippo Sorcinelli|Roberto Ugolini",
}
tier_of = {}
for t, names in TIERS.items():
    for b in names.split("|"):
        tier_of[b] = t
d["bt"] = [tier_of.get(b, 0) for b in B]
missing = [b for b in tier_of if b not in set(B)]

txt = json.dumps(d, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(p, "w", encoding="utf-8").write(txt)
tiered = sum(1 for x in P if d["bt"][x[1]])
print("gender: unknown", gcount[0], "male", gcount[1], "female", gcount[2], "| perfumes with brand tier:", tiered, "of", len(P),
      "| tier brands not in base:", len(missing), "| bytes", len(txt.encode("utf-8")))
