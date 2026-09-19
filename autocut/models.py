"""Data model shared by all pipeline stages. Everything is JSON-serialisable."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class TimeRange:
    start: float
    end: float

    @property
    def duration(self) -> float:
        return max(0.0, self.end - self.start)


@dataclass
class Word:
    text: str
    start: float
    end: float


@dataclass
class TranscriptSegment:
    text: str
    start: float
    end: float
    words: list[Word] = field(default_factory=list)

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class Scene:
    index: int
    start: float
    end: float
    text: str = ""
    keywords: list[str] = field(default_factory=list)
    query: str = ""

    @property
    def duration(self) -> float:
        return self.end - self.start


@dataclass
class ClipCandidate:
    provider: str
    id: str
    title: str = ""
    url: str = ""
    download_url: str = ""
    duration: float = 0.0
    width: int = 0
    height: int = 0
    tags: list[str] = field(default_factory=list)
    author: str = ""
    license: str = ""
    extra: dict[str, Any] = field(default_factory=dict)

    @property
    def key(self) -> str:
        return f"{self.provider}:{self.id}"

    @property
    def orientation(self) -> str:
        if not self.width or not self.height:
            return "unknown"
        if self.width > self.height:
            return "landscape"
        if self.width < self.height:
            return "portrait"
        return "square"


@dataclass
class ClipAssignment:
    scene_index: int
    path: str | None  # None -> placeholder card is rendered
    in_point: float = 0.0
    candidate: ClipCandidate | None = None
    score: float = 0.0
    loop: bool = False
    is_image: bool = False


@dataclass
class TrimResult:
    source: str
    output: str
    original_duration: float
    trimmed_duration: float
    keep_ranges: list[TimeRange]
    silences: list[TimeRange]
    has_video: bool


@dataclass
class Project:
    workdir: str
    source: str
    format_name: str
    trim: TrimResult | None = None
    transcript: list[TranscriptSegment] = field(default_factory=list)
    scenes: list[Scene] = field(default_factory=list)
    assignments: list[ClipAssignment] = field(default_factory=list)
    output: str | None = None
    topic: str = ""

    # ---- persistence -------------------------------------------------
    @property
    def path(self) -> Path:
        return Path(self.workdir) / "project.json"

    def save(self) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(asdict(self), indent=2))
        return self.path

    @classmethod
    def load(cls, workdir: str | Path) -> "Project":
        data = json.loads((Path(workdir) / "project.json").read_text())
        return cls.from_dict(data)

    @classmethod
    def from_dict(cls, d: dict[str, Any]) -> "Project":
        trim = None
        if d.get("trim"):
            t = d["trim"]
            trim = TrimResult(
                source=t["source"],
                output=t["output"],
                original_duration=t["original_duration"],
                trimmed_duration=t["trimmed_duration"],
                keep_ranges=[TimeRange(**r) for r in t["keep_ranges"]],
                silences=[TimeRange(**r) for r in t["silences"]],
                has_video=t["has_video"],
            )
        transcript = [
            TranscriptSegment(
                text=s["text"], start=s["start"], end=s["end"], words=[Word(**w) for w in s.get("words", [])]
            )
            for s in d.get("transcript", [])
        ]
        scenes = [Scene(**s) for s in d.get("scenes", [])]
        assignments = []
        for a in d.get("assignments", []):
            cand = ClipCandidate(**a["candidate"]) if a.get("candidate") else None
            assignments.append(
                ClipAssignment(
                    scene_index=a["scene_index"],
                    path=a.get("path"),
                    in_point=a.get("in_point", 0.0),
                    candidate=cand,
                    score=a.get("score", 0.0),
                    loop=a.get("loop", False),
                    is_image=a.get("is_image", False),
                )
            )
        return cls(
            workdir=d["workdir"],
            source=d["source"],
            format_name=d["format_name"],
            trim=trim,
            transcript=transcript,
            scenes=scenes,
            assignments=assignments,
            output=d.get("output"),
            topic=d.get("topic", ""),
        )

    # ---- helpers -----------------------------------------------------
    @property
    def timeline_duration(self) -> float:
        if self.trim:
            return self.trim.trimmed_duration
        return 0.0

    @property
    def trimmed_media(self) -> str:
        if not self.trim:
            raise RuntimeError("Run the trim stage first.")
        return self.trim.output
