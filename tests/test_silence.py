from autocut.models import TimeRange
from autocut.silence import SilenceParams, detect_silence, keep_ranges, map_time, parse_silencedetect, trim

LOG = """
[silencedetect @ 0x1] silence_start: 1.2
[silencedetect @ 0x1] silence_end: 3.0 | silence_duration: 1.8
[silencedetect @ 0x1] silence_start: 4.2
[silencedetect @ 0x1] silence_end: 6.0 | silence_duration: 1.8
[silencedetect @ 0x1] silence_start: 10.2
"""


def test_parse_silencedetect_handles_trailing_silence():
    r = parse_silencedetect(LOG, 12.0)
    assert [(s.start, s.end) for s in r] == [(1.2, 3.0), (4.2, 6.0), (10.2, 12.0)]


def test_keep_ranges_inverts_and_pads():
    sil = [TimeRange(1.2, 3.0), TimeRange(4.2, 6.0), TimeRange(10.2, 12.0)]
    keeps = keep_ranges(12.0, sil, SilenceParams(pad=0.1, min_keep=0.2))
    assert len(keeps) == 3
    assert keeps[0].start == 0.0 and abs(keeps[0].end - 1.3) < 1e-6
    assert abs(keeps[1].start - 2.9) < 1e-6 and abs(keeps[1].end - 4.3) < 1e-6
    assert abs(keeps[2].start - 5.9) < 1e-6 and abs(keeps[2].end - 10.3) < 1e-6


def test_keep_ranges_merges_when_pad_covers_gap():
    sil = [TimeRange(1.0, 1.1)]  # 0.1s gap, 0.12s pad each side -> merges back into one range
    keeps = keep_ranges(2.0, sil, SilenceParams(pad=0.12))
    assert len(keeps) == 1 and keeps[0].start == 0.0 and keeps[0].end == 2.0


def test_keep_ranges_max_gap_keeps_a_breath():
    sil = [TimeRange(1.0, 3.0)]
    keeps = keep_ranges(5.0, sil, SilenceParams(pad=0.0, max_gap=0.4))
    assert abs(keeps[0].end - 1.2) < 1e-6 and abs(keeps[1].start - 2.8) < 1e-6


def test_map_time():
    keeps = [TimeRange(0, 1), TimeRange(3, 4)]
    assert map_time(0.5, keeps) == 0.5
    assert map_time(2.0, keeps) == 1.0  # inside removed gap -> collapses
    assert map_time(3.5, keeps) == 1.5


def test_detect_and_trim_audio(fixtures, tmp_path):
    sil = detect_silence(fixtures["voice"])
    assert len(sil) == 4
    res = trim(fixtures["voice"], tmp_path / "out.wav")
    assert res.original_duration > 11.9
    # 4 bursts of ~1.2s plus 0.12s padding each side
    assert 5.0 < res.trimmed_duration < 6.2
    assert res.output.endswith(".wav") and not res.has_video


def test_trim_video_keeps_video(fixtures, tmp_path):
    from autocut import ffmpeg

    res = trim(fixtures["cam"], tmp_path / "out.mp4")
    assert res.has_video
    info = ffmpeg.probe(res.output)
    assert info.has_video and info.has_audio
    assert abs(info.duration - res.trimmed_duration) < 0.3
