# video-grid-skill

English | [Simplified Chinese](README.zh-CN.md)

`video-grid-skill` samples frames evenly from local videos and creates
timestamped contact sheets. It can process one video or batch-process a
directory.

## Features

- Sample fractional timestamps evenly within the video's start and end
  boundaries, avoiding repeated frames in short videos caused by whole-second
  rounding
- Use a `0.5` scale ratio by default, with a white header and white timestamp
  labels outlined in black
- Prefer Microsoft YaHei when available, then try common system fonts and
  finally Pillow's default font
- Label each frame with a timestamp and write the filename, size, resolution,
  and duration at the top
- Process single files, directories, recursive directory scans, and concurrent
  batches
- Skip existing outputs by default and overwrite only with `--overwrite`
- Preserve source-relative directory structure for separate batch output
  directories
- Support both human-readable output and structured `--json` output

## Requirements

- Python 3.9 or newer
- `ffmpeg` and `ffprobe` on `PATH`
- Pillow

Install Python dependencies with pip:

```bash
python -m pip install -r <skill-dir>/requirements.txt
```

## Install As A Skill

Copy or symlink the `video-grid-skill` directory into the Skill search path
supported by your agent runtime. Installation paths and discovery mechanisms
vary between agents; keep this directory structure intact and ensure the runtime
can read `SKILL.md`.

The Skill identifier is `video-grid-skill`.

## Runtime Directory

Treat the installed Skill directory as read-only. Run commands from the user's
workspace. Keep source videos, generated grids, and other runtime data in the
user workspace or another location explicitly requested by the user. Temporary
frames created during processing use the operating system's temporary
directory.

The examples below use `<skill-dir>` for the installed Skill directory and
`<workspace>` for the user workspace.

## Single Video

```bash
python <skill-dir>/scripts/create_video_grid.py <workspace>/video.mp4
```

By default, the script creates `<video-name>_grid.jpg` beside the source video.
Set a custom layout and output path:

```bash
python <skill-dir>/scripts/create_video_grid.py <workspace>/video.mp4 \
  --rows 3 \
  --columns 5 \
  --scale-ratio 0.4 \
  --output <workspace>/contact-sheet.jpg
```

## Batch Processing

```bash
python <skill-dir>/scripts/create_video_grid.py <workspace>/videos --recursive
```

Write results to a separate directory and preserve source-relative
subdirectories:

```bash
python <skill-dir>/scripts/create_video_grid.py <workspace>/videos \
  --recursive \
  --output <workspace>/grids \
  --jobs 4
```

## Common Options

- `INPUT`: required local video file or directory
- `-o, --output`: output image for a single video, or output directory for
  directory mode
- `-r, --rows`: row count; default is `4`
- `-c, --columns, --cols`: column count; default is `4`
- `-s, --scale-ratio, --ratio`: thumbnail ratio relative to the source frame;
  default is `0.5`
- `-w, --thumbnail-width`: explicit thumbnail width; mutually exclusive with
  `--scale-ratio`
- `--suffix`: default output filename suffix; default is `_grid.jpg`
- `--font`: custom TrueType/OpenType font file; omitted means auto-select a
  system font
- `--recursive`: scan input directories recursively
- `--overwrite`: replace existing outputs
- `-j, --jobs`: number of concurrent workers; default is `1`
- `--json`: print JSON results

Supported input extensions are `.mp4`, `.mov`, `.mkv`, `.avi`, `.wmv`, `.flv`,
`.m4v`, `.ts`, `.mts`, `.m2ts`, `.webm`, `.mpeg`, and `.mpg`.

## Structure

```text
video-grid-skill/
|-- SKILL.md
|-- README.md
|-- README.zh-CN.md
|-- requirements.txt
|-- evals/
|   `-- evals.json
|-- scripts/
|   `-- create_video_grid.py
`-- tests/
    `-- test_create_video_grid.py
```
