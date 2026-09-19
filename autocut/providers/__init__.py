"""Clip providers: places we can find footage that matches a scene."""
from __future__ import annotations

import os
from pathlib import Path

from .base import ClipProvider, ProviderError
from .local import LocalProvider
from .pexels import PexelsProvider
from .pixabay import PixabayProvider
from .youtube import YouTubeProvider

__all__ = ["ClipProvider", "ProviderError", "LocalProvider", "PexelsProvider", "PixabayProvider", "YouTubeProvider", "build_providers"]


def build_providers(names: list[str], *, assets_dir: str | Path | None, cache_dir: str | Path, log=print) -> list[ClipProvider]:
    """Instantiate the requested providers, skipping those that are not configured."""
    out: list[ClipProvider] = []
    for name in names:
        try:
            if name == "local":
                if assets_dir and Path(assets_dir).exists():
                    out.append(LocalProvider(assets_dir))
                else:
                    log("  [local] no assets directory, skipping")
            elif name == "pexels":
                key = os.environ.get("PEXELS_API_KEY")
                if key:
                    out.append(PexelsProvider(key, cache_dir))
                else:
                    log("  [pexels] PEXELS_API_KEY not set, skipping")
            elif name == "pixabay":
                key = os.environ.get("PIXABAY_API_KEY")
                if key:
                    out.append(PixabayProvider(key, cache_dir))
                else:
                    log("  [pixabay] PIXABAY_API_KEY not set, skipping")
            elif name == "youtube":
                try:
                    import yt_dlp  # noqa: F401

                    out.append(YouTubeProvider(cache_dir))
                except ImportError:
                    log("  [youtube] yt-dlp not installed (pip install yt-dlp), skipping")
            else:
                log(f"  unknown provider '{name}', skipping")
        except ProviderError as exc:
            log(f"  [{name}] {exc}")
    return out
