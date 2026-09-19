"""Thin wrapper around the ffmpeg binary.

ffprobe is not always available (the static build shipped by imageio-ffmpeg has
none), so media probing parses ffmpeg's own ``-i`` banner instead.
"""
from __future__ import annotations

import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Sequence


class FFmpegError(RuntimeError):
    pass


@lru_cache(maxsize=1)
def ffmpeg_bin() -> str:
    """Locate ffmpeg: $AUTOCUT_FFMPEG, then PATH, then the imageio-ffmpeg wheel."""
    env = os.environ.get("AUTOCUT_FFMPEG")
    if env and Path(env).exists():
        return env
    found = shutil.which("ffmpeg")
    if found:
        return found
    try:
        import imageio_ffmpeg  # type: ignore

        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:  # pragma: no cover - depends on environment
        raise FFmpegError(
            "ffmpeg not found. Install ffmpeg, set AUTOCUT_FFMPEG, or `pip install imageio-ffmpeg`."
        ) from exc


def run(args: Sequence[str], *, check: bool = True, quiet: bool = True) -> subprocess.CompletedProcess:
    """Run ffmpeg with ``args`` (everything after the binary name)."""
    cmd = [ffmpeg_bin(), "-hide_banner", "-nostdin"]
    if quiet:
        cmd += ["-loglevel", "error"]
    cmd += list(args)
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if check and proc.returncode != 0:
        tail = "\n".join(proc.stderr.strip().splitlines()[-25:])
        raise FFmpegError(f"ffmpeg failed ({proc.returncode}): {' '.join(cmd)}\n{tail}")
    return proc


@dataclass
class MediaInfo:
    path: str
    duration: float
    has_video: bool
    has_audio: bool
    width: int = 0
    height: int = 0
    fps: float = 0.0
    is_image: bool = False

    @property
    def orientation(self) -> str:
        if not self.width or not self.height:
            return "unknown"
        if self.width > self.height:
            return "landscape"
        if self.width < self.height:
            return "portrait"
        return "square"


_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_RE = re.compile(r"Stream #\d+:\d+.*?:\s*Video:\s*(.*)")
_AUDIO_RE = re.compile(r"Stream #\d+:\d+.*?:\s*Audio:")
_SIZE_RE = re.compile(r"\b(\d{2,5})x(\d{2,5})\b")
_FPS_RE = re.compile(r"([\d.]+)\s*fps")

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".gif", ".tif", ".tiff"}
VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".mts", ".ts"}
AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg", ".opus", ".wma"}
MEDIA_EXTS = IMAGE_EXTS | VIDEO_EXTS | AUDIO_EXTS


def probe(path: str | os.PathLike) -> MediaInfo:
    """Return duration / stream info for a media file by parsing ffmpeg's banner."""
    path = str(path)
    if not Path(path).exists():
        raise FileNotFoundError(path)
    proc = run(["-i", path], check=False, quiet=False)
    text = proc.stderr
    duration = 0.0
    m = _DURATION_RE.search(text)
    if m:
        duration = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))
    has_audio = bool(_AUDIO_RE.search(text))
    width = height = 0
    fps = 0.0
    vm = _VIDEO_RE.search(text)
    has_video = vm is not None
    if vm:
        line = vm.group(1)
        sm = _SIZE_RE.search(line)
        if sm:
            width, height = int(sm.group(1)), int(sm.group(2))
        fm = _FPS_RE.search(line)
        if fm:
            try:
                fps = float(fm.group(1))
            except ValueError:
                fps = 0.0
    is_image = Path(path).suffix.lower() in IMAGE_EXTS or (has_video and duration == 0.0 and not has_audio)
    return MediaInfo(path, duration, has_video, has_audio, width, height, fps, is_image)


def escape_filter_path(path: str) -> str:
    """Escape a filesystem path for use inside an ffmpeg filter argument (e.g. ass=...)."""
    out = path.replace("\\", "/")
    for ch in ["'", ":", "[", "]", ",", ";"]:
        out = out.replace(ch, "\\" + ch)
    return out
