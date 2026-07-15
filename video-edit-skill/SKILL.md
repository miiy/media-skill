---
name: video-edit-skill
description: Edit local videos with deterministic FFmpeg scripts. Use whenever the user asks to trim or cut a video by time, concatenate clips, add an intro or outro, change playback speed, crop, resize, rotate, remove audio, or produce either a frame-accurate re-encoded edit or a fast keyframe-aligned lossless stream copy. Supports local files only; use a download skill first for remote URLs.
compatibility: Requires Python 3.9 or newer plus ffmpeg and ffprobe on PATH. The bundled scripts use only the Python standard library.
---

# Video Edit

Use the bundled scripts for predictable local video editing. Resolve scripts relative to this `SKILL.md` and treat the Skill directory as read-only.

## Runtime Boundaries

- Run commands with the process working directory set to the user's workspace.
- Keep source videos, edited videos, logs, concat lists, and other runtime data in the workspace or another path explicitly requested by the user.
- Do not create outputs, virtual environments, or persistent temporary files under the Skill directory. The scripts use the operating system temporary directory and atomic output files beside the requested destination.
- Confirm `ffmpeg` and `ffprobe` are on `PATH`. Report missing prerequisites instead of substituting another editing workflow.
- Process local files only. When given a URL, use an appropriate download skill first and then edit the downloaded file.

## Choose A Mode

Use `precise` unless the user explicitly prioritizes speed or no quality loss.

- `--mode precise` is the default. It decodes and re-encodes, so time cuts are frame-accurate and filters are available. Default output is H.264, AAC, CRF 18, `yuv420p`, and fast-start metadata for MP4/MOV.
- `--mode lossless` copies compressed streams. It is fast and avoids generation loss, but cut points can move to nearby keyframes. It supports trimming, removing audio, and concatenating already compatible streams. It cannot change speed, crop, scale, or rotate.
- For lossless concatenation, the script verifies video codec, dimensions, pixel format, frame rate, and audio layout before invoking FFmpeg. If inputs are incompatible, use precise mode.

Explain the keyframe limitation briefly whenever a user requests both an exact cut and lossless mode. Prefer exact timing over losslessness when their priority is unclear.

## Edit One Video

Frame-accurate trim:

```bash
python <skill-dir>/scripts/edit_video.py "<workspace>/input.mp4" \
  --start 00:00:12.500 --end 00:01:08 \
  --output "<workspace>/trimmed.mp4"
```

Use `--duration` instead of `--end` when the requested length is known. Time values accept seconds, `MM:SS`, or `HH:MM:SS` with optional decimals.

Fast lossless trim:

```bash
python <skill-dir>/scripts/edit_video.py "<workspace>/input.mp4" \
  --start 30 --duration 45 --mode lossless \
  --output "<workspace>/clip.mp4"
```

Combine transformations in one precise pass to avoid repeated generation loss:

```bash
python <skill-dir>/scripts/edit_video.py "<workspace>/input.mp4" \
  --start 5 --end 35 --speed 1.25 \
  --crop 1080x1080+420+0 --scale 1080x1080 --rotate cw \
  --remove-audio --output "<workspace>/edited.mp4"
```

Crop accepts `WIDTHxHEIGHT+X+Y` or FFmpeg-style `WIDTH:HEIGHT:X:Y`. Scale accepts `WIDTHxHEIGHT`. Crop and scale dimensions must be even because the default `yuv420p` output requires even dimensions.

## Concatenate Videos

Normalize and concatenate clips with different sizes, frame rates, codecs, or missing audio:

```bash
python <skill-dir>/scripts/concat_videos.py \
  "<workspace>/part-1.mp4" "<workspace>/part-2.mov" \
  --output "<workspace>/joined.mp4"
```

Precise mode uses the first main video's dimensions and frame rate by default. Set a fixed canvas or frame rate only when requested:

```bash
python <skill-dir>/scripts/concat_videos.py \
  "<workspace>/part-1.mp4" "<workspace>/part-2.mp4" \
  --size 1920x1080 --fps 30 --output "<workspace>/joined.mp4"
```

Add an intro and outro without manually reordering the main inputs:

```bash
python <skill-dir>/scripts/concat_videos.py "<workspace>/main.mp4" \
  --intro "<workspace>/intro.mp4" --outro "<workspace>/outro.mp4" \
  --output "<workspace>/published.mp4"
```

When the intro, main clips, and outro already have identical stream parameters, use lossless concatenation:

```bash
python <skill-dir>/scripts/concat_videos.py \
  "<workspace>/part-1.mp4" "<workspace>/part-2.mp4" \
  --mode lossless --output "<workspace>/joined.mp4"
```

## Compose Multiple Operations

When the main video needs filters as well as an intro or outro:

1. Run `edit_video.py` once with all trim, speed, crop, scale, rotate, and audio options for the main video.
2. Run `concat_videos.py` with the edited main file plus `--intro` and/or `--outro`.
3. Use precise concat unless all sources were deliberately encoded to identical stream parameters.

This two-stage workflow keeps transformation rules unambiguous and avoids applying the main video's crop or speed changes to the intro and outro.

## Output Safety And Reporting

- Do not add `--overwrite` unless the user explicitly requests replacement. Existing outputs return `skipped` without running FFmpeg.
- Use workspace-rooted absolute `--output` paths. Supported containers are MP4, MOV, MKV, TS, and WebM; codec/container incompatibilities are surfaced by FFmpeg.
- Use `--json` when structured status is useful to another tool. Otherwise report the human-readable succeeded, skipped, or failed status.
- After success, verify the output exists and is non-empty. For higher-risk edits, use `ffprobe` to confirm duration, dimensions, codecs, and audio presence before reporting completion.
- Surface FFmpeg's relevant error. Do not claim a file was created based only on the process exit code.
