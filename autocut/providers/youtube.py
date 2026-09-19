"""Find clips on YouTube with yt-dlp and download only the section we need.

YouTube footage is generally NOT licensed for reuse; use this for content you
have rights to (your own channel, Creative Commons uploads via
``creative_commons=True``, or fair-use commentary).

YouTube sometimes answers downloads with "Sign in to confirm you're not a bot"
(common on cloud/datacenter IPs). Pass cookies to get around it:
``AUTOCUT_YT_COOKIES=/path/to/cookies.txt`` or ``AUTOCUT_YT_COOKIES_BROWSER=chrome``.
"""
from __future__ import annotations

import os
from pathlib import Path

from .. import ffmpeg

from ..models import ClipCandidate
from .base import ClipProvider, ProviderError


class YouTubeProvider(ClipProvider):
    name = "youtube"
    licensed = False

    def __init__(
        self,
        cache_dir: str | Path,
        *,
        max_video_duration: float = 15 * 60,
        start_fraction: float = 0.15,
        creative_commons: bool = False,
        max_height: int = 1080,
        duration_filter: str = "short",  # short (<4 min) | medium (4-20 min) | any
    ):
        self.duration_filter = duration_filter
        self.cache_dir = Path(cache_dir) / "youtube"
        self.max_video_duration = max_video_duration
        self.start_fraction = start_fraction
        self.creative_commons = creative_commons
        self.max_height = max_height

    def _ydl(self, **opts):
        import yt_dlp  # type: ignore

        base = {"quiet": True, "no_warnings": True, "noplaylist": True, "skip_download": True}
        base.update(self._auth_opts())
        base.update(opts)
        return yt_dlp.YoutubeDL(base)

    @staticmethod
    def _auth_opts() -> dict:
        opts: dict = {}
        cookies = os.environ.get("AUTOCUT_YT_COOKIES")
        browser = os.environ.get("AUTOCUT_YT_COOKIES_BROWSER")
        if cookies:
            opts["cookiefile"] = cookies
        elif browser:
            opts["cookiesfrombrowser"] = (browser,)
        return opts

    # YouTube's own "duration" search filters (the `sp` query parameter).
    _SP = {"short": "EgIYAQ%253D%253D", "medium": "EgIYAw%253D%253D", "any": ""}

    def _search_entries(self, q: str, limit: int) -> list[dict]:
        import urllib.parse

        sp = self._SP.get(self.duration_filter, "")
        url = f"https://www.youtube.com/results?search_query={urllib.parse.quote_plus(q)}" + (f"&sp={sp}" if sp else "")
        with self._ydl(extract_flat="in_playlist", playlist_items=f"1-{limit}") as ydl:
            info = ydl.extract_info(url, download=False)
        entries = [e for e in ((info or {}).get("entries") or []) if e and e.get("id")]
        if not entries:  # fall back to the plain search extractor
            with self._ydl(extract_flat="in_playlist") as ydl:
                info = ydl.extract_info(f"ytsearch{limit}:{q}", download=False)
            entries = [e for e in ((info or {}).get("entries") or []) if e and e.get("id")]
        return entries

    def search(self, query: str, *, min_duration: float, orientation: str, limit: int = 10) -> list[ClipCandidate]:
        q = query + (" creative commons" if self.creative_commons else "")
        if orientation == "portrait":
            q += " #shorts"
        try:
            entries = self._search_entries(q, limit * 2)
        except Exception as exc:  # network / extractor errors
            raise ProviderError(f"youtube search failed: {exc}") from exc
        out: list[ClipCandidate] = []
        for e in entries:
            dur = float(e.get("duration") or 0)
            if dur and (dur < min_duration or dur > self.max_video_duration):
                continue
            if e.get("live_status") in ("is_live", "is_upcoming"):
                continue
            out.append(
                ClipCandidate(
                    provider=self.name,
                    id=e["id"],
                    title=e.get("title", ""),
                    url=e.get("url") or f"https://www.youtube.com/watch?v={e['id']}",
                    download_url=f"https://www.youtube.com/watch?v={e['id']}",
                    duration=dur,
                    width=int(e.get("width") or 0),
                    height=int(e.get("height") or 0),
                    tags=[],
                    author=e.get("uploader") or e.get("channel") or "",
                    license="unknown (YouTube)",
                )
            )
            if len(out) >= limit:
                break
        return out

    def download(self, candidate: ClipCandidate, dest_dir: Path, *, needed_duration: float) -> Path:
        """Download a section slightly longer than needed, starting a bit into the video (skips intros)."""
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        length = needed_duration + 2.0
        start = 0.0
        if candidate.duration:
            start = min(candidate.duration * self.start_fraction, max(0.0, candidate.duration - length))
        dest = self.cache_dir / f"{candidate.id}_{int(start)}_{int(length)}.mp4"
        if dest.exists():
            return dest
        try:
            import yt_dlp  # type: ignore
            from yt_dlp.utils import download_range_func  # type: ignore

            opts = {
                "quiet": True,
                "no_warnings": True,
                "noplaylist": True,
                "format": f"bestvideo[height<={self.max_height}][ext=mp4]+bestaudio[ext=m4a]/best[height<={self.max_height}][ext=mp4]/best",
                "outtmpl": str(dest.with_suffix("")) + ".%(ext)s",
                "download_ranges": download_range_func(None, [(start, start + length)]),
                "force_keyframes_at_cuts": True,
                "merge_output_format": "mp4",
                "ffmpeg_location": str(Path(ffmpeg.ffmpeg_bin()).parent),
            }
            opts.update(self._auth_opts())
            with yt_dlp.YoutubeDL(opts) as ydl:
                ydl.download([candidate.download_url])
        except Exception as exc:
            raise ProviderError(f"youtube download failed for {candidate.id}: {exc}") from exc
        if not dest.exists():
            # yt-dlp may pick a different extension
            matches = list(self.cache_dir.glob(dest.stem + ".*"))
            if not matches:
                raise ProviderError(f"youtube download produced no file for {candidate.id}")
            return matches[0]
        return dest
