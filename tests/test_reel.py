from autocut.reel import Chunk, _parse_markup, time_chunks, _crop_expr, Segment

COLORS = {"white": "#FFFFFF", "green": "#3CFF3C", "yellow": "#FFE01B", "red": "#FF2B2B"}
WORDS = [
    {"w": "This", "s": 0.0, "e": 0.2}, {"w": "is", "s": 0.2, "e": 0.3}, {"w": "what", "s": 0.3, "e": 0.5},
    {"w": "fascia", "s": 0.5, "e": 0.8}, {"w": "training", "s": 0.8, "e": 1.1}, {"w": "will", "s": 1.1, "e": 1.3},
    {"w": "do.", "s": 1.3, "e": 1.5}, {"w": "By", "s": 3.7, "e": 3.8}, {"w": "day", "s": 3.8, "e": 4.0},
    {"w": "30,", "s": 4.0, "e": 4.4}, {"w": "your", "s": 4.6, "e": 4.7}, {"w": "shots", "s": 4.7, "e": 5.0},
]


def test_parse_markup_colours_words():
    out = _parse_markup("BY #DAY 30# you're *comfortable* !not!", COLORS)
    assert out == [("BY", "#FFFFFF"), ("DAY", "#FFE01B"), ("30", "#FFE01B"), ("you're", "#FFFFFF"), ("comfortable", "#3CFF3C"), ("not", "#FF2B2B")]


def test_time_chunks_matches_in_order_and_skips_hook():
    chunks = [Chunk("BY #DAY THIRTY#"), Chunk("YOUR SHOTS")]  # first chunk skips the hook sentence
    timed = time_chunks(chunks, WORDS, COLORS)
    assert timed[0].start == 3.7 and abs(timed[0].end - (4.6 - 0.02)) < 1e-6  # held until next chunk
    assert timed[1].start == 4.6 and timed[1].end > 5.0


def test_crop_expr_positions_window():
    seg = Segment("x", 0, 1, crop="x=0.62")
    assert _crop_expr(seg, 1920, 1080) == "crop=607:1080:886:0"
    assert _crop_expr(Segment("x", 0, 1), 1920, 1080) == "crop=607:1080:656:0"
    assert _crop_expr(Segment("x", 0, 1), 720, 1280) == "crop=720:1280:0:0"
