# Notes for Claude

Owner: Shoh Parfumer (perfume shop, Dushanbe). Talks in Russian; prefers short, factual answers,
minimal design, and wants questions asked BEFORE building anything unclear.

- Edit `src/site.html` (template), never hand-edit `public/index.html`.
- Rebuild: `python3 -I src/make_site.py src/site.html data/db.json public/index.html --standalone`.
- Owner settings live at the top of the script in `src/site.html`: TELEGRAM, GOATCOUNTER, SITE_URL, STOCK.
- Workflow (owner's rule): never push to `main` right away. Build a test version first (non-standalone build →
  Claude artifact link), let the owner check it, and push only after he says «загружай».
- Known dupes live in `data/dupes.txt`; apply with `python3 -I src/add_dupes.py data/db.json data/dupes.txt`
  (adds `du`/`xd` to the DB), then rebuild. The «Найти дюп» screen shows ONLY known dupes (up to 5) — the owner
  rejected formula-based «похож по нотам» there. Search on that screen covers only perfumes with known dupes;
  otherwise a «Написать нам» button opens feedback. More dupes = add lines to data/dupes.txt.
- Owner's firm rule: never "fix" bad or missing data by switching a feature off or hiding results. Data gaps
  (missing notes, borrowed notes, missing dupe brands, no 2025–26 releases) get filled from real sources
  (official brand sites, shops, a licensed data API). Disabling the formula is not an acceptable solution.
- All UI text exists in three languages (ru / tg / en): keep them in sync (I18N and I18N_X objects).
- Design: dark-first, yellow buttons (#FFC61A) in both themes, theme follows the phone (not persisted).
- Bottles are generic drawn SVGs (minimal style), never copies of brand bottles. No scraped photos.
- After a rebuild, run a quick Playwright check (pick 3 perfumes → questions → results) before pushing.
- Cloudflare Workers (project `shoh-parfumer`, config `wrangler.jsonc`) publishes `public/` on every push to `main`,
  serving shoh-parfumer.com and www. Netlify is no longer used (its free plan forces a badge).
