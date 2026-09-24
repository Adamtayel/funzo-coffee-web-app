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

1. Vercel → Project Settings → Git → Deploy Hooks → create a hook named
   `sheet-edit` on `main` → copy the URL.
2. In the sheet: Extensions → Apps Script. Replace everything in `Code.gs`
   with the contents of [`apps-script.js`](apps-script.js), and paste the
   deploy hook URL into `DEPLOY_HOOK` at the top. Save.
3. Triggers (clock icon) → Add Trigger → function `onMenuEdit` → event source
   *From spreadsheet* → event type *On edit* → Save. Approve the permission
   prompt (it needs to call the deploy hook and schedule timers).
4. Reload the sheet. A new menu, **الموقع → حدّث الموقع دلوقتي**, appears —
   that forces a rebuild immediately.

Edit a price and the page updates about 1–2 minutes after the owner stops
typing, with a second rebuild ~6 minutes later as a guarantee. Google
republishes the CSV with a delay after edits, which is why one rebuild alone
can occasionally pick up the old price. `build.py` also adds a cache-busting
parameter to the CSV fetch so Google's 5-minute CDN cache is never the issue.

To check it worked: the menu footer shows "آخر تحديث للأسعار" with the date
of the last successful build, and Vercel → Deployments lists each rebuild.

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
