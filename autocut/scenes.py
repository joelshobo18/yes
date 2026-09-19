"""Split a transcript into scenes and derive a search query for each."""
from __future__ import annotations

import json
import os
import re
from collections import Counter

from .models import Scene, TranscriptSegment, Word

STOPWORDS = set(
    """
a about above after again against all am an and any are aren't as at be because been before being below between both
but by can can't cannot could couldn't did didn't do does doesn't doing don't down during each few for from further had
hadn't has hasn't have haven't having he he'd he'll he's her here here's hers herself him himself his how how's i i'd
i'll i'm i've if in into is isn't it it's its itself let's me more most mustn't my myself no nor not of off on once only
or other ought our ours ourselves out over own same shan't she she'd she'll she's should shouldn't so some such than
that that's the their theirs them themselves then there there's these they they'd they'll they're they've this those
through to too under until up very was wasn't we we'd we'll we're we've were weren't what what's when when's where
where's which while who who's whom why why's with won't would wouldn't you you'd you'll you're you've your yours
yourself yourselves just like really actually basically literally thing things get got go going gonna wanna know
think mean okay ok yeah yes right also even still one two three lot lots make made way well much many every
""".split()
)

_TOKEN_RE = re.compile(r"[a-zA-Z][a-zA-Z'\-]+")


def tokenize(text: str) -> list[str]:
    return [t.lower().strip("'-") for t in _TOKEN_RE.findall(text)]


def keywords(text: str, n: int = 3) -> list[str]:
    """Top-n content words by frequency, ties broken by first appearance and length."""
    toks = [t for t in tokenize(text) if t not in STOPWORDS and len(t) >= 3]
    if not toks:
        return []
    counts = Counter(toks)
    first = {t: i for i, t in reversed(list(enumerate(toks)))}
    ranked = sorted(counts, key=lambda t: (-counts[t], first[t], -len(t)))
    return ranked[:n]


def _all_words(segments: list[TranscriptSegment]) -> list[Word]:
    out: list[Word] = []
    for s in segments:
        out.extend(s.words)
    return out


def build_scenes(
    segments: list[TranscriptSegment],
    duration: float,
    *,
    min_scene: float,
    target_scene: float,
    max_scene: float,
    topic: str = "",
) -> list[Scene]:
    """Group sentences into scenes of roughly ``target_scene`` seconds.

    Sentence boundaries are preferred; over-long sentences are split on words;
    with no transcript the timeline is cut into fixed slices.
    """
    scenes: list[Scene] = []
    if not segments or not any(s.text.strip() for s in segments):
        t = 0.0
        while t < duration - 1e-3:
            end = min(duration, t + target_scene)
            if duration - end < min_scene:  # absorb a tiny tail
                end = duration
            scenes.append(Scene(len(scenes), t, end))
            t = end
        return _finalise(scenes, topic)

    # 1) explode into atomic chunks no longer than max_scene
    atoms: list[TranscriptSegment] = []
    for seg in segments:
        if seg.duration <= max_scene or not seg.words:
            atoms.append(seg)
            continue
        buf: list[Word] = []
        for w in seg.words:
            if buf and (w.end - buf[0].start) > max_scene:
                atoms.append(TranscriptSegment(" ".join(x.text for x in buf), buf[0].start, buf[-1].end, list(buf)))
                buf = []
            buf.append(w)
        if buf:
            atoms.append(TranscriptSegment(" ".join(x.text for x in buf), buf[0].start, buf[-1].end, list(buf)))

    # 2) greedily merge atoms towards target length
    cur: list[TranscriptSegment] = []
    cur_start = 0.0
    for i, a in enumerate(atoms):
        if not cur:
            cur_start = a.start if not scenes else scenes[-1].end
        cur.append(a)
        span = a.end - cur_start
        nxt = atoms[i + 1] if i + 1 < len(atoms) else None
        close = span >= target_scene or nxt is None or (nxt.end - cur_start) > max_scene
        if close:
            end = nxt.start if nxt is not None else duration
            scenes.append(Scene(len(scenes), cur_start, end, " ".join(x.text for x in cur)))
            cur = []
    if scenes:
        scenes[0].start = 0.0
        scenes[-1].end = max(scenes[-1].end, duration)

    # 3) absorb scenes that ended up too short into their neighbour
    merged: list[Scene] = []
    for s in scenes:
        if merged and (s.duration < min_scene or merged[-1].duration < min_scene) and (s.end - merged[-1].start) <= max_scene * 1.5:
            merged[-1].end = s.end
            merged[-1].text = (merged[-1].text + " " + s.text).strip()
        else:
            merged.append(s)
    for i, s in enumerate(merged):
        s.index = i
    return _finalise(merged, topic)


def _finalise(scenes: list[Scene], topic: str) -> list[Scene]:
    for s in scenes:
        s.keywords = keywords(s.text)
        s.query = make_query(s.keywords, topic)
    return scenes


def make_query(kws: list[str], topic: str = "") -> str:
    parts = list(kws)
    if topic and topic.lower() not in " ".join(parts):
        parts.append(topic)
    return " ".join(parts).strip() or topic or "abstract background"


# --- optional: Claude generates better stock-footage queries ----------------

def claude_available() -> bool:
    try:
        import anthropic  # noqa: F401
    except ImportError:
        return False
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def refine_queries_with_claude(scenes: list[Scene], topic: str = "", model: str | None = None) -> list[Scene]:
    """Ask Claude for one visual stock-footage query per scene. Falls back silently on any error."""
    import anthropic

    model = model or os.environ.get("AUTOCUT_CLAUDE_MODEL", "claude-opus-5")
    client = anthropic.Anthropic()
    lines = "\n".join(f"{s.index}: {s.text or '(no speech)'}" for s in scenes)
    schema = {
        "type": "object",
        "properties": {
            "queries": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {"index": {"type": "integer"}, "query": {"type": "string"}},
                    "required": ["index", "query"],
                    "additionalProperties": False,
                },
            }
        },
        "required": ["queries"],
        "additionalProperties": False,
    }
    prompt = (
        "You write search queries for stock-footage sites (Pexels, Pixabay) and YouTube to find b-roll that "
        "visually matches each line of a voice-over. For every scene index give one concrete, visual, 2-5 word query "
        "(objects, places, actions - not abstract concepts). "
        + (f"The overall video topic is: {topic}.\n\n" if topic else "\n\n")
        + "Scenes:\n"
        + lines
    )
    response = client.messages.create(
        model=model,
        max_tokens=4096,
        messages=[{"role": "user", "content": prompt}],
        output_config={"format": {"type": "json_schema", "schema": schema}},
    )
    if response.stop_reason == "refusal":
        return scenes
    text = next(b.text for b in response.content if b.type == "text")
    data = json.loads(text)
    by_index = {int(q["index"]): q["query"].strip() for q in data.get("queries", []) if q.get("query")}
    for s in scenes:
        if s.index in by_index:
            s.query = by_index[s.index]
    return scenes
