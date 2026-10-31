-- Отзывы покупателей (раздел «Отзывы»). База D1 «shoh-parfumer-reviews».
-- Новый отзыв сначала «pending» (на проверке у владельца в Telegram), после одобрения «ok», удалённый — «no».
CREATE TABLE IF NOT EXISTS reviews (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  uid TEXT NOT NULL,                    -- код аромата, как на сайте: hash(«Бренд|Название») в base36
  brand TEXT NOT NULL,
  name TEXT NOT NULL,
  stars INTEGER NOT NULL,               -- 1–5
  lon INTEGER,                          -- стойкость: 1 до 2 ч, 2 — 2–5 ч, 3 — 5–8 ч, 4 весь день
  sil INTEGER,                          -- шлейф: 1 слабый, 2 средний, 3 сильный
  sea INTEGER,                          -- когда носят: 1 лето, 2 осень и зима, 3 круглый год
  who INTEGER,                          -- для кого: 1 мужчина, 2 женщина, 3 оба
  again INTEGER,                        -- купили бы снова: 1 да, 0 нет
  text TEXT,
  author TEXT,
  lang TEXT,
  pcode TEXT,                           -- код покупки (если был) — «Проверенная покупка»
  bonus TEXT,                           -- бонус-код, выданный за отзыв с кодом покупки
  bonus_used INTEGER NOT NULL DEFAULT 0,
  bonus_used_at TEXT,
  status TEXT NOT NULL DEFAULT 'pending',
  created TEXT NOT NULL,
  decided TEXT,
  iph TEXT,                             -- хеш IP (только для ограничения спама)
  dev TEXT,                             -- случайный код устройства (один отзыв на аромат)
  tg_msg INTEGER                        -- сообщение владельцу в Telegram (чтобы отметить решение)
);
CREATE INDEX IF NOT EXISTS reviews_uid ON reviews (uid, status);
CREATE INDEX IF NOT EXISTS reviews_iph ON reviews (iph, created);
CREATE INDEX IF NOT EXISTS reviews_bonus ON reviews (bonus);

-- Коды покупки: владелец получает их у бота командой /kod и даёт покупателю (один код — один отзыв с бонусом)
CREATE TABLE IF NOT EXISTS codes (
  code TEXT PRIMARY KEY,
  created TEXT NOT NULL,
  used_by INTEGER                       -- номер отзыва, к которому применён код
);

-- Настройки: чат владельца в Telegram, адрес бота (webhook)
CREATE TABLE IF NOT EXISTS settings (
  k TEXT PRIMARY KEY,
  v TEXT
);
