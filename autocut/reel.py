"""Reel renderer: an editor-style timeline (segments, captions, titles, trackers, overlays) rendered with ffmpeg + libass.

Built to replicate a specific creator format (see examples/instinctfooty/STYLE.md):

* Segments: source in/out, playback speed (motion-interpolated slow-mo), full-screen 9:16 crop, push-in zoom,
  black & white, `delogo` to wipe burned-in text; a still image gets a Ken Burns push-in.
* Captions (ASS): 2-line phrase chunks timed from word timestamps, on screen from the first word, fixed in the
  middle, heavy caps, black outline + colour-linked drop shadow, per-word highlight colours, pop-in.
* Trackers (ASS vector shapes): a red arrow that follows the head and a white circle that follows the ball,
  keyframed, glowing, popping in with a flash.
* Titles / pop-ups (PNG overlays): big bold keyword titles with Apple emoji at the top, rounded app card,
  product card; pop-in scale, fade out, flash on entry.
* Flashes: quick white flash on every big text entry and scene change.
"""
from __future__ import annotations

import re
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
    start: float = 0.0  # source in-point (s)
    end: float = 0.0  # source out-point (s)
    speed: float = 1.0
    duration: float | None = None  # timeline length; derived from (end-start)/speed when None
    crop: str = "center"  # center | left | right | x=<0..1> (horizontal centre of the 9:16 window)
    zoom: float = 0.0  # push-in over the segment (0.08 = 8%)
    bw: bool = False
    delogo: tuple[int, int, int, int] | None = None  # x, y, w, h in SOURCE pixels
    interpolate: bool = True
    image: bool = False  # still image with a Ken Burns push-in (duration required)
    label: str = ""

    @property
    def timeline_duration(self) -> float:
        if self.duration is not None:
            return self.duration
        return (self.end - self.start) / self.speed


@dataclass
class Chunk:
    """Caption phrase. Markup: *green* #yellow# !red!  ('|' forces a line break)."""
    text: str
    start: float | None = None
    end: float | None = None
    hide: bool = False  # timed (keeps the flow) but not drawn, e.g. when a keyword title shows the same words


@dataclass
class Overlay:
    png: str
    start: float
    end: float
    x: str = "(W-w)/2"
    y: str = "H*0.18"
    fade_in: float = 0.12
    fade_out: float = 0.30
    scale: float = 1.0
    pop: bool = True  # scale-in 86% -> 100% over the first 0.12s
    flash: bool = False


@dataclass
class Track:
    """Keyframed arrow (points at the head) or circle (around the ball) drawn in ASS."""
    kind: str  # arrow | circle
    keys: list[tuple[float, int, int]]  # (time, x, y) in canvas pixels; the arrow tip / circle centre
    radius: int = 95
    flash: bool = True


@dataclass
class TextCard:
    """ASS text block held at a fixed spot (used for the CTA)."""
    lines: list[str]
    start: float
    end: float
    y_frac: float
    size: int = 96


@dataclass
class ReelSpec:
    audio: str
    out: str
    workdir: str
    segments: list[Segment]
    words: list[dict]
    chunks: list[Chunk]
    cards: list[TextCard] = field(default_factory=list)
    overlays: list[Overlay] = field(default_factory=list)
    tracks: list[Track] = field(default_factory=list)
    flashes: list[float] = field(default_factory=list)
    flash_on_cuts: bool = True
    video_offset: float = 0.5
    caption_y_frac: float = 0.47
    caption_size: int = 68
    caption_max_chars: int = 16
    font: str = "THE BOLD FONT (FREE VERSION)"  # libass matches the family name inside the font file
    fontsdir: str | None = None
    colors: dict = field(default_factory=lambda: {"white": "#FFFFFF", "green": "#3CFF3C", "yellow": "#FFE01B", "red": "#FF2B2B"})
    bw_ranges: list[tuple[float, float]] = field(default_factory=list)
    captions_until: float | None = None
    total: float | None = None

    def cut_times(self) -> list[float]:
        t = self.video_offset
        out = []
        for s in self.segments[:-1]:
            t += s.timeline_duration
            out.append(round(t, 3))
        return out


# ---------------------------------------------------------------------------
# segments
# ---------------------------------------------------------------------------


def _crop_expr(seg: Segment, sw: int, sh: int) -> str:
    cw = int(sh * W / H)
    if cw > sw:
        ch = int(sw * H / W)
        return f"crop={sw}:{ch}:0:{(sh - ch) // 2}"
    if seg.crop == "left":
        cx = 0
    elif seg.crop == "right":
        cx = sw - cw
    elif seg.crop.startswith("x="):
        cx = max(0, min(sw - cw, int(float(seg.crop[2:]) * sw - cw / 2)))
    else:
        cx = (sw - cw) // 2
    return f"crop={cw}:{sh}:{cx}:0"


def render_segment(seg: Segment, out: Path, log: Logger = print) -> Path:
    tl = seg.timeline_duration
    n = max(1, int(round(tl * FPS)))
    if seg.image:
        z = seg.zoom or 0.10
        vf = (
            f"scale={W * 1.3:.0f}:{H * 1.3:.0f}:force_original_aspect_ratio=increase,crop={W * 1.3:.0f}:{H * 1.3:.0f},"
            f"zoompan=z='1+{z:.4f}*on/{n}':d=1:s={W}x{H}:fps={FPS}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)',setsar=1,format=yuv420p"
        )
        args = ["-y", "-loop", "1", "-framerate", str(FPS), "-t", f"{tl:.3f}", "-i", seg.src, "-vf", vf, "-t", f"{tl:.3f}",
                "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-r", str(FPS), str(out)]
        log(f"segment {out.name}: still {Path(seg.src).name} -> {tl:.2f}s")
        ffmpeg.run(args)
        return out

    info = ffmpeg.probe(seg.src)
    src_len = seg.end - seg.start
    speed = src_len / tl
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
        filters.append(f"zoompan=z='1+{seg.zoom:.4f}*on/{n}':d=1:s={W}x{H}:fps={FPS}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'")
    if seg.bw:
        filters.append("hue=s=0")
    filters.append("setsar=1,format=yuv420p")
    args = ["-y", "-ss", f"{seg.start:.3f}", "-t", f"{src_len:.3f}", "-i", seg.src, "-an", "-vf", ",".join(filters),
            "-t", f"{tl:.3f}", "-c:v", "libx264", "-preset", "fast", "-crf", "16", "-r", str(FPS), str(out)]
    log(f"segment {out.name}: {Path(seg.src).name} {seg.start:.1f}-{seg.end:.1f}s x{speed:.2f} -> {tl:.2f}s {seg.label}")
    ffmpeg.run(args)
    got = ffmpeg.probe(out).duration
    if got < tl - 0.1:
        tmp = out.with_name(out.stem + "_pad.mp4")
        ffmpeg.run(["-y", "-i", str(out), "-vf", f"tpad=stop_mode=clone:stop_duration={tl - got + 0.1:.3f}", "-t", f"{tl:.3f}",
                    "-c:v", "libx264", "-preset", "fast", "-crf", "16", str(tmp)])
        tmp.replace(out)
    return out


# ---------------------------------------------------------------------------
# captions
# ---------------------------------------------------------------------------

_MARK = re.compile(r"(\*[^*]+\*|#[^#]+#|![^!]+!)")
_WORD_CLEAN = re.compile(r"[^a-z0-9']")
NUMBER_WORDS = {"10": "ten", "20": "twenty", "30": "thirty", "3": "three", "4": "four", "1": "one", "2": "two"}


def _norm(w: str) -> str:
    return _WORD_CLEAN.sub("", w.lower().replace("’", "'"))


def parse_markup(text: str, colors: dict) -> list[tuple[str, str]]:
    """'*hello* world|next' -> [(word, colour)...]; '|' becomes a ('\\N', '') line-break token."""
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
        for w in part.replace("|", " | ").split():
            out.append(("\\N", "") if w == "|" else (w, color))
    return out


# backwards-compatible alias
_parse_markup = parse_markup


def time_chunks(chunks: list[Chunk], words: list[dict], colors: dict) -> list[Chunk]:
    """Assign start/end to each chunk by matching its words, in order, against the transcript words.

    Chunks hold until the next chunk starts, so the screen always shows text (word, word, word - no gaps)."""
    wi = 0
    timed: list[Chunk] = []
    for c in chunks:
        if c.start is not None and c.end is not None:
            timed.append(c)
            continue
        toks = [_norm(w) for w, _ in parse_markup(c.text, colors) if w != "\\N"]
        first = last = None
        for k, tok in enumerate(toks):
            j, found = wi, None
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
    for i, c in enumerate(timed):
        if i + 1 < len(timed):
            c.end = max(c.end, timed[i + 1].start) - 0.001
        else:
            c.end = c.end + 0.6
    return timed


def shadow_of(color_hex: str) -> str:
    """Colour-linked shadow: a dark version of the text colour (black for white text)."""
    h = color_hex.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    if r > 200 and g > 200 and b > 200:
        return "#000000"
    return "#%02X%02X%02X" % (int(r * 0.22), int(g * 0.22), int(b * 0.22))


def _style_line(name, font, size, colors, outline, shadow, align, margin_v, bold: bool = True):
    return ",".join([f"Style: {name}", font, str(size), ass_color(colors["white"]), ass_color(colors["yellow"]),
                     ass_color("#000000"), ass_color("#000000"), "-1" if bold else "0", "0", "0", "0", "100", "100", "0", "0", "1",
                     str(outline), str(shadow), str(align), "40", "40", str(margin_v), "1"])


def render_text(words: list[tuple[str, str]], colors: dict, max_chars: int = 16) -> str:
    """Words + colours -> ASS text with per-word colour / shadow overrides and automatic line wrapping."""
    lines: list[list[tuple[str, str]]] = [[]]
    for w, col in words:
        if w == "\\N":
            lines.append([])
            continue
        cur = lines[-1]
        if cur and sum(len(x) for x, _ in cur) + len(cur) + len(w) > max_chars:
            lines.append([])
        lines[-1].append((w, col))
    out = []
    for line in lines:
        out.append(" ".join(f"{{\\c{ass_color(col)}\\4c{ass_color(shadow_of(col))}}}{w.upper()}" for w, col in line))
    return "\\N".join(out)


# ---------------------------------------------------------------------------
# trackers (arrow / circle)
# ---------------------------------------------------------------------------

ARROW = "m -240 -330 l -190 -365 l -60 -160 l -25 -205 l 0 0 l -165 -70 l -125 -105 z"  # tip at 0,0, coming from top-left


def _circle_path(r: int) -> str:
    k = 0.5523 * r
    return (f"m {-r} 0 b {-r} {-k} {-k} {-r} 0 {-r} b {k} {-r} {r} {-k} {r} 0 "
            f"b {r} {k} {k} {r} 0 {r} b {-k} {r} {-r} {k} {-r} 0")


def _track_events(tr: Track, colors: dict) -> list[str]:
    ev: list[str] = []
    keys = tr.keys
    if tr.kind == "arrow":
        shape = ARROW
        full, small = 54, 38
        body = f"\\bord7\\3c&H000000&\\1c{ass_color(colors['red'])}\\shad0"
        glow = f"\\bord22\\3c{ass_color(colors['red'])}\\1c{ass_color(colors['red'])}\\blur14\\1a&H60&\\3a&H60&\\shad0"
    else:
        shape = _circle_path(tr.radius)
        full, small = 100, 65
        body = "\\bord8\\3c&HFFFFFF&\\1a&HFF&\\shad0"
        glow = "\\bord18\\3c&HFFFFFF&\\1a&HFF&\\3a&H70&\\blur12\\shad0"
    for i in range(len(keys) - 1):
        t0, x0, y0 = keys[i]
        t1, x1, y1 = keys[i + 1]
        move = f"\\move({x0},{y0},{x1},{y1})"
        pop = f"\\fscx{small}\\fscy{small}\\t(0,140,\\fscx{full}\\fscy{full})" if i == 0 else f"\\fscx{full}\\fscy{full}"
        fade = "\\fad(60,0)" if i == 0 else ("\\fad(0,150)" if i == len(keys) - 2 else "")
        for layer, style in ((5, glow), (6, body)):
            ev.append(f"Dialogue: {layer},{ass_time(t0)},{ass_time(t1)},Draw,,0,0,0,,{{\\an7{move}{style}{pop}{fade}\\p1}}{shape}{{\\p0}}")
    return ev


def build_ass(spec: ReelSpec, chunks: list[Chunk]) -> str:
    colors = spec.colors
    header = "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {W}", f"PlayResY: {H}", "WrapStyle: 2", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, "
        "StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        _style_line("Cap", spec.font, spec.caption_size, colors, 4, 5, 5, 0),
        _style_line("Card", spec.font, 96, colors, 5, 6, 5, 0),
        _style_line("Draw", spec.font, 20, colors, 0, 0, 7, 0),
        "", "[Events]", "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ])
    ev: list[str] = []
    pop = "\\fscx86\\fscy86\\t(0,90,\\fscx100\\fscy100)"
    cy = int(H * spec.caption_y_frac)
    for c in chunks:
        if spec.captions_until is not None and c.start >= spec.captions_until:
            break
        if c.hide:
            continue
        end = c.end if spec.captions_until is None else min(c.end, spec.captions_until)
        text = render_text(parse_markup(c.text, colors), colors, spec.caption_max_chars)
        ev.append(f"Dialogue: 2,{ass_time(c.start)},{ass_time(end)},Cap,,0,0,0,,{{\\an5\\pos({W // 2},{cy}){pop}}}{text}")
    for card in spec.cards:
        y = int(H * card.y_frac)
        text = "\\N".join(render_text(parse_markup(line, colors), colors, 99) for line in card.lines)
        ev.append(f"Dialogue: 3,{ass_time(card.start)},{ass_time(card.end)},Card,,0,0,0,,{{\\an5\\pos({W // 2},{y})\\fs{card.size}{pop}}}{text}")
    for tr in spec.tracks:
        ev.extend(_track_events(tr, colors))
    return header + "\n" + "\n".join(ev) + "\n"


# ---------------------------------------------------------------------------
# compose
# ---------------------------------------------------------------------------


def _flash_expr(times: list[float], strength: float = 0.55, length: float = 0.14) -> str:
    terms = [f"{strength}*max(0,1-(t-{t:.3f})/{length})*gte(t,{t:.3f})" for t in times]
    return "+".join(terms) if terms else "0"


def render(spec: ReelSpec, log: Logger = print) -> Path:
    work = Path(spec.workdir)
    work.mkdir(parents=True, exist_ok=True)
    total = spec.total or ffmpeg.probe(spec.audio).duration

    seg_files: list[Path] = []
    for i, seg in enumerate(spec.segments):
        out = work / f"seg{i:02d}.mp4"
        if not out.exists():
            render_segment(seg, out, log)
        seg_files.append(out)
    log(f"segments total {sum(s.timeline_duration for s in spec.segments):.2f}s + lead-in {spec.video_offset:.2f}s (audio {total:.2f}s)")

    chunks = time_chunks(spec.chunks, spec.words, spec.colors)
    ass_path = work / "captions.ass"
    ass_path.write_text(build_ass(spec, chunks), encoding="utf-8")

    args: list[str] = ["-y"]
    for f_ in seg_files:
        args += ["-i", str(f_)]
    n = len(seg_files)
    args += ["-i", spec.audio]
    ov_idx: list[int] = []
    for ov in spec.overlays:
        args += ["-loop", "1", "-framerate", str(FPS), "-t", f"{ov.end - ov.start + 0.5:.3f}", "-i", ov.png]
        ov_idx.append(n + 1 + len(ov_idx))

    f: list[str] = [f"color=c=black:s={W}x{H}:r={FPS}:d={spec.video_offset:.3f},format=yuv420p[lead]"]
    f.append("[lead]" + "".join(f"[{i}:v]" for i in range(n)) + f"concat=n={n + 1}:v=1:a=0,fps={FPS},format=yuv420p[v0]")
    cur = "v0"
    for k, (a, b) in enumerate(spec.bw_ranges):
        f.append(f"[{cur}]hue=s=0:enable='between(t,{a:.3f},{b:.3f})'[vbw{k}]")
        cur = f"vbw{k}"
    for k, (ov, idx) in enumerate(zip(spec.overlays, ov_idx)):
        d = ov.end - ov.start
        chain = []
        if abs(ov.scale - 1.0) > 1e-3:
            chain.append(f"scale=iw*{ov.scale:.3f}:-2")
        if ov.pop:
            # overlay needs a constant frame size: pad onto a transparent canvas and zoompan from 86% to 100%
            from PIL import Image

            pw, ph = Image.open(ov.png).size
            pw, ph = int(pw * ov.scale) // 2 * 2, int(ph * ov.scale) // 2 * 2
            chain.append("format=rgba,pad=w=iw*1.16:h=ih*1.16:x=(ow-iw)/2:y=(oh-ih)/2:color=black@0")
            chain.append(f"zoompan=z='min(1.16,1+0.16*on/4)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={pw}x{ph}:fps={FPS}")
        chain.append("format=rgba")
        chain.append(f"fade=t=in:st=0:d={ov.fade_in:.3f}:alpha=1")
        if ov.fade_out:
            chain.append(f"fade=t=out:st={max(0, d - ov.fade_out):.3f}:d={ov.fade_out:.3f}:alpha=1")
        chain.append(f"setpts=PTS-STARTPTS+{ov.start:.3f}/TB")
        f.append(f"[{idx}:v]{','.join(chain)}[ov{k}]")
        f.append(f"[{cur}][ov{k}]overlay=x='{ov.x}':y='{ov.y}':enable='between(t,{ov.start:.3f},{ov.end:.3f})':eof_action=pass[vo{k}]")
        cur = f"vo{k}"
    flashes = list(spec.flashes) + [ov.start for ov in spec.overlays if ov.flash] + [tr.keys[0][0] for tr in spec.tracks if tr.flash]
    if spec.flash_on_cuts:
        flashes += spec.cut_times()
    flashes = sorted({round(t, 3) for t in flashes})
    if flashes:
        f.append(f"[{cur}]eq=brightness='{_flash_expr(flashes)}':eval=frame[vfl]")
        cur = "vfl"
    fontsdir = f":fontsdir='{ffmpeg.escape_filter_path(spec.fontsdir)}'" if spec.fontsdir else ""
    f.append(f"[{cur}]ass='{ffmpeg.escape_filter_path(str(ass_path))}'{fontsdir}[vout]")
    f.append(f"[{n}:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[aout]")
    script = work / "compose.filter"
    script.write_text(";\n".join(f))
    args += ["-filter_complex_script", str(script), "-map", "[vout]", "-map", "[aout]", "-t", f"{total:.3f}",
             "-c:v", "libx264", "-preset", "medium", "-crf", "18", "-pix_fmt", "yuv420p", "-r", str(FPS),
             "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", spec.out]
    log(f"composing ({len(flashes)} flashes, {len(spec.overlays)} overlays, {len(chunks)} caption chunks) ...")
    ffmpeg.run(args)
    return Path(spec.out)
