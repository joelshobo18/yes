"""End-to-end: trim -> script alignment -> scenes -> local clip matching -> render. Offline, ~10s."""
from pathlib import Path

from autocut import ffmpeg, pipeline
from autocut.cli import main
from autocut.formats import load_format
from autocut.models import Project
from autocut.silence import SilenceParams


def test_full_pipeline_with_local_assets(fixtures, tmp_path):
    spec = load_format("tiktok", {"audio": {"music": str(fixtures["music"])}})
    log = lambda m: None
    p = pipeline.new_project(str(fixtures["voice"]), tmp_path / "proj", spec.name, topic="road trip")
    pipeline.stage_trim(p, SilenceParams(), log=log)
    pipeline.stage_transcribe(p, script_path=str(fixtures["script"]), log=log)
    pipeline.stage_scenes(p, spec, log=log)
    pipeline.stage_find(p, spec, assets_dir=str(fixtures["assets"]), providers=["local"], log=log)
    pipeline.stage_render(p, spec, log=log)

    assert 5.0 < p.timeline_duration < 6.2
    assert len(p.scenes) >= 1 and all(s.query for s in p.scenes)
    assert p.assignments and all(a.path for a in p.assignments), "every scene should match a local asset"
    assert p.assignments[0].candidate.id == "city_traffic_night.mp4"

    out = ffmpeg.probe(p.output)
    assert (out.width, out.height) == (1080, 1920)
    assert out.has_video and out.has_audio
    assert abs(out.duration - p.timeline_duration) < 0.25
    assert (Path(p.workdir) / "captions.ass").exists()
    assert (Path(p.workdir) / "credits.txt").exists()

    # project round-trips through JSON
    reloaded = Project.load(p.workdir)
    assert reloaded.output == p.output and len(reloaded.assignments) == len(p.assignments)


def test_split_layout_with_intro_and_placeholders(fixtures, tmp_path):
    spec = load_format("talking-head", {"intro": str(fixtures["assets"] / "forest_trees.png")})
    log = lambda m: None
    p = pipeline.new_project(str(fixtures["cam"]), tmp_path / "proj", spec.name)
    pipeline.stage_trim(p, SilenceParams(), log=log)
    pipeline.stage_transcribe(p, backend="none", log=log)
    pipeline.stage_scenes(p, spec, log=log)
    pipeline.stage_find(p, spec, providers=[], log=log)  # no providers -> placeholders
    assert all(a.path is None for a in p.assignments)
    pipeline.stage_render(p, spec, log=log)
    out = ffmpeg.probe(p.output)
    assert (out.width, out.height) == (1080, 1920)
    assert abs(out.duration - (p.timeline_duration + 3.0)) < 0.3  # 3s image intro


def test_cli_run_and_inspect(fixtures, tmp_path, capsys):
    work = tmp_path / "cli"
    rc = main([
        "run", str(fixtures["voice"]), "--script", str(fixtures["script"]), "--assets", str(fixtures["assets"]),
        "--providers", "local", "--format", "square", "--workdir", str(work), "--no-captions", "--max-duration", "4",
    ])
    assert rc == 0
    out_path = capsys.readouterr().out.strip()
    assert Path(out_path).exists()
    info = ffmpeg.probe(out_path)
    assert (info.width, info.height) == (1080, 1080) and info.duration <= 4.3
    assert main(["inspect", "--workdir", str(work)]) == 0
    assert "clip=local:" in capsys.readouterr().out
    assert main(["formats"]) == 0
