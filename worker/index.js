// Shoh Parfumer — отзывы покупателей.
// Сайт (public/) отдаёт Cloudflare как есть; сюда попадают только адреса /api/* (см. wrangler.jsonc).
//
//   GET  /api/reviews?uid=…            одобренные отзывы об аромате и сводка (стойкость, шлейф…)
//   GET  /api/reviews/summary?uids=…   число отзывов и средняя оценка для нескольких ароматов
//   POST /api/reviews                  новый отзыв → на проверку владельцу в Telegram
//   POST /api/tg/<секрет>              Telegram-бот: «Опубликовать / Удалить», /kod, проверка бонус-кода
//   GET  /api/health                   проверка: подключён ли бот (без секретов)
//   по расписанию (раз в 3 часа)        сайт обновился (новая дата в sitemap.xml) → сообщить Яндексу и Bing (IndexNow)
//
// Секрет TG_TOKEN (токен бота от @BotFather) владелец добавляет сам в Cloudflare: Workers → shoh-parfumer →
// Settings → Variables and Secrets. Адрес бота (webhook) Worker настраивает сам. Чат владельца запоминается,
// когда он пишет боту /start со своего аккаунта (OWNER_TG в wrangler.jsonc).

const LON = ["", "до 2 ч", "2–5 ч", "5–8 ч", "весь день"];
const SIL = ["", "слабый", "средний", "сильный"];
const SEA = ["", "лето", "осень и зима", "круглый год"];
const WHO = ["", "мужчина", "женщина", "оба"];
const ABC = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789";     // без похожих 0/O и 1/I
const LIMIT_PER_IP_DAY = 5;                          // отзывов с одного адреса за сутки
const MAX_PENDING = 300;                             // если на проверке больше — новые временно не принимаем

let webhookChecked = false;

export default {
  async fetch(request, env, ctx) {
    const url = new URL(request.url);
    if (/^\/(yandex_[0-9a-f]+|google[0-9a-f]+)\.html$/.test(url.pathname)) return verifyFile(env, url);
    if (!url.pathname.startsWith("/api/")) return env.ASSETS.fetch(request);
    if (request.method === "OPTIONS") return new Response(null, { status: 204, headers: cors() });
    try {
      if (env.TG_TOKEN && !webhookChecked) ctx.waitUntil(ensureWebhook(env));
      const p = url.pathname;
      if (p === "/api/reviews" && request.method === "GET") return await listReviews(env, url);
      if (p === "/api/reviews/summary" && request.method === "GET") return await summary(env, url);
      if (p === "/api/reviews" && request.method === "POST") return await addReview(request, env, ctx);
      if (p.startsWith("/api/tg/") && request.method === "POST") return await telegram(request, env, p.slice(8));
      if (p === "/api/health") return json({ ok: true, bot: !!env.TG_TOKEN, owner: !!(await getSetting(env, "owner_chat")) });
      return json({ error: "not_found" }, 404);
    } catch (e) {
      console.error(e && e.stack || e);
      return json({ error: "server" }, 500);
    }
  },
  async scheduled(event, env, ctx) {
    ctx.waitUntil(indexNow(env).catch((e) => console.error("indexnow", e && e.stack || e)));
  },
};

/* ---------------- Файлы подтверждения Google Search Console и Яндекс Вебмастера ---------------- */
// Лежат в public/ (yandex_КОД.html, googleКОД.html). Cloudflare отдаёт .html с перенаправлением на адрес без .html,
// а проверка поисковика ждёт ответ 200 ровно по этому адресу — поэтому отдаём файл здесь.
async function verifyFile(env, url) {
  const r = await env.ASSETS.fetch(new Request(url.origin + url.pathname.replace(/\.html$/, "")));
  if (!r.ok) return r;                    // такого файла нет — обычная страница 404
  return new Response(await r.text(), { status: 200, headers: { "content-type": "text/html; charset=utf-8", "cache-control": "no-cache" } });
}

/* ---------------- IndexNow: сообщить поисковикам об обновлении ---------------- */
// Яндекс, Bing и другие поисковики с IndexNow узнают об изменениях сразу, а не при следующем обходе.
// Google IndexNow не использует — он находит обновления сам по sitemap.xml.
async function indexNow(env) {
  if (!env.INDEXNOW_KEY || !env.SITE) return;
  const r = await env.ASSETS.fetch(new Request(env.SITE + "/sitemap.xml"));
  if (!r.ok) return;
  const xml = await r.text();
  const urls = [...xml.matchAll(/<loc>([^<]+)<\/loc>/g)].map((m) => m[1]);
  const mark = (xml.match(/<lastmod>([^<]+)<\/lastmod>/) || [])[1] || "";
  if (!urls.length || !mark || (await getSetting(env, "indexnow")) === mark) return;
  const res = await fetch(env.INDEXNOW_API || "https://api.indexnow.org/indexnow", {
    method: "POST",
    headers: { "content-type": "application/json; charset=utf-8" },
    body: JSON.stringify({ host: new URL(env.SITE).host, key: env.INDEXNOW_KEY, keyLocation: env.SITE + "/" + env.INDEXNOW_KEY + ".txt", urlList: urls }),
  });
  console.log("indexnow", mark, res.status);
  if (res.status === 200 || res.status === 202) await setSetting(env, "indexnow", mark);
}

/* ---------------- общее ---------------- */
function cors() {
  return { "access-control-allow-origin": "*", "access-control-allow-methods": "GET, POST, OPTIONS", "access-control-allow-headers": "content-type" };
}
function json(data, status = 200, cache = "no-store") {
  return new Response(JSON.stringify(data), { status, headers: { "content-type": "application/json; charset=utf-8", "cache-control": cache, ...cors() } });
}
// Тот же код аромата, что на сайте (src/site.html: hash(p.b + "|" + p.n).toString(36))
function siteUid(s) { let h = 0; for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0; return h.toString(36); }
async function sha256(s) {
  const b = await crypto.subtle.digest("SHA-256", new TextEncoder().encode(s));
  return [...new Uint8Array(b)].map((x) => x.toString(16).padStart(2, "0")).join("");
}
function randCode(n) { const a = crypto.getRandomValues(new Uint8Array(n)); return [...a].map((x) => ABC[x % ABC.length]).join(""); }
// Код покупки не начинается с «B», чтобы не путать его с бонус-кодом «B-XXXXX»
function purchaseCode() { let c; do { c = randCode(6); } while (c[0] === "B"); return c; }
function now() { return new Date().toISOString(); }
// Дата по времени Душанбе (UTC+5)
function dt(iso, time) { const d = new Date(Date.parse(iso) + 5 * 3600e3).toISOString(); return d.slice(8, 10) + "." + d.slice(5, 7) + "." + d.slice(0, 4) + (time ? " " + d.slice(11, 16) : ""); }
function cleanText(v, max, multiline) {
  let s = String(v == null ? "" : v).normalize("NFC");
  s = multiline ? s.replace(/\r\n?/g, "\n").replace(/[\u0000-\u0009\u000B-\u001F\u007F]/g, "").replace(/\n{3,}/g, "\n\n")
                : s.replace(/[\u0000-\u001F\u007F]/g, " ");
  s = s.replace(/[ \t]{2,}/g, " ").trim();
  return s.slice(0, max);
}
function int(v, lo, hi) { const n = Number(v); return Number.isInteger(n) && n >= lo && n <= hi ? n : null; }
function esc(s) { return String(s).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;"); }
async function getSetting(env, k) { const r = await env.DB.prepare("SELECT v FROM settings WHERE k = ?").bind(k).first(); return r ? r.v : null; }
async function setSetting(env, k, v) { await env.DB.prepare("INSERT INTO settings (k, v) VALUES (?, ?) ON CONFLICT(k) DO UPDATE SET v = excluded.v").bind(k, String(v)).run(); }

/* ---------------- отзывы на сайте ---------------- */
function counts(rows, key, n) { const c = new Array(n).fill(0); rows.forEach((r) => { const v = r[key]; if (v >= 1 && v <= n) c[v - 1]++; }); return c; }

async function listReviews(env, url) {
  const uid = (url.searchParams.get("uid") || "").toLowerCase();
  if (!/^[0-9a-z]{1,8}$/.test(uid)) return json({ error: "bad" }, 400);
  const { results } = await env.DB.prepare(
    "SELECT stars, lon, sil, sea, who, again, text, author, created, pcode IS NOT NULL AS ver FROM reviews WHERE uid = ? AND status = 'ok' ORDER BY id DESC LIMIT 500"
  ).bind(uid).all();
  const n = results.length, again = results.filter((r) => r.again === 1 || r.again === 0);
  return json({
    uid, n,
    avg: n ? Math.round(10 * results.reduce((a, r) => a + r.stars, 0) / n) / 10 : 0,
    lon: counts(results, "lon", 4), sil: counts(results, "sil", 3), sea: counts(results, "sea", 3), who: counts(results, "who", 3),
    again: [again.filter((r) => r.again === 1).length, again.filter((r) => r.again === 0).length],
    items: results.slice(0, 100).map((r) => ({
      s: r.stars, lon: r.lon, sil: r.sil, sea: r.sea, who: r.who, again: r.again,
      text: r.text || "", author: r.author || "", date: dt(r.created), ver: !!r.ver,
    })),
  }, 200, "public, max-age=30");
}

async function summary(env, url) {
  const uids = [...new Set((url.searchParams.get("uids") || "").toLowerCase().split(",").filter((u) => /^[0-9a-z]{1,8}$/.test(u)))].slice(0, 60);
  if (!uids.length) return json({});
  const q = "SELECT uid, COUNT(*) AS n, AVG(stars) AS avg, " +
    "SUM(lon = 1) AS l1, SUM(lon = 2) AS l2, SUM(lon = 3) AS l3, SUM(lon = 4) AS l4, SUM(sil = 1) AS s1, SUM(sil = 2) AS s2, SUM(sil = 3) AS s3 " +
    "FROM reviews WHERE status = 'ok' AND uid IN (" + uids.map(() => "?").join(",") + ") GROUP BY uid";
  const { results } = await env.DB.prepare(q).bind(...uids).all();
  const out = {};
  results.forEach((r) => { out[r.uid] = { n: r.n, avg: Math.round(10 * r.avg) / 10, lon: [r.l1, r.l2, r.l3, r.l4], sil: [r.s1, r.s2, r.s3] }; });
  return json(out, 200, "public, max-age=30");
}

async function addReview(request, env, ctx) {
  const b = await request.json().catch(() => null);
  if (!b || typeof b !== "object") return json({ error: "bad" }, 400);
  if (b.website) return json({ ok: true, bonus: null });            // ловушка для роботов: поле скрыто от людей
  const brand = cleanText(b.brand, 80), name = cleanText(b.name, 160);
  const stars = int(b.stars, 1, 5), lon = int(b.lon, 1, 4), sil = int(b.sil, 1, 3);
  if (!brand || !name || !stars || !lon || !sil) return json({ error: "bad" }, 400);
  const sea = int(b.sea, 1, 3), who = int(b.who, 1, 3), again = b.again === 1 || b.again === 0 ? b.again : null;
  const text = cleanText(b.text, 1000, true), author = cleanText(b.author, 40);
  const lang = ["ru", "tg", "en"].includes(b.lang) ? b.lang : "ru";
  const dev = /^[a-z0-9]{8,40}$/.test(b.dev || "") ? b.dev : null;
  const uid = siteUid(brand + "|" + name);
  const iph = (await sha256((request.headers.get("cf-connecting-ip") || "") + "|" + (env.TG_TOKEN || "shoh"))).slice(0, 24);
  const db = env.DB;

  // Защита от спама: не больше 5 отзывов с адреса за сутки, один отзыв об аромате с устройства
  const day = new Date(Date.now() - 864e5).toISOString();
  const byIp = await db.prepare("SELECT COUNT(*) AS c FROM reviews WHERE iph = ? AND created > ?").bind(iph, day).first();
  if (byIp.c >= LIMIT_PER_IP_DAY) return json({ error: "limit" }, 429);
  const dup = await db.prepare("SELECT COUNT(*) AS c FROM reviews WHERE uid = ? AND status != 'no' AND (iph = ? OR dev = ?)").bind(uid, iph, dev || "-").first();
  if (dup.c > 0) return json({ error: "dup" }, 409);
  const pend = await db.prepare("SELECT COUNT(*) AS c FROM reviews WHERE status = 'pending'").first();
  if (pend.c >= MAX_PENDING) return json({ error: "busy" }, 503);

  // Код покупки → «Проверенная покупка» и бонус-код (один код — один отзыв)
  const code = String(b.code || "").toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 12);
  let bonus = null;
  if (code) {
    const row = await db.prepare("SELECT used_by FROM codes WHERE code = ?").bind(code).first();
    if (!row) return json({ error: "code" }, 400);
    const take = await db.prepare("UPDATE codes SET used_by = -1 WHERE code = ? AND used_by IS NULL").bind(code).run();
    if (!take.meta.changes) return json({ error: "code_used" }, 400);
    bonus = "B-" + randCode(5);
  }
  const ins = await db.prepare(
    "INSERT INTO reviews (uid, brand, name, stars, lon, sil, sea, who, again, text, author, lang, pcode, bonus, status, created, iph, dev) " +
    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?)"
  ).bind(uid, brand, name, stars, lon, sil, sea, who, again, text || null, author || null, lang, code || null, bonus, now(), iph, dev).run();
  const id = ins.meta.last_row_id;
  if (code) await db.prepare("UPDATE codes SET used_by = ? WHERE code = ?").bind(id, code).run();
  ctx.waitUntil(notifyOwner(env, id).catch((e) => console.error("notify", e)));
  return json({ ok: true, id, bonus, verified: !!code });
}

/* ---------------- Telegram ---------------- */
async function tg(env, method, body) {
  const base = env.TG_API || "https://api.telegram.org";
  const r = await fetch(base + "/bot" + env.TG_TOKEN + "/" + method, { method: "POST", headers: { "content-type": "application/json" }, body: JSON.stringify(body) });
  return r.json().catch(() => ({ ok: false }));
}
async function hookSecret(env) { return (await sha256(env.TG_TOKEN + "|shoh-hook")).slice(0, 40); }

// Подключить бота к сайту (один раз для каждого токена)
async function ensureWebhook(env) {
  webhookChecked = true;
  const site = env.SITE || "https://shoh-parfumer.com";
  const want = (await sha256(env.TG_TOKEN + "|" + site)).slice(0, 16);
  if ((await getSetting(env, "webhook")) === want) return;
  const sec = await hookSecret(env);
  const r = await tg(env, "setWebhook", { url: site + "/api/tg/" + sec, secret_token: sec, allowed_updates: ["message", "callback_query"] });
  if (!r.ok) { webhookChecked = false; console.error("setWebhook", JSON.stringify(r)); return; }
  await setSetting(env, "webhook", want);
  await tg(env, "setMyCommands", { commands: [
    { command: "kod", description: "Новый код покупки (бонус за отзыв)" },
    { command: "otzyvy", description: "Отзывы на проверке" },
    { command: "pomosh", description: "Как пользоваться ботом" },
  ] });
}

function stars(n) { return "★".repeat(n) + "☆".repeat(5 - n); }
const STATUS = { pending: "⏳ на проверке", ok: "✅ опубликован", no: "❌ удалён" };

function reviewMessage(r) {
  const lines = [
    "📝 <b>Отзыв №" + r.id + "</b> · " + dt(r.created, true),
    "<b>" + esc(r.name) + "</b> — " + esc(r.brand),
    stars(r.stars) + " (" + r.stars + " из 5)",
    "Стойкость: " + (LON[r.lon] || "—") + " · Шлейф: " + (SIL[r.sil] || "—"),
  ];
  const extra = [];
  if (r.sea) extra.push("Носят: " + SEA[r.sea]);
  if (r.who) extra.push("Для кого: " + WHO[r.who]);
  if (r.again === 1 || r.again === 0) extra.push("Купили бы снова: " + (r.again ? "да" : "нет"));
  if (extra.length) lines.push(extra.join(" · "));
  lines.push(r.text ? "«" + esc(r.text) + "»" : "<i>без текста</i>");
  if (r.author) lines.push("Имя: " + esc(r.author));
  lines.push(r.pcode ? "✓ Код покупки " + r.pcode + " → бонус-код <b>" + r.bonus + "</b>" : "Без кода покупки — бонуса нет");
  lines.push("Статус: " + STATUS[r.status] + (r.decided ? " (" + dt(r.decided, true) + ")" : ""));
  if (r.bonus && r.status === "ok") lines.push("Бонус: " + (r.bonus_used ? "🎁 выдан " + dt(r.bonus_used_at) : "не выдан"));
  return lines.join("\n");
}
function reviewButtons(r) {
  if (r.status === "pending") return [[{ text: "✅ Опубликовать", callback_data: "ok:" + r.id }, { text: "❌ Удалить", callback_data: "no:" + r.id }]];
  if (r.status === "ok") {
    const row = [{ text: "❌ Снять с сайта", callback_data: "no:" + r.id }];
    if (r.bonus && !r.bonus_used) row.unshift({ text: "🎁 Бонус выдан", callback_data: "use:" + r.id });
    return [row];
  }
  return [[{ text: "↩️ Всё-таки опубликовать", callback_data: "ok:" + r.id }]];
}
async function getReview(env, id) { return env.DB.prepare("SELECT * FROM reviews WHERE id = ?").bind(id).first(); }

async function notifyOwner(env, id) {
  if (!env.TG_TOKEN) return;
  const chat = await getSetting(env, "owner_chat");
  if (!chat) return;                                   // владелец ещё не написал боту /start — отзыв ждёт в базе
  const r = await getReview(env, id);
  const m = await tg(env, "sendMessage", { chat_id: Number(chat), text: reviewMessage(r), parse_mode: "HTML", reply_markup: { inline_keyboard: reviewButtons(r) } });
  if (m.ok) await env.DB.prepare("UPDATE reviews SET tg_msg = ? WHERE id = ?").bind(m.result.message_id, id).run();
}

const HELP = [
  "<b>Бот отзывов Shoh Parfumer</b>",
  "• Новый отзыв с сайта приходит сюда. Нажмите «Опубликовать» или «Удалить» — без вашего решения отзыв на сайте не появится.",
  "• /kod — новый код покупки. Дайте его покупателю (или ссылку с ним): по коду его отзыв отмечается «Проверенная покупка», а он получает бонус-код. /kod 10 — сразу 10 кодов (для печати).",
  "• Покупатель пришёл с бонус-кодом — отправьте код сюда (например, B-4T8PK): бот покажет, действует ли он, и кнопку «Бонус выдан».",
  "• /otzyvy — отзывы, которые ждут проверки.",
].join("\n");

async function telegram(request, env, pathSecret) {
  if (!env.TG_TOKEN) return json({ ok: true });
  const sec = await hookSecret(env);
  if (pathSecret !== sec || request.headers.get("x-telegram-bot-api-secret-token") !== sec) return json({ error: "forbidden" }, 403);
  const u = await request.json().catch(() => null);
  if (!u) return json({ ok: true });
  const owner = await getSetting(env, "owner_chat");
  if (u.callback_query) await onButton(env, u.callback_query, owner);
  else if (u.message && u.message.chat && u.message.chat.type === "private") await onMessage(env, u.message, owner);
  return json({ ok: true });
}

async function onMessage(env, m, owner) {
  const chat = m.chat.id, text = String(m.text || "").trim(), user = String(m.from && m.from.username || "").toLowerCase();
  const isOwnerName = !!env.OWNER_TG && user === String(env.OWNER_TG).toLowerCase();
  const send = (t, extra) => tg(env, "sendMessage", { chat_id: chat, text: t, parse_mode: "HTML", disable_web_page_preview: true, ...(extra || {}) });

  if (/^\/start\b/.test(text) && isOwnerName) {
    await setSetting(env, "owner_chat", chat);
    await send("Готово! Отзывы с сайта будут приходить сюда.\n\n" + HELP);
    await sendPending(env, chat);
    return;
  }
  if (!owner || String(chat) !== String(owner)) {
    await send("Здравствуйте! Это бот отзывов магазина Shoh Parfumer. Оставить отзыв об аромате можно на сайте: " + (env.SITE || "https://shoh-parfumer.com"));
    return;
  }
  const kod = text.match(/^\/(kod|code|код)(?:@\w+)?\s*(\d+)?/i);
  if (kod) {
    const n = Math.min(Math.max(Number(kod[2] || 1), 1), 20), made = [];
    for (let i = 0; i < n; i++) {
      const c = purchaseCode();
      await env.DB.prepare("INSERT OR IGNORE INTO codes (code, created) VALUES (?, ?)").bind(c, now()).run();
      made.push(c);
    }
    const site = env.SITE || "https://shoh-parfumer.com";
    await send((n === 1 ? "Код покупки: <b>" + made[0] + "</b>\nСсылка для покупателя (откроет форму отзыва с этим кодом):\n" + site + "/?otziv=" + made[0]
      : "Коды покупки (каждый — на один отзыв с бонусом):\n" + made.map((c) => "<b>" + c + "</b> — " + site + "/?otziv=" + c).join("\n")) +
      "\n\nПокупатель выбирает купленный аромат, пишет отзыв — и получает бонус-код.");
    return;
  }
  if (/^\/(otzyvy|otzivy|pending|отзывы)/i.test(text)) { await sendPending(env, chat); return; }
  if (/^\/(pomosh|help|start)/i.test(text)) { await send(HELP); return; }

  // Код от покупателя: бонус-код (B-XXXXX) или код покупки (6 знаков)
  const raw = text.toUpperCase().replace(/[^A-Z0-9]/g, "");
  const bonus = raw.startsWith("B") && raw.length === 6 ? "B-" + raw.slice(1) : null;
  if (bonus) {
    const r = await env.DB.prepare("SELECT * FROM reviews WHERE bonus = ?").bind(bonus).first();
    if (!r) { await send("Бонус-код <b>" + bonus + "</b> не найден. Проверьте, правильно ли он написан."); return; }
    const state = r.status !== "ok" ? "Бонус пока не действует: отзыв " + STATUS[r.status] + "."
      : r.bonus_used ? "🎁 Бонус уже выдан " + dt(r.bonus_used_at, true) + "." : "✅ Бонус действует — можно выдать.";
    await send("🎁 <b>" + bonus + "</b>\n" + state + "\n\n" + reviewMessage(r), { reply_markup: { inline_keyboard: reviewButtons(r) } });
    return;
  }
  if (raw.length === 6) {
    const c = await env.DB.prepare("SELECT * FROM codes WHERE code = ?").bind(raw).first();
    if (c) { await send("Код покупки <b>" + raw + "</b>: " + (c.used_by ? "уже использован (отзыв №" + c.used_by + ")." : "ещё не использован.")); return; }
  }
  await send("Не понял команду.\n\n" + HELP);
}

async function sendPending(env, chat) {
  const { results } = await env.DB.prepare("SELECT * FROM reviews WHERE status = 'pending' ORDER BY id LIMIT 10").all();
  const total = (await env.DB.prepare("SELECT COUNT(*) AS c FROM reviews WHERE status = 'pending'").first()).c;
  if (!total) { await tg(env, "sendMessage", { chat_id: chat, text: "Отзывов на проверке нет." }); return; }
  await tg(env, "sendMessage", { chat_id: chat, text: "На проверке: " + total + (total > 10 ? " (показываю первые 10)" : "") });
  for (const r of results) {
    const m = await tg(env, "sendMessage", { chat_id: chat, text: reviewMessage(r), parse_mode: "HTML", reply_markup: { inline_keyboard: reviewButtons(r) } });
    if (m.ok) await env.DB.prepare("UPDATE reviews SET tg_msg = ? WHERE id = ?").bind(m.result.message_id, r.id).run();
  }
}

async function onButton(env, q, owner) {
  const answer = (text) => tg(env, "answerCallbackQuery", { callback_query_id: q.id, text });
  if (!owner || String(q.from && q.from.id) !== String(owner)) { await answer("Нет доступа"); return; }
  const m = String(q.data || "").match(/^(ok|no|use):(\d+)$/);
  if (!m) { await answer(""); return; }
  const id = Number(m[2]), t = now();
  let note = "";
  if (m[1] === "use") {
    const r = await env.DB.prepare("UPDATE reviews SET bonus_used = 1, bonus_used_at = ? WHERE id = ? AND status = 'ok' AND bonus IS NOT NULL AND bonus_used = 0").bind(t, id).run();
    note = r.meta.changes ? "Бонус отмечен как выданный" : "Бонус уже выдан или отзыв не опубликован";
  } else {
    const st = m[1] === "ok" ? "ok" : "no";
    await env.DB.prepare("UPDATE reviews SET status = ?, decided = ? WHERE id = ?").bind(st, t, id).run();
    note = st === "ok" ? "Отзыв опубликован на сайте" : "Отзыв удалён с сайта";
  }
  const r = await getReview(env, id);
  if (r && q.message) {
    await tg(env, "editMessageText", { chat_id: q.message.chat.id, message_id: q.message.message_id, text: reviewMessage(r), parse_mode: "HTML", reply_markup: { inline_keyboard: reviewButtons(r) } });
  }
  await answer(note);
}
