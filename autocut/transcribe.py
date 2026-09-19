"""Word-timed transcription with several backends.

Backends (``backend=`` argument):
  auto            faster-whisper if installed, else openai-whisper, else error.
  faster-whisper  https://github.com/SYSTRAN/faster-whisper (pip install faster-whisper)
  whisper         openai-whisper (pip install openai-whisper)
  srt             read an existing .srt (words are spread evenly inside each cue)
  script          align plain text you already have to the audio duration (proportional)
  none            a single empty segment; scenes are then cut by fixed length
"""
from __future__ import annotations

import re
from pathlib import Path

from . import ffmpeg
from .models import TranscriptSegment, Word

_SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]*")


def transcribe(
    audio_path: str | Path,
    *,
    backend: str = "auto",
    model_size: str = "base",
    language: str | None = None,
    script_text: str | None = None,
    srt_path: str | Path | None = None,
) -> list[TranscriptSegment]:
    duration = ffmpeg.probe(audio_path).duration
    if srt_path:
        backend = "srt"
    elif script_text is not None:
        backend = "script"

    if backend == "auto":
        try:
            import faster_whisper  # noqa: F401

            backend = "faster-whisper"
        except ImportError:
            try:
                import whisper  # noqa: F401

                backend = "whisper"
            except ImportError as exc:
                raise RuntimeError(
                    "No speech-to-text backend installed. `pip install faster-whisper`, or pass --script / --srt, "
                    "or use --transcriber none."
                ) from exc

    if backend == "faster-whisper":
        return _faster_whisper(audio_path, model_size, language)
    if backend == "whisper":
        return _openai_whisper(audio_path, model_size, language)
    if backend == "srt":
        return parse_srt(Path(srt_path).read_text(encoding="utf-8"))
    if backend == "script":
        return align_script(script_text or "", duration)
    if backend == "none":
        return [TranscriptSegment(text="", start=0.0, end=duration, words=[])]
    raise ValueError(f"Unknown transcription backend: {backend}")


# --- ML backends ----------------------------------------------------------

def _faster_whisper(path, model_size, language):
    from faster_whisper import WhisperModel  # type: ignore

    model = WhisperModel(model_size, device="auto", compute_type="auto")
    segments, _info = model.transcribe(str(path), word_timestamps=True, language=language, vad_filter=True)
    out: list[TranscriptSegment] = []
    for seg in segments:
        words = [Word(w.word.strip(), float(w.start), float(w.end)) for w in (seg.words or []) if w.word.strip()]
        out.append(TranscriptSegment(seg.text.strip(), float(seg.start), float(seg.end), words))
    return split_sentences(out)


def _openai_whisper(path, model_size, language):
    import whisper  # type: ignore

    model = whisper.load_model(model_size)
    result = model.transcribe(str(path), word_timestamps=True, language=language)
    out: list[TranscriptSegment] = []
    for seg in result["segments"]:
        words = [Word(w["word"].strip(), float(w["start"]), float(w["end"])) for w in seg.get("words", []) if w["word"].strip()]
        out.append(TranscriptSegment(seg["text"].strip(), float(seg["start"]), float(seg["end"]), words))
    return split_sentences(out)


# --- text based backends ---------------------------------------------------

_SRT_TIME = re.compile(r"(\d+):(\d+):(\d+)[,.](\d+)\s*-->\s*(\d+):(\d+):(\d+)[,.](\d+)")


def parse_srt(text: str) -> list[TranscriptSegment]:
    segs: list[TranscriptSegment] = []
    for block in re.split(r"\n\s*\n", text.strip()):
        lines = [l.strip() for l in block.splitlines() if l.strip()]
        if len(lines) < 2:
            continue
        m = _SRT_TIME.search(lines[1] if _SRT_TIME.search(lines[1]) else lines[0])
        if not m:
            continue
        h1, m1, s1, ms1, h2, m2, s2, ms2 = (int(x) for x in m.groups())
        start = h1 * 3600 + m1 * 60 + s1 + ms1 / 1000
        end = h2 * 3600 + m2 * 60 + s2 + ms2 / 1000
        body_lines = lines[2:] if _SRT_TIME.search(lines[1]) else lines[1:]
        body = re.sub(r"<[^>]+>", "", " ".join(body_lines)).strip()
        if body:
            segs.append(TranscriptSegment(body, start, end, spread_words(body, start, end)))
    return segs


def spread_words(text: str, start: float, end: float) -> list[Word]:
    """Distribute words evenly across [start, end], weighted by word length."""
    tokens = text.split()
    if not tokens:
        return []
    weights = [len(t) + 1 for t in tokens]
    total = float(sum(weights))
    words: list[Word] = []
    t = start
    for tok, w in zip(tokens, weights):
        dur = (end - start) * (w / total)
        words.append(Word(tok, t, t + dur))
        t += dur
    return words


def align_script(text: str, duration: float) -> list[TranscriptSegment]:
    """Proportionally align a script to the audio duration, one segment per sentence."""
    sentences = [s.strip() for s in _SENTENCE_RE.findall(text) if s.strip()]
    if not sentences:
        return [TranscriptSegment("", 0.0, duration, [])]
    weights = [len(s) + 4 for s in sentences]
    total = float(sum(weights))
    out: list[TranscriptSegment] = []
    t = 0.0
    for s, w in zip(sentences, weights):
        dur = duration * (w / total)
        out.append(TranscriptSegment(s, t, t + dur, spread_words(s, t, t + dur)))
        t += dur
    return out


def split_sentences(segments: list[TranscriptSegment]) -> list[TranscriptSegment]:
    """Re-cut word-timed segments on sentence punctuation so scenes align with sentences."""
    out: list[TranscriptSegment] = []
    for seg in segments:
        if not seg.words:
            out.append(seg)
            continue
        buf: list[Word] = []
        for w in seg.words:
            buf.append(w)
            if w.text.rstrip().endswith((".", "!", "?")):
                out.append(TranscriptSegment(" ".join(x.text for x in buf), buf[0].start, buf[-1].end, list(buf)))
                buf = []
        if buf:
            out.append(TranscriptSegment(" ".join(x.text for x in buf), buf[0].start, buf[-1].end, list(buf)))
    return out


def to_srt(segments: list[TranscriptSegment]) -> str:
    def fmt(t: float) -> str:
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02d}:{ms // 60000 % 60:02d}:{ms // 1000 % 60:02d},{ms % 1000:03d}"

    return "\n".join(f"{i}\n{fmt(s.start)} --> {fmt(s.end)}\n{s.text}\n" for i, s in enumerate(segments, 1))
