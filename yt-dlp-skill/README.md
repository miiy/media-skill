# yt-dlp-skill

English | [Simplified Chinese](README.zh-CN.md)

A Skill for inspecting downloadable media formats and downloading selected audio or video streams with [yt-dlp](https://github.com/yt-dlp/yt-dlp).

## Features

- List downloadable formats using yt-dlp's native table layout
- Produce structured JSON for automation
- Show resolution, codecs, bitrate, file size, protocol, and format ID
- Handle audio-only media without requiring a video resolution
- Download the best available video and audio automatically
- Download a specific format or combine video and audio IDs such as `137+140`
- Use Node automatically when it is available on `PATH`
- Inherit `http_proxy` and `https_proxy` from the environment
- Remain anonymous by default, with optional explicit Cookie file support

## Requirements

- Python 3.10 or newer
- pip
- Node.js 22 or newer is recommended for full YouTube JavaScript challenge support
- ffmpeg is required when merging separate video and audio streams

## Install Dependencies

Install the bundled requirements into an active, user-managed Python environment:

```bash
python -m pip install -r <skill-dir>/requirements.txt
```

The `yt-dlp[default]` dependency includes the recommended Python dependencies and `yt-dlp-ejs`.

## Install As A Skill

Copy or symlink the `yt-dlp-skill` directory into the Skill search path supported by your agent runtime. Installation paths and discovery mechanisms vary between agents; keep the directory structure intact and ensure the runtime can read `SKILL.md`.

The Skill identifier is `yt-dlp-skill`.

## Runtime Directory

Treat the installed Skill directory as read-only. Run commands from the user's workspace, read
scripts and requirements from `<skill-dir>`, and keep downloads, Cookie files, logs, and other
runtime data in `<workspace>` or another user-requested location. Every download example below
uses an explicit workspace-rooted output template.

## List Formats

Print video metadata and all downloadable audio/video formats:

```bash
python <skill-dir>/scripts/list_formats.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

Output JSON instead:

```bash
python <skill-dir>/scripts/list_formats.py --json \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

The table uses the same columns as `yt-dlp -F`, including `ID`, `RESOLUTION`, codecs, bitrate, size, protocol, and `MORE INFO`.
Audio-only media reports `audio only` in the human-readable summary and `null` for `best_resolution` in JSON.

## Download

Download the best available video and audio:

```bash
python <skill-dir>/scripts/download.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --output "<workspace>/%(title)s [%(id)s].%(ext)s"
```

Download one precombined format:

```bash
python <skill-dir>/scripts/download.py "https://www.youtube.com/watch?v=VIDEO_ID" 18 \
  --output "<workspace>/%(title)s [%(id)s].%(ext)s"
```

Combine a video-only format with an audio-only format:

```bash
python <skill-dir>/scripts/download.py "https://www.youtube.com/watch?v=VIDEO_ID" "137+140" \
  --output "<workspace>/%(title)s [%(id)s].%(ext)s"
```

Format IDs vary by video. Run `list_formats.py` first instead of assuming that the example IDs are available.

Set a custom output template:

```bash
python <skill-dir>/scripts/download.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  "137+140" \
  --output "<workspace>/downloads/%(title)s [%(id)s].%(ext)s"
```

After downloading and completing any merge or other post-processing, the script prints the final
absolute path as `Download complete: <absolute-path>`.

## Proxy

The scripts use the standard proxy environment variables:

```bash
export https_proxy=http://127.0.0.1:7890
python <skill-dir>/scripts/list_formats.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Cookies

The bundled scripts do not read browser profiles or cookies by default. To use an exported Mozilla/Netscape-format Cookie file explicitly:

```bash
python <skill-dir>/scripts/list_formats.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --cookies "<workspace>/cookies.txt"

python <skill-dir>/scripts/download.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  "137+140" \
  --cookies "<workspace>/cookies.txt" \
  --output "<workspace>/%(title)s [%(id)s].%(ext)s"
```

Cookie files contain account credentials. Do not commit them, print their contents, or share them. The scripts do not support automatic browser-profile extraction.

## Structure

```text
yt-dlp-skill/
|-- SKILL.md
|-- README.md
|-- README.zh-CN.md
|-- requirements.txt
|-- evals/
|   `-- evals.json
|-- scripts/
|   |-- list_formats.py
|   `-- download.py
`-- tests/
    |-- test_download.py
    `-- test_list_formats.py
```
