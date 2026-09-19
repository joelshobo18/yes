"""Pixabay video API (free). https://pixabay.com/api/docs/#api_search_videos"""
from __future__ import annotations

from pathlib import Path

import requests

from ..models import ClipCandidate
from .base import ClipProvider, ProviderError

API = "https://pixabay.com/api/videos/"


class PixabayProvider(ClipProvider):
    name = "pixabay"
    licensed = True

    def __init__(self, api_key: str, cache_dir: str | Path, prefer: str = "medium"):
        if not api_key:
            raise ProviderError("PIXABAY_API_KEY is required")
        self.api_key = api_key
        self.cache_dir = Path(cache_dir) / "pixabay"
        self.prefer = prefer

    def search(self, query: str, *, min_duration: float, orientation: str, limit: int = 10) -> list[ClipCandidate]:
        params = {"key": self.api_key, "q": query, "per_page": max(limit, 3), "safesearch": "true"}
        r = requests.get(API, params=params, timeout=30)
        if r.status_code != 200:
            raise ProviderError(f"pixabay search failed: {r.status_code} {r.text[:200]}")
        out: list[ClipCandidate] = []
        for h in r.json().get("hits", []):
            videos = h.get("videos") or {}
            v = videos.get(self.prefer) or videos.get("large") or videos.get("small") or videos.get("tiny")
            if not v or not v.get("url"):
                continue
            w, hgt = int(v.get("width") or 0), int(v.get("height") or 0)
            cand_orient = "landscape" if w > hgt else "portrait" if w < hgt else "square"
            if orientation in ("portrait", "landscape", "square") and cand_orient != orientation:
                continue  # pixabay has no orientation filter, do it client side
            out.append(
                ClipCandidate(
                    provider=self.name,
                    id=str(h["id"]),
                    title=h.get("tags", ""),
                    url=h.get("pageURL", ""),
                    download_url=v["url"],
                    duration=float(h.get("duration") or 0),
                    width=w,
                    height=hgt,
                    tags=[t.strip() for t in (h.get("tags") or "").split(",") if t.strip()],
                    author=h.get("user", ""),
                    license="Pixabay Content License",
                )
            )
        return out[:limit]

    def download(self, candidate: ClipCandidate, dest_dir: Path, *, needed_duration: float) -> Path:
        dest = self.cache_dir / f"{candidate.id}.mp4"
        return self._download_file(candidate.download_url, dest)
