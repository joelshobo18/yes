"""Video 4 of the instinctfooty trial task: "Fascia -> shooting in 30 days" (keyword POWER).

Usage:
    python examples/instinctfooty/build_04_power.py --src DIR --vo 04_POWER_fascia.mp3 --words vo_words.json \
        --fonts FONTS_DIR --emoji EMOJI_DIR --work WORK_DIR --out 04_POWER_fascia-30-days.mp4

`--src` holds the source clips named below (see README.md); `--emoji` holds Apple emoji PNGs named by codepoint.
Every visual rule here comes from STYLE.md (the reference breakdown + the review notes).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from autocut import cards
from autocut.reel import Chunk, Overlay, ReelSpec, Segment, TextCard, Track, render, render_segment

COLORS = {"white": "#FFFFFF", "green": "#3CFF3C", "yellow": "#FFE01B", "red": "#FF2B2B"}
# analyst caption box in the Mbappé technique video (source pixels): small white text mid-frame
DELOGO = (640, 500, 640, 90)
TOTAL = 64.06
OFFSET = 0.5  # VO starts 0.5s before the picture

# Timeline cut points = the exact word the clip must land on (voice-over seconds, from vo_words.json).
CUTS = {
    "hook": 0.5, "day20": 8.14, "day30": 11.74, "clean": 14.20, "not_bigger": 16.30, "look_legs": 18.36,
    "power": 20.14, "glute": 23.86, "heres": 27.78, "week1": 29.40, "week2": 34.38, "week34": 39.06,
    "weak_only": 42.62, "app": 46.86, "our_players": 52.50, "cta": 56.54, "end": TOTAL,
}
ORDER = list(CUTS)


def dur(a: str) -> float:
    i = ORDER.index(a)
    return round(CUTS[ORDER[i + 1]] - CUTS[a], 3)


def build(args) -> ReelSpec:
    src = Path(args.src)
    mb, psg, pack = str(src / "mbappe_tech.mp4"), str(src / "psg_session.mp4"), str(src / "mbappe_pack.mp4")
    words = json.loads(Path(args.words).read_text())
    fonts, emoji, work = Path(args.fonts), Path(args.emoji), Path(args.work)
    bold = fonts / "bold" / "THEBOLDFONT-FREEVERSION.ttf"

    # ---------------- footage: every clip shows the thing being said, cut on the keyword -----------------
    segments = [
        # HOOK: full-body side-on strike (player, ball, defender, pitch all visible), slow, arrow on head + circle on ball
        Segment(mb, 49.3, 52.9, duration=dur("hook"), delogo=DELOGO, crop="x=0.62", label="hook side-on strike"),
        # "by day 20 ... striking with your weak foot in games": beating defenders in a match
        Segment(pack, 57.5, 57.5 + dur("day20"), label="in games dribble"),
        # "by day 30 you're your team's top scorer": pointing celebration
        Segment(pack, 11.0, 11.0 + dur("day30"), label="top scorer celebration"),
        # "hitting them clean from outside the box": long-range strike towards goal
        Segment(mb, 52.0, 55.0, duration=dur("clean"), delogo=DELOGO, label="outside the box into the net"),
        # "not because you got bigger legs": B/W + slowed close-up of the legs
        Segment(mb, 36.25, 37.35, duration=dur("not_bigger"), delogo=DELOGO, bw=True, label="bigger legs bw"),
        # "just look at Mbappe's legs": legs at contact, circle tracks the leg
        Segment(mb, 40.0, 40.95, duration=dur("look_legs"), delogo=DELOGO, crop="x=0.36", label="look legs"),
        # "power doesn't come from muscle size ... fascial chain": POV from behind the player on the run-up
        Segment(mb, 22.5, 25.0, duration=dur("power"), delogo=DELOGO, label="pov run-up"),
        # "glute, hamstring, calf, foot, nobody trains it": anatomy render, push-in (as the reference does)
        Segment(str(src / "fascia_anatomy.png"), duration=dur("glute"), image=True, zoom=0.12, label="anatomy"),
        # "so here's the 30 days": strike close-up
        Segment(mb, 26.5, 28.0, duration=dur("heres"), delogo=DELOGO, label="heres strike"),
        # WEEK 1 foot strength: barefoot juggling close-up (feet + ball, as the reference's exercise inserts)
        Segment(str(src / "barefoot.mp4"), 10.0, 10.0 + dur("week1"), label="barefoot juggling"),
        # WEEK 2 hip loading: single-leg bridge
        Segment(str(src / "bridge.mp4"), 19.0, 19.0 + dur("week2"), crop="x=0.40", zoom=0.05, label="single leg bridge"),
        # WEEKS 3-4 the strike: pro training-ground shooting, then a second shot on "weak foot only"
        Segment(psg, 63.3, 63.3 + dur("week34"), label="20 shots"),
        Segment(psg, 68.0, 68.0 + dur("weak_only"), label="weak foot shots"),
        # "the whole block is in the app ... using it outside of team training": training footage under the pop-up
        Segment(pack, 26.5, 26.5 + dur("app"), label="app: pro celebration"),
        # "our players ... scoring from outside the box now": shot and goal
        Segment(pack, 53.0, 53.0 + dur("our_players") * 0.85, duration=dur("our_players"), label="scoring"),
        # CTA: bookend with the POV strike
        Segment(mb, 26.5, 31.5, duration=dur("cta"), delogo=DELOGO, zoom=0.06, label="cta strike"),
    ]

    # ---------------- captions: centred, from the first word, *green* #yellow# !red!, '|' = line break --------
    TITLED = {"MORE *SNAP*", "YOUR *WEAK FOOT*", "*TOP SCORER*", "*MBAPPE'S* LEGS", "YOUR *FASCIAL*|CHAIN", "*GLUTE*",
              "*HAMSTRING*", "*CALF*", "*FOOT*", "#WEEK ONE#", "*FOOT STRENGTH*", "#WEEK TWO#", "*HIP LOADING*",
              "#WEEKS THREE#|AND FOUR", "THE *STRIKE*|ITSELF"}
    chunks = [Chunk(t, hide=t in TITLED) for t in [
        "THIS IS WHAT", "*FASCIA* TRAINING", "WILL DO TO", "YOUR *SHOOTING*", "IN JUST #30 DAYS#",
        "BY #DAY 10#", "YOUR SHOTS START", "FEELING *DIFFERENT*", "MORE *SNAP*", "LESS !EFFORT!",
        "BY #DAY 20#", "YOU'RE *COMFORTABLE*", "STRIKING WITH", "YOUR *WEAK FOOT*", "IN GAMES",
        "BY #DAY 30#", "YOU'RE YOUR TEAM'S", "*TOP SCORER*", "HITTING THEM *CLEAN*", "FROM *OUTSIDE*|THE BOX",
        "AND IT'S !NOT!|BECAUSE", "YOU GOT|!BIGGER LEGS!", "JUST LOOK AT", "*MBAPPE'S* LEGS",
        "*POWER* DOESN'T|COME", "FROM !MUSCLE SIZE!", "IT COMES UP|THROUGH", "YOUR *FASCIAL*|CHAIN",
        "*GLUTE*", "*HAMSTRING*", "*CALF*", "*FOOT*", "AND ALMOST|!NOBODY!", "TRAINS IT",
        "SO HERE'S", "THE #30 DAYS#",
        "#WEEK ONE#", "*FOOT STRENGTH*", "BAREFOOT|*JUGGLING*", "AND *TOE|CRUNCHES*", "#10 MINUTES#|A DAY",
        "#WEEK TWO#", "*HIP LOADING*", "*SINGLE LEG*|BRIDGES", "AND *HIP HINGES*", "BEFORE EVERY|SESSION",
        "#WEEKS THREE#|AND FOUR", "THE *STRIKE*|ITSELF", "#20 SHOTS# A DAY", "*WEAK FOOT* ONLY",
        "AND YOU'RE|!NOT ALLOWED!", "TO USE YOUR|*STRONG FOOT*", "UNTIL THE #20#|ARE DONE",
        "THE *WHOLE BLOCK*", "IS IN THE *APP*", "DAY BY DAY", "AND *FOOTBALLERS*", "ARE ALREADY|USING IT",
        "OUTSIDE OF|*TEAM TRAINING*", "OUR *PLAYERS*", "WHO *FINISHED* IT", "THIS YEAR", "ARE THE ONES|*SCORING*",
        "FROM *OUTSIDE*|THE BOX", "NOW",
    ]]

    # ---------------- keyword titles at the top, with Apple emoji, flash on entry -----------------------------
    def title(name, lines, emoji_cp, start, end, size=92):
        png = cards.title_png(work / f"title_{name}.png", lines, font_path=bold, colors=COLORS, size=size,
                              emoji_png=emoji / f"{emoji_cp}.png" if emoji_cp else None)
        yf = 0.30 if name == "hook" else 0.20
        return Overlay(str(png), start, end, y=f"H*{yf}-h/2", fade_in=0.08, fade_out=0.15, flash=True)

    cta_at = round(TOTAL * 0.84, 2)  # 53.81s: CTA holds to the last frame
    overlays = [
        # hook title = first sentence of the script (0-5s, upper third)
        title("hook", ["THIS IS WHAT", "*FASCIA* TRAINING", "WILL DO TO YOUR", "SHOOTING IN #30 DAYS#"], "1f631", 0.0, 5.0, size=66),
        title("snap", ["MORE *SNAP*"], "26a1", 6.24, 8.14),
        title("weakfoot", ["*WEAK FOOT*"], "1f9b6", 10.38, 11.74),
        title("topscorer", ["*TOP SCORER*"], "1f3c6", 13.32, 16.30),
        title("legs", ["*MBAPPE'S* LEGS"], "1f631", 18.36, 20.14),
        title("chain", ["*FASCIAL CHAIN*"], "1f525", 22.80, 23.86),
        title("g1", ["*GLUTE*"], None, 23.86, 24.48, size=84),
        title("g2", ["*GLUTE* · *HAMSTRING*"], None, 24.48, 25.24, size=84),
        title("g3", ["*GLUTE* · *HAMSTRING*", "· *CALF*"], None, 25.24, 25.82, size=84),
        title("g4", ["*GLUTE* · *HAMSTRING*", "· *CALF* · *FOOT*"], "1f9b5", 25.82, 27.78, size=84),
        title("week1", ["#WEEK 1#", "*FOOT STRENGTH*"], "1f9b6", 29.40, 34.38),
        title("week2", ["#WEEK 2#", "*HIP LOADING*"], "1f525", 34.38, 39.06),
        title("week34", ["#WEEKS 3-4#", "*THE STRIKE*"], "1f3af", 39.06, 46.86),
    ]
    # app pop-up (curved, logo on top, flash in, fades out) and the product card above the CTA
    card_png = cards.app_card(work / "app_card.png", fonts_dir=fonts, width=620)
    overlays += [
        Overlay(str(card_png), 46.86, 51.6, y="H*0.10", scale=0.78, flash=True, fade_out=0.4),
        Overlay(str(card_png), cta_at, TOTAL + 0.5, y="H*0.10", scale=0.78, flash=True, fade_out=0.0),
    ]

    cards_ = [TextCard(["COMMENT", "#\"POWER\"#"], cta_at, TOTAL + 0.5, y_frac=0.58, size=108)]

    # ---------------- trackers: arrow follows the head, circle follows the ball (keyframed) -----------------
    tracks = [
        Track("arrow", keys=args.head, flash=True),
        Track("circle", keys=args.ball, radius=95, flash=False),
        Track("circle", keys=args.leg, radius=130, flash=True),
    ]

    return ReelSpec(
        audio=args.vo, out=args.out, workdir=str(work), segments=segments, words=words, chunks=chunks, cards=cards_,
        overlays=overlays, tracks=tracks, flashes=[OFFSET], video_offset=OFFSET, caption_y_frac=0.47, caption_size=76,
        font="THE BOLD FONT (FREE VERSION)", fontsdir=str(fonts / "bold"), captions_until=cta_at, total=TOTAL,
    )


def _keys(s: str) -> list[tuple[float, int, int]]:
    """'t,x,y;t,x,y;...' -> keyframes"""
    return [tuple(float(v) if i == 0 else int(v) for i, v in enumerate(k.split(","))) for k in s.split(";") if k]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--src", required=True)
    ap.add_argument("--vo", required=True)
    ap.add_argument("--words", required=True)
    ap.add_argument("--fonts", required=True)
    ap.add_argument("--emoji", required=True)
    ap.add_argument("--work", required=True)
    ap.add_argument("--out", required=True)
    # keyframes are measured on the rendered hook / legs segments (see README): time,x,y;...
    ap.add_argument("--head", type=_keys, default=_keys("1.0,690,170;1.5,760,170;2.0,790,175;2.5,815,210;3.1,780,200"))
    ap.add_argument("--ball", type=_keys, default=_keys("1.0,110,1540;1.5,325,1540;2.0,630,1540;2.5,670,1500;3.1,810,1440"))
    ap.add_argument("--leg", type=_keys, default=_keys("18.36,420,1400;18.86,500,1380;19.36,600,1360;20.14,700,1320"))
    ap.add_argument("--segments-only", action="store_true")
    args = ap.parse_args()
    spec = build(args)
    if args.segments_only:
        for i, seg in enumerate(spec.segments):
            out = Path(spec.workdir) / f"seg{i:02d}.mp4"
            if not out.exists():
                render_segment(seg, out)
        return
    print(render(spec))


if __name__ == "__main__":
    main()
