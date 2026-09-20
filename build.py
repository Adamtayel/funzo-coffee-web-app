#!/usr/bin/env python3
"""
Funzo menu builder.

Reads the menu from a published Google Sheet (CSV) and writes static HTML to
public/menu/index.html. Nothing is fetched at runtime — the phone gets
finished HTML.

    python3 build.py                 # uses the SHEET_CSV_URL env var
    python3 build.py menu.csv        # local file, for testing

On Vercel, set SHEET_CSV_URL under Project Settings > Environment Variables.
"""

import csv
import html
import io
import json
import os
import sys
import urllib.request
from datetime import date

# ---------------------------------------------------------------- config

CAFE_NAME = "Funzo"
WIFI = "funzo2026"
PHONE = "011 5709 7578"
PHONE_RAW = "+201157097578"
SITE_URL = "https://funzo.vercel.app"
TAYEL_URL = "https://tayel.ai"
CURRENCY = "EGP"

TEMPLATE = "template.html"
OUTPUT = "public/menu/index.html"

HOME_TEMPLATE = "home.html"
HOME_OUTPUT = "public/index.html"

# If the sheet ever returns fewer rows than this, something is wrong: the
# publish link was revoked, the sheet was cleared, or Google returned an error
# page. Fail the build so the last good deployment stays live.
MIN_ITEMS = 50

# ------------------------------------------------------------- ui strings
# The only Arabic in this repo outside menu.csv. These are printed on the page
# for Arabic-speaking customers, so they are content, not code. Everything
# else — names, comments, docs, commit messages — is English.

LABEL_SINGLE = "سنجل"
LABEL_DOUBLE = "دبل"
LABEL_SOLD_OUT = "خلص النهاردة"

MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
          "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

# ---------------------------------------------------------------- reading


def load_rows():
    """Read menu rows from a local CSV argument, or from the published sheet."""
    local = sys.argv[1] if len(sys.argv) > 1 else None
    if local:
        with open(local, encoding="utf-8-sig") as f:
            return list(csv.DictReader(f))

    url = os.environ.get("SHEET_CSV_URL", "").strip()
    if not url:
        sys.exit("SHEET_CSV_URL is not set. Pass a local CSV path to test:\n"
                 "    python3 build.py menu.csv")

    with urllib.request.urlopen(url, timeout=25) as r:
        text = r.read().decode("utf-8-sig")

    if "<html" in text[:400].lower():
        sys.exit("The sheet URL returned a web page instead of CSV. "
                 "Re-check File > Share > Publish to web > CSV.")

    return list(csv.DictReader(io.StringIO(text)))


def clean(row):
    return {k: (v or "").strip() for k, v in row.items() if k}


def is_available(value):
    """Accept the shapes a checkbox column can arrive in."""
    return value.upper() not in ("FALSE", "0", "NO")


def group(rows):
    """Sheet order is menu order. Returns [(name_ar, name_en, items), ...]."""
    sections, index = [], {}
    for raw in rows:
        r = clean(raw)
        name = r.get("item", "")
        section = r.get("section_ar", "")
        if not name or not section:
            continue
        if section not in index:
            index[section] = len(sections)
            sections.append((section, r.get("section_en", ""), []))
        sections[index[section]][2].append({
            "name": name,
            "name_en": r.get("item_en", ""),
            "options": r.get("options", ""),
            "options_en": r.get("options_en", ""),
            "single": r.get("single", ""),
            "double": r.get("double", ""),
            "available": is_available(r.get("available", "TRUE")),
        })
    return sections

# ---------------------------------------------------------------- rendering


def price_cell(value):
    """An em dash marks a size the item is not sold in — not a missing price."""
    if not value:
        return '<span class="p empty">—</span>'
    return '<span class="p">%s</span>' % html.escape(value)


def render_item(item, two_columns):
    e = html.escape
    css = "" if item["available"] else ' class="out"'
    flag = "" if item["available"] else '<span class="flag">%s</span>' % LABEL_SOLD_OUT

    cells = price_cell(item["single"])
    if two_columns:
        cells += price_cell(item["double"])

    name = e(item["name"]) + flag
    if item["name_en"]:
        name += '<span class="en">%s</span>' % e(item["name_en"])

    out = ['<li%s>' % css,
           '<div class="row"><span class="name">%s</span>'
           '<span class="dots"></span>%s</div>' % (name, cells)]

    if item["options"] or item["options_en"]:
        opts = e(item["options"])
        if item["options_en"]:
            opts += '<span class="en">%s</span>' % e(item["options_en"])
        out.append('<p class="opts">%s</p>' % opts)

    out.append('</li>')
    return "".join(out)


def render(sections):
    """Return the chip navigation and the section markup."""
    chips, blocks = [], []

    for i, (name_ar, name_en, items) in enumerate(sections):
        sid = "s%d" % i
        chips.append('<a href="#%s">%s</a>' % (sid, html.escape(name_ar)))

        # A section shows two price columns as soon as one item has a double.
        two = any(it["double"] for it in items)

        head = '<div class="head"><h2>%s</h2>' % html.escape(name_ar)
        if name_en:
            head += '<span>%s</span>' % html.escape(name_en)
        head += '</div>'

        labels = ""
        if two:
            labels = ('<div class="labels"><span class="dots"></span>'
                      '<span class="p">%s</span><span class="p">%s</span></div>'
                      % (LABEL_SINGLE, LABEL_DOUBLE))

        rows = "\n".join(render_item(it, two) for it in items)
        blocks.append('<section id="%s">\n%s%s\n<ul>\n%s\n</ul>\n</section>'
                      % (sid, head, labels, rows))

    return "\n".join(chips), "\n\n".join(blocks)


def render_jsonld(sections):
    """Structured data, so search engines can read the menu itself."""
    menu_sections = []
    for name_ar, name_en, items in sections:
        entries = []
        for it in items:
            if not it["available"] or not it["single"]:
                continue
            entries.append({
                "@type": "MenuItem",
                "name": it["name"],
                "alternateName": it["name_en"] or it["name"],
                "offers": {"@type": "Offer",
                           "price": it["single"],
                           "priceCurrency": CURRENCY},
            })
        if entries:
            menu_sections.append({"@type": "MenuSection",
                                  "name": name_ar, "hasMenuItem": entries})

    return json.dumps({
        "@context": "https://schema.org",
        "@type": "CafeOrCoffeeShop",
        "name": CAFE_NAME,
        "url": SITE_URL,
        "telephone": PHONE_RAW,
        "servesCuisine": "Coffee",
        "hasMenu": {"@type": "Menu", "hasMenuSection": menu_sections},
    }, ensure_ascii=False, separators=(",", ":"))


def format_date(d):
    return "%d %s %d" % (d.day, MONTHS[d.month - 1], d.year)


def build_home():
    """The homepage is static content, not the sheet — see CLAUDE.md."""
    with open(HOME_TEMPLATE, encoding="utf-8") as f:
        page = f.read()

    for key, value in {
        "{{WIFI}}": html.escape(WIFI),
        "{{PHONE}}": html.escape(PHONE),
        "{{PHONE_RAW}}": html.escape(PHONE_RAW),
        "{{TAYEL_URL}}": html.escape(TAYEL_URL),
    }.items():
        page = page.replace(key, value)

    os.makedirs(os.path.dirname(HOME_OUTPUT), exist_ok=True)
    with open(HOME_OUTPUT, "w", encoding="utf-8") as f:
        f.write(page)

    print("%s — %.1f KB" % (HOME_OUTPUT, len(page.encode()) / 1024))

# ---------------------------------------------------------------- entry


def main():
    # Static and independent of the sheet, so a bad sheet never blocks it.
    build_home()

    sections = group(load_rows())
    total = sum(len(items) for _, _, items in sections)

    if total < MIN_ITEMS:
        sys.exit("Only %d items found, expected at least %d. "
                 "Build stopped so the live menu stays as it is."
                 % (total, MIN_ITEMS))

    chips, blocks = render(sections)

    with open(TEMPLATE, encoding="utf-8") as f:
        page = f.read()

    for key, value in {
        "{{CHIPS}}": chips,
        "{{SECTIONS}}": blocks,
        "{{JSONLD}}": render_jsonld(sections),
        "{{UPDATED}}": format_date(date.today()),
        "{{WIFI}}": html.escape(WIFI),
        "{{PHONE}}": html.escape(PHONE),
        "{{PHONE_RAW}}": html.escape(PHONE_RAW),
        "{{TAYEL_URL}}": html.escape(TAYEL_URL),
    }.items():
        page = page.replace(key, value)

    os.makedirs(os.path.dirname(OUTPUT), exist_ok=True)
    with open(OUTPUT, "w", encoding="utf-8") as f:
        f.write(page)

    print("%s — %d sections, %d items, %.1f KB"
          % (OUTPUT, len(sections), total, len(page.encode()) / 1024))


if __name__ == "__main__":
    main()
