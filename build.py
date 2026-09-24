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
import re
import sys
import time
import urllib.request
from datetime import date

# ---------------------------------------------------------------- config

CAFE_NAME = "Funzo"
WIFI = "funzo2026"
PHONE = "011 5709 7578"
PHONE_RAW = "+201157097578"
SITE_URL = "https://funzo.vercel.app"
TAYEL_URL = "https://tayel.net"
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
LABEL_ITEMS = "صنف"

MONTHS = ["يناير", "فبراير", "مارس", "أبريل", "مايو", "يونيو",
          "يوليو", "أغسطس", "سبتمبر", "أكتوبر", "نوفمبر", "ديسمبر"]

# ---------------------------------------------------------------- icons
# Line icons (24x24, stroke = currentColor) keyed by section slug. A section
# the sheet adds later without an entry here gets DEFAULT_ICON.

ICONS = {
    "coffee": '<path d="M5 10h11v4a5 5 0 0 1-5 5h-1a5 5 0 0 1-5-5z"/><path d="M16 11h1.5a2.5 2.5 0 0 1 0 5H16"/><path d="M3.5 21.5h15"/><path d="M8.5 3c1 1-1 2 0 3.5M12.5 3c1 1-1 2 0 3.5"/>',
    "hot-drinks": '<path d="M5 9h12v5a5 5 0 0 1-5 5h-2a5 5 0 0 1-5-5z"/><path d="M17 10h1a2.5 2.5 0 0 1 0 5h-1"/><path d="M11 9V4.5l3-1.5"/><rect x="13" y="3" width="3.2" height="3.4" rx=".6"/>',
    "mojito": '<path d="M6 4h12l-1.8 16H7.8z"/><path d="M6.6 9h10.8"/><path d="M14 14.5c0-2.2 1.8-3.6 3.6-3.6 0 2.2-1.7 3.6-3.6 3.6z"/><path d="M10 2.5l2 6.5"/>',
    "frappe": '<path d="M6.5 10h11l-1.5 10.5H8z"/><path d="M5 10h14"/><path d="M7.2 10a4.8 4.8 0 0 1 9.6 0"/><path d="M12 5.2 14.6 1.8"/>',
    "juices": '<path d="M6.5 8h11l-1.4 12.5H7.9z"/><path d="M13 8l2.4-5.5H18"/><path d="M7 12.5h10"/>',
    "mixed-juices": '<path d="M2.5 9h7.5l-1 11.5H3.5z"/><path d="M14 9h7.5l-1 11.5h-5.5z"/><path d="M7.5 9l1.2-5.5M19 9l1.2-5.5"/>',
    "smoothies": '<path d="M7 8h10l-1.2 12.5H8.2z"/><path d="M6.5 8c0-2.3 2.4-3.6 5.5-3.6s5.5 1.3 5.5 3.6"/><path d="M13 4.4 14.2 1.5"/>',
    "mixed-smoothies": '<path d="M7 8h10l-1.2 12.5H8.2z"/><path d="M6.5 8c0-2.3 2.4-3.6 5.5-3.6s5.5 1.3 5.5 3.6"/><path d="M7.9 12.5c2.3 1.4 5.9-1.4 8.2 0M8.3 16.5c2.1 1.4 5.3-1.4 7.4 0"/>',
    "milk-shake": '<path d="M7 11h10l-1.4 9.5H8.4z"/><path d="M6 11c0-2.6 2.6-4.2 6-4.2s6 1.6 6 4.2z"/><circle cx="12" cy="4.2" r="1.7"/>',
    "yogurt": '<path d="M3 11h18a9 9 0 0 1-18 0z"/><path d="M8 11c0-2.5 1.8-4.2 4-4.2s4 1.7 4 4.2"/><path d="M8 21.5h8"/>',
    "desserts": '<path d="M3 19.5h18v-7L4.5 7z"/><path d="M3 14.5h18"/><circle cx="7.5" cy="4.6" r="1.6"/>',
    "bakery": '<path d="M2.5 15c2-6 6-9 9.5-9s7.5 3 9.5 9c-2 1.2-4 1-5-1-1 2-3 3-4.5 3s-3.5-1-4.5-3c-1 2-3 2.2-5 1z"/><path d="M10 7l1 6.5M14 7l-1 6.5"/>',
    "extra": '<circle cx="12" cy="12" r="9"/><path d="M12 8v8M8 12h8"/>',
}
DEFAULT_ICON = ICONS["extra"]


def icon(slug):
    return ('<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" '
            'stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round" '
            'aria-hidden="true">%s</svg>' % ICONS.get(slug, DEFAULT_ICON))


def slugify(text, fallback):
    """Stable, readable section ids: "Mixed Juices" -> "mixed-juices"."""
    slug = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
    return slug or fallback

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

    # Google serves the published CSV with a 5-minute cache. A unique query
    # string skips that cache, so a rebuild right after an edit sees the edit.
    fresh = "%s%scb=%d" % (url, "&" if "?" in url else "?", time.time())
    with urllib.request.urlopen(fresh, timeout=25) as r:
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


def section_ids(sections):
    """One id per section, unique even if two English names slug the same."""
    ids, seen = [], set()
    for i, (_, name_en, _) in enumerate(sections):
        sid = slugify(name_en, "s%d" % i)
        if sid in seen:
            sid = "%s-%d" % (sid, i)
        seen.add(sid)
        ids.append(sid)
    return ids


def render(sections):
    """Return the chip navigation and the section markup."""
    chips, blocks = [], []

    for sid, (name_ar, name_en, items) in zip(section_ids(sections), sections):
        chips.append('<a href="#%s">%s</a>' % (sid, html.escape(name_ar)))

        # A section shows two price columns as soon as one item has a double.
        two = any(it["double"] for it in items)

        head = ('<div class="head"><span class="ic">%s</span><h2>%s</h2>'
                % (icon(sid), html.escape(name_ar)))
        if name_en:
            head += '<span class="sub">%s</span>' % html.escape(name_en)
        head += '<em class="count">%d %s</em></div>' % (len(items), LABEL_ITEMS)

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


def render_categories(sections):
    """Homepage tiles, one per menu section, each deep-linking into /menu."""
    tiles = []
    for sid, (name_ar, name_en, items) in zip(section_ids(sections), sections):
        tiles.append(
            '<a class="cat" href="/menu#%s"><span class="cat-ic">%s</span>'
            '<span class="cat-t"><b>%s</b><i>%s</i></span>'
            '<em>%d</em></a>'
            % (sid, icon(sid), html.escape(name_ar), html.escape(name_en),
               len(items)))
    return "\n".join(tiles)


def fill(template, output, values):
    with open(template, encoding="utf-8") as f:
        page = f.read()
    for key, value in values.items():
        page = page.replace(key, value)

    os.makedirs(os.path.dirname(output), exist_ok=True)
    with open(output, "w", encoding="utf-8") as f:
        f.write(page)
    return page

# ---------------------------------------------------------------- entry


def main():
    sections = group(load_rows())
    total = sum(len(items) for _, _, items in sections)

    if total < MIN_ITEMS:
        sys.exit("Only %d items found, expected at least %d. "
                 "Build stopped so the live menu stays as it is."
                 % (total, MIN_ITEMS))

    chips, blocks = render(sections)

    # Copy on the homepage is static; only counts and categories come from
    # the sheet — see CLAUDE.md.
    shared = {
        "{{ITEM_COUNT}}": str(total),
        "{{SECTION_COUNT}}": str(len(sections)),
        "{{WIFI}}": html.escape(WIFI),
        "{{PHONE}}": html.escape(PHONE),
        "{{PHONE_RAW}}": html.escape(PHONE_RAW),
        "{{TAYEL_URL}}": html.escape(TAYEL_URL),
    }

    home = fill(HOME_TEMPLATE, HOME_OUTPUT,
                dict(shared, **{"{{CATEGORIES}}": render_categories(sections)}))
    print("%s — %.1f KB" % (HOME_OUTPUT, len(home.encode()) / 1024))

    page = fill(TEMPLATE, OUTPUT, dict(shared, **{
        "{{CHIPS}}": chips,
        "{{SECTIONS}}": blocks,
        "{{JSONLD}}": render_jsonld(sections),
        "{{UPDATED}}": format_date(date.today()),
    }))

    print("%s — %d sections, %d items, %.1f KB"
          % (OUTPUT, len(sections), total, len(page.encode()) / 1024))


if __name__ == "__main__":
    main()
