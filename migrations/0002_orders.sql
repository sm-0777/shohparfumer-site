-- Заявки на ароматы Shoh Parfumer (форма «Заказать» на сайте → Telegram-бот владельца)
CREATE TABLE IF NOT EXISTS orders (
  id        INTEGER PRIMARY KEY AUTOINCREMENT,
  item      TEXT NOT NULL,              -- id аромата на сайте (OWN в src/site.html)
  name      TEXT NOT NULL,              -- название, как на сайте: «Shoh Parfumer …»
  item_of   TEXT,                       -- оригинал: «Creed Absolu Aventus»
  ml        INTEGER,                    -- объём
  price     INTEGER,                    -- цена за 1 шт. на сайте в момент заказа (0 — «цену уточняйте»)
  qty       INTEGER NOT NULL DEFAULT 1,
  get       TEXT NOT NULL,              -- delivery | pickup
  addr      TEXT,                       -- адрес доставки
  pay       TEXT,                       -- cash | card | пусто
  cname     TEXT NOT NULL,              -- имя покупателя
  phone     TEXT NOT NULL,              -- телефон, как ввёл покупатель
  phone_d   TEXT,                       -- телефон цифрами с кодом страны (для WhatsApp)
  comment   TEXT,
  lang      TEXT,
  status    TEXT NOT NULL DEFAULT 'new', -- new | ok (принят) | done (выполнен) | no (отменён)
  created   TEXT NOT NULL,
  decided   TEXT,
  pcode     TEXT,                       -- код для отзыва (выдаётся, когда заказ выполнен)
  iph       TEXT,                       -- хеш IP (защита от спама)
  dev       TEXT,
  tg_msg    INTEGER
);
CREATE INDEX IF NOT EXISTS orders_iph ON orders (iph, created);
CREATE INDEX IF NOT EXISTS orders_status ON orders (status);
