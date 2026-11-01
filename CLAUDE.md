# Notes for Claude

Owner: Shoh Parfumer (perfume shop, Dushanbe). Talks in Russian; prefers short, factual answers,
minimal design, and wants questions asked BEFORE building anything unclear.

- Edit `src/site.html` (template), never hand-edit `public/index.html`.
- Rebuild: `python3 -I src/make_site.py src/site.html data/db.json public/index.html --standalone`.
- Owner settings live at the top of the script in `src/site.html`: TELEGRAM, GOATCOUNTER, SITE_URL, STOCK.
- Workflow: since 30.10.2026 the owner asks for finished changes to go live right away AND be shown in the chat
  (non-standalone build → Claude artifact link, same URL each time). If he says «пока не загружай» / «не публикуй»,
  build the test version only and push after he says «загружай».
- Known dupes live in `data/dupes.txt`; apply with `python3 -I src/add_dupes.py data/db.json data/dupes.txt`
  (adds `du`/`xd` to the DB), then rebuild. The «Найти дюп» screen shows ONLY known dupes (up to 5) — the owner
  rejected formula-based «похож по нотам» there. Its search covers the whole base (perfumes with dupes first);
  a perfume without dupes shows «дюпов пока нет», a same-line original with dupes (Absolu Aventus → Aventus)
  and a «Написать нам» button. More dupes = add lines to data/dupes.txt.
- Search: raw → sound key (phon) → consonant skeleton (skel, Russian letters only) → typos (osa). Russian-letter
  queries are ranked by popularity; Latin ones by match level. Test with smoke_search/smoke_s2-style checks.
- Owner's firm rule: never "fix" bad or missing data by switching a feature off or hiding results. Data gaps
  (missing notes, borrowed notes, missing dupe brands, no 2025–26 releases) get filled from real sources
  (official brand sites, shops, a licensed data API). Disabling the formula is not an acceptable solution.
- All UI text exists in three languages (ru / tg / en): keep them in sync (I18N and I18N_X objects).
- Design: dark-first, yellow buttons (#FFC61A) in both themes, theme follows the phone (not persisted).
- Bottles are generic drawn SVGs (minimal style), never copies of brand bottles. No scraped photos.
- Results are sorted by match % (owner's decision); the «Хит» label stays on its perfume wherever it lands.
- History: every screen is a history entry with a state snapshot (snap/applySnap/histPush in `src/site.html`), so the
  phone Back button goes to the previous screen or closes an open sheet, and reload keeps the selection. In-page «Назад»
  buttons use navBack(). Disabled inside the Claude preview. New screens must call go()/histPush(); new sheets must call
  histOverlay() on open and histOverlayClosed() on close.
- Search keys are prepared in the background (prepLoop); until ready, search matches by spelling and refreshes itself.
  Keep the first screen free of long synchronous work (weak Android phones: test with CPU throttling ×4–×6).
- Link preview: og tags are added by make_site.py (--standalone); image `public/og.png` from `src/og.html`.
- Search engines (owner, 01.11.2026): make_site.py --standalone also writes public/tg/index.html, public/en/index.html
  (same page, static texts pre-translated from I18N via node; title/description = I18N pageTitle/metaDesc), canonical +
  hreflang, JSON-LD Store (Dushanbe; add address/hours/phone ONLY when the owner sends them), sitemap.xml (lastmod
  changes only when pages change), robots.txt. The page language follows the path (/, /tg/, /en/) and langSync() keeps
  the address in step with the language. Verification codes: VERIFY in make_site.py + public/yandex_*.html /
  google*.html (worker/index.js serves them with 200, no redirect). IndexNow: worker cron every 3 h pings Yandex/Bing
  when sitemap lastmod changes (key file public/7760fe….txt). Icons: src/make_icons.py.
  Unknown paths → `public/404.html` (redirects home) via `not_found_handling` in wrangler.jsonc.
- «Сравнить ароматы» = step 7 (mode "compare"): entry button only at the bottom of home after «Найти дюп» (owner).
  Rows with no data on both sides are hidden; longevity/sillage only «по отзывам» (≥3 approved reviews), never invented.
  Year/concentration come from src/add_info.py (Parfumo; poisoned rows' years dropped; verified fixes in data/info_manual.txt).
  «Характер» bars show % (of the perfume's strongest trait, 5% steps) small inside the bar (owner): exact values in
  public/taste.json from src/make_taste.py (run LAST after any DB rebuild; tag `th` must match), fetched only when
  «Сравнить» opens; inlined in the artifact build. Coarse 0–3 digits stay for matching. No file/mismatch → bars without %.
- Reviews (owner: every review is moderated in Telegram before it shows; bonus only via purchase codes):
  worker/index.js + D1 `shoh-parfumer-reviews` (id d1e16ec0-…, tables in migrations/0001_reviews.sql, created via the
  Cloudflare connector). Site: rvBtn/rvLoad/openReviews in src/site.html, `#rv` sheet, `?otziv=CODE` link.
  Secret TG_TOKEN is added by the owner in the Cloudflare dashboard — never ask for it in chat. Don't put test reviews
  into the production DB (if you must check live, delete the row right after).
- Layout must hold from 320 px in all three languages (Tajik strings are the longest); never let words break mid-word.
- After a rebuild, run a quick Playwright check (pick 3 perfumes → questions → results) before pushing.
- Cloudflare Workers (project `shoh-parfumer`, config `wrangler.jsonc`) publishes `public/` on every push to `main`,
  serving shoh-parfumer.com and www. Netlify is no longer used (its free plan forces a badge).
