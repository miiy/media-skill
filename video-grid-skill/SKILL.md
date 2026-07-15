---
name: video-grid-skill
description: Create visual contact sheets, storyboard grids, timeline mosaics, or thumbnail overview images from local video files by sampling frames evenly and labeling them with timestamps. Use whenever the user asks to preview, summarize, compare, or inspect a video visually, make a video grid/contact sheet, or batch-generate overview images for a directory of videos. Do not use for extracting one exact frame, editing video, or transcribing speech.
compatibility: Requires Python 3.9 or newer, Pillow, and ffmpeg/ffprobe on PATH.
---

# Video Grid

Use the bundled script for deterministic local video processing. Resolve bundled resources relative to this `SKILL.md` and treat the Skill directory as read-only.

## Runtime Boundaries

- Run commands with the process working directory set to the user's workspace.
- Read the script and requirements from `<skill-dir>`, but do not create or modify files there.
- Keep source videos, generated grids, logs, and other runtime data in `<workspace>` or another path requested by the user.
- Never create virtual environments, caches, outputs, or persistent temporary files under `<skill-dir>`. The script's transient frame files use the operating system's temporary directory.

## Prepare The Runtime

Check that the local input exists before running the script. Install the Python dependency into the active environment if Pillow is unavailable:

```bash
python -m pip install -r <skill-dir>/requirements.txt
```

`ffmpeg` and `ffprobe` must be available on `PATH`. If either command is missing, report the prerequisite instead of attempting to replace it with a different media workflow.

## Create A Grid

For one local video:

```bash
python <skill-dir>/scripts/create_video_grid.py "<workspace>/video.mp4"
```

The default result is `<video-name>_grid.jpg` beside the source. Frames use a 0.5 scale ratio, the canvas and 100-pixel metadata header are white, spacing is 5 pixels, and whole-second timestamp labels use white text with a black outline and no background box. The script prefers Microsoft YaHei when it is installed, then tries common system fonts, and finally falls back to Pillow's default font. Set the layout, scale, or destination when the user requests them:

```bash
python <skill-dir>/scripts/create_video_grid.py "<workspace>/video.mp4" \
  --rows 3 --columns 5 --scale-ratio 0.4 \
  --output "<workspace>/video-contact-sheet.jpg"
```

Use `--overwrite` only when the user explicitly wants to replace an existing image. Otherwise the script safely reports the existing output as skipped.

## Process A Directory

Pass a directory to process its supported videos. Add `--recursive` only when subdirectories should be included:

```bash
python <skill-dir>/scripts/create_video_grid.py "<workspace>/videos" --recursive
```

Keep the source-relative directory structure under a separate output directory:

```bash
python <skill-dir>/scripts/create_video_grid.py "<workspace>/videos" \
  --recursive --output "<workspace>/grids" --jobs 4
```

Use conservative parallelism because every job starts ffmpeg and decodes multiple frames. Start with `--jobs 1`; increase it only when the user asks for faster batch processing or the machine has enough CPU and storage throughput.

## Choose Options

- Defaults are 4 rows, 4 columns, and a 0.5 scale ratio.
- Use `--thumbnail-width` only when the user explicitly requests a fixed pixel width; it is mutually exclusive with `--scale-ratio`.
- Use `--suffix _preview.png` to change batch output naming and format.
- Use `--font <workspace>/fonts/font.ttf` when the user requests a specific font or the automatically selected system font cannot render the filename.
- Use `--json` when another tool needs structured per-file status. Human-readable output is more concise for interactive use.
- Supported input extensions are `.avi`, `.flv`, `.m4v`, `.mkv`, `.mov`, `.mp4`, `.mpeg`, `.mpg`, `.mts`, `.m2ts`, `.ts`, `.webm`, and `.wmv`.

The script samples fractional time points evenly inside the video's start and end boundaries to avoid common black or transition frames and repeated frames in short videos. It labels each thumbnail with a compact whole-second timestamp and writes file name, size, resolution, and duration above the grid.

After processing, report the output path for each successful file, note skipped files, and surface failed files with the script's error message. Do not claim success based only on a zero-sized or missing output.
