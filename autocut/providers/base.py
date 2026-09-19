from __future__ import annotations

from pathlib import Path

import requests

from ..models import ClipCandidate


class ProviderError(RuntimeError):
    pass


class ClipProvider:
    name = "base"
    #: whether the provider returns footage the user has rights to use (stock sites) vs. arbitrary web video
    licensed = True

    def search(self, query: str, *, min_duration: float, orientation: str, limit: int = 10) -> list[ClipCandidate]:
        raise NotImplementedError

    def download(self, candidate: ClipCandidate, dest_dir: Path, *, needed_duration: float) -> Path:
        raise NotImplementedError

    # helpers ------------------------------------------------------------
    @staticmethod
    def _download_file(url: str, dest: Path, headers: dict | None = None, timeout: int = 120) -> Path:
        dest.parent.mkdir(parents=True, exist_ok=True)
        if dest.exists() and dest.stat().st_size > 0:
            return dest
        tmp = dest.with_suffix(dest.suffix + ".part")
        with requests.get(url, stream=True, headers=headers or {}, timeout=timeout) as r:
            r.raise_for_status()
            with open(tmp, "wb") as fh:
                for chunk in r.iter_content(chunk_size=1 << 16):
                    if chunk:
                        fh.write(chunk)
        tmp.rename(dest)
        return dest
