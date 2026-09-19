"""Rounded-corner pop-up cards (app mock-up, product card) rendered to PNG with Pillow."""
from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont


def _font(fonts_dir: str | Path, name: str, size: int) -> ImageFont.FreeTypeFont:
    p = Path(fonts_dir) / name
    if p.exists():
        return ImageFont.truetype(str(p), size)
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)


def app_card(
    out: str | Path,
    *,
    fonts_dir: str | Path,
    title: str = "INSTINCT FOOTY",
    subtitle: str = "30-DAY FASCIA BLOCK",
    rows: list[tuple[str, str, bool]] | None = None,
    width: int = 760,
    accent: str = "#3CFF3C",
    yellow: str = "#FFE01B",
) -> Path:
    """A phone-style app card with rounded corners, drop shadow and a checklist. Transparent PNG."""
    rows = rows or [
        ("WEEK 1", "Foot strength · barefoot juggling", True),
        ("WEEK 2", "Hip loading · single-leg bridges", True),
        ("WEEKS 3-4", "The strike · 20 weak-foot shots", False),
    ]
    pad = 40
    row_h = 120
    card_h = 300 + row_h * len(rows) + 90
    img = Image.new("RGBA", (width + pad * 2, card_h + pad * 2), (0, 0, 0, 0))

    # shadow
    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad + 6, pad + 18, pad + width + 6, pad + card_h + 18], radius=54, fill=(0, 0, 0, 170))
    sh = sh.filter(ImageFilter.GaussianBlur(18))
    img.alpha_composite(sh)

    card = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([pad, pad, pad + width, pad + card_h], radius=54, fill=(16, 18, 24, 245), outline=(255, 255, 255, 60), width=3)
    # header bar
    d.rounded_rectangle([pad, pad, pad + width, pad + 150], radius=54, fill=(24, 28, 38, 255))
    d.rectangle([pad, pad + 96, pad + width, pad + 150], fill=(24, 28, 38, 255))
    # app icon
    d.rounded_rectangle([pad + 34, pad + 34, pad + 116, pad + 116], radius=22, fill=accent)
    # simple football glyph: white disc with a black pentagon
    import math
    cx0, cy0 = pad + 75, pad + 75
    d.ellipse([cx0 - 28, cy0 - 28, cx0 + 28, cy0 + 28], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=3)
    pent = [(cx0 + 12 * math.cos(math.radians(-90 + 72 * i)), cy0 + 12 * math.sin(math.radians(-90 + 72 * i))) for i in range(5)]
    d.polygon(pent, fill=(0, 0, 0, 255))
    f_title = _font(fonts_dir, "Montserrat-Black.ttf", 44)
    f_sub = _font(fonts_dir, "Montserrat-Black.ttf", 30)
    d.text((pad + 140, pad + 52), title, font=f_title, fill=(255, 255, 255, 255), anchor="lm")
    d.text((pad + 140, pad + 104), subtitle, font=f_sub, fill=yellow, anchor="lm")

    # progress
    f_small = _font(fonts_dir, "Montserrat-Black.ttf", 26)
    y = pad + 190
    d.text((pad + 40, y), "DAY 1 OF 30", font=f_small, fill=(200, 200, 200, 255), anchor="lm")
    d.rounded_rectangle([pad + 40, y + 28, pad + width - 40, y + 46], radius=9, fill=(50, 54, 66, 255))
    d.rounded_rectangle([pad + 40, y + 28, pad + 40 + int((width - 80) * 0.33), y + 46], radius=9, fill=accent)

    # rows
    f_row = _font(fonts_dir, "Montserrat-Black.ttf", 30)
    f_row2 = _font(fonts_dir, "Montserrat-ExtraBoldItalic.ttf", 27)
    y = pad + 280
    for label, desc, done in rows:
        d.rounded_rectangle([pad + 34, y, pad + width - 34, y + row_h - 16], radius=26, fill=(32, 36, 48, 255))
        cx, cy = pad + 80, y + (row_h - 16) // 2
        if done:
            d.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], fill=accent)
            d.line([(cx - 12, cy), (cx - 3, cy + 10), (cx + 13, cy - 10)], fill=(0, 0, 0, 255), width=6)
        else:
            d.ellipse([cx - 24, cy - 24, cx + 24, cy + 24], outline=(255, 255, 255, 140), width=4)
        d.text((pad + 124, cy - 20), label, font=f_row, fill=(255, 255, 255, 255), anchor="lm")
        d.text((pad + 124, cy + 20), desc, font=f_row2, fill=(190, 195, 205, 255), anchor="lm")
        y += row_h
    # footer
    d.rounded_rectangle([pad + 34, y + 6, pad + width - 34, y + 70], radius=30, fill=accent)
    d.text(((pad * 2 + width) // 2, y + 38), "START TODAY · FREE", font=f_row, fill=(0, 0, 0, 255), anchor="mm")

    img.alpha_composite(card)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out
