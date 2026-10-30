# Notes for Claude

Owner: Shoh Parfumer (perfume shop, Dushanbe). Talks in Russian; prefers short, factual answers,
minimal design, and wants questions asked BEFORE building anything unclear.

- Edit `src/site.html` (template), never hand-edit `public/index.html`.
- Rebuild: `python3 -I src/make_site.py src/site.html data/db.json public/index.html --standalone`.
- Owner settings live at the top of the script in `src/site.html`: TELEGRAM, GOATCOUNTER, SITE_URL, STOCK.
- All UI text exists in three languages (ru / tg / en): keep them in sync (I18N and I18N_X objects).
- Design: dark-first, yellow buttons (#FFC61A) in both themes, theme follows the phone (not persisted).
- Bottles are generic drawn SVGs (minimal style), never copies of brand bottles. No scraped photos.
- After a rebuild, run a quick Playwright check (pick 3 perfumes → questions → results) before pushing.
- Cloudflare Workers (project `shoh-parfumer`, config `wrangler.jsonc`) publishes `public/` on every push to `main`,
  serving shoh-parfumer.com and www. Netlify is no longer used (its free plan forces a badge).
