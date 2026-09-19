"""Video 4 of the instinctfooty trial task: "Fascia -> shooting in 30 days" (keyword POWER).

Usage:
    python examples/instinctfooty/build_04_power.py --src DIR --vo 04_POWER_fascia.mp3 --words vo_words.json \
        --fonts FONTS_DIR --work WORK_DIR --out 04_POWER_fascia-30-days.mp4

`--src` must contain the source clips named below (see README in this folder for where they came from).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autocut import cards
from autocut.reel import Chunk, Overlay, ReelSpec, Segment, TextCard, render

# analyst caption box in the Mbappé technique video (source pixels, 1920x1080): small white text mid-frame
DELOGO = (640, 500, 640, 90)


def build(args) -> ReelSpec:
    src = Path(args.src)
    mb = str(src / "mbappe_tech.mp4")
    psg = str(src / "psg_session.mp4")
    words = json.loads(Path(args.words).read_text())
    total = 64.06

    # --- footage timeline (voice-over time) --------------------------------------------------
    segments = [
        # 0.5-8.14  hook + "by day 10": slow-mo close-up strike, plant foot, keeper set
        Segment(mb, 26.5, 31.5, duration=7.64, zoom=0.06, delogo=DELOGO),
        # 8.14-11.74 "by day 20 ... weak foot in games": run-up
        Segment(mb, 22.5, 25.0, duration=3.60, delogo=DELOGO),
        # 11.74-16.3 "by day 30 ... clean from outside the box": ball flies past the keeper into the net
        Segment(mb, 52.0, 55.0, duration=4.56, delogo=DELOGO),
        # 16.3-20.14 "not bigger legs / just look at Mbappe's legs": close-up legs at contact (circle + arrow)
        Segment(mb, 40.0, 42.0, duration=3.84, delogo=DELOGO, crop="x=0.36"),
        # 20.14-23.86 "power doesn't come from muscle size, fascial chain": close-up leg swing
        Segment(mb, 36.25, 38.0, duration=3.72, delogo=DELOGO),
        # 23.86-29.4 "glute, hamstring, calf, foot ... here's the 30 days": full-body side-on strike, very slow
        Segment(mb, 49.5, 52.0, duration=5.54, delogo=DELOGO, crop="x=0.62"),
        # 29.4-34.38 week one: barefoot juggling
        Segment(str(src / "barefoot.mp4"), 10.0, 15.0, duration=4.98, zoom=0.05),
        # 34.38-39.06 week two: single-leg bridge
        Segment(str(src / "bridge.mp4"), 19.0, 23.68, duration=4.68, crop="x=0.40", zoom=0.05),
        # 39.06-46.86 weeks three & four: 20 shots a day (training ground shooting)
        Segment(psg, 63.3, 71.1, duration=7.80),
        # 46.86-52.5 "the whole block is in the app ... team training": shot + keeper save (app pop-up here)
        Segment(psg, 71.2, 76.84, duration=5.64),
        # 52.5-56.54 "our players ... scoring from outside the box now"
        Segment(psg, 57.8, 61.84, duration=4.04),
        # 56.54-64.06 CTA: bookend with the hook strike
        Segment(mb, 26.5, 31.5, duration=7.52, zoom=0.06, delogo=DELOGO),
    ]

    # --- captions: markup *green* #yellow# !red! ---------------------------------------------
    chunks = [Chunk(t) for t in [
        "YOUR SHOTS START", "FEELING *DIFFERENT*", "MORE *SNAP*", "LESS !EFFORT!",
        "BY #DAY 20#", "YOU'RE *COMFORTABLE*", "STRIKING WITH", "YOUR *WEAK FOOT*", "IN GAMES",
        "BY #DAY 30#", "YOU'RE YOUR TEAM'S", "*TOP SCORER*", "HITTING THEM *CLEAN*", "FROM *OUTSIDE THE BOX*",
        "AND IT'S !NOT! BECAUSE", "YOU GOT !BIGGER LEGS!", "JUST LOOK AT", "*MBAPPE'S* LEGS",
        "*POWER* DOESN'T COME", "FROM !MUSCLE SIZE!", "IT COMES UP THROUGH", "YOUR *FASCIAL CHAIN*",
        "*GLUTE*", "*HAMSTRING*", "*CALF*", "*FOOT*", "AND ALMOST !NOBODY!", "TRAINS IT",
        "SO HERE'S", "THE #30 DAYS#",
        "#WEEK ONE#", "*FOOT STRENGTH*", "BAREFOOT *JUGGLING*", "AND *TOE CRUNCHES*", "#10 MINUTES# A DAY",
        "#WEEK TWO#", "*HIP LOADING*", "*SINGLE LEG BRIDGES*", "AND *HIP HINGES*", "BEFORE EVERY SESSION",
        "#WEEKS THREE AND FOUR#", "THE *STRIKE* ITSELF", "#20 SHOTS# A DAY", "*WEAK FOOT* ONLY",
        "AND YOU'RE !NOT ALLOWED!", "TO USE YOUR *STRONG FOOT*", "UNTIL THE #20# ARE DONE",
        "THE *WHOLE BLOCK*", "IS IN THE *APP*", "DAY BY DAY", "AND *FOOTBALLERS*", "ARE ALREADY USING IT",
        "OUTSIDE OF *TEAM TRAINING*", "OUR *PLAYERS*", "WHO *FINISHED* IT", "THIS YEAR", "ARE THE ONES *SCORING*",
        "FROM *OUTSIDE THE BOX*", "NOW",
    ]]

    cta_at = round(total * 0.84, 2)  # 53.81s
    cards_ = [
        # hook: first sentence, caps, upper third, 0-5s, with arrow + circle on the plant foot
        TextCard(["THIS IS WHAT", "*FASCIA TRAINING*", "WILL DO TO YOUR SHOOTING", "IN JUST #THIRTY DAYS#"],
                 0.0, 5.0, y_frac=0.26, size=60, arrow=args.arrow, arrow_scale=0.5, circle=args.circle, circle_start=2.6),
        # "just look at Mbappe's legs": circle on the leg
        TextCard([], 18.3, 20.1, y_frac=0.5, size=1, circle=args.circle2, fade_out=0.2),
        # CTA at 84% to the last frame
        TextCard(["COMMENT", "#\"POWER\"#"], cta_at, total + 0.5, y_frac=0.56, size=104, fade_out=0.0),
    ]

    fonts = Path(args.fonts)
    work = Path(args.work)
    card_png = cards.app_card(work / "app_card.png", fonts_dir=fonts, width=600)
    overlays = [
        Overlay(str(card_png), 46.86, 51.6, y="H*0.10", scale=0.8),  # "the whole block is in the app" pop-up, then fades
        Overlay(str(card_png), cta_at, total + 0.5, y="H*0.11", fade=0.3, scale=0.8),  # product card above the CTA
    ]

    return ReelSpec(
        audio=args.vo, out=args.out, workdir=str(work), segments=segments, words=words, chunks=chunks,
        cards=cards_, overlays=overlays, video_offset=0.5, caption_y_frac=0.50, caption_size=84,
        font="Montserrat Black", fontsdir=str(fonts), bw_ranges=[(16.3, 18.3)], captions_until=cta_at, total=total,
    )


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--vo", required=True)
    ap.add_argument("--words", required=True)
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--arrow", type=lambda s: tuple(int(x) for x in s.split(",")), default=(640, 330))
    ap.add_argument("--circle", type=lambda s: tuple(int(x) for x in s.split(",")), default=(860, 1400, 200))
    ap.add_argument("--circle2", type=lambda s: tuple(int(x) for x in s.split(",")), default=(520, 1420, 210))
    ap.add_argument("--segments-only", action="store_true")
    args = ap.parse_args()
    spec = build(args)
    if args.segments_only:
        from autocut.reel import render_segment
        for i, seg in enumerate(spec.segments):
            out = Path(spec.workdir) / f"seg{i:02d}.mp4"
            if not out.exists():
                render_segment(seg, out)
        return
    print(render(spec))


if __name__ == "__main__":
    main()
