"""Assemble the final video with ffmpeg according to a FormatSpec."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import ffmpeg
from .captions import build_ass
from .formats import FormatSpec
from .models import ClipAssignment, Project

Logger = Callable[[str], None]

PLACEHOLDER_COLORS = ["0x1f2937", "0x312e81", "0x134e4a", "0x3f1d2e", "0x1e3a5f"]


def _fit(w: int, h: int, fps: int) -> str:
    return f"scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h},setsar=1,fps={fps},format=yuv420p"


def _even(n: float) -> int:
    return int(n) // 2 * 2


def build_body_command(project: Project, spec: FormatSpec, assignments: list[ClipAssignment], out: Path, ass_path: Path | None) -> list[str]:
    """Return the full ffmpeg argument list for rendering the body (no intro/outro)."""
    T = project.timeline_duration
    W, H, FPS = spec.width, spec.height, spec.fps
    bw, bh = spec.broll_size()
    layout = spec.layout
    has_cam = bool(project.trim and project.trim.has_video)
    if layout in ("split", "pip", "camera") and not has_cam:
        layout = "broll"

    args: list[str] = ["-y", "-i", project.trimmed_media]
    n_inputs = 1
    filters: list[str] = []
    scenes = {s.index: s for s in project.scenes}

    # --- b-roll -------------------------------------------------------
    broll_labels: list[str] = []
    if layout != "camera":
        for a in assignments:
            sc = scenes[a.scene_index]
            D = max(0.1, sc.duration)
            label = f"b{a.scene_index}"
            if a.path is None:
                color = PLACEHOLDER_COLORS[a.scene_index % len(PLACEHOLDER_COLORS)]
                filters.append(f"color=c={color}:s={bw}x{bh}:r={FPS}:d={D:.3f},format=yuv420p[{label}]")
            else:
                idx = n_inputs
                n_inputs += 1
                if a.is_image:
                    args += ["-loop", "1", "-framerate", str(FPS), "-t", f"{D + 0.5:.3f}", "-i", a.path]
                    chain = f"[{idx}:v]{_fit(bw, bh, FPS)}"
                elif a.loop:
                    args += ["-stream_loop", "-1", "-t", f"{D + 0.5:.3f}", "-i", a.path]
                    chain = f"[{idx}:v]{_fit(bw, bh, FPS)}"
                else:
                    args += ["-i", a.path]
                    chain = f"[{idx}:v]trim=start={a.in_point:.3f},setpts=PTS-STARTPTS,{_fit(bw, bh, FPS)}"
                chain += f",tpad=stop_mode=clone:stop_duration={D:.3f},trim=duration={D:.3f},setpts=PTS-STARTPTS[{label}]"
                filters.append(chain)
            broll_labels.append(f"[{label}]")
        filters.append(f"{''.join(broll_labels)}concat=n={len(broll_labels)}:v=1:a=0[broll]")

    # --- layout --------------------------------------------------------
    if layout == "broll":
        filters.append(f"[broll]trim=duration={T:.3f},setpts=PTS-STARTPTS[body]")
    elif layout == "camera":
        filters.append(f"[0:v]{_fit(W, H, FPS)},trim=duration={T:.3f},setpts=PTS-STARTPTS[body]")
    elif layout == "split":
        filters.append(f"[0:v]{_fit(W, H - bh, FPS)}[cam]")
        filters.append(f"[broll][cam]vstack=inputs=2,trim=duration={T:.3f},setpts=PTS-STARTPTS[body]")
    elif layout == "pip":
        pw = _even(W / 3)
        filters.append(f"[0:v]scale={pw}:-2,fps={FPS},format=yuv420p[cam]")
        filters.append(f"[broll][cam]overlay=W-w-40:H-h-40,trim=duration={T:.3f},setpts=PTS-STARTPTS[body]")
    else:
        raise ValueError(f"unknown layout {layout}")

    # --- captions ------------------------------------------------------
    if ass_path is not None:
        filters.append(f"[body]ass='{ffmpeg.escape_filter_path(str(ass_path))}'[vout]")
    else:
        filters.append("[body]null[vout]")

    # --- audio ---------------------------------------------------------
    au = spec.audio
    afmt = "aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo"
    filters.append(f"[0:a]{afmt},volume={float(au.get('voice_volume', 1.0))}[voice]")
    music = au.get("music")
    if music and Path(music).exists():
        midx = n_inputs
        n_inputs += 1
        args += ["-stream_loop", "-1", "-t", f"{T + 1:.3f}", "-i", str(music)]
        filters.append(f"[{midx}:a]{afmt},volume={float(au.get('music_volume', 0.12))}[mus]")
        filters.append("[voice][mus]amix=inputs=2:duration=first:normalize=0[amixed]")
        alabel = "amixed"
    else:
        alabel = "voice"
    if au.get("loudnorm", True):
        filters.append(f"[{alabel}]loudnorm=I={float(au.get('target_lufs', -14))}:TP=-1.5:LRA=11,aresample=48000[aout]")
    else:
        filters.append(f"[{alabel}]anull[aout]")

    script = out.with_suffix(".filter")
    script.write_text(";\n".join(filters))
    enc = spec.encode
    args += [
        "-filter_complex_script", str(script),
        "-map", "[vout]", "-map", "[aout]",
        "-t", f"{T:.3f}",
        "-c:v", enc.get("codec", "libx264"), "-crf", str(enc.get("crf", 20)), "-preset", str(enc.get("preset", "medium")),
        "-pix_fmt", enc.get("pix_fmt", "yuv420p"), "-r", str(FPS),
        "-c:a", "aac", "-b:a", str(enc.get("audio_bitrate", "192k")), "-ar", "48000",
        "-movflags", "+faststart",
        str(out),
    ]
    return args


def normalise_bumper(src: str, dst: Path, spec: FormatSpec) -> Path:
    """Re-encode an intro/outro to the canvas so it can be concatenated with the body."""
    info = ffmpeg.probe(src)
    W, H, FPS = spec.width, spec.height, spec.fps
    args = ["-y"]
    if info.is_image:
        args += ["-loop", "1", "-framerate", str(FPS), "-t", "3", "-i", src]
        dur = 3.0
    else:
        args += ["-i", src]
        dur = info.duration
    args += ["-f", "lavfi", "-t", f"{dur:.3f}", "-i", "anullsrc=r=48000:cl=stereo"]
    afilter = "[0:a]aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=stereo[a]" if info.has_audio else "[1:a]anull[a]"
    fc = f"[0:v]{_fit(W, H, FPS)},trim=duration={dur:.3f},setpts=PTS-STARTPTS[v];{afilter}"
    enc = spec.encode
    args += [
        "-filter_complex", fc, "-map", "[v]", "-map", "[a]", "-t", f"{dur:.3f}",
        "-c:v", enc.get("codec", "libx264"), "-crf", str(enc.get("crf", 20)), "-preset", "fast",
        "-pix_fmt", enc.get("pix_fmt", "yuv420p"), "-r", str(FPS), "-c:a", "aac", "-ar", "48000", str(dst),
    ]
    ffmpeg.run(args)
    return dst


def concat_parts(parts: list[Path], out: Path, spec: FormatSpec, max_duration: float | None) -> Path:
    args = ["-y"]
    for p in parts:
        args += ["-i", str(p)]
    labels = "".join(f"[{i}:v][{i}:a]" for i in range(len(parts)))
    enc = spec.encode
    args += ["-filter_complex", f"{labels}concat=n={len(parts)}:v=1:a=1[v][a]", "-map", "[v]", "-map", "[a]"]
    if max_duration:
        args += ["-t", f"{max_duration:.3f}"]
    args += [
        "-c:v", enc.get("codec", "libx264"), "-crf", str(enc.get("crf", 20)), "-preset", str(enc.get("preset", "medium")),
        "-pix_fmt", enc.get("pix_fmt", "yuv420p"), "-c:a", "aac", "-b:a", str(enc.get("audio_bitrate", "192k")),
        "-movflags", "+faststart", str(out),
    ]
    ffmpeg.run(args)
    return out


def render(project: Project, spec: FormatSpec, out: str | Path, *, log: Logger = print) -> Path:
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    work = Path(project.workdir)
    if not project.scenes:
        raise RuntimeError("No scenes: run the scenes stage first.")
    assignments = project.assignments or [ClipAssignment(s.index, None) for s in project.scenes]
    by_scene = {a.scene_index: a for a in assignments}
    assignments = [by_scene.get(s.index, ClipAssignment(s.index, None)) for s in project.scenes]

    ass_path = None
    cap = spec.captions
    if cap.get("enabled", True) and cap.get("mode", "word") != "none" and any(s.words for s in project.transcript):
        ass_path = work / "captions.ass"
        ass_path.write_text(build_ass(project.transcript, spec), encoding="utf-8")
        log(f"captions -> {ass_path}")

    has_bumpers = bool(spec.raw.get("intro") or spec.raw.get("outro"))
    body_out = work / "body.mp4" if has_bumpers else out
    log(f"rendering body ({spec.width}x{spec.height}@{spec.fps}, layout={spec.layout}, {len(assignments)} scenes) ...")
    ffmpeg.run(build_body_command(project, spec, assignments, body_out, ass_path))

    if has_bumpers:
        parts: list[Path] = []
        if spec.raw.get("intro"):
            parts.append(normalise_bumper(spec.raw["intro"], work / "intro.mp4", spec))
        parts.append(body_out)
        if spec.raw.get("outro"):
            parts.append(normalise_bumper(spec.raw["outro"], work / "outro.mp4", spec))
        log("adding intro/outro ...")
        concat_parts(parts, out, spec, spec.max_duration)
    elif spec.max_duration and project.timeline_duration > spec.max_duration:
        log(f"warning: timeline is {project.timeline_duration:.1f}s, longer than the format's max of {spec.max_duration}s; trimming")
        tmp = out.with_name(out.stem + ".full" + out.suffix)
        out.rename(tmp)
        ffmpeg.run(["-y", "-i", str(tmp), "-t", f"{spec.max_duration:.3f}", "-c", "copy", str(out)])
        tmp.unlink(missing_ok=True)
    return out
