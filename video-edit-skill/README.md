# video-edit-skill

English | [Simplified Chinese](README.zh-CN.md)

`video-edit-skill` provides deterministic FFmpeg scripts for trimming,
transforming, and concatenating local videos.

## Features

- Frame-accurate trimming with re-encoding
- Fast keyframe-aligned lossless trimming with stream copy
- Playback speed changes with synchronized audio
- Crop, exact resize, and clockwise, counter-clockwise, or 180-degree rotation
- Audio removal
- Precise concatenation that normalizes mixed input dimensions, frame rates, and
  audio layouts
- Validated lossless concatenation for compatible streams
- Intro and outro insertion
- Atomic outputs, safe skip-by-default behavior, and JSON status

## Requirements

- Python 3.9 or newer
- `ffmpeg` and `ffprobe` on `PATH`
- No third-party Python packages

## Edit One Video

```bash
python <skill-dir>/scripts/edit_video.py <workspace>/input.mp4 \
  --start 12.5 --end 68 \
  --output <workspace>/trimmed.mp4
```

Apply several transformations in one encoding pass:

```bash
python <skill-dir>/scripts/edit_video.py <workspace>/input.mp4 \
  --speed 1.25 \
  --crop 1080x1080+420+0 \
  --scale 1080x1080 \
  --rotate cw \
  --output <workspace>/edited.mp4
```

Use stream copy for a fast, keyframe-aligned trim:

```bash
python <skill-dir>/scripts/edit_video.py <workspace>/input.mp4 \
  --start 30 --duration 45 --mode lossless \
  --output <workspace>/clip.mp4
```

## Concatenate

Normalize and concatenate mixed inputs:

```bash
python <skill-dir>/scripts/concat_videos.py \
  <workspace>/part-1.mp4 <workspace>/part-2.mov \
  --output <workspace>/joined.mp4
```

Add an intro and outro:

```bash
python <skill-dir>/scripts/concat_videos.py <workspace>/main.mp4 \
  --intro <workspace>/intro.mp4 \
  --outro <workspace>/outro.mp4 \
  --output <workspace>/published.mp4
```

Losslessly concatenate inputs that already have identical stream parameters:

```bash
python <skill-dir>/scripts/concat_videos.py \
  <workspace>/part-1.mp4 <workspace>/part-2.mp4 \
  --mode lossless --output <workspace>/joined.mp4
```

Precise mode is the default. It uses the first main video's canvas and frame
rate unless `--size` or `--fps` is specified. Lossless mode does not support
filters and its trim points are limited by source keyframes.

Both scripts skip existing outputs unless `--overwrite` is passed. Add `--json`
for structured output.

## Structure

```text
video-edit-skill/
|-- SKILL.md
|-- README.md
|-- README.zh-CN.md
|-- requirements.txt
|-- evals/
|   `-- evals.json
|-- scripts/
|   |-- edit_video.py
|   |-- concat_videos.py
|   `-- media_utils.py
`-- tests/
    `-- test_video_edit.py
```
