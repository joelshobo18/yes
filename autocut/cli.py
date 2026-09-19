"""Command line interface: ``autocut run`` does everything, the other commands run one stage."""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__, pipeline
from .formats import list_builtin, load_format
from .models import Project
from .silence import SilenceParams


def _log(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _format_from_args(args, project: Project | None = None):
    overrides: dict = {}
    if getattr(args, "layout", None):
        overrides["layout"] = args.layout
    if getattr(args, "music", None):
        overrides.setdefault("audio", {})["music"] = str(Path(args.music).resolve())
    if getattr(args, "no_captions", False):
        overrides.setdefault("captions", {})["enabled"] = False
    if getattr(args, "intro", None):
        overrides["intro"] = str(Path(args.intro).resolve())
    if getattr(args, "outro", None):
        overrides["outro"] = str(Path(args.outro).resolve())
    if getattr(args, "max_duration", None) is not None:
        overrides["max_duration"] = args.max_duration
    name = getattr(args, "format", None) or (project.format_name if project else "tiktok")
    return load_format(name, overrides)


def _silence_params(args) -> SilenceParams:
    return SilenceParams(noise_db=args.noise, min_silence=args.min_silence, pad=args.pad, max_gap=args.max_gap)


def _add_trim_args(p):
    p.add_argument("--noise", type=float, default=-35.0, help="silence threshold in dB (default -35)")
    p.add_argument("--min-silence", type=float, default=0.45, help="pauses shorter than this are kept (s)")
    p.add_argument("--pad", type=float, default=0.12, help="silence kept around speech (s)")
    p.add_argument("--max-gap", type=float, default=None, help="cap pauses to this length instead of removing them")
    p.add_argument("--audio-only", action="store_true", help="drop the video track even if the source has one")


def _add_transcribe_args(p):
    p.add_argument("--transcriber", default="auto", choices=["auto", "faster-whisper", "whisper", "none"])
    p.add_argument("--model-size", default="base", help="whisper model size (tiny/base/small/medium/large-v3)")
    p.add_argument("--language", default=None)
    p.add_argument("--script", default=None, help="plain-text script to align instead of running speech-to-text")
    p.add_argument("--srt", default=None, help="existing .srt to use instead of running speech-to-text")


def _add_format_args(p):
    p.add_argument("--format", "-f", default=None, help=f"built-in ({', '.join(list_builtin())}) or path to YAML")
    p.add_argument("--layout", choices=["broll", "split", "pip", "camera"], default=None)
    p.add_argument("--music", default=None, help="background music file")
    p.add_argument("--intro", default=None)
    p.add_argument("--outro", default=None)
    p.add_argument("--no-captions", action="store_true")
    p.add_argument("--max-duration", type=float, default=None)


def _add_find_args(p):
    p.add_argument("--assets", default=None, help="folder with your own clips/images (LocalProvider)")
    p.add_argument("--providers", default=None, help="comma list overriding the format's providers, e.g. local,pexels")
    p.add_argument("--claude-queries", action="store_true", help="use Claude to write visual search queries")


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="autocut", description="Trim dead air, find matching clips online, render to a format.")
    ap.add_argument("--version", action="version", version=__version__)
    sub = ap.add_subparsers(dest="cmd", required=True)

    run = sub.add_parser("run", help="run the whole pipeline")
    run.add_argument("source", help="voice-over audio or talking-head video")
    run.add_argument("--workdir", "-w", default=None, help="project folder (default work/<source stem>)")
    run.add_argument("--out", "-o", default=None, help="output mp4 path")
    run.add_argument("--topic", default="", help="topic hint appended to search queries")
    _add_trim_args(run)
    _add_transcribe_args(run)
    _add_format_args(run)
    _add_find_args(run)
    run.add_argument("--skip-find", action="store_true", help="render placeholders instead of searching for clips")

    t = sub.add_parser("trim", help="only remove dead air")
    t.add_argument("source")
    t.add_argument("--out", "-o", required=True)
    _add_trim_args(t)

    for name, adder in [("transcribe", _add_transcribe_args), ("scenes", None), ("find", _add_find_args), ("render", None)]:
        p = sub.add_parser(name, help=f"re-run the {name} stage on an existing project")
        p.add_argument("--workdir", "-w", required=True)
        if adder:
            adder(p)
        if name in ("scenes", "find", "render"):
            _add_format_args(p)
        if name == "scenes":
            p.add_argument("--claude-queries", action="store_true")
            p.add_argument("--topic", default=None)
        if name == "render":
            p.add_argument("--out", "-o", default=None)

    sub.add_parser("formats", help="list built-in formats")
    ins = sub.add_parser("inspect", help="print a project's scenes and clip assignments")
    ins.add_argument("--workdir", "-w", required=True)
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return _dispatch(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # surface a clean message instead of a traceback
        _log(f"error: {exc}")
        return 1


def _dispatch(args) -> int:
    if args.cmd == "formats":
        for name in list_builtin():
            spec = load_format(name)
            print(f"{name:14s} {spec.width}x{spec.height}@{spec.fps} layout={spec.layout:6s} {spec.raw.get('description', '')}")
        return 0

    if args.cmd == "trim":
        from .silence import trim

        res = trim(args.source, args.out, _silence_params(args), keep_video=not args.audio_only)
        _log(f"removed {res.original_duration - res.trimmed_duration:.1f}s of {res.original_duration:.1f}s -> {res.output}")
        return 0

    if args.cmd == "run":
        workdir = args.workdir or Path("work") / Path(args.source).stem
        spec = _format_from_args(args)
        project = pipeline.new_project(args.source, workdir, spec.name, topic=args.topic)
        pipeline.stage_trim(project, _silence_params(args), keep_video=not args.audio_only, log=_log)
        pipeline.stage_transcribe(
            project, backend=args.transcriber, model_size=args.model_size, language=args.language,
            script_path=args.script, srt_path=args.srt, log=_log,
        )
        pipeline.stage_scenes(project, spec, use_claude=args.claude_queries, log=_log)
        if not args.skip_find:
            provs = args.providers.split(",") if args.providers else None
            pipeline.stage_find(project, spec, assets_dir=args.assets, providers=provs, log=_log)
        pipeline.stage_render(project, spec, out=args.out, log=_log)
        print(project.output)
        return 0

    if args.cmd == "inspect":
        project = Project.load(args.workdir)
        print(f"source: {project.source}\nformat: {project.format_name}")
        if project.trim:
            print(f"trimmed: {project.trim.original_duration:.1f}s -> {project.trim.trimmed_duration:.1f}s ({project.trim.output})")
        by_scene = {a.scene_index: a for a in project.assignments}
        for s in project.scenes:
            a = by_scene.get(s.index)
            clip = f"{a.candidate.key}" if a and a.candidate else ("placeholder" if a else "-")
            print(f"{s.index:02d} {s.start:6.2f}-{s.end:6.2f} q='{s.query}' clip={clip}\n    {s.text}")
        if project.output:
            print(f"output: {project.output}")
        return 0

    project = Project.load(args.workdir)
    spec = _format_from_args(args, project)
    if args.cmd == "transcribe":
        pipeline.stage_transcribe(
            project, backend=args.transcriber, model_size=args.model_size, language=args.language,
            script_path=args.script, srt_path=args.srt, log=_log,
        )
    elif args.cmd == "scenes":
        if args.topic is not None:
            project.topic = args.topic
        pipeline.stage_scenes(project, spec, use_claude=args.claude_queries, log=_log)
    elif args.cmd == "find":
        provs = args.providers.split(",") if args.providers else None
        pipeline.stage_find(project, spec, assets_dir=args.assets, providers=provs, log=_log)
    elif args.cmd == "render":
        pipeline.stage_render(project, spec, out=args.out, log=_log)
        print(project.output)
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
