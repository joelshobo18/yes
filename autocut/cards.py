"""PNG overlays rendered with Pillow: keyword titles with Apple emoji, rounded app pop-up, product card."""
from __future__ import annotations

import math
import re
from pathlib import Path

from PIL import Image, ImageDraw, ImageFilter, ImageFont

_MARK = re.compile(r"(\*[^*]+\*|#[^#]+#|![^!]+!)")


def _font(path: str | Path, size: int) -> ImageFont.FreeTypeFont:
    p = Path(path)
    if p.exists():
        return ImageFont.truetype(str(p), size)
    return ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", size)


def _hex(c: str) -> tuple[int, int, int, int]:
    h = c.lstrip("#")
    return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), 255


def shadow_of(c: str) -> tuple[int, int, int, int]:
    r, g, b, _ = _hex(c)
    if r > 200 and g > 200 and b > 200:
        return (0, 0, 0, 255)
    return (int(r * 0.22), int(g * 0.22), int(b * 0.22), 255)


def _words(text: str, colors: dict) -> list[tuple[str, str]]:
    out = []
    for part in _MARK.split(text):
        if not part:
            continue
        col = colors["white"]
        if part[0] == "*" and part[-1] == "*":
            col, part = colors["green"], part[1:-1]
        elif part[0] == "#" and part[-1] == "#":
            col, part = colors["yellow"], part[1:-1]
        elif part[0] == "!" and part[-1] == "!":
            col, part = colors["red"], part[1:-1]
        out.extend((w, col) for w in part.split())
    return out


def title_png(
    out: str | Path,
    lines: list[str],
    *,
    font_path: str | Path,
    colors: dict,
    size: int = 76,
    emoji_png: str | Path | None = None,
    emoji_size: int | None = None,
    outline: int = 5,
    shadow: int = 6,
    max_width: int = 1000,
) -> Path:
    """Big bold title: caps, black outline, colour-linked drop shadow, optional Apple emoji after the last line."""
    font = _font(font_path, size)
    emoji_size = emoji_size or int(size * 1.05)
    rows: list[list[tuple[str, str]]] = [_words(l, colors) for l in lines]
    line_h = int(size * 1.18)
    widths = []
    for row in rows:
        w = sum(font.getlength(t.upper()) for t, _ in row) + font.getlength(" ") * (len(row) - 1)
        widths.append(w)
    if emoji_png:
        widths[-1] += emoji_size + 12
    width = int(min(max_width + 2 * (outline + shadow), max(widths) + 2 * (outline + shadow) + 40))
    height = line_h * len(rows) + 2 * (outline + shadow) + 30
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    y = outline + shadow + 10
    for row, rw in zip(rows, widths):
        x = (width - rw) / 2
        for t, col in row:
            t = t.upper()
            # shadow, outline, fill
            d.text((x + shadow, y + shadow), t, font=font, fill=shadow_of(col), stroke_width=outline, stroke_fill=shadow_of(col))
            d.text((x, y), t, font=font, fill=_hex(col), stroke_width=outline, stroke_fill=(0, 0, 0, 255))
            x += font.getlength(t) + font.getlength(" ")
        if row is rows[-1] and emoji_png and Path(emoji_png).exists():
            em = Image.open(emoji_png).convert("RGBA").resize((emoji_size, emoji_size), Image.LANCZOS)
            img.alpha_composite(em, (int(x - font.getlength(" ") + 12), int(y + (line_h - emoji_size) / 2 - 4)))
        y += line_h
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out


def app_card(
    out: str | Path,
    *,
    fonts_dir: str | Path,
    title: str = "INSTINCT FOOTY",
    subtitle: str = "30-DAY FASCIA BLOCK",
    rows: list[tuple[str, str, bool]] | None = None,
    width: int = 640,
    accent: str = "#3CFF3C",
    yellow: str = "#FFE01B",
) -> Path:
    """App pop-up: rounded corners, soft shadow, the app logo sitting on TOP of the card, checklist inside."""
    rows = rows or [
        ("WEEK 1", "Foot strength · barefoot juggling", True),
        ("WEEK 2", "Hip loading · single-leg bridges", True),
        ("WEEKS 3-4", "The strike · 20 weak-foot shots", False),
    ]
    fonts_dir = Path(fonts_dir)
    f_bold = fonts_dir / "bold" / "THEBOLDFONT-FREEVERSION.ttf"
    f_mont = fonts_dir / "Montserrat-Black.ttf"
    f_mont_i = fonts_dir / "Montserrat-ExtraBoldItalic.ttf"
    pad, logo = 44, 150
    row_h = 112
    card_h = 260 + row_h * len(rows) + 96
    img = Image.new("RGBA", (width + pad * 2, card_h + pad * 2 + logo // 2), (0, 0, 0, 0))
    top = pad + logo // 2

    sh = Image.new("RGBA", img.size, (0, 0, 0, 0))
    ImageDraw.Draw(sh).rounded_rectangle([pad + 6, top + 20, pad + width + 6, top + card_h + 20], radius=56, fill=(0, 0, 0, 180))
    img.alpha_composite(sh.filter(ImageFilter.GaussianBlur(20)))

    card = Image.new("RGBA", img.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(card)
    d.rounded_rectangle([pad, top, pad + width, top + card_h], radius=56, fill=(14, 16, 22, 248), outline=(255, 255, 255, 70), width=3)
    cx = pad + width // 2
    # logo on top (overlapping the card edge)
    d.rounded_rectangle([cx - logo // 2, top - logo // 2, cx + logo // 2, top + logo // 2], radius=40, fill=accent, outline=(0, 0, 0, 255), width=5)
    bx, by = cx, top
    d.ellipse([bx - 44, by - 44, bx + 44, by + 44], fill=(255, 255, 255, 255), outline=(0, 0, 0, 255), width=4)
    pent = [(bx + 19 * math.cos(math.radians(-90 + 72 * i)), by + 19 * math.sin(math.radians(-90 + 72 * i))) for i in range(5)]
    d.polygon(pent, fill=(0, 0, 0, 255))
    d.text((cx, top + logo // 2 + 40), title, font=_font(f_bold, 46), fill=(255, 255, 255, 255), anchor="mm")
    d.text((cx, top + logo // 2 + 92), subtitle, font=_font(f_bold, 30), fill=_hex(yellow), anchor="mm")
    y = top + 205
    d.text((pad + 40, y), "DAY 1 OF 30", font=_font(f_mont, 24), fill=(200, 200, 200, 255), anchor="lm")
    d.rounded_rectangle([pad + 40, y + 24, pad + width - 40, y + 40], radius=8, fill=(50, 54, 66, 255))
    d.rounded_rectangle([pad + 40, y + 24, pad + 40 + int((width - 80) * 0.33), y + 40], radius=8, fill=accent)
    y = top + 262
    for label, desc, done in rows:
        d.rounded_rectangle([pad + 30, y, pad + width - 30, y + row_h - 14], radius=28, fill=(30, 34, 46, 255))
        ccx, ccy = pad + 76, y + (row_h - 14) // 2
        if done:
            d.ellipse([ccx - 22, ccy - 22, ccx + 22, ccy + 22], fill=accent)
            d.line([(ccx - 11, ccy), (ccx - 3, ccy + 9), (ccx + 12, ccy - 9)], fill=(0, 0, 0, 255), width=6)
        else:
            d.ellipse([ccx - 22, ccy - 22, ccx + 22, ccy + 22], outline=(255, 255, 255, 150), width=4)
        d.text((pad + 118, ccy - 18), label, font=_font(f_mont, 28), fill=(255, 255, 255, 255), anchor="lm")
        d.text((pad + 118, ccy + 20), desc, font=_font(f_mont_i, 25), fill=(190, 195, 205, 255), anchor="lm")
        y += row_h
    d.rounded_rectangle([pad + 30, y + 8, pad + width - 30, y + 74], radius=33, fill=accent)
    d.text((cx, y + 41), "START TODAY · FREE", font=_font(f_bold, 30), fill=(0, 0, 0, 255), anchor="mm")
    img.alpha_composite(card)
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    img.save(out)
    return out
