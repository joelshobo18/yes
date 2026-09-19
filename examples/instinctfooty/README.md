# instinctfooty-style reel (editor trial task, video 4)

`build_04_power.py` reproduces the @instinctfooty format for the "Fascia -> shooting in 30 days" voice-over
(keyword POWER) with `autocut.reel`: one flowing 9:16 edit under the supplied VO, no music, no face.

## What the reference does, and how it is replicated

| Reference beat | Replication |
|---|---|
| Hook: first sentence on screen 0-5s, caps, white with black stroke, red arrow to the player, white circle on the boot | `TextCard` in the upper third (y=0.26), arrow + circle drawn as ASS vector shapes, slow-mo push-in on the strike |
| Continuous 2-4 word centred captions, heavy black-weight caps, green = the positive thing, yellow = numbers / days, red = the negative thing, each phrase pops in | `Chunk` list with `*green*` `#yellow#` `!red!` markup, timed from whisper word timestamps, `\fscx` pop-in |
| Footage changes on every step of the plan so the viewer sees the thing being named | segments: Mbappé strikes -> barefoot juggling -> single-leg bridge -> shooting drills |
| "It's in the app" gets a rounded-corner app pop-up that slides in, then fades | `Overlay` of `autocut.cards.app_card` PNG, 46.9-51.6s |
| Negative line goes black & white | `bw_ranges=[(16.3, 18.3)]` |
| CTA: product card + `COMMENT "KEYWORD"` (keyword yellow) held to the last frame | card overlay + `TextCard` from 84% of runtime (53.8s) to the end, flowing captions stop |
| VO starts 0.5s before the picture | `video_offset=0.5` black lead-in |

## Sources used (via Algrow / yt-dlp; not licensed for reuse - trial footage only)

| file | source | used for |
|---|---|---|
| `mbappe_tech.mp4` | youtube GegZ1rOeX-M (0-120s) | hook side-on strike, POV run-up, legs close-ups, ball into the net; analyst captions wiped with `delogo` |
| `mbappe_pack.mp4` | youtube DLbM1_Or4fI (4K scene pack) | in-game dribble, celebrations, shot + goal |
| `psg_session.mp4` | youtube szkU_PwTgUk | training-ground shooting (weeks 3-4) |
| `barefoot.mp4` | youtube Cjmb90TjVbQ (30-100s) | week one barefoot juggling |
| `bridge.mp4` | youtube xxlixggAenk | week two single-leg bridge |
| `fascia_anatomy.png` | generated (GPT Image) | "glute, hamstring, calf, foot" anatomy render with push-in |

Word timestamps come from faster-whisper (`small`) on the supplied MP3 (`vo_words.json`).
Fonts (`--fonts`): `bold/THEBOLDFONT-FREEVERSION.ttf` (captions, titles, CTA), Montserrat Black / ExtraBold Italic (card body).
Emoji (`--emoji`): Apple emoji PNGs named by codepoint (e.g. `1f525.png`) from the `emoji-data` set.

```bash
python examples/instinctfooty/build_04_power.py --src SRC --vo 04_POWER_fascia.mp3 --words vo_words.json \
    --fonts fonts/ --emoji emoji160/ --work work04b/ --out 04_POWER_fascia-30-days.mp4
# tracker keyframes (time,x,y;...) measured on the rendered hook / legs segments, tweakable without re-rendering:
#   --head "1.0,690,170;1.5,760,170;2.0,790,175;2.5,815,210;3.1,780,200"
#   --ball "1.0,110,1540;1.5,325,1540;2.0,630,1540;2.5,670,1500;3.1,810,1440"
#   --leg  "18.36,420,1400;18.86,500,1380;19.36,600,1360;20.14,700,1320"
```

See `STYLE.md` for the frame-by-frame breakdown of the reference and how each rule maps to the renderer.
