"""Stage orchestration. Every stage reads/writes ``<workdir>/project.json`` so it can be re-run alone."""
from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Callable

from . import ffmpeg
from .formats import FormatSpec
from .match import credits_text, find_clips
from .models import Project
from .providers import build_providers
from .scenes import build_scenes, claude_available, refine_queries_with_claude
from .silence import SilenceParams, trim
from .transcribe import to_srt, transcribe
from .render import render

Logger = Callable[[str], None]


def new_project(source: str, workdir: str | Path, format_name: str, topic: str = "") -> Project:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    p = Project(workdir=str(workdir), source=str(Path(source).resolve()), format_name=format_name, topic=topic)
    p.save()
    return p


def stage_trim(project: Project, params: SilenceParams, *, keep_video: bool = True, log: Logger = print) -> Project:
    info = ffmpeg.probe(project.source)
    ext = ".mp4" if (info.has_video and not info.is_image and keep_video) else ".wav"
    dst = Path(project.workdir) / f"trimmed{ext}"
    log(f"trim: analysing {project.source} ({info.duration:.1f}s) noise<{params.noise_db}dB pauses>={params.min_silence}s")
    res = trim(project.source, dst, params, keep_video=keep_video)
    project.trim = res
    project.save()
    removed = res.original_duration - res.trimmed_duration
    log(f"trim: {len(res.silences)} silences, removed {removed:.1f}s -> {res.trimmed_duration:.1f}s ({res.output})")
    (Path(project.workdir) / "edl.json").write_text(json.dumps([asdict(k) for k in res.keep_ranges], indent=2))
    return project


def stage_transcribe(
    project: Project,
    *,
    backend: str = "auto",
    model_size: str = "base",
    language: str | None = None,
    script_path: str | None = None,
    srt_path: str | None = None,
    log: Logger = print,
) -> Project:
    script_text = Path(script_path).read_text(encoding="utf-8") if script_path else None
    log(f"transcribe: backend={'srt' if srt_path else 'script' if script_text is not None else backend}")
    project.transcript = transcribe(
        project.trimmed_media, backend=backend, model_size=model_size, language=language, script_text=script_text, srt_path=srt_path
    )
    project.save()
    work = Path(project.workdir)
    (work / "transcript.srt").write_text(to_srt(project.transcript), encoding="utf-8")
    words = sum(len(s.words) for s in project.transcript)
    log(f"transcribe: {len(project.transcript)} segments, {words} words -> {work / 'transcript.srt'}")
    return project


def stage_scenes(project: Project, spec: FormatSpec, *, use_claude: bool = False, log: Logger = print) -> Project:
    p = spec.pacing
    project.scenes = build_scenes(
        project.transcript,
        project.timeline_duration,
        min_scene=float(p["min_scene"]),
        target_scene=float(p["target_scene"]),
        max_scene=float(p["max_scene"]),
        topic=project.topic,
    )
    if use_claude:
        if claude_available():
            try:
                log("scenes: asking Claude for visual search queries ...")
                refine_queries_with_claude(project.scenes, project.topic)
            except Exception as exc:
                log(f"scenes: Claude query refinement failed ({exc}); using keyword queries")
        else:
            log("scenes: --claude-queries requested but `anthropic` is not installed or no API key is set; using keywords")
    project.save()
    log(f"scenes: {len(project.scenes)} scenes")
    for s in project.scenes:
        log(f"  {s.index:02d} {s.start:6.2f}-{s.end:6.2f}  q='{s.query}'  | {s.text[:70]}")
    return project


def stage_find(
    project: Project,
    spec: FormatSpec,
    *,
    assets_dir: str | None = None,
    providers: list[str] | None = None,
    log: Logger = print,
) -> Project:
    names = providers or list(spec.clips.get("providers", ["local"]))
    log(f"find: providers requested: {', '.join(names)}")
    cache = Path(project.workdir).parent / "cache"
    provs = build_providers(names, assets_dir=assets_dir, cache_dir=cache, log=log)
    if not provs:
        log("find: no usable providers; every scene will get a placeholder card")
    project.assignments = find_clips(project.scenes, provs, spec, Path(project.workdir) / "clips", log=log)
    project.save()
    (Path(project.workdir) / "credits.txt").write_text(credits_text(project.assignments))
    found = sum(1 for a in project.assignments if a.path)
    log(f"find: {found}/{len(project.assignments)} scenes matched")
    return project


def stage_render(project: Project, spec: FormatSpec, *, out: str | None = None, log: Logger = print) -> Project:
    out_path = Path(out) if out else Path(project.workdir) / f"output_{spec.name}.mp4"
    render(project, spec, out_path, log=log)
    project.output = str(out_path)
    project.save()
    info = ffmpeg.probe(out_path)
    log(f"render: {out_path} ({info.width}x{info.height}, {info.duration:.1f}s)")
    return project
