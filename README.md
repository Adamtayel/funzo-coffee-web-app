# Funzo — QR Menu

A static menu built from a Google Sheet. The owner edits a price in the sheet;
the site rebuilds itself. Customers reach it by scanning a QR code at the table,
so the page is optimised for a slow connection and a phone screen.

## Files

| | |
|---|---|
| `menu.csv` | Seed data, Arabic and English. Imported into Google Sheets once. |
| `template.html` | Layout, colours, motion. This is the file to iterate on. |
| `build.py` | Reads the sheet, writes `public/menu/index.html`. Standard library only. |
| `vercel.json` | Build and routing config. |

`public/` is not tracked — it is generated on every deploy.

### Sheet columns

`section_ar` `section_en` `item` `item_en` `options` `options_en` `single` `double` `available`

A section renders two price columns (single / double) as soon as one of its
items has a `double` value.

---

## 1. GitHub

```bash
cd funzo
git init
git add .
git commit -m "Funzo menu: bilingual static build from Google Sheets"
git branch -M main
git remote add origin git@github.com:USERNAME/funzo-menu.git
git push -u origin main
```

## 2. Google Sheet

1. Open `sheets.new` → File → Import → upload `menu.csv` → Replace spreadsheet.
2. View → Freeze → 1 row.
3. Data → Protect sheets and ranges → `A:F` → Set permissions → Only you.
   This leaves the owner able to edit `single`, `double` and `available` only.
4. On the `available` column: Data → Data validation → Checkbox.
5. File → Share → Publish to web → pick the sheet →
   **Comma-separated values (.csv)** → Publish. Copy the link.

## 3. Vercel

1. vercel.com → Add New → Project → pick the repo.
2. Framework Preset: **Other**. Leave Build Command and Output Directory
   empty — `vercel.json` sets both.
3. Environment Variables → add:
   ```
   SHEET_CSV_URL = <the CSV link from step 2>
   ```
   Enable it for Production, Preview and Development.
4. Deploy.

The menu lives at `/menu`. `/` redirects there until a homepage exists.

> If the build fails with `python3: command not found`, change `buildCommand`
> in `vercel.json` to `python build.py`.

## 4. Rebuild on edit

[`.github/workflows/sync-prices.yml`](.github/workflows/sync-prices.yml)
checks the sheet every 5 minutes. When anything changed, it validates the
sheet with `build.py` and commits the new `menu.csv`; that push triggers a
normal Vercel deploy. Nothing to install in Google, no deploy hook.

One-time setup: GitHub → repo → Settings → Secrets and variables → Actions →
New repository secret → name `SHEET_CSV_URL`, value = the published CSV link.

Expect a price edit to be live in roughly 5–15 minutes (GitHub runs scheduled
jobs every 5 minutes at best, sometimes later under load; Google also takes a
few minutes to republish the CSV). Run it immediately from the repo's Actions
tab → *Sync prices from Google Sheet* → *Run workflow*.

Things to know:
- A broken sheet (fewer than `MIN_ITEMS` rows) fails the workflow and commits
  nothing — the live menu stays. GitHub emails the repo owner on failure.
- Every price change becomes a commit, so `git log -- menu.csv` is the price
  history.
- GitHub pauses scheduled workflows after 60 days with no commits. Price
  changes count as commits, so this only bites if nothing changes for two
  months; re-enable it from the Actions tab.
- Free on a public repo. On a private repo, a 5-minute schedule uses more
  than the free 2,000 Actions minutes/month — switch the cron to `*/30` or
  use the Apps Script option below.
- `build.py` cache-busts the CSV fetch, so Google's 5-minute CDN cache never
  serves Vercel an old price.

**Optional, faster (~1–2 min):** [`apps-script.js`](apps-script.js) runs
inside the sheet and fires a Vercel deploy hook when the owner edits. Setup
steps are in the comment at the top of that file; it needs someone logged
into the owner's Google account and Vercel. Both mechanisms can run at once.

To check it worked: the menu footer shows "آخر تحديث للأسعار" with the date
of the last build, and Vercel → Deployments lists each rebuild.

---

## 5. Iterating

```bash
python3 build.py menu.csv          # local, without touching the sheet
open public/menu/index.html
```

When it looks right:

```bash
git add template.html
git commit -m "Refine spacing in section headers"
git push
```

Every push to `main` deploys.

For anything larger — a different palette, a new layout — branch it:

```bash
git checkout -b darker-olive
git push -u origin darker-olive
```

Vercel builds a separate preview URL per branch. Send that to the owner to open
on his own phone, and merge once he approves.

## 6. QR code

Point the QR at the final domain (`funzo.com/menu`), never at the sheet or a
temporary Vercel URL. Stickers get printed once; a domain you control can be
repointed later without reprinting anything.

## Failure behaviour

`build.py` stops the build if the sheet returns fewer than 50 items, or returns
an HTML page instead of CSV. Vercel keeps the previous deployment live when a
build fails, so a broken sheet leaves the last good menu on the tables rather
than an empty page.

## Language

Code, comments, docs and commit messages are English. The Arabic in `menu.csv`
and in the `ui strings` block of `build.py` is customer-facing content.
