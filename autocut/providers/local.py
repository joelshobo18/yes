"""Use the user's own asset folder as a clip source.

Files are tagged by their filename tokens (``city_traffic_night.mp4`` -> city, traffic, night)
plus optional sidecars: ``<file>.txt`` (free text) or a folder-level ``tags.json``
mapping filename -> list of tags.
"""
from __future__ import annotations

import json
import re
from pathlib import Path

from .. import ffmpeg
from ..models import ClipCandidate
from ..scenes import STOPWORDS
from .base import ClipProvider

_TOK = re.compile(r"[a-zA-Z]+")


class LocalProvider(ClipProvider):
    name = "local"
    licensed = True

    def __init__(self, root: str | Path):
        self.root = Path(root)
        self._index: list[ClipCandidate] | None = None

    def _build_index(self) -> list[ClipCandidate]:
        tags_file = self.root / "tags.json"
        extra_tags: dict[str, list[str]] = {}
        if tags_file.exists():
            try:
                extra_tags = {k: [str(t).lower() for t in v] for k, v in json.loads(tags_file.read_text()).items()}
            except Exception:
                extra_tags = {}
        out: list[ClipCandidate] = []
        for p in sorted(self.root.rglob("*")):
            if not p.is_file() or p.suffix.lower() not in (ffmpeg.VIDEO_EXTS | ffmpeg.IMAGE_EXTS):
                continue
            tags = {t.lower() for t in _TOK.findall(p.stem)} - STOPWORDS
            sidecar = p.with_suffix(p.suffix + ".txt")
            if sidecar.exists():
                tags |= {t.lower() for t in _TOK.findall(sidecar.read_text())} - STOPWORDS
            tags |= set(extra_tags.get(p.name, [])) | set(extra_tags.get(str(p.relative_to(self.root)), []))
            try:
                info = ffmpeg.probe(p)
            except Exception:
                continue
            out.append(
                ClipCandidate(
                    provider=self.name,
                    id=str(p.relative_to(self.root)),
                    title=p.stem.replace("_", " ").replace("-", " "),
                    url=str(p),
                    download_url=str(p),
                    duration=info.duration,
                    width=info.width,
                    height=info.height,
                    tags=sorted(tags),
                    license="own",
                    extra={"is_image": info.is_image},
                )
            )
        return out

    @property
    def index(self) -> list[ClipCandidate]:
        if self._index is None:
            self._index = self._build_index()
        return self._index

    def search(self, query: str, *, min_duration: float, orientation: str, limit: int = 10) -> list[ClipCandidate]:
        q = {t.lower() for t in _TOK.findall(query)} - STOPWORDS
        scored: list[tuple[int, ClipCandidate]] = []
        for c in self.index:
            hits = len(q & set(c.tags)) + sum(1 for t in q if any(t in tag or tag in t for tag in c.tags))
            if hits:
                scored.append((hits, c))
        scored.sort(key=lambda x: -x[0])
        return [c for _, c in scored[:limit]]

    def download(self, candidate: ClipCandidate, dest_dir: Path, *, needed_duration: float) -> Path:
        return Path(candidate.download_url)
