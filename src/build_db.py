#!/usr/bin/env python3
"""Собирает компактную базу ароматов для сайта из CSV (Parfumo, TidyTuesday 2024-12-10).

Запуск: python3 -I build_db.py <parfumo.csv> <out.json>
"""
import csv, json, math, re, sys, collections

SRC, OUT = sys.argv[1], sys.argv[2]

AX = ["cit", "fresh", "flo", "fru", "swe", "spi", "woo", "amb", "mus", "lea"]
IDX = {a: i for i, a in enumerate(AX)}

PRIORITY = set("""Louis Vuitton|Creed|Maison Crivelli|Maison Francis Kurkdjian|Parfums de Marly|Initio|XerJoff|Amouage|Nishane|Byredo|Le Labo|Maison Margiela|Jo Malone|Giorgio Armani|Yves Saint Laurent|Hermès|Versace|Gucci|Dior|Chanel|Tom Ford|Paco Rabanne|Guerlain|Lattafa|Armaf|Rasasi|Afnan Perfumes|Al Haramain|Cartier|Givenchy|Prada|Burberry|Dolce & Gabbana|Azzaro|Kilian|Mugler|Carolina Herrera|Lancôme|Narciso Rodriguez|Hugo Boss|Calvin Klein|Montblanc|Issey Miyake|Davidoff|Jean Paul Gaultier|Viktor & Rolf|Chloé|Nautica|Marc Jacobs""".split("|"))

# ---------- аккорды -> оси вкуса ----------
ACC = {
    "Floral": {"flo": 3}, "Spicy": {"spi": 3}, "Sweet": {"swe": 3}, "Woody": {"woo": 3},
    "Fresh": {"fresh": 3}, "Fruity": {"fru": 3}, "Citrus": {"cit": 3}, "Green": {"fresh": 2},
    "Powdery": {"mus": 2, "flo": 1}, "Oriental": {"amb": 2, "spi": 1.5, "swe": 1},
    "Creamy": {"swe": 1.5, "mus": 1}, "Gourmand": {"swe": 3}, "Resinous": {"amb": 3},
    "Aquatic": {"fresh": 3}, "Smoky": {"lea": 2, "woo": 1}, "Leathery": {"lea": 3},
    "Earthy": {"woo": 2}, "Animal": {"lea": 1.5, "mus": 1},
    "Chypre": {"woo": 1.5, "flo": 1, "cit": 0.5}, "Fougère": {"fresh": 1.5, "woo": 1.5, "spi": 0.5},
}
POS = [1.0, 0.85, 0.7, 0.6, 0.5, 0.4, 0.35, 0.3]
ACC_ORDER = list(ACC.keys())
ACC_LETTER = {a: "abcdefghijklmnopqrstuvwxyz"[i] for i, a in enumerate(ACC_ORDER)}

# ---------- ноты -> оси вкуса (по ключевым словам) ----------
RULES = [
    (r"bergamot|lemon|\blime\b|mandarin|grapefruit|citrus|yuzu|tangerine|petitgrain|citron|clementine|pomelo|kumquat|bitter orange|blood orange|\borange\b(?! blossom)|verbena|vervain|neroli", {"cit": 1}),
    (r"neroli|orange blossom", {"flo": 0.6, "cit": 0.4}),
    (r"mint|marine|\bsea\b|seawater|salt|ozon|aquatic|water lily|waterlily|\bwater\b|green|grass|\btea\b|cucumber|lavender|rosemary|\bsage\b|basil|galbanum|leaf|leaves|aldehyd|eucalyptus|cypress|juniper|\bpine\b|\bfir\b|thyme|tarragon|herb|fern\b|ivy|bamboo|breeze|solar|fresh|aromatic|artemisia|mugwort|absinth|angelica|rain\b|\bice\b", {"fresh": 1}),
    (r"\brose\b|\brosa\b|\broses\b|jasmin|lily|iris|orris|violet|peony|tuberose|ylang|blossom|magnolia|freesia|lilac|geranium|orchid|gardenia|heliotrope|carnation|mimosa|osmanthus|narcissus|hyacinth|lotus|cyclamen|honeysuckle|floral|flower|daisy|chamomile|muguet|tiar|frangipani|hibiscus|wisteria|champaca|linden|marigold|sweet pea|passion flower|hawthorn", {"flo": 1}),
    (r"apple|pear\b|peach|plum|cherry|raspberr|strawberr|currant|berry|berries|apricot|pineapple|mango|coconut|melon|lychee|\bfig\b|pomegranate|grape\b|banana|passion ?fruit|papaya|cranberry|fruit|quince|nectarine|guava|kiwi|rhubarb|blueberr|watermelon|mirabelle", {"fru": 1}),
    (r"vanill|caramel|honey|sugar|chocolate|cocoa|cacao|tonka|prali|marshmallow|candy|almond|coffee|cream|milk|benzoin|toffee|maple|\brum\b|cognac|gourmand|sweet|hazelnut|coumarin|liquorice|licorice|beeswax|cookie|cake|dessert|\bdate\b", {"swe": 1}),
    (r"pepper|cinnamon|cardamom|clove|nutmeg|ginger|saffron|cumin|coriander|anise|aniseed|spice|spicy|curry|pimento|allspice|paprika|chili|cassia|caraway|mace\b|turmeric|cypriol|nagarmotha", {"spi": 1}),
    (r"cedar|sandal|vetiver|patchouli|\boud\b|agarwood|gaiac|guaiac|\bwood|oakmoss|\bmoss|birch|rosewood|\boak\b|ebony|teak|cashmeran|cashmere wood|papyrus|amyris|driftwood|mahogany|palo santo|akigalawood|cypress|\bpine\b", {"woo": 1}),
    (r"amber|ambrox|ambergris|labdanum|incense|frankincense|olibanum|resin|myrrh|opoponax|elemi|balsam|styrax|castoreum|cistus|tolu|peru\b|benzoin|mastic|copal", {"amb": 1}),
    (r"musk|ambrette|powdery|\bskin\b|cashmere(?! wood)|iso e|hedione|orris|\biris\b|talc|laundry|cotton|linen|soap", {"mus": 1}),
    (r"leather|tobacco|suede|smoke|smoky|\btar\b|animal|civet|castoreum|\bhay\b|cade\b|whisk|fume|charcoal|burnt|\bash\b", {"lea": 1}),
]
RULES = [(re.compile(p), w) for p, w in RULES]

# ---------- перевод нот ----------
DICT_TEXT = """
musk=мускус
white musk=белый мускус
bergamot=бергамот
sandalwood=сандал
jasmine=жасмин
amber=амбра
vanilla=ваниль
patchouli=пачули
rose=роза
vetiver=ветивер
mandarin orange=мандарин
lemon=лимон
cedarwood=кедр
cedar=кедр
tonka bean=тонка
lily of the valley=ландыш
lavender=лаванда
orange blossom=цветок апельсина
iris=ирис
ylang-ylang=иланг-иланг
cardamom=кардамон
violet=фиалка
grapefruit=грейпфрут
pink pepper=розовый перец
oakmoss=дубовый мох
geranium=герань
frankincense=ладан
leather=кожа
orange=апельсин
blackcurrant=чёрная смородина
peach=персик
oud=уд
ambergris=серая амбра
cinnamon=корица
freesia=фрезия
benzoin=бензоин
neroli=нероли
nutmeg=мускатный орех
saffron=шафран
ginger=имбирь
labdanum=лабданум
tuberose=тубероза
raspberry=малина
peony=пион
woody notes=древесные ноты
apple=яблоко
heliotrope=гелиотроп
coriander=кориандр
moss=мох
pear=груша
clove=гвоздика
magnolia=магнолия
black pepper=чёрный перец
carnation=гвоздика (цветок)
green notes=зелёные ноты
gardenia=гардения
aldehydes=альдегиды
gaiac wood=гваяк
guaiac wood=гваяк
pepper=перец
violet leaf=лист фиалки
mint=мята
pineapple=ананас
lime=лайм
plum=слива
rosemary=розмарин
basil=базилик
galbanum=гальбанум
sage=шалфей
petitgrain=петитгрейн
tobacco=табак
clary sage=мускатный шалфей
lily=лилия
woods=древесные ноты
honey=мёд
jasmine sambac=жасмин самбак
orchid=орхидея
myrrh=мирра
citrus notes=цитрусовые ноты
caramel=карамель
cashmere wood=кашмеран
floral notes=цветочные ноты
cyclamen=цикламен
spices=специи
rosewood=палисандр
cypress=кипарис
coconut=кокос
orris root=корень ириса
osmanthus=османтус
marine notes=морские ноты
elemi resin=смола элеми
elemi=элеми
hyacinth=гиацинт
lychee=личи
mimosa=мимоза
aquatic notes=водные ноты
lotus=лотос
juniper=можжевельник
civet=цибет
apricot=абрикос
almond=миндаль
fruity notes=фруктовые ноты
bitter orange=горький апельсин
white blossoms=белые цветы
honeysuckle=жимолость
juniper berry=ягоды можжевельника
green apple=зелёное яблоко
melon=дыня
thyme=тимьян
tangerine=танжерин
narcissus=нарцисс
praliné=пралине
praline=пралине
lilac=сирень
virginia cedar=виргинский кедр
citrus fruits=цитрусовые
cistus=ладанник
cashmeran=кашмеран
ambroxan=амброксан
ambrox=амброксан
aniseed=анис
styrax=стиракс
frangipani=франжипани
coffee=кофе
amberwood=амбровое дерево
passion fruit=маракуйя
tarragon=эстрагон
suede=замша
strawberry=клубника
rhubarb=ревень
artemisia=полынь
blackberry=ежевика
blond woods=светлое дерево
green tea=зелёный чай
yuzu=юдзу
cumin=зира
star anise=бадьян
cypriol=ципериол
fig=инжир
cocoa=какао
opoponax=опопонакс
rum=ром
water lily=кувшинка
waterlily=кувшинка
spicy notes=пряные ноты
mango=манго
davana=давана
white amber=белая амбра
blood orange=красный апельсин
green leaves=зелёные листья
castoreum=кастореум
watermelon=арбуз
pink grapefruit=розовый грейпфрут
tolu balm=бальзам толу
tea=чай
pine=сосна
red fruits=красные фрукты
pimento=душистый перец
tagetes=бархатцы
precious woods=ценные породы дерева
tiaré=тиаре
tiare=тиаре
red berries=красные ягоды
vervain=вербена
birch=берёза
cherry=вишня
caraway=тмин
pomegranate=гранат
peppermint=перечная мята
ambrette seed=амбретта
ambrette=амбретта
peru balsam=перуанский бальзам
fig leaf=лист инжира
chamomile=ромашка
cashmere=кашемир
citron=цитрон
white pepper=белый перец
eucalyptus=эвкалипт
chocolate=шоколад
powdery notes=пудровые ноты
clementine=клементин
musky notes=мускусные ноты
angelica=дудник
milk=молоко
cherry blossom=цветок вишни
nectarine=нектарин
amyris=амирис
mugwort=полынь
coumarin=кумарин
papyrus=папирус
driftwood=дрифтвуд
white cedar=белый кедр
iris florentina=ирис
rosa centifolia=роза
blossoms=цветы
grass=трава
ozone=озон
sugar=сахар
bamboo=бамбук
apple blossom=цветок яблони
white rose=белая роза
fresh notes=свежие ноты
black tea=чёрный чай
teakwood=тик
resins=смолы
hawthorn=боярышник
peach blossom=цветок персика
laurel=лавр
red currant=красная смородина
coconut milk=кокосовое молоко
spearmint=курчавая мята
balsamic notes=бальзамические ноты
myrtle=мирт
sichuan pepper=сычуаньский перец
fir balsam=пихтовый бальзам
nagarmotha=нагармота
tree moss=древесный мох
aromatic notes=ароматические ноты
ivy=плющ
hibiscus=гибискус
maté=мате
sweet notes=сладкие ноты
blackcurrant bud=почки чёрной смородины
fruits=фрукты
absinth=абсент
hazelnut=фундук
dry woods=сухое дерево
vanilla orchid=ванильная орхидея
cedar leaf=листья кедра
hedione=гедион
animalic notes=животные ноты
white woods=белое дерево
blueberry=черника
white tea=белый чай
smoke=дым
liquorice=лакрица
gurjum balsam=бальзам гурджун
sea salt=морская соль
bay leaf=лавровый лист
orris butter=масло ириса
kumquat=кумкват
hay=сено
ebony=эбеновое дерево
pine needle=хвоя
leathery notes=кожаные ноты
solar note=солнечные ноты
lemon zest=цедра лимона
currant=смородина
fir=пихта
mastic=мастика
white lily=белая лилия
immortelle=бессмертник
marshmallow=зефир
cucumber=огурец
cassia=кассия
beeswax=пчелиный воск
coconut water=кокосовая вода
dried fruits=сухофрукты
kiwi=киви
mahogany=красное дерево
guava=гуава
white peony=белый пион
bitter almond=горький миндаль
berries=ягоды
balsam=бальзам
carrot seed=семена моркови
pink peony=розовый пион
fern=папоротник
dark chocolate=тёмный шоколад
jasminum auriculatum=жасмин
jasminum grandiflorum=жасмин
herbs=травы
almond blossom=цветок миндаля
seawater=морская вода
cranberry=клюква
papaya=папайя
quince=айва
lemon grass=лемонграсс
lemongrass=лемонграсс
wisteria=глициния
cream=сливки
sweet pea=душистый горошек
leaves=листья
salt=соль
leaf green=зелёная листва
sea breeze=морской бриз
oak wood=дуб
oak=дуб
black amber=чёрная амбра
pot marigold=календула
granny smith apple=зелёное яблоко
mirabelle plum=мирабель
red pepper=красный перец
champaca flower=чампака
linden blossom=липа
broom=дрок
rose water=розовая вода
wild berries=лесные ягоды
wild rose=шиповник
lemon vervain=лимонная вербена
gourmand notes=гурманские ноты
passion flower=пассифлора
red rose=красная роза
brown sugar=коричневый сахар
date=финик
tomato leaf=лист томата
cognac=коньяк
birch leaf=берёзовый лист
charcoal=уголь
oriental notes=восточные ноты
ozonic notes=озоновые ноты
ozonic=озоновые ноты
patchouly=пачули
ambreine=амбра
cassis=чёрная смородина
mineral amber=минеральная амбра
rose petals=лепестки розы
lemon peel=цедра лимона
white flowers=белые цветы
white florals=белые цветы
woody=древесные ноты
sandal=сандал
oakmoss absolute=дубовый мох
cotton candy=сахарная вата
cotton=хлопок
incense=ладан
iso e super=изо э супер
orange peel=апельсиновая корка
mandarin=мандарин
tuberose absolute=тубероза
praliné=пралине
"""
DICT = {}
for line in DICT_TEXT.strip().splitlines():
    if "=" in line:
        k, v = line.split("=", 1)
        DICT[k.strip().lower()] = v.strip()

QUAL = set("""italian calabrian sicilian bulgarian turkish damask indian australian mysore haitian indonesian egyptian french provençal provencal brazilian bourbon madagascar may grasse atlas texas java thai laotian cambodian moroccan taif florentine spanish tunisian chinese ceylon guatemala siam amalfi sri lankan jamaican himalayan mexican persian tahitian reunion réunion paraguayan sardinian corsican""".split())
TRAIL = set("absolute absolue concrete essence oil extract resinoid co2 accord".split())


def translate(note):
    n = note.strip().lower()
    if n in DICT:
        return DICT[n]
    toks = n.split()
    while toks and toks[0] in QUAL:
        toks = toks[1:]
    while toks and toks[-1] in TRAIL:
        toks = toks[:-1]
    m = " ".join(toks)
    if m in DICT:
        return DICT[m]
    for i in range(1, len(toks)):          # самый длинный суффикс: "ceylonese sandalwood" -> "sandalwood"
        suf = " ".join(toks[i:])
        if suf in DICT:
            return DICT[suf]
    for j in range(len(toks) - 1, 0, -1):  # самый длинный префикс: "grapefruit zest" -> "grapefruit"
        pre = " ".join(toks[:j])
        if pre in DICT:
            return DICT[pre]
    return m if m else n


def clean(x):
    return None if x in ("", "NA") else x


def unit(v):
    n = math.sqrt(sum(x * x for x in v))
    return [x / n for x in v] if n else v


def accord_vec(s):
    v = [0.0] * 10
    if not s:
        return v
    for i, a in enumerate(x.strip() for x in s.split(",")):
        w = ACC.get(a)
        if not w:
            continue
        p = POS[i] if i < len(POS) else 0.25
        for k, val in w.items():
            v[IDX[k]] += val * p
    return v


def note_vec(notes):
    v = [0.0] * 10
    for note in notes:
        low = note.lower()
        for rx, w in RULES:
            if rx.search(low):
                for k, val in w.items():
                    v[IDX[k]] += val
    return v


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


rows = list(csv.DictReader(open(SRC, encoding="utf-8")))
brands, notes_idx = [], {}
notes_list, brand_idx = [], {}
items = {}
en_counts = collections.defaultdict(collections.Counter)

for r in rows:
    acc = clean(r["Main_Accords"])
    tops = [x.strip() for x in (clean(r["Top_Notes"]) or "").split(",") if x.strip()]
    mids = [x.strip() for x in (clean(r["Middle_Notes"]) or "").split(",") if x.strip()]
    bases = [x.strip() for x in (clean(r["Base_Notes"]) or "").split(",") if x.strip()]
    if not acc and not (tops or mids or bases):
        continue
    brand = clean_brand(r["Brand"])
    pc = int(float(r["Rating_Count"])) if clean(r["Rating_Count"]) else 0
    rating = float(r["Rating_Value"]) if clean(r["Rating_Value"]) else 0.0
    if pc < 20 and brand not in PRIORITY:
        continue
    year = clean(r["Release_Year"])
    year = str(int(float(year))) if year else None
    name = clean_name(r["Name"], brand, year)
    if not name:
        continue

    a = unit(accord_vec(acc))
    nv = unit(note_vec(tops + mids + bases))
    if any(a) and any(nv):
        u = [0.6 * x + 0.4 * y for x, y in zip(a, nv)]
    else:
        u = a if any(a) else nv
    if not any(u):
        continue
    mx = max(u)
    digits = "".join(str(int(round(3 * x / mx))) for x in u)
    uu = unit(u)
    F = uu[0] + uu[1] + 0.3 * uu[3]
    W = uu[4] + uu[7] + 0.8 * uu[5] + 0.8 * uu[9] + 0.3 * uu[6]
    diff = F - W
    season = 0 if diff > 0.1 else (1 if diff < -0.3 else 2)  # 0 лето, 1 прохлада, 2 весь год
    hit = 1 if (pc >= 150 and rating >= 7.0) else 0

    # Все ноты с их слоем: 1 верхние, 2 сердце, 3 база. Одна нота учитывается один раз.
    seen, ni = set(), []
    for layer, grp in ((1, tops), (2, mids), (3, bases)):
        for note in grp:
            t = translate(note)
            if t:
                en_counts[t][note.strip().lower()] += 1
            if not t or t in seen:
                continue
            seen.add(t)
            j = notes_idx.get(t)
            if j is None:
                j = len(notes_list)
                notes_idx[t] = j
                notes_list.append(t)
            ni.append(j * 4 + layer)
    ni = ni[:20]
    # Аккорды по порядку значимости, по одной букве на аккорд
    accs = "".join(ACC_LETTER[x.strip()] for x in (acc or "").split(",") if x.strip() in ACC_LETTER)

    bi = brand_idx.setdefault(brand, len(brand_idx))
    if bi == len(brands):
        brands.append(brand)
    pri = 1 if brand in PRIORITY else 0
    row = [name, bi, digits, season + 4 * hit + 8 * pri, pc, int(round(rating * 10)), ni, accs]
    key = (brand.lower(), name.lower())
    if key not in items or items[key][4] < pc:
        items[key] = row

data = sorted(items.values(), key=lambda x: -x[4])
notes_en = [en_counts[t].most_common(1)[0][0] if en_counts[t] else t for t in notes_list]
out = {"b": brands, "n": notes_list, "ne": notes_en, "a": ACC_ORDER, "p": data}
txt = json.dumps(out, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
open(OUT, "w", encoding="utf-8").write(txt)

cnt = collections.Counter(x[3] % 4 for x in data)
print("perfumes", len(data), "brands", len(brands), "notes", len(notes_list), "bytes", len(txt.encode("utf-8")))
print("season s/c/a", cnt[0], cnt[1], cnt[2], "hits", sum(1 for x in data if (x[3] // 4) % 2), "pc>=30", sum(1 for x in data if x[4] >= 30))
for b in ("Louis Vuitton", "Creed", "Maison Crivelli", "Dior", "Chanel", "Tom Ford", "Maison Francis Kurkdjian"):
    print(b, sum(1 for x in data if brands[x[1]] == b))
