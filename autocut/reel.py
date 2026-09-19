"""Reel renderer: an editor-style timeline (segments, captions, overlays) rendered with ffmpeg + libass.

This is the "replicate this creator's style" layer on top of the generic pipeline:

* Segments: a source file, in/out points, playback speed (slow-mo with motion
  interpolation), 9:16 crop, optional push-in zoom, black & white grade and a
  `delogo` box to wipe burned-in text from the source.
* Captions: phrase chunks timed from word timestamps, heavy caps, black outline,
  per-word highlight colours, pop-in animation.
* Hook: first sentence in the upper third with an optional red arrow + white circle.
* Overlays: PNG cards (rounded-corner app pop-up, CTA product card) that fade in/out.
* CTA: "COMMENT <KEYWORD>" held to the last frame.
"""
from __future__ import annotations

import re
import subprocess
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import ffmpeg
from .captions import ass_color, ass_time

Logger = Callable[[str], None]

W, H, FPS = 1080, 1920, 30

# ---------------------------------------------------------------------------
# data model
# ---------------------------------------------------------------------------


@dataclass
class Segment:
    src: str
    start: float  # source in-point (s)
    end: float  # source out-point (s)
    speed: float = 1.0  # 0.5 = half speed
    duration: float | None = None  # timeline length; derived from (end-start)/speed when None
    crop: str = "center"  # center | left | right | top, or "x=<0..1>" horizontal centre of the 9:16 window
    zoom: float = 0.0  # push-in amount over the segment, e.g. 0.08 = 8%
    bw: bool = False
    delogo: tuple[int, int, int, int] | None = None  # x, y, w, h in SOURCE pixels
    interpolate: bool = True  # motion-interpolate slow-mo to FPS

    @property
    def timeline_duration(self) -> float:
        if self.duration is not None:
            return self.duration
        return (self.end - self.start) / self.speed


@dataclass
class Chunk:
    """A caption phrase. Markup: *green* #yellow# !red! ; words are matched to the transcript in order."""
    text: str
    start: float | None = None
    end: float | None = None


@dataclass
class Overlay:
    png: str
    start: float
    end: float
    x: str = "(W-w)/2"  # ffmpeg overlay expressions
    y: str = "H*0.18"
    fade: float = 0.35
    slide: int = 40  # px of upward slide during fade-in
    scale: float = 1.0  # resize the PNG before overlaying


@dataclass
class TextCard:
    """Static text block (hook / CTA)."""
    lines: list[str]  # markup allowed
    start: float
    end: float
    y_frac: float  # vertical centre as a fraction of H
    size: int = 84
    arrow: tuple[int, int] | None = None  # (x, y) tip of a red arrow pointing down-right at the subject
    arrow_scale: float = 0.6
    circle: tuple[int, int, int] | None = None  # (cx, cy, r) white circle
    circle_start: float | None = None
    fade_out: float = 0.25


@dataclass
class ReelSpec:
    audio: str
    out: str
    workdir: str
    segments: list[Segment]
    words: list[dict]  # [{"w": "This", "s": 0.0, "e": 0.18}, ...]
    chunks: list[Chunk]
    cards: list[TextCard] = field(default_factory=list)
    overlays: list[Overlay] = field(default_factory=list)
    video_offset: float = 0.5  # black lead-in so the voice-over starts before the picture
    caption_y_frac: float = 0.50
    caption_size: int = 84
    font: str = "Montserrat"
    fontsdir: str | None = None
    colors: dict = field(default_factory=lambda: {"white": "#FFFFFF", "green": "#3CFF3C", "yellow": "#FFE01B", "red": "#FF2B2B"})
    bw_ranges: list[tuple[float, float]] = field(default_factory=list)  # timeline ranges rendered black & white
    captions_until: float | None = None  # stop flowing captions here (e.g. when the CTA takes over)
    total: float | None = None


# ---------------------------------------------------------------------------
# segments
# ---------------------------------------------------------------------------


def _crop_expr(seg: Segment, sw: int, sh: int) -> str:
    """Crop a 9:16 window out of the source (full height), returning an ffmpeg crop=... string."""
    cw = int(sh * W / H)
    if cw > sw:  # source is narrower than 9:16 -> crop height instead
        ch = int(sw * H / W)
        return f"crop={sw}:{ch}:0:{(sh - ch) // 2}"
    if seg.crop == "left":
        cx = 0
    elif seg.crop == "right":
        cx = sw - cw
    elif seg.crop.startswith("x="):
        cx = int(float(seg.crop[2:]) * sw - cw / 2)
        cx = max(0, min(sw - cw, cx))
    else:
        cx = (sw - cw) // 2
    return f"crop={cw}:{sh}:{cx}:0"


def render_segment(seg: Segment, out: Path, log: Logger = print) -> Path:
    info = ffmpeg.probe(seg.src)
    src_len = seg.end - seg.start
    tl = seg.timeline_duration
    speed = src_len / tl  # effective speed after honouring an explicit duration
    filters: list[str] = []
    if seg.delogo:
        x, y, w, h = seg.delogo
        filters.append(f"delogo=x={x}:y={y}:w={w}:h={h}:show=0")
    filters.append(_crop_expr(seg, info.width, info.height))
    if abs(speed - 1.0) > 1e-3:
        filters.append(f"setpts={1 / speed:.5f}*PTS")
        if speed < 1.0 and seg.interpolate:
            filters.append(f"minterpolate=fps={FPS}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1")
    filters.append(f"fps={FPS}")
    filters.append(f"scale={W}:{H}:flags=lanczos")
    if seg.zoom:
        n = max(1, int(round(tl * FPS)))
        filters.append(
            f"zoompan=z='1+{seg.zoom:.4f}*on/{n}':d=1:s={W}x{H}:fps={FPS}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
        )
    if seg.bw:
        filters.append("hue=s=0")
    filters.append("setsar=1,format=yuv420p")
    args = [
        "-y", "-ss", f"{seg.start:.3f}", "-t", f"{src_len:.3f}", "-i", seg.src,
        "-an", "-vf", ",".join(filters), "-t", f"{tl:.3f}",
        "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-r", str(FPS), str(out),
    ]
    log(f"segment {out.name}: {Path(seg.src).name} {seg.start:.1f}-{seg.end:.1f}s x{speed:.2f} -> {tl:.2f}s")
    ffmpeg.run(args)
    got = ffmpeg.probe(out).duration
    if got < tl - 0.1:  # pad with the last frame if interpolation came up short
        tmp = out.with_name(out.stem + "_pad.mp4")
        ffmpeg.run(["-y", "-i", str(out), "-vf", f"tpad=stop_mode=clone:stop_duration={tl - got + 0.1:.3f}", "-t", f"{tl:.3f}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "16", str(tmp)])
        tmp.replace(out)
    return out


# ---------------------------------------------------------------------------
# captions (ASS)
# ---------------------------------------------------------------------------

_MARK = re.compile(r"(\*[^*]+\*|#[^#]+#|![^!]+!)")
_WORD_CLEAN = re.compile(r"[^a-z0-9']")


def _norm(w: str) -> str:
    return _WORD_CLEAN.sub("", w.lower().replace("’", "'"))


def _parse_markup(text: str, colors: dict) -> list[tuple[str, str]]:
    """'*hello* world' -> [('hello', '#3CFF3C'), ('world', '#FFFFFF')] one entry per word."""
    out: list[tuple[str, str]] = []
    for part in _MARK.split(text):
        if not part:
            continue
        color = colors["white"]
        if part[0] == "*" and part[-1] == "*":
            color, part = colors["green"], part[1:-1]
        elif part[0] == "#" and part[-1] == "#":
            color, part = colors["yellow"], part[1:-1]
        elif part[0] == "!" and part[-1] == "!":
            color, part = colors["red"], part[1:-1]
        for w in part.split():
            out.append((w, color))
    return out


NUMBER_WORDS = {"10": "ten", "20": "twenty", "30": "thirty", "3": "three", "4": "four", "1": "one", "2": "two"}


def time_chunks(chunks: list[Chunk], words: list[dict], colors: dict) -> list[Chunk]:
    """Assign start/end to each chunk by matching its words, in order, against the transcript words."""
    wi = 0
    timed: list[Chunk] = []
    for c in chunks:
        if c.start is not None and c.end is not None:
            timed.append(c)
            continue
        toks = [_norm(w) for w, _ in _parse_markup(c.text, colors)]
        first = last = None
        for k, tok in enumerate(toks):
            # find tok from wi forward; the first word of a chunk may skip further (e.g. past the hook sentence)
            j = wi
            found = None
            window = 16 if k == 0 else 6
            while j < len(words) and j < wi + window:
                tw = _norm(words[j]["w"])
                if tw == tok or NUMBER_WORDS.get(tw) == tok or NUMBER_WORDS.get(tok) == tw or (len(tok) > 3 and (tw.startswith(tok) or tok.startswith(tw))):
                    found = j
                    break
                j += 1
            if found is None:
                continue
            if first is None:
                first = found
            last = found
            wi = found + 1
        if first is None:
            raise ValueError(f"could not time chunk {c.text!r} against transcript near word {wi}")
        c.start, c.end = float(words[first]["s"]), float(words[last]["e"])
        timed.append(c)
    # hold each chunk until the next one starts (short cap), so words don't flicker
    for i, c in enumerate(timed):
        nxt = timed[i + 1].start if i + 1 < len(timed) else c.end + 0.5
        c.end = max(c.end, min(nxt, c.end + 0.6)) - 0.02
    return timed


def _style_line(name: str, font: str, size: int, colors: dict, outline: int, shadow: int, align: int, margin_v: int) -> str:
    return ",".join([
        f"Style: {name}", font, str(size), ass_color(colors["white"]), ass_color(colors["yellow"]), ass_color("#000000"),
        ass_color("#000000", 90), "-1", "0", "0", "0", "100", "100", "0", "0", "1", str(outline), str(shadow), str(align),
        "40", "40", str(margin_v), "1",
    ])


def _render_text(words: list[tuple[str, str]], colors: dict, per_line: int | None = None, max_chars: int = 18) -> str:
    """Words with colours -> ASS text with \\c overrides and \\N line breaks."""
    lines: list[list[tuple[str, str]]] = [[]]
    for w, col in words:
        cur = lines[-1]
        length = sum(len(x) for x, _ in cur) + len(cur) + len(w)
        if cur and ((per_line and len(cur) >= per_line) or length > max_chars):
            lines.append([])
        lines[-1].append((w, col))
    out_lines = []
    for line in lines:
        parts = []
        for w, col in line:
            parts.append(f"{{\\c{ass_color(col)}}}{w.upper()}")
        out_lines.append(" ".join(parts))
    return "\\N".join(out_lines)


def _arrow_shape(tip_x: int, tip_y: int) -> str:
    """Red arrow (ASS vector) pointing down-right, ending at (tip_x, tip_y). Coordinates absolute."""
    # arrow drawn relative to the tip, then positioned with \pos
    # shaft from (-260,-330) to (-60,-80), head triangle around the tip
    shape = (
        "m -300 -360 l -240 -400 l -60 -150 l -20 -190 l 0 0 l -170 -60 l -130 -100 z"
    )
    return f"{{\\an7\\pos({tip_x},{tip_y})\\bord10\\3c&H000000&\\1c&H2B2BFF&\\shad0\\p1}}{shape}{{\\p0}}"


def _circle_shape(cx: int, cy: int, r: int) -> str:
    k = 0.5523 * r
    shape = (
        f"m {cx - r} {cy} b {cx - r} {cy - k} {cx - k} {cy - r} {cx} {cy - r} "
        f"b {cx + k} {cy - r} {cx + r} {cy - k} {cx + r} {cy} "
        f"b {cx + r} {cy + k} {cx + k} {cy + r} {cx} {cy + r} "
        f"b {cx - k} {cy + r} {cx - r} {cy + k} {cx - r} {cy}"
    )
    return f"{{\\an7\\pos(0,0)\\bord9\\3c&HFFFFFF&\\1a&HFF&\\shad3\\4c&H000000&\\p1}}{shape}{{\\p0}}"


def build_ass(spec: ReelSpec, chunks: list[Chunk]) -> str:
    colors = spec.colors
    header = "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
        "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        _style_line("Cap", spec.font, spec.caption_size, colors, 7, 4, 5, 0),
        _style_line("Card", spec.font, 84, colors, 7, 4, 5, 0),
        _style_line("Draw", spec.font, 20, colors, 0, 0, 7, 0),
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])
    ev: list[str] = []
    pop = "\\fscx82\\fscy82\\t(0,110,\\fscx100\\fscy100)"
    cy = int(H * spec.caption_y_frac)

    for c in chunks:
        if spec.captions_until is not None and c.start >= spec.captions_until:
            break
        end = c.end if spec.captions_until is None else min(c.end, spec.captions_until)
        words = _parse_markup(c.text, colors)
        text = _render_text(words, colors)
        ev.append(f"Dialogue: 2,{ass_time(c.start)},{ass_time(end)},Cap,,0,0,0,,{{\\an5\\pos({W // 2},{cy}){pop}}}{text}")

    for card in spec.cards:
        y = int(H * card.y_frac)
        words = [w for line in card.lines for w in _parse_markup(line, colors)]
        # keep the author's line breaks: render each line separately
        rendered = "\\N".join(_render_text(_parse_markup(line, colors), colors, max_chars=99) for line in card.lines)
        fade = f"\\fad(0,{int(card.fade_out * 1000)})" if card.fade_out else ""
        ev.append(
            f"Dialogue: 3,{ass_time(card.start)},{ass_time(card.end)},Card,,0,0,0,,{{\\an5\\pos({W // 2},{y})\\fs{card.size}{pop}{fade}}}{rendered}"
        )
        if card.arrow:
            ax, ay = card.arrow
            s0, s1 = int(card.arrow_scale * 75), int(card.arrow_scale * 100)
            bob = f"\\fscx{s0}\\fscy{s0}\\t(0,350,\\fscx{s1}\\fscy{s1})"
            ev.append(f"Dialogue: 4,{ass_time(card.start)},{ass_time(card.end)},Draw,,0,0,0,,{{{bob}{fade}}}{_arrow_shape(ax, ay)}")
        if card.circle:
            cx_, cy_, r = card.circle
            cs = card.circle_start if card.circle_start is not None else card.start
            ev.append(f"Dialogue: 4,{ass_time(cs)},{ass_time(card.end)},Draw,,0,0,0,,{{\\fad(150,0){fade}}}{_circle_shape(cx_, cy_, r)}")
    return header + "\n" + "\n".join(ev) + "\n"


# ---------------------------------------------------------------------------
# compose
# ---------------------------------------------------------------------------


def render(spec: ReelSpec, log: Logger = print) -> Path:
    work = Path(spec.workdir)
    work.mkdir(parents=True, exist_ok=True)
    total = spec.total or ffmpeg.probe(spec.audio).duration

    # 1) segments
    seg_files: list[Path] = []
    for i, seg in enumerate(spec.segments):
        out = work / f"seg{i:02d}.mp4"
        if not out.exists():
            render_segment(seg, out, log)
        seg_files.append(out)
    seg_total = sum(s.timeline_duration for s in spec.segments)
    log(f"segments total {seg_total:.2f}s + lead-in {spec.video_offset:.2f}s (audio {total:.2f}s)")

    # 2) captions
    chunks = time_chunks(spec.chunks, spec.words, spec.colors)
    ass_path = work / "captions.ass"
    ass_path.write_text(build_ass(spec, chunks), encoding="utf-8")

    # 3) compose
    args: list[str] = ["-y"]
    for f in seg_files:
        args += ["-i", str(f)]
    n = len(seg_files)
    args += ["-i", spec.audio]
    aidx = n
    ov_idx: list[int] = []
    for ov in spec.overlays:
        args += ["-loop", "1", "-framerate", str(FPS), "-t", f"{ov.end - ov.start + 0.5:.3f}", "-i", ov.png]
        ov_idx.append(n + 1 + len(ov_idx))

    f: list[str] = []
    f.append(f"color=c=black:s={W}x{H}:r={FPS}:d={spec.video_offset:.3f},format=yuv420p[lead]")
    labels = "[lead]" + "".join(f"[{i}:v]" for i in range(n))
    f.append(f"{labels}concat=n={n + 1}:v=1:a=0,fps={FPS},format=yuv420p[v0]")
    cur = "v0"
    for a, b in spec.bw_ranges:
        f.append(f"[{cur}]hue=s=0:enable='between(t,{a:.3f},{b:.3f})'[vbw]")
        cur = "vbw"
    for k, (ov, idx) in enumerate(zip(spec.overlays, ov_idx)):
        d = ov.end - ov.start
        sc = f"scale=iw*{ov.scale:.3f}:-2," if abs(ov.scale - 1.0) > 1e-3 else ""
        f.append(
            f"[{idx}:v]{sc}format=rgba,fade=t=in:st=0:d={ov.fade:.3f}:alpha=1,fade=t=out:st={d - ov.fade:.3f}:d={ov.fade:.3f}:alpha=1,"
            f"setpts=PTS-STARTPTS+{ov.start:.3f}/TB[ov{k}]"
        )
        yexpr = f"({ov.y})+{ov.slide}*max(0,1-(t-{ov.start:.3f})/{ov.fade:.3f})"
        f.append(f"[{cur}][ov{k}]overlay=x='{ov.x}':y='{yexpr}':enable='between(t,{ov.start:.3f},{ov.end:.3f})':eof_action=pass[vo{k}]")
        cur = f"vo{k}"
    fontsdir = f":fontsdir='{ffmpeg.escape_filter_path(spec.fontsdir)}'" if spec.fontsdir else ""
    f.append(f"[{cur}]ass='{ffmpeg.escape_filter_path(str(ass_path))}'{fontsdir}[vout]")
    f.append(f"[{aidx}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[aout]")
    script = work / "compose.filter"
    script.write_text(";\n".join(f))
    args += [
        "-filter_complex_script", str(script), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
        "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
        "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", spec.out,
    ]
    log("composing ...")
    ffmpeg.run(args)
    return Path(spec.out)
