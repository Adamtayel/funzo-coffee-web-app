#!/usr/bin/env python3
"""
Generates the table-sticker QR code for Funzo's menu.

Not part of the website build (build.py stays dependency-free on purpose —
see CLAUDE.md). This is a one-off local tool for producing print art, so it's
fine for it to need packages:

    pip install qrcode[pil]
    python3 make_qr.py

Writes two files to qr/:
  - funzo-menu-qr.png       plain, highest scan reliability
  - funzo-menu-qr-logo.png  with the Funzo mark in the center (needs the
                             high error-correction level to stay scannable
                             with part of the code covered)

Before printing: open funzo-menu-qr-logo.png and actually scan it with a
phone camera from a normal distance. A QR code that renders fine on screen
can still fail to scan once it's shrunk onto a table sticker.
"""

import qrcode
from qrcode.constants import ERROR_CORRECT_H
from PIL import Image, ImageDraw

# Each QR code: (url, output basename). The menu one is the table sticker;
# the homepage one is for anything that should land on the full site.
TARGETS = [
    ("https://menu.funzo.cc", "funzo-menu-qr"),
    ("https://funzo.cc", "funzo-home-qr"),
]
OUT_DIR = "qr"

# Funzo brand colours (see template.html / home.html :root)
YELLOW = "#E7B84C"
PINK = "#EA8FA4"
BLUE = "#78C6DC"
INK = "#0C0D0F"


def make_logo(size):
    """The three-circle donut mark, rendered as a standalone PNG."""
    scale = 4  # supersample, then downsize, for clean anti-aliased circles
    s = size * scale
    img = Image.new("RGBA", (s, s), (255, 255, 255, 255))
    d = ImageDraw.Draw(img)

    def circle(cx, cy, r, fill=None, outline=None, width=0):
        d.ellipse([cx - r, cy - r, cx + r, cy + r], fill=fill, outline=outline, width=width)

    u = s / 96  # same coordinate space as the logo's 96x64 viewBox
    circle(22 * u, 38 * u, 19 * u, fill=YELLOW)
    circle(74 * u, 38 * u + 13 * u, 19 * u, fill=BLUE)
    circle(48 * u, 43 * u, 23 * u, fill="#F3E9DA")
    circle(48 * u, 43 * u, 23 * u, outline=PINK, width=int(7 * u))
    circle(48 * u, 43 * u, 7.5 * u, fill=INK)

    return img.resize((size, size), Image.LANCZOS)


def make_qr(url, logo=None):
    qr = qrcode.QRCode(
        error_correction=ERROR_CORRECT_H,  # up to ~30% of the code can be
        box_size=20,                       # covered — needed since the logo
        border=4,                          # sits on top of the center
    )
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color=INK, back_color="white").convert("RGBA")

    if logo:
        logo_size = img.size[0] // 4
        mark = make_logo(logo_size)
        pad = logo_size // 6
        badge = Image.new("RGBA", (logo_size + pad, logo_size + pad), "white")
        badge.paste(mark, (pad // 2, pad // 2), mark)
        pos = ((img.size[0] - badge.size[0]) // 2, (img.size[1] - badge.size[1]) // 2)
        img.alpha_composite(badge, pos)

    return img


def main():
    import os
    os.makedirs(OUT_DIR, exist_ok=True)

    for url, name in TARGETS:
        plain = make_qr(url, logo=False)
        plain.save(f"{OUT_DIR}/{name}.png")
        print(f"{OUT_DIR}/{name}.png — {plain.size[0]}x{plain.size[1]}px, points to {url}")

        branded = make_qr(url, logo=True)
        branded.save(f"{OUT_DIR}/{name}-logo.png")
        print(f"{OUT_DIR}/{name}-logo.png — {branded.size[0]}x{branded.size[1]}px, with logo")

    print("\nScan each file with an actual phone before printing.")


if __name__ == "__main__":
    main()
