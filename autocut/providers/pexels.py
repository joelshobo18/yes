"""Pexels video API (free, attribution appreciated). https://www.pexels.com/api/"""
from __future__ import annotations

from pathlib import Path

import requests

from ..models import ClipCandidate
from .base import ClipProvider, ProviderError

API = "https://api.pexels.com/videos/search"


class PexelsProvider(ClipProvider):
    name = "pexels"
    licensed = True

    def __init__(self, api_key: str, cache_dir: str | Path, target_height: int = 1080):
        if not api_key:
            raise ProviderError("PEXELS_API_KEY is required")
        self.api_key = api_key
        self.cache_dir = Path(cache_dir) / "pexels"
        self.target_height = target_height

    def search(self, query: str, *, min_duration: float, orientation: str, limit: int = 10) -> list[ClipCandidate]:
        params = {"query": query, "per_page": max(limit, 5), "size": "medium"}
        if orientation in ("portrait", "landscape", "square"):
            params["orientation"] = orientation
        r = requests.get(API, params=params, headers={"Authorization": self.api_key}, timeout=30)
        if r.status_code != 200:
            raise ProviderError(f"pexels search failed: {r.status_code} {r.text[:200]}")
        out: list[ClipCandidate] = []
        for v in r.json().get("videos", []):
            files = [f for f in v.get("video_files", []) if f.get("link") and f.get("height")]
            if not files:
                continue
            best = min(files, key=lambda f: abs(int(f.get("height") or 0) - self.target_height))
            out.append(
                ClipCandidate(
                    provider=self.name,
                    id=str(v["id"]),
                    title=(v.get("url") or "").rstrip("/").split("/")[-1].replace("-", " "),
                    url=v.get("url", ""),
                    download_url=best["link"],
                    duration=float(v.get("duration") or 0),
                    width=int(best.get("width") or v.get("width") or 0),
                    height=int(best.get("height") or v.get("height") or 0),
                    tags=[t for t in (v.get("url") or "").rstrip("/").split("/")[-1].split("-") if t and not t.isdigit()],
                    author=(v.get("user") or {}).get("name", ""),
                    license="Pexels License",
                )
            )
        return out[:limit]

    def download(self, candidate: ClipCandidate, dest_dir: Path, *, needed_duration: float) -> Path:
        dest = self.cache_dir / f"{candidate.id}.mp4"
        return self._download_file(candidate.download_url, dest)
