from autocut.captions import ass_color, ass_time, build_ass, chunk_words
from autocut.formats import load_format
from autocut.models import TranscriptSegment, Word
from autocut.scenes import build_scenes, keywords, make_query
from autocut.transcribe import align_script, parse_srt, split_sentences


def test_keywords_drop_stopwords():
    assert keywords("the city traffic never stops at night in the city") == ["city", "traffic", "never"]
    assert keywords("") == []


def test_make_query_appends_topic_once():
    assert make_query(["ocean", "waves"], "beach") == "ocean waves beach"
    assert make_query(["beach", "waves"], "beach") == "beach waves"
    assert make_query([], "") == "abstract background"


def test_align_script_covers_duration():
    segs = align_script("One sentence. Another one here! Third?", 9.0)
    assert len(segs) == 3
    assert segs[0].start == 0.0 and abs(segs[-1].end - 9.0) < 1e-6
    assert all(s.words for s in segs)


def test_parse_srt():
    srt = "1\n00:00:00,000 --> 00:00:02,500\nHello <i>there</i>\n\n2\n00:00:02,500 --> 00:00:04,000\nWorld\n"
    segs = parse_srt(srt)
    assert [s.text for s in segs] == ["Hello there", "World"]
    assert segs[1].start == 2.5 and segs[1].end == 4.0


def test_split_sentences_recuts_on_punctuation():
    words = [Word("Hi.", 0, 0.5), Word("Bye", 0.6, 1.0), Word("now.", 1.0, 1.4)]
    segs = split_sentences([TranscriptSegment("Hi. Bye now.", 0, 1.4, words)])
    assert [s.text for s in segs] == ["Hi.", "Bye now."]


def test_build_scenes_respects_pacing():
    segs = align_script(" ".join(f"Sentence number {i} talks about topic {i}." for i in range(12)), 36.0)
    scenes = build_scenes(segs, 36.0, min_scene=2, target_scene=4, max_scene=7)
    assert scenes[0].start == 0.0 and abs(scenes[-1].end - 36.0) < 1e-6
    for a, b in zip(scenes, scenes[1:]):
        assert abs(a.end - b.start) < 1e-6  # contiguous
    assert all(2.0 <= s.duration <= 7.0 + 1e-6 for s in scenes)
    assert all(s.query for s in scenes)


def test_build_scenes_without_transcript_uses_fixed_slices():
    scenes = build_scenes([], 10.0, min_scene=2, target_scene=4, max_scene=6)
    assert [(s.start, s.end) for s in scenes] == [(0.0, 4.0), (4.0, 8.0), (8.0, 10.0)]


def test_ass_helpers():
    assert ass_color("#FFD400") == "&H0000D4FF"
    assert ass_time(61.234) == "0:01:01.23"


def test_chunk_words_limits():
    words = [Word(f"w{i}", i * 0.3, i * 0.3 + 0.25) for i in range(10)]
    chunks = chunk_words(words, max_words=3, max_chars=100)
    assert [len(c.words) for c in chunks] == [3, 3, 3, 1]
    assert chunks[0].end == chunks[1].start  # held until the next chunk starts


def test_build_ass_word_mode_highlights_each_word():
    spec = load_format("tiktok")
    segs = align_script("Hello big world.", 3.0)
    ass = build_ass(segs, spec)
    assert "PlayResX: 1080" in ass
    dialogues = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogues) == 3
    assert "{\\c&H0000D4FF}HELLO{\\c&H00FFFFFF}" in dialogues[0]


def test_build_ass_line_mode():
    spec = load_format("youtube")
    segs = align_script("Hello big world.", 3.0)
    ass = build_ass(segs, spec)
    dialogues = [l for l in ass.splitlines() if l.startswith("Dialogue:")]
    assert len(dialogues) == 1 and dialogues[0].endswith(",Hello big world.")
