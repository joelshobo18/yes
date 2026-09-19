"""Score clip candidates against a scene and pick the best one per scene."""
from __future__ import annotations

from pathlib import Path
from typing import Callable

from . import ffmpeg
from .formats import FormatSpec
from .models import ClipAssignment, ClipCandidate, Scene
from .providers import ClipProvider, ProviderError
from .scenes import STOPWORDS, tokenize

Logger = Callable[[str], None]


def relevance(query: str, candidate: ClipCandidate) -> float:
    """0..1 overlap between query terms and the candidate's title/tags."""
    q = {t for t in tokenize(query) if t not in STOPWORDS}
    if not q:
        return 0.0
    hay = set(candidate.tags) | set(tokenize(candidate.title))
    hits = 0.0
    for t in q:
        if t in hay:
            hits += 1.0
        elif any(t in h or h in t for h in hay if len(h) > 3):
            hits += 0.5
    return min(1.0, hits / len(q))


def duration_fit(needed: float, candidate: ClipCandidate, min_clip: float) -> float:
    d = candidate.duration
    if candidate.extra.get("is_image"):
        return 0.6  # images can be held for any length, but video is preferred
    if d <= 0:
        return 0.5  # unknown, assume fine
    if d >= needed:
        return 1.0 if d <= needed * 6 else 0.85  # very long clips are fine, just less "on point"
    if d < min_clip:
        return 0.1
    return 0.4 + 0.4 * (d / needed)  # will need looping


def orientation_fit(wanted: str, candidate: ClipCandidate) -> float:
    o = candidate.orientation
    if wanted == "any" or o == "unknown":
        return 0.8
    if o == wanted:
        return 1.0
    if "square" in (o, wanted):
        return 0.7
    return 0.4  # cropping landscape -> portrait loses most of the frame


def score(scene: Scene, candidate: ClipCandidate, spec: FormatSpec, recent: list[str], provider_rank: int) -> float:
    s = 0.45 * relevance(scene.query, candidate)
    s += 0.25 * duration_fit(scene.duration, candidate, float(spec.clips.get("min_clip_duration", 2.0)))
    s += 0.15 * orientation_fit(spec.orientation, candidate)
    s += 0.10 * max(0.0, 1.0 - provider_rank * 0.25)  # earlier providers in the format list are preferred
    if candidate.key in recent:
        s -= 0.5  # heavy penalty for repeating a clip within the last N scenes
    if candidate.height and candidate.height < 480:
        s -= 0.1
    return round(s, 4)


def find_clips(
    scenes: list[Scene],
    providers: list[ClipProvider],
    spec: FormatSpec,
    clips_dir: str | Path,
    *,
    per_provider: int = 6,
    log: Logger = print,
) -> list[ClipAssignment]:
    """For every scene search all providers, score, download the best and return assignments."""
    clips_dir = Path(clips_dir)
    clips_dir.mkdir(parents=True, exist_ok=True)
    avoid_n = int(spec.clips.get("avoid_repeat_within", 3))
    allow_images = bool(spec.clips.get("allow_images", True))
    wanted = spec.orientation
    assignments: list[ClipAssignment] = []
    used: list[str] = []
    search_cache: dict[tuple[str, str], list[ClipCandidate]] = {}

    for scene in scenes:
        log(f"scene {scene.index:02d} [{scene.start:6.2f}-{scene.end:6.2f}] query='{scene.query}'")
        recent = used[-avoid_n:] if avoid_n else []
        ranked: list[tuple[float, ClipCandidate, ClipProvider]] = []
        for rank, prov in enumerate(providers):
            key = (prov.name, scene.query)
            if key not in search_cache:
                try:
                    search_cache[key] = prov.search(
                        scene.query,
                        min_duration=float(spec.clips.get("min_clip_duration", 2.0)),
                        orientation=wanted,
                        limit=per_provider,
                    )
                except ProviderError as exc:
                    log(f"  [{prov.name}] {exc}")
                    search_cache[key] = []
                except Exception as exc:  # network etc.
                    log(f"  [{prov.name}] search error: {exc}")
                    search_cache[key] = []
            for c in search_cache[key]:
                if c.extra.get("is_image") and not allow_images:
                    continue
                ranked.append((score(scene, c, spec, recent, rank), c, prov))
        ranked.sort(key=lambda x: -x[0])

        chosen: ClipAssignment | None = None
        for sc, cand, prov in ranked[:5]:
            try:
                path = prov.download(cand, clips_dir, needed_duration=scene.duration)
            except Exception as exc:
                log(f"  [{prov.name}] download failed for {cand.id}: {exc}")
                continue
            info = ffmpeg.probe(path)
            if not info.has_video:
                continue
            is_image = info.is_image
            loop = (not is_image) and info.duration < scene.duration
            in_point = 0.0
            if not is_image and info.duration > scene.duration * 2 and prov.name != "youtube":
                in_point = round((info.duration - scene.duration) * 0.25, 2)  # skip the very start
            chosen = ClipAssignment(scene.index, str(path), in_point, cand, sc, loop, is_image)
            log(f"  -> {cand.provider}:{cand.id} score={sc:.2f} dur={info.duration:.1f}s {'(loop)' if loop else ''}")
            break
        if chosen is None:
            log("  -> no clip found, placeholder card will be rendered")
            chosen = ClipAssignment(scene.index, None, 0.0, None, 0.0, False, False)
        else:
            used.append(chosen.candidate.key if chosen.candidate else "")
        assignments.append(chosen)
    return assignments


def credits_text(assignments: list[ClipAssignment]) -> str:
    seen = set()
    lines = ["Footage credits", "==============="]
    for a in assignments:
        c = a.candidate
        if not c or c.key in seen or c.provider == "local":
            continue
        seen.add(c.key)
        who = f" by {c.author}" if c.author else ""
        lines.append(f"- {c.provider}: {c.title or c.id}{who} ({c.license}) {c.url}")
    return "\n".join(lines) + "\n"
