"""@theart0fwar-style true-crime story: "The Story Of Amjad Ali" (rewritten script, same format).

Format (see STYLE.md): one still per beat with a slow push-in, cut on the keyword, 2-3 word centred captions in
The Bold Font (white, yellow = numbers/key nouns, green = names), black outline + shadow, no titles, no flashes,
dark vignette grade, voice-over only.

Usage:
    python examples/theartofwar/build_amjad_ali.py --img IMG_DIR --vo vo_fast.mp3 --words vo_fast_words.json \
        --fonts FONTS_DIR --work WORK --out amjad_ali.mp4
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autocut.reel import Chunk, ReelSpec, Segment, render

COLORS = {"white": "#FFFFFF", "green": "#3CFF3C", "yellow": "#FFE01B", "red": "#FF2B2B"}


def word_time(words: list[dict], text: str, nth: int = 1) -> float:
    """Start time of the nth occurrence of a word (case/punctuation-insensitive)."""
    import re

    key = re.sub(r"[^a-z0-9]", "", text.lower())
    n = 0
    for w in words:
        if re.sub(r"[^a-z0-9]", "", w["w"].lower()) == key:
            n += 1
            if n == nth:
                return float(w["s"])
    raise ValueError(f"word {text!r} #{nth} not found")


def build(args) -> ReelSpec:
    img = Path(args.img)
    words = json.loads(Path(args.words).read_text())
    total = float(args.total) if args.total else words[-1]["e"] + 0.6
    t = lambda w, n=1: word_time(words, w, n)

    # beat -> still image; each beat starts on the word that introduces it
    # (start word, image, push-in, fit): police photos are near-square -> 'contain' over a blurred copy, like the reference
    beats = [
        (0.0, "mug_a.png", 0.10, "contain"),                 # hook: mugshot
        (t("Amjad"), "mug_b.png", 0.08, "contain"),       # who he was: second framing of the mugshot
        (t("Every"), "sorting_centre.png", 0.10, "cover"),   # the sorting centre
        (t("Before"), "cannabis.png", 0.10, "contain"),      # the parcels were full of cannabis
        (t("Rather"), "mug_a.png", 0.08, "contain"),         # he robbed the dealers
        (t("scheme"), "storage_corridor.png", 0.10, "cover"),# the raid on the storage unit
        (t("Inside"), "cash.png", 0.12, "contain"),          # suitcases of cash
        (t("another"), "suitcase_cash.png", 0.10, "cover"),  # £42k at home
        (t("haul"), "cash.png", 0.06, "contain"),            # record seizure
        (t("admitted"), "mug_b.png", 0.08, "contain"),       # the charges
        (t("September"), "court.png", 0.10, "cover"),        # Reading Crown Court
        (t("jailed"), "mug_a.png", 0.10, "contain"),         # the sentence
    ]
    segments = []
    for i, (start, file, zoom, fit) in enumerate(beats):
        end = beats[i + 1][0] if i + 1 < len(beats) else total
        segments.append(Segment(str(img / file), duration=round(end - start, 3), image=True, zoom=zoom, fit=fit, label=file))

    chunks = [Chunk(c) for c in [
        "THIS *POSTMAN*", "SPENT A YEAR", "ROBBING #DRUG DEALERS#", "THROUGH THE *MAIL*", "AND IT MADE HIM", "A #MILLIONAIRE#",
        "*AMJAD ALI* WAS", "#50 YEARS# OLD", "AND WORKED AT", "ONE OF *ROYAL MAIL'S*", "BIGGEST *SORTING*|CENTRES", "IN #SLOUGH#",
        "EVERY SHIFT", "*THOUSANDS* OF|PARCELS", "ROLLED PAST HIM", "AND *ALI* HAD|LEARNED", "WHICH ONES WERE", "STUFFED WITH|#CANNABIS#",
        "BEFORE THEY|REACHED", "THE #X-RAY#", "HE PULLED THEM", "OFF THE LINE", "SWAPPED THE|*LABELS*", "AND *REROUTED*", "THE PACKAGES", "TO HIMSELF",
        "RATHER THAN|HAND", "THE #DEALERS#", "TO THE *POLICE*", "HE *RIPPED*|THEM OFF", "AND SOLD|THE #WEED#", "ON FOR HIS", "OWN *PROFIT*",
        "THE SCHEME RAN", "THROUGH #2024#", "AND #2025#", "UNTIL *OFFICERS*", "RAIDED HIS|#HOUSE#", "HIS #CAR#", "AND A PRIVATE", "*STORAGE UNIT*",
        "INSIDE THE UNIT", "THEY FOUND", "*SUITCASES*|PACKED", "WITH MORE THAN", "#£1.1 MILLION#", "IN *CASH*", "WITH ANOTHER", "#£42,000#", "HIDDEN AT|HIS *HOME*",
        "THE #£1.2 MILLION#", "HAUL WAS THE", "*BIGGEST*|CASH SEIZURE", "IN *THAMES VALLEY*", "POLICE HISTORY",
        "*ALI* ADMITTED", "SUPPLYING|#CANNABIS#", "STEALING|*PARCELS*", "HOLDING|*CRIMINAL* MONEY", "AND POSSESSING", "AN #OFFENSIVE#|WEAPON",
        "IN #SEPTEMBER#|#2026#", "A JUDGE AT", "*READING*|*CROWN COURT*", "*JAILED* HIM FOR", "#SIX YEARS#", "AND #NINE#|MONTHS",
    ]]

    fonts = Path(args.fonts)
    return ReelSpec(
        audio=args.vo, out=args.out, workdir=args.work, segments=segments, words=words, chunks=chunks,
        video_offset=0.0, caption_y_frac=0.54, caption_size=58, caption_max_chars=15, flash_on_cuts=False,
        font="THE BOLD FONT (FREE VERSION)", fontsdir=str(fonts / "bold"), colors=COLORS, total=total,
        post="vignette=angle=PI/5.4,eq=saturation=0.9:contrast=1.03",
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--img", required=True)
    ap.add_argument("--vo", required=True)
    ap.add_argument("--words", required=True)
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--total", default=None)
    args = ap.parse_args()
    print(render(build(args)))


if __name__ == "__main__":
    main()
