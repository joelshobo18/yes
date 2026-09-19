import pytest

from autocut.formats import list_builtin, load_format
from autocut.match import duration_fit, orientation_fit, relevance, score
from autocut.models import ClipCandidate, Scene


def test_builtin_formats_load():
    names = list_builtin()
    assert {"tiktok", "youtube", "square", "talking-head"} <= set(names)
    tt = load_format("tiktok")
    assert (tt.width, tt.height, tt.orientation) == (1080, 1920, "portrait")
    yt = load_format("youtube")
    assert yt.orientation == "landscape" and yt.captions["mode"] == "line"


def test_extends_and_overrides():
    th = load_format("talking-head")
    assert th.layout == "split" and th.max_duration == 60  # inherited from tiktok
    assert th.broll_size() == (1080, 960)
    custom = load_format("tiktok", {"canvas": {"fps": 60}, "captions": {"enabled": False}})
    assert custom.fps == 60 and custom.captions["enabled"] is False and custom.captions["mode"] == "word"


def test_unknown_format_raises():
    with pytest.raises(FileNotFoundError):
        load_format("does-not-exist")


def test_yaml_path_format(tmp_path):
    p = tmp_path / "mine.yaml"
    p.write_text("canvas: {width: 720, height: 720, fps: 24}\nlayout: broll\n")
    spec = load_format(str(p))
    assert spec.name == "mine" and spec.width == 720 and spec.orientation == "square"


def _cand(**kw):
    base = dict(provider="pexels", id="1", title="city traffic at night", duration=10, width=1080, height=1920, tags=["city", "night"])
    base.update(kw)
    return ClipCandidate(**base)


def test_relevance():
    assert relevance("city traffic night", _cand()) == 1.0
    assert relevance("ocean waves", _cand()) == 0.0
    assert 0 < relevance("nights", _cand()) < 1  # substring match counts half


def test_duration_and_orientation_fit():
    assert duration_fit(4, _cand(duration=10), 2) == 1.0
    assert duration_fit(4, _cand(duration=3), 2) < 1.0
    assert duration_fit(4, _cand(duration=1), 2) == 0.1
    assert orientation_fit("portrait", _cand()) == 1.0
    assert orientation_fit("landscape", _cand()) == 0.4


def test_score_penalises_repeats_and_prefers_relevant():
    spec = load_format("tiktok")
    scene = Scene(0, 0, 4, "city traffic", ["city", "traffic"], "city traffic")
    good = _cand()
    bad = _cand(id="2", title="ocean waves", tags=["ocean"])
    assert score(scene, good, spec, [], 0) > score(scene, bad, spec, [], 0)
    assert score(scene, good, spec, ["pexels:1"], 0) < score(scene, bad, spec, [], 0)
