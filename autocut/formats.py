"""Format specs: the output "shape" a render must match (canvas, pacing, layout, captions, audio)."""
from __future__ import annotations

import copy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml

BUILTIN_DIR = Path(__file__).parent / "formats"

DEFAULT_SPEC: dict[str, Any] = {
    "name": "custom",
    "description": "",
    "canvas": {"width": 1080, "height": 1920, "fps": 30},
    "layout": "broll",  # broll | split | pip | camera
    "pacing": {"min_scene": 2.0, "target_scene": 4.0, "max_scene": 7.0},
    "max_duration": None,
    "clips": {
        "orientation": "auto",  # auto | portrait | landscape | square | any
        "providers": ["local", "pexels", "pixabay", "youtube"],
        "min_clip_duration": 2.0,
        "allow_images": True,
        "avoid_repeat_within": 3,
    },
    "captions": {
        "enabled": True,
        "mode": "word",  # word | line | none
        "font": "DejaVu Sans",
        "size": 72,
        "bold": True,
        "color": "#FFFFFF",
        "highlight_color": "#FFD400",
        "outline_color": "#000000",
        "outline": 4,
        "shadow": 0,
        "position": "center",  # top | center | bottom
        "margin_v": 120,
        "max_words": 4,
        "max_chars": 20,
        "uppercase": True,
    },
    "audio": {
        "loudnorm": True,
        "target_lufs": -14,
        "music": None,
        "music_volume": 0.12,
        "voice_volume": 1.0,
    },
    "intro": None,
    "outro": None,
    "encode": {"codec": "libx264", "crf": 20, "preset": "medium", "audio_bitrate": "192k", "pix_fmt": "yuv420p"},
}


def _deep_merge(base: dict, override: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


@dataclass
class FormatSpec:
    raw: dict[str, Any] = field(default_factory=lambda: copy.deepcopy(DEFAULT_SPEC))

    # convenient accessors --------------------------------------------
    @property
    def name(self) -> str:
        return self.raw.get("name", "custom")

    @property
    def width(self) -> int:
        return int(self.raw["canvas"]["width"])

    @property
    def height(self) -> int:
        return int(self.raw["canvas"]["height"])

    @property
    def fps(self) -> int:
        return int(self.raw["canvas"]["fps"])

    @property
    def layout(self) -> str:
        return self.raw.get("layout", "broll")

    @property
    def pacing(self) -> dict[str, float]:
        return self.raw["pacing"]

    @property
    def clips(self) -> dict[str, Any]:
        return self.raw["clips"]

    @property
    def captions(self) -> dict[str, Any]:
        return self.raw["captions"]

    @property
    def audio(self) -> dict[str, Any]:
        return self.raw["audio"]

    @property
    def encode(self) -> dict[str, Any]:
        return self.raw["encode"]

    @property
    def max_duration(self) -> float | None:
        v = self.raw.get("max_duration")
        return float(v) if v else None

    @property
    def orientation(self) -> str:
        """Orientation clips should have. 'auto' derives it from the canvas / layout."""
        o = self.clips.get("orientation", "auto")
        if o != "auto":
            return o
        w, h = self.broll_size()
        if w > h:
            return "landscape"
        if w < h:
            return "portrait"
        return "square"

    def broll_size(self) -> tuple[int, int]:
        """Pixel size b-roll occupies on the canvas for the current layout."""
        if self.layout == "split":
            return self.width, self.height // 2
        return self.width, self.height

    def __getitem__(self, key: str) -> Any:
        return self.raw[key]


def list_builtin() -> list[str]:
    return sorted(p.stem for p in BUILTIN_DIR.glob("*.yaml"))


def load_format(name_or_path: str | Path | None, overrides: dict | None = None) -> FormatSpec:
    """Load a format by built-in name (``tiktok``) or YAML path; ``overrides`` are deep-merged on top."""
    spec = copy.deepcopy(DEFAULT_SPEC)
    if name_or_path:
        p = Path(name_or_path)
        if not p.exists():
            candidate = BUILTIN_DIR / f"{name_or_path}.yaml"
            if not candidate.exists():
                raise FileNotFoundError(
                    f"Unknown format '{name_or_path}'. Built-ins: {', '.join(list_builtin())} or pass a YAML path."
                )
            p = candidate
        data = yaml.safe_load(p.read_text()) or {}
        if "extends" in data:
            parent = load_format(data.pop("extends")).raw
            spec = _deep_merge(spec, parent)
        spec = _deep_merge(spec, data)
        spec.setdefault("name", p.stem)
        if spec.get("name") == "custom":
            spec["name"] = p.stem
    if overrides:
        spec = _deep_merge(spec, overrides)
    return FormatSpec(spec)
