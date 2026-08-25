#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Build the synthetic multimodal images used by Lab 5.

Outputs
-------
* 10 product images  -> data/multimodal/products/{stem}.png
* 5  user uploads    -> data/multimodal/user_uploads/*.png

Each image is 800 x 800 RGB PNG drawn with PIL only (no external font files).
Idempotent: rerun any time, files are overwritten.
"""

from __future__ import annotations

import os
import random
from typing import Iterable

from PIL import Image, ImageDraw, ImageFilter, ImageFont


# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

DATA_DIR = os.path.dirname(os.path.abspath(__file__))
PRODUCTS_DIR = os.path.join(DATA_DIR, "multimodal", "products")
UPLOADS_DIR  = os.path.join(DATA_DIR, "multimodal", "user_uploads")

CANVAS = 800   # square canvas in px


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _font(size: int) -> ImageFont.ImageFont:
    """Pick a default font, scaled with the load_default size= argument when
    available (PIL >= 10). Falls back to bitmap font otherwise."""
    try:
        return ImageFont.load_default(size=size)
    except TypeError:  # older Pillow
        return ImageFont.load_default()


def _text_size(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont) -> tuple[int, int]:
    bbox = draw.textbbox((0, 0), text, font=font)
    return bbox[2] - bbox[0], bbox[3] - bbox[1]


def _draw_centered_text(
    draw: ImageDraw.ImageDraw,
    text: str,
    y: int,
    font: ImageFont.ImageFont,
    fill: tuple[int, int, int],
) -> None:
    w, _ = _text_size(draw, text, font)
    draw.text(((CANVAS - w) // 2, y), text, fill=fill, font=font)


def _contrast_fg(bg: tuple[int, int, int]) -> tuple[int, int, int]:
    luma = 0.2126 * bg[0] + 0.7152 * bg[1] + 0.0722 * bg[2]
    return (30, 30, 30) if luma > 160 else (245, 245, 245)


def _save(img: Image.Image, path: str) -> None:
    os.makedirs(os.path.dirname(path), exist_ok=True)
    img.save(path, format="PNG", optimize=True)


# ---------------------------------------------------------------------------
# Silhouettes
# ---------------------------------------------------------------------------

def _phone_silhouette(draw: ImageDraw.ImageDraw, color: tuple[int, int, int]) -> None:
    # rounded rectangle, portrait
    x0, y0, x1, y1 = 290, 160, 510, 600
    draw.rounded_rectangle((x0, y0, x1, y1), radius=42, fill=color, outline=(80, 80, 80), width=4)
    # screen
    draw.rounded_rectangle((x0 + 18, y0 + 30, x1 - 18, y1 - 50), radius=24, fill=(20, 20, 20))
    # speaker
    draw.rounded_rectangle((385, 175, 415, 188), radius=6, fill=(60, 60, 60))


def _laptop_silhouette(draw: ImageDraw.ImageDraw, color: tuple[int, int, int]) -> None:
    # trapezoid base + screen
    # screen
    draw.rounded_rectangle((180, 200, 620, 480), radius=18, fill=color, outline=(60, 60, 60), width=4)
    draw.rounded_rectangle((200, 220, 600, 460), radius=10, fill=(20, 20, 20))
    # base trapezoid
    draw.polygon([(140, 480), (660, 480), (700, 540), (100, 540)], fill=color, outline=(60, 60, 60))


def _tablet_silhouette(draw: ImageDraw.ImageDraw, color: tuple[int, int, int]) -> None:
    draw.rounded_rectangle((220, 170, 580, 600), radius=30, fill=color, outline=(60, 60, 60), width=4)
    draw.rounded_rectangle((240, 200, 560, 580), radius=18, fill=(25, 25, 25))


def _earbuds_silhouette(draw: ImageDraw.ImageDraw, color: tuple[int, int, int]) -> None:
    # two spheres
    draw.ellipse((250, 320, 380, 450), fill=color, outline=(60, 60, 60), width=4)
    draw.ellipse((420, 320, 550, 450), fill=color, outline=(60, 60, 60), width=4)
    # stems
    draw.rounded_rectangle((300, 430, 330, 540), radius=14, fill=color, outline=(60, 60, 60))
    draw.rounded_rectangle((470, 430, 500, 540), radius=14, fill=color, outline=(60, 60, 60))


def _headphones_silhouette(draw: ImageDraw.ImageDraw, color: tuple[int, int, int]) -> None:
    # headband (arc) + two ear cups
    draw.arc((230, 180, 570, 480), start=180, end=360, fill=color, width=22)
    draw.ellipse((220, 360, 340, 510), fill=color, outline=(60, 60, 60), width=4)
    draw.ellipse((460, 360, 580, 510), fill=color, outline=(60, 60, 60), width=4)


def _drone_silhouette(draw: ImageDraw.ImageDraw, color: tuple[int, int, int]) -> None:
    # cross / X plus center body
    draw.rectangle((200, 380, 600, 420), fill=color, outline=(60, 60, 60))
    draw.rectangle((380, 200, 420, 600), fill=color, outline=(60, 60, 60))
    draw.ellipse((350, 360, 450, 460), fill=color, outline=(60, 60, 60), width=3)
    # propellers
    for cx, cy in [(200, 400), (600, 400), (400, 200), (400, 600)]:
        draw.ellipse((cx - 50, cy - 18, cx + 50, cy + 18), fill=color, outline=(40, 40, 40))


def _powerbank_silhouette(draw: ImageDraw.ImageDraw, color: tuple[int, int, int]) -> None:
    draw.rounded_rectangle((230, 250, 570, 560), radius=44, fill=color, outline=(60, 60, 60), width=4)
    # LED indicators
    for i, x in enumerate(range(290, 530, 60)):
        draw.ellipse((x, 320, x + 20, 340), fill=(60, 220, 100) if i < 3 else (90, 90, 90))
    # USB ports
    draw.rectangle((300, 500, 360, 540), fill=(40, 40, 40))
    draw.rectangle((440, 500, 500, 540), fill=(40, 40, 40))


SILHOUETTE_FN = {
    "phone":      _phone_silhouette,
    "laptop":     _laptop_silhouette,
    "tablet":     _tablet_silhouette,
    "earbuds":    _earbuds_silhouette,
    "headphones": _headphones_silhouette,
    "drone":      _drone_silhouette,
    "powerbank":  _powerbank_silhouette,
}


# ---------------------------------------------------------------------------
# Product specs
# ---------------------------------------------------------------------------

# (stem, brand, brand_color, silhouette, body_color, label, sub_label)
PRODUCTS: list[tuple[str, str, tuple[int, int, int], str, tuple[int, int, int], str, str]] = [
    ("iphone_15",        "Apple",   (0xF5, 0xF5, 0xF7), "phone",      (40, 40, 60),       "iPhone 15",          "Apple"),
    ("galaxy_s24",       "Samsung", (0x14, 0x28, 0xA0), "phone",      (30, 30, 30),       "Galaxy S24",         "Samsung"),
    ("macbook_pro",      "Apple",   (0xF5, 0xF5, 0xF7), "laptop",     (180, 180, 190),    "MacBook Pro",        "Apple"),
    ("airpods_pro2",     "Apple",   (0xF5, 0xF5, 0xF7), "earbuds",    (255, 255, 255),    "AirPods Pro 2",      "Apple"),
    ("sony_wh1000xm5",   "Sony",    (0x00, 0x00, 0x00), "headphones", (40, 40, 40),       "WH-1000XM5",         "Sony"),
    ("thinkpad_x1",      "Lenovo",  (0x1A, 0x1A, 0x1A), "laptop",     (35, 35, 35),       "ThinkPad X1",        "Lenovo"),
    ("dji_mini4",        "DJI",     (0xE0, 0xE0, 0xE0), "drone",      (90, 90, 100),      "DJI Mini 4 Pro",     "DJI"),
    ("galaxy_tab_s9",    "Samsung", (0x14, 0x28, 0xA0), "tablet",     (35, 35, 35),       "Galaxy Tab S9",      "Samsung"),
    ("bose_qc_ultra",    "Bose",    (0x33, 0x33, 0x33), "headphones", (245, 245, 245),    "QC Ultra",           "Bose"),
    ("anker_powercore",  "Anker",   (0x00, 0x7C, 0xC8), "powerbank",  (30, 30, 30),       "PowerCore 20K",      "Anker"),
]


def _draw_product(stem: str, brand: str, bg: tuple[int, int, int],
                  shape: str, body: tuple[int, int, int],
                  label: str, sub_label: str) -> Image.Image:
    img = Image.new("RGB", (CANVAS, CANVAS), bg)
    draw = ImageDraw.Draw(img)

    # subtle background ring to add visual texture
    draw.ellipse((60, 60, CANVAS - 60, CANVAS - 60),
                 outline=_contrast_fg(bg), width=2)

    # silhouette
    SILHOUETTE_FN[shape](draw, body)

    # captions
    title_font = _font(56)
    sub_font   = _font(34)
    fg = _contrast_fg(bg)
    _draw_centered_text(draw, label, 660, title_font, fg)
    _draw_centered_text(draw, f"Brand: {sub_label}", 730, sub_font, fg)

    return img


def build_products() -> int:
    n = 0
    for stem, brand, bg, shape, body, label, sub in PRODUCTS:
        img = _draw_product(stem, brand, bg, shape, body, label, sub)
        path = os.path.join(PRODUCTS_DIR, f"{stem}.png")
        _save(img, path)
        n += 1
    return n


# ---------------------------------------------------------------------------
# User uploads
# ---------------------------------------------------------------------------

def _build_damaged_screen() -> Image.Image:
    img = Image.new("RGB", (CANVAS, CANVAS), (210, 210, 215))
    draw = ImageDraw.Draw(img)
    # phone body
    draw.rounded_rectangle((220, 100, 580, 720), radius=48,
                           fill=(30, 30, 30), outline=(80, 80, 80), width=4)
    # cracked screen base
    draw.rounded_rectangle((250, 140, 550, 680), radius=28, fill=(40, 60, 90))
    # crack pattern emanating from impact point
    rng = random.Random(7)
    cx, cy = 380, 360
    draw.ellipse((cx - 18, cy - 18, cx + 18, cy + 18), fill=(240, 240, 250))
    for _ in range(28):
        ex = rng.randint(260, 540)
        ey = rng.randint(160, 660)
        draw.line((cx, cy, ex, ey), fill=(240, 240, 250), width=rng.randint(1, 3))
        # secondary fork
        mx = (cx + ex) // 2 + rng.randint(-30, 30)
        my = (cy + ey) // 2 + rng.randint(-30, 30)
        draw.line((mx, my, ex + rng.randint(-40, 40), ey + rng.randint(-40, 40)),
                  fill=(220, 220, 230), width=1)

    title_font = _font(40)
    _draw_centered_text(draw, "Damaged Screen / 碎屏", 740, title_font, (40, 40, 40))
    return img


def _build_wrong_color() -> Image.Image:
    bg = (252, 226, 235)  # pale pink
    img = Image.new("RGB", (CANVAS, CANVAS), bg)
    draw = ImageDraw.Draw(img)
    # pink earbuds
    pink = (236, 102, 158)
    _earbuds_silhouette(draw, pink)
    # tag with order info
    draw.rounded_rectangle((120, 600, 680, 720), radius=20,
                           fill=(255, 255, 255), outline=(120, 120, 120), width=3)
    label_font = _font(30)
    note_font  = _font(26)
    draw.text((150, 615), "订单颜色: 黑色 (Black)", fill=(20, 20, 20), font=label_font)
    draw.text((150, 655), "实物颜色: 粉色 (Pink) — 颜色错发", fill=(170, 30, 60), font=label_font)
    draw.text((150, 690), "Issue: wrong color shipped", fill=(80, 80, 80), font=note_font)
    return img


def _build_order_screenshot() -> Image.Image:
    """Render in a small canvas with the non-AA bitmap default font, then
    upscale via NEAREST to 800x800. Block-uniform pixels compress to a
    much smaller PNG than anti-aliased TrueType text."""
    W = 400
    img = Image.new("RGB", (W, W), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    f = ImageFont.load_default()  # tiny non-AA bitmap font

    # browser bar
    draw.rectangle((0, 0, W, 30), fill=(235, 235, 240))
    draw.text((10, 10), "https://shop.example.com/orders/SO-20260118-0042",
              fill=(60, 60, 60), font=f)

    # title + meta
    draw.text((20,  50), "Order Detail / 订单详情",        fill=(20, 20, 20), font=f)
    draw.text((20,  70), "Order No. : SO-20260118-0042",   fill=(40, 40, 40), font=f)
    draw.text((20,  85), "Status    : 已发货 (Shipped)",    fill=(40, 40, 40), font=f)
    draw.text((20, 100), "Date      : 2026-01-18 14:32",   fill=(40, 40, 40), font=f)
    draw.text((20, 115), "Customer  : Q. Guang",           fill=(40, 40, 40), font=f)

    # table header
    table_top = 150
    cols_x   = [20, 200, 270, 340]
    headers  = ["Item", "Qty", "Unit", "Total"]
    draw.rectangle((10, table_top, W - 10, table_top + 20), fill=(60, 90, 160))
    for x, h in zip(cols_x, headers):
        draw.text((x, table_top + 5), h, fill=(255, 255, 255), font=f)

    rows = [
        ("iPhone 15 (黑色, 128GB)", "1", "5999", "5999"),
        ("AirPods Pro 2",           "1", "1899", "1899"),
        ("MagSafe 充电器",          "2",  "329",  "658"),
    ]
    for i, row in enumerate(rows):
        y = table_top + 20 + i * 26
        draw.line([(10, y + 26), (W - 10, y + 26)], fill=(210, 210, 210), width=1)
        for x, v in zip(cols_x, row):
            draw.text((x, y + 6), v, fill=(30, 30, 30), font=f)

    # totals
    total_y = table_top + 20 + len(rows) * 26 + 14
    draw.line([(10, total_y), (W - 10, total_y)], fill=(180, 180, 180), width=1)
    draw.text((250, total_y +  8), "Subtotal: ¥ 8556", fill=(40, 40, 40), font=f)
    draw.text((250, total_y + 24), "Shipping: ¥    0", fill=(40, 40, 40), font=f)
    draw.text((250, total_y + 40), "TOTAL   : ¥ 8556", fill=(170, 40, 40), font=f)

    draw.text((20, total_y + 60), "Shipping addr: 北京市海淀区...", fill=(80, 80, 80), font=f)
    draw.text((20, total_y + 76), "Tracking: SF1234567890CN",       fill=(80, 80, 80), font=f)

    # upscale 2x to 800x800 with NEAREST so flat blocks compress well
    return img.resize((CANVAS, CANVAS), resample=Image.NEAREST)


def _build_damaged_box() -> Image.Image:
    img = Image.new("RGB", (CANVAS, CANVAS), (240, 232, 220))
    draw = ImageDraw.Draw(img)

    # shadow
    draw.ellipse((140, 620, 660, 700), fill=(200, 188, 170))

    # box base (front face)
    box = (160, 220, 640, 620)
    draw.rectangle(box, fill=(165, 110, 60), outline=(110, 70, 40), width=4)
    # top flaps
    draw.polygon([(160, 220), (400, 140), (640, 220)], fill=(190, 130, 70), outline=(110, 70, 40))
    draw.line([(400, 140), (400, 220)], fill=(110, 70, 40), width=4)
    # tape
    draw.rectangle((360, 140, 440, 620), fill=(220, 200, 160), outline=(160, 140, 100))

    # dent / crumple in front
    dent = [(260, 360), (320, 320), (380, 380), (440, 330), (520, 410), (470, 470), (340, 460)]
    draw.polygon(dent, fill=(120, 80, 40), outline=(80, 50, 20))

    # tear / crack on side
    rng = random.Random(11)
    crack = [(610, 280)]
    for _ in range(8):
        last_x, last_y = crack[-1]
        crack.append((last_x - rng.randint(5, 25), last_y + rng.randint(20, 40)))
    draw.line(crack, fill=(40, 25, 10), width=5)
    draw.line([(c[0] + 6, c[1] + 4) for c in crack], fill=(40, 25, 10), width=2)

    # FRAGILE label
    draw.rectangle((200, 240, 360, 290), fill=(255, 255, 255), outline=(200, 50, 50), width=3)
    draw.text((218, 252), "FRAGILE", fill=(200, 50, 50), font=_font(28))

    title_font = _font(36)
    _draw_centered_text(draw, "Damaged Box / 包装破损", 700, title_font, (40, 30, 20))
    return img


def _build_broken_charger() -> Image.Image:
    img = Image.new("RGB", (CANVAS, CANVAS), (235, 235, 240))
    draw = ImageDraw.Draw(img)

    # charger head (rounded rectangle, vertical)
    head = (320, 180, 480, 470)
    draw.rounded_rectangle(head, radius=30, fill=(245, 245, 245),
                           outline=(120, 120, 120), width=4)
    # USB-C port at bottom of head
    draw.rounded_rectangle((360, 450, 440, 478), radius=8, fill=(50, 50, 50))
    # plug prongs at top
    draw.rectangle((360, 130, 380, 190), fill=(190, 190, 190), outline=(120, 120, 120))
    draw.rectangle((420, 130, 440, 190), fill=(190, 190, 190), outline=(120, 120, 120))

    # crack across the head
    rng = random.Random(3)
    crack = [(330, 230)]
    for _ in range(10):
        lx, ly = crack[-1]
        crack.append((lx + rng.randint(10, 25), ly + rng.randint(8, 30)))
    draw.line(crack, fill=(20, 20, 20), width=4)
    # secondary forks
    for px, py in crack[2:-1:2]:
        draw.line((px, py, px + rng.randint(-30, 30), py + rng.randint(15, 40)),
                  fill=(20, 20, 20), width=2)

    # burn mark
    draw.ellipse((360, 350, 440, 420), fill=(60, 30, 20))
    draw.ellipse((375, 365, 425, 405), fill=(120, 60, 30))

    # cable hanging out the bottom
    draw.line((400, 478, 380, 560), fill=(60, 60, 60), width=10)
    draw.line((380, 560, 320, 640), fill=(60, 60, 60), width=10)
    # frayed end
    for i in range(6):
        draw.line((320 + i * 4, 640, 300 + i * 6, 690 + i * 2),
                  fill=(60, 60, 60), width=2)

    title_font = _font(36)
    _draw_centered_text(draw, "Broken Charger / 充电头损坏", 720, title_font, (40, 40, 40))
    return img


UPLOAD_BUILDERS = {
    "damaged_screen":   _build_damaged_screen,
    "wrong_color":      _build_wrong_color,
    "order_screenshot": _build_order_screenshot,
    "damaged_box":      _build_damaged_box,
    "broken_charger":   _build_broken_charger,
}


def build_uploads() -> int:
    n = 0
    for stem, fn in UPLOAD_BUILDERS.items():
        img = fn()
        path = os.path.join(UPLOADS_DIR, f"{stem}.png")
        _save(img, path)
        n += 1
    return n


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def _sizes(paths: Iterable[str]) -> list[tuple[str, int]]:
    return [(p, os.path.getsize(p)) for p in paths]


def main() -> None:
    n_products = build_products()
    n_uploads  = build_uploads()
    print(f"[images] products generated: {n_products}")
    print(f"[images] user uploads generated: {n_uploads}")

    # report sizes for sanity (5 - 40 KB target window)
    for d, label in [(PRODUCTS_DIR, "products"), (UPLOADS_DIR, "user_uploads")]:
        files = sorted(os.path.join(d, f) for f in os.listdir(d) if f.endswith(".png"))
        for p in files:
            kb = os.path.getsize(p) / 1024
            print(f"  - {label:<13s} {os.path.basename(p):<24s} {kb:6.1f} KB")


if __name__ == "__main__":
    main()
