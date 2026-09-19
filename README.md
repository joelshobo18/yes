# autocut

Automatic video editing from a voice-over or talking-head recording:

1. **Trim** dead air (silence) out of the audio, or out of the video and audio together.
2. **Transcribe** with word timestamps (faster-whisper / whisper), or align a script / SRT you already have.
3. **Scenes**: split the trimmed timeline into scenes at sentence boundaries and derive a visual search query per scene (keywords, or Claude for better queries).
4. **Find** clips that match each scene from your own asset folder, Pexels, Pixabay and YouTube (yt-dlp), score them, and download the best.
5. **Render** everything to a **format** spec (9:16 TikTok, 16:9 YouTube, 1:1, split-screen talking head, or your own YAML) with burned-in word-highlight captions, music, loudness normalisation, intro/outro.

Every stage writes `project.json` in the work folder so you can re-run any single stage.

## Install

```bash
pip install -e .                 # core: pyyaml, requests, imageio-ffmpeg (ships a static ffmpeg)
pip install -e ".[youtube]"      # + yt-dlp for the YouTube provider
pip install -e ".[whisper]"      # + faster-whisper for speech-to-text
pip install -e ".[llm]"          # + anthropic for Claude-written search queries
pip install -e ".[all,dev]"
```

ffmpeg: a system `ffmpeg` on PATH is used if present, otherwise the static build from `imageio-ffmpeg`. Set `AUTOCUT_FFMPEG=/path/to/ffmpeg` to force one.

API keys (only needed for the providers you use):

```bash
export PEXELS_API_KEY=...      # https://www.pexels.com/api/
export PIXABAY_API_KEY=...     # https://pixabay.com/api/docs/
export ANTHROPIC_API_KEY=...   # optional, for --claude-queries
```

## Quick start

```bash
# voice-over -> vertical short with stock b-roll and karaoke captions
autocut run voiceover.wav --format tiktok --topic "morning routine" --assets ./my_clips

# talking-head video -> b-roll on top, camera on the bottom half
autocut run me_talking.mp4 --format talking-head --music beat.mp3

# no speech-to-text installed? give it the script you read from, or an SRT
autocut run voiceover.wav --script script.txt --format youtube

# use Claude to write the search queries and only search Pexels + your own clips
autocut run voiceover.wav --claude-queries --providers local,pexels --assets ./my_clips

# just remove dead air from a recording
autocut trim raw.mp4 -o tight.mp4 --min-silence 0.6 --pad 0.15
```

Outputs land in `work/<source name>/`:

```
trimmed.mp4|wav      dead air removed
edl.json             the kept source ranges
transcript.srt       word-timed transcript
captions.ass         burned-in captions (libass)
clips/               chosen clips (downloads are cached in work/cache/)
credits.txt          attribution for stock footage
output_<format>.mp4  the final video
project.json         state for re-running stages
```

Re-run a single stage, e.g. after editing queries in `project.json` or changing format:

```bash
autocut scenes  -w work/voiceover --format youtube --claude-queries
autocut find    -w work/voiceover --providers local,pixabay --assets ./my_clips
autocut render  -w work/voiceover --format square --layout pip --no-captions -o square.mp4
autocut inspect -w work/voiceover
```

## Formats

`autocut formats` lists the built-ins (`tiktok`, `youtube`, `square`, `talking-head`). A format is a YAML file; pass a path to use your own, and `extends:` a built-in to change only a few keys:

```yaml
# formats/my-brand.yaml
extends: tiktok
name: my-brand
canvas: { width: 1080, height: 1920, fps: 30 }
layout: split                 # broll | split | pip | camera
max_duration: 45
pacing: { min_scene: 2, target_scene: 3.5, max_scene: 6 }
clips:
  orientation: auto           # auto | portrait | landscape | square | any
  providers: [local, pexels, youtube]
  min_clip_duration: 2
  avoid_repeat_within: 4
captions:
  mode: word                  # word (highlight current word) | line | none
  font: DejaVu Sans
  size: 80
  color: "#FFFFFF"
  highlight_color: "#00E5FF"
  outline: 4
  position: center            # top | center | bottom
  max_words: 3
  uppercase: true
audio:
  loudnorm: true
  target_lufs: -14
  music: /path/to/bed.mp3
  music_volume: 0.1
intro: /path/to/logo.png      # image (3s) or video, normalised to the canvas
outro: /path/to/endcard.mp4
encode: { codec: libx264, crf: 20, preset: medium }
```

Layouts: `broll` fills the canvas with matched clips; `split` puts b-roll on the top half and your camera on the bottom; `pip` overlays the camera in a corner; `camera` renders only the trimmed camera footage.

## Clip providers

| provider | source | needs | licence |
|---|---|---|---|
| `local` | your `--assets` folder; tags come from file names (`city_traffic_night.mp4`), `<file>.txt` sidecars, or `tags.json` | nothing | yours |
| `pexels` | Pexels video search | `PEXELS_API_KEY` | Pexels License (free, attribution appreciated) |
| `pixabay` | Pixabay video search | `PIXABAY_API_KEY` | Pixabay Content License |
| `youtube` | YouTube search via yt-dlp, downloads only the needed section, "under 4 minutes" filter | `pip install yt-dlp` | **not licensed for reuse** unless it's your own or Creative Commons content; you are responsible for rights |

Scoring per candidate: 45% query/title/tag relevance, 25% duration fit (short clips are looped, images are held), 15% orientation fit, 10% provider order, and a penalty for reusing a clip within the last N scenes. Scenes with no match get a coloured placeholder card so a render never fails.

YouTube may answer "Sign in to confirm you're not a bot" from cloud IPs; pass cookies with `AUTOCUT_YT_COOKIES=cookies.txt` or `AUTOCUT_YT_COOKIES_BROWSER=chrome`.

## Silence trimming

`--noise -35` (dB threshold), `--min-silence 0.45` (pauses shorter than this are kept as natural rhythm), `--pad 0.12` (silence kept around speech so cuts don't clip words), `--max-gap 0.3` (keep a short breath instead of a hard cut). Cuts are frame-accurate re-encodes through ffmpeg's `trim`/`atrim` + `concat`.

## Development

```bash
pip install -e ".[dev]"
pytest            # offline; generates synthetic audio/video fixtures with ffmpeg
```

Layout: `autocut/silence.py` (trim), `transcribe.py`, `scenes.py`, `providers/`, `match.py`, `captions.py`, `render.py`, `pipeline.py`, `cli.py`, `formats/*.yaml`.
