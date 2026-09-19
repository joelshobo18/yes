"""Dead-air detection and removal using ffmpeg's silencedetect filter."""
from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from . import ffmpeg
from .models import TimeRange, TrimResult


@dataclass
class SilenceParams:
    noise_db: float = -35.0  # anything quieter than this is "silence"
    min_silence: float = 0.45  # silences shorter than this are kept (natural pauses)
    pad: float = 0.12  # seconds of the silence to keep on each side of speech
    min_keep: float = 0.2  # drop kept fragments shorter than this
    max_gap: float | None = None  # if set, cap remaining pauses to this length instead of removing them fully


_START_RE = re.compile(r"silence_start:\s*(-?[\d.]+)")
_END_RE = re.compile(r"silence_end:\s*(-?[\d.]+)")


def detect_silence(path: str | Path, params: SilenceParams | None = None) -> list[TimeRange]:
    """Return silent ranges (in source time) using silencedetect."""
    params = params or SilenceParams()
    proc = ffmpeg.run(
        [
            "-i",
            str(path),
            "-vn",
            "-af",
            f"silencedetect=noise={params.noise_db}dB:d={params.min_silence}",
            "-f",
            "null",
            "-",
        ],
        check=True,
        quiet=False,
    )
    return parse_silencedetect(proc.stderr, ffmpeg.probe(path).duration)


def parse_silencedetect(log: str, duration: float) -> list[TimeRange]:
    ranges: list[TimeRange] = []
    start: float | None = None
    for line in log.splitlines():
        if "silencedetect" not in line:
            continue
        m = _START_RE.search(line)
        if m:
            start = max(0.0, float(m.group(1)))
            continue
        m = _END_RE.search(line)
        if m and start is not None:
            ranges.append(TimeRange(start, float(m.group(1))))
            start = None
    if start is not None:  # silence runs to the end of the file
        ranges.append(TimeRange(start, duration))
    return ranges


def keep_ranges(duration: float, silences: list[TimeRange], params: SilenceParams | None = None) -> list[TimeRange]:
    """Invert silences into the ranges to keep, padding speech and merging tiny gaps."""
    params = params or SilenceParams()
    keeps: list[TimeRange] = []
    cursor = 0.0
    for s in sorted(silences, key=lambda r: r.start):
        if s.start > cursor:
            keeps.append(TimeRange(cursor, s.start))
        cursor = max(cursor, s.end)
    if cursor < duration:
        keeps.append(TimeRange(cursor, duration))
    if not keeps:
        return []

    # Pad each keep into the surrounding silence.
    padded: list[TimeRange] = []
    for k in keeps:
        padded.append(TimeRange(max(0.0, k.start - params.pad), min(duration, k.end + params.pad)))

    # Optionally keep a capped gap between phrases (max_gap) instead of a hard cut.
    if params.max_gap is not None:
        capped: list[TimeRange] = []
        for i, k in enumerate(padded):
            if i + 1 < len(padded):
                gap = padded[i + 1].start - k.end
                if gap > 0:
                    k = TimeRange(k.start, k.end + min(gap, params.max_gap) / 2)
                    padded[i + 1] = TimeRange(padded[i + 1].start - min(gap, params.max_gap) / 2, padded[i + 1].end)
            capped.append(k)
        padded = capped

    # Merge overlapping / touching ranges and drop tiny fragments.
    merged: list[TimeRange] = []
    for k in padded:
        if merged and k.start <= merged[-1].end + 1e-3:
            merged[-1] = TimeRange(merged[-1].start, max(merged[-1].end, k.end))
        else:
            merged.append(TimeRange(k.start, k.end))
    return [k for k in merged if k.duration >= params.min_keep]


def cut_media(src: str | Path, dst: str | Path, keeps: list[TimeRange], *, with_video: bool) -> None:
    """Write ``dst`` containing only ``keeps`` from ``src`` (frame-accurate re-encode)."""
    src, dst = str(src), str(dst)
    if not keeps:
        raise ValueError("Nothing to keep: the whole file was detected as silence.")
    lines: list[str] = []
    labels: list[str] = []
    for i, k in enumerate(keeps):
        if with_video:
            lines.append(f"[0:v]trim=start={k.start:.4f}:end={k.end:.4f},setpts=PTS-STARTPTS[v{i}]")
        lines.append(f"[0:a]atrim=start={k.start:.4f}:end={k.end:.4f},asetpts=PTS-STARTPTS[a{i}]")
        labels.append(f"[v{i}][a{i}]" if with_video else f"[a{i}]")
    n = len(keeps)
    if with_video:
        lines.append(f"{''.join(labels)}concat=n={n}:v=1:a=1[outv][outa]")
    else:
        lines.append(f"{''.join(labels)}concat=n={n}:v=0:a=1[outa]")
    script = Path(dst).with_suffix(".filter")
    script.write_text(";\n".join(lines))

    args = ["-y", "-i", src, "-filter_complex_script", str(script)]
    if with_video:
        args += ["-map", "[outv]", "-map", "[outa]", "-c:v", "libx264", "-preset", "fast", "-crf", "18", "-pix_fmt", "yuv420p"]
    else:
        args += ["-map", "[outa]"]
    if Path(dst).suffix.lower() == ".wav":
        args += ["-c:a", "pcm_s16le"]
    else:
        args += ["-c:a", "aac", "-b:a", "192k"]
    args += [dst]
    ffmpeg.run(args)
    script.unlink(missing_ok=True)


def trim(src: str | Path, dst: str | Path, params: SilenceParams | None = None, *, keep_video: bool = True) -> TrimResult:
    """Detect and remove dead air from an audio or video file."""
    params = params or SilenceParams()
    info = ffmpeg.probe(src)
    if not info.has_audio:
        raise ValueError(f"{src} has no audio stream to analyse.")
    silences = detect_silence(src, params)
    keeps = keep_ranges(info.duration, silences, params)
    with_video = bool(info.has_video and not info.is_image and keep_video)
    dst = Path(dst)
    if not with_video and dst.suffix.lower() not in {".wav", ".m4a", ".mp3", ".aac"}:
        dst = dst.with_suffix(".wav")
    cut_media(src, dst, keeps, with_video=with_video)
    return TrimResult(
        source=str(src),
        output=str(dst),
        original_duration=info.duration,
        trimmed_duration=sum(k.duration for k in keeps),
        keep_ranges=keeps,
        silences=silences,
        has_video=with_video,
    )


def map_time(t: float, keeps: list[TimeRange]) -> float:
    """Map a source timestamp to the trimmed timeline (clamps into the nearest kept range)."""
    offset = 0.0
    for k in keeps:
        if t < k.start:
            return offset
        if t <= k.end:
            return offset + (t - k.start)
        offset += k.duration
    return offset
