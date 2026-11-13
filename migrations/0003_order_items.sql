-- Корзина: в одной заявке несколько ароматов (14.11.2026).
-- items — JSON-список [{id, name, of, ml, price, qty}]; total — сумма по ценам на сайте (0 — если у какого-то аромата цена «уточняйте»).
-- Первый аромат по-прежнему лежит и в колонках item/name/item_of/ml/price/qty.
ALTER TABLE orders ADD COLUMN items TEXT;
ALTER TABLE orders ADD COLUMN total INTEGER;
