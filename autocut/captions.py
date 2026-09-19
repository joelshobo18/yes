"""Generate ASS subtitles (burned in with libass) from a word-timed transcript."""
from __future__ import annotations

from dataclasses import dataclass

from .formats import FormatSpec
from .models import TranscriptSegment, Word

_ALIGN = {"bottom": 2, "center": 5, "top": 8}


def ass_color(hex_color: str, alpha: int = 0) -> str:
    """'#RRGGBB' -> '&HAABBGGRR' as libass expects."""
    h = hex_color.lstrip("#")
    if len(h) != 6:
        raise ValueError(f"bad colour {hex_color!r}")
    r, g, b = h[0:2], h[2:4], h[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(t: float) -> str:
    t = max(0.0, t)
    cs = int(round(t * 100))
    return f"{cs // 360000}:{cs // 6000 % 60:02d}:{cs // 100 % 60:02d}.{cs % 100:02d}"


def _escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace("{", "\\{").replace("}", "\\}")


@dataclass
class Chunk:
    words: list[Word]
    start: float
    end: float


def chunk_words(words: list[Word], max_words: int, max_chars: int, max_gap: float = 0.8) -> list[Chunk]:
    """Group consecutive words into on-screen chunks bounded by count, length and pauses."""
    chunks: list[Chunk] = []
    buf: list[Word] = []
    for w in words:
        if buf:
            chars = sum(len(x.text) for x in buf) + len(buf) + len(w.text)
            gap = w.start - buf[-1].end
            ends_sentence = buf[-1].text.rstrip().endswith((".", "!", "?"))
            if len(buf) >= max_words or chars > max_chars or gap > max_gap or ends_sentence:
                chunks.append(Chunk(buf, buf[0].start, buf[-1].end))
                buf = []
        buf.append(w)
    if buf:
        chunks.append(Chunk(buf, buf[0].start, buf[-1].end))
    # hold each chunk on screen until the next one starts (up to a short limit) to avoid flicker
    for i, c in enumerate(chunks):
        nxt_start = chunks[i + 1].start if i + 1 < len(chunks) else c.end + 0.6
        c.end = max(c.end, min(nxt_start, c.end + 0.6))
    return chunks


def build_ass(transcript: list[TranscriptSegment], spec: FormatSpec, *, offset: float = 0.0) -> str:
    cap = spec.captions
    words = [w for s in transcript for w in s.words if w.text.strip()]
    mode = cap.get("mode", "word")
    upper = bool(cap.get("uppercase", False))
    if upper:
        words = [Word(w.text.upper(), w.start, w.end) for w in words]

    style = ",".join(
        [
            "Style: Default",
            str(cap.get("font", "DejaVu Sans")),
            str(int(cap.get("size", 64))),
            ass_color(cap.get("color", "#FFFFFF")),  # primary
            ass_color(cap.get("highlight_color", "#FFD400")),  # secondary
            ass_color(cap.get("outline_color", "#000000")),  # outline
            ass_color("#000000", 128),  # back (shadow)
            "-1" if cap.get("bold", True) else "0",
            "0",
            "0",
            "0",  # italic underline strikeout
            "100",
            "100",
            "0",
            "0",  # scale x/y, spacing, angle
            "1",  # border style: outline + shadow
            str(int(cap.get("outline", 3))),
            str(int(cap.get("shadow", 0))),
            str(_ALIGN.get(cap.get("position", "center"), 5)),
            "60",
            "60",
            str(int(cap.get("margin_v", 100))),
            "1",
        ]
    )
    header = "\n".join(
        [
            "[Script Info]",
            "ScriptType: v4.00+",
            f"PlayResX: {spec.width}",
            f"PlayResY: {spec.height}",
            "WrapStyle: 0",
            "ScaledBorderAndShadow: yes",
            "",
            "[V4+ Styles]",
            "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
            "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
            "MarginR, MarginV, Encoding",
            style,
            "",
            "[Events]",
            "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        ]
    )
    events: list[str] = []
    chunks = chunk_words(words, int(cap.get("max_words", 4)), int(cap.get("max_chars", 20)))
    hl = ass_color(cap.get("highlight_color", "#FFD400"))
    normal = ass_color(cap.get("color", "#FFFFFF"))

    def dialogue(start: float, end: float, text: str) -> str:
        return f"Dialogue: 0,{ass_time(start + offset)},{ass_time(end + offset)},Default,,0,0,0,,{text}"

    for c in chunks:
        if mode == "line" or len(c.words) == 1:
            events.append(dialogue(c.start, c.end, _escape(" ".join(w.text for w in c.words))))
            continue
        # word mode: one event per word interval, current word highlighted
        for i, w in enumerate(c.words):
            start = w.start if i > 0 else c.start
            end = c.words[i + 1].start if i + 1 < len(c.words) else c.end
            if end <= start:
                end = start + 0.05
            parts = []
            for j, x in enumerate(c.words):
                t = _escape(x.text)
                parts.append(f"{{\\c{hl}}}{t}{{\\c{normal}}}" if j == i else t)
            events.append(dialogue(start, end, " ".join(parts)))
    return header + "\n" + "\n".join(events) + "\n"
