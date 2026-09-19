# instinctfooty reference style — frame-by-frame breakdown

Studied at 4 frames/second on three reels (`DcWUbJUOwqb` Mbappé legs, `Da5i8nZOdc_` never train alone,
`DcLuyg3ur-c` 30 days), plus the two review-note PDFs. Every rule below maps to a setting in `autocut/reel.py`.

## 1. Captions (the "autocaption" style)

| what the reference does | setting |
|---|---|
| Font: **THE BOLD FONT** (Sven Pels) — rigid, wide, geometric caps; fills far more width than Montserrat | `font="THE BOLD FONT"`, `fontsdir` |
| Caps, 2 lines max, 2–4 words per chunk; a chunk is one thought ("YOU DON'T / NEED😳") | `Chunk` list, `caption_max_chars=16`, `|` forces a break |
| Text lands **on the word**; a chunk holds until the next chunk — word, word, word, no gaps | `time_chunks` (start = first word start, end = next chunk start) |
| On screen from the very first frame | first chunk starts at the first word |
| Fixed in the **middle** (~47% height), never moves | `caption_y_frac=0.47` |
| White base; **green** = the positive/subject word, **yellow** = numbers, days, "this"; **red** = the negative | `*green*  #yellow#  !red!` markup |
| Black outline (~4px at 1080) + drop shadow **colour-linked to the word** (dark green under green) — no glow | `Cap` style outline 4, shadow 5, per-word `\4c` = `shadow_of(colour)` |
| Each chunk pops in (small scale-up, ~90ms) | `\fscx86\fscy86\t(0,90,...)` |
| Apple emoji at the end of key lines (😳 🚫 🧠 ✅) | `title_png(..., emoji_png=...)` (Apple PNG set) |
| Hook line is bigger than the flow captions; if the video opens with a title it stays at the top | hook `title_png`, y ≈ 17% |
| Keyword / summary words become **big bold titles with emoji** (e.g. "1 TRAINING🚫 MISTAKE", "TRAIN YOUR ATHLETICISM💪") | `Overlay` titles at the top, `flash=True` |

Colours measured from the reels: green `#3CFF3C`, yellow `#FFE01B`, red `#FF2B2B`.

## 2. Arrow & circle

* Red curved arrow pops in with a flash at ~0.25s and **tracks the head** for the whole hook shot; one arrow, one
  size, never a straight/bold variant. Glossy red with dark outline and a soft glow.
* White circle (default marker) pops in at the same moment and tracks the **ball / boot**. Yellow dashed variant
  exists (Messi reel) but white is the default.
* Both fade out when the shot changes.

→ `Track("arrow", keys=[(t,x,y)...])`, `Track("circle", ...)`: keyframed `\move`, glow layer (`\blur`), scale pop, `\fad`.

## 3. Flashes

Quick white flash on: hook entry, every big-text entry, every pop-up / CTA entry, every scene change.
→ `flashes`, `Overlay(flash=True)`, `flash_on_cuts=True` (an `eq` brightness spike decaying over 140ms).

## 4. Clips

* Every clip **full screen** 9:16, no borders; tight on player + ball; POV from behind the player where possible.
* Professional footage / scene packs, famous players and clubs (social proof); no amateur B-roll of people
  standing around. Exercise inserts (towel curls, toe crunches) are the one place the reference uses close-up feet.
* The clip changes **on the keyword** and shows exactly the thing being said.
* Negative line = black & white **and slowed**.
* "Fascial connections" gets a glowing anatomy render with a slow push-in.

→ one `Segment` per beat, `start` on the word timestamp, `bw=True` + slow speed, `image=True` push-in for the render.

## 5. Pop-ups

* App / product pop-up: **curved corners**, logo **on top**, soft shadow, pops in with a flash, **fades out** into the
  next clip (never a hard cut). Sits above the captions.
* Testimonial screenshots / student cards cascade in with rounded corners at "our students".
* CTA: product card above `COMMENT "KEYWORD"` (keyword yellow), held to the last frame, captions stop.

→ `cards.app_card` (logo overlapping the top edge), `Overlay(flash=True, fade_out=...)`, `TextCard` for the CTA.

## 6. Timeline rules from the brief

9:16 1080×1920, length = the VO, VO starts 0.5s before the picture, no music, no face,
hook = first sentence 0–5s, CTA at 84% of runtime to the last frame, filename `{n}_{KEYWORD}_{title}.mp4`.

## Submission checklist (from the notes)

arrow on the head + circle + flash in → caption up from frame one → text lands on the word → Apple emojis →
correct font, colour-matched shadow → captions fixed in the middle, titles fixed at the top → every clip full
screen → black & white = slowed → every clip clear, notable player, matching the voiceover → no gaps, no black
flashes → app pop-up curved, logo on top, fades out.
