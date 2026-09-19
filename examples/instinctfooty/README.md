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
| `mbappe_tech.mp4` | youtube GegZ1rOeX-M (0-120s) | Mbappé slow-mo strike, plant foot, net; small burned-in captions wiped with `delogo` |
| `psg_session.mp4` | youtube szkU_PwTgUk | training-ground shooting (weeks 3-4, app beat, "our players") |
| `barefoot.mp4` | youtube Cjmb90TjVbQ (30-100s) | week one barefoot juggling |
| `bridge.mp4` | youtube xxlixggAenk | week two single-leg bridge |

Word timestamps come from faster-whisper (`small`) on the supplied MP3 (`vo_words.json`).
Fonts: Montserrat Black / ExtraBold Italic (OFL) in `--fonts`.

```bash
python examples/instinctfooty/build_04_power.py --src SRC --vo 04_POWER_fascia.mp3 --words vo_words.json \
    --fonts fonts/ --work work04/ --out 04_POWER_fascia-30-days.mp4
# tweak the arrow / circles without re-rendering segments:
#   --arrow 640,330 --circle 860,1400,200 --circle2 520,1420,210
```
