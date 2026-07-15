---
name: yt-dlp-skill
description: Inspect media URLs and download audio or video with yt-dlp using bundled scripts. Use whenever the user asks to parse a video URL, list available formats, resolutions, codecs or file sizes, choose a format ID, download the best quality or a specific video/audio combination, use an explicit cookie file for authenticated media, save media with a custom filename, or troubleshoot missing YouTube formats. Supports yt-dlp-native tables and JSON. Does not read cookies by default or scan browser profiles.
compatibility: Requires Python 3.10 or newer and the bundled pip requirements. Node.js 22 or newer is recommended for YouTube JavaScript challenges; ffmpeg is required to merge separate streams.
---

# yt-dlp Skill

Use the bundled scripts for deterministic format inspection and downloads. Resolve bundled resources relative to this `SKILL.md` and treat the Skill directory as read-only.

## Runtime Boundaries

- Run commands with the process working directory set to the user's workspace.
- Read the scripts and requirements from `<skill-dir>`, but do not create or modify files there.
- Keep downloads, output metadata, cookie files, logs, and other runtime data in `<workspace>` or another path requested by the user.
- Always pass a workspace-rooted `--output` template for downloads. Never create virtual environments, caches, downloads, or temporary files under `<skill-dir>`.

## Inspect Formats

Inspect before downloading when the user has not already selected a format:

```bash
python <skill-dir>/scripts/list_formats.py "<url>"
```

The table uses yt-dlp's native columns. Read the `ID`, `RESOLUTION`, codecs, size, and `MORE INFO` fields when recommending a format. Audio-only media is valid and reports `audio only` instead of a video resolution.

Use JSON only when structured output helps another command or program:

```bash
python <skill-dir>/scripts/list_formats.py --json "<url>"
```

For audio-only media, `best_resolution` is `null`; inspect the entries whose `type` is `audio` normally.

## Select a Format

- Use a `video+audio` format ID by itself when the user wants a single precombined stream.
- Combine a video-only ID and an audio-only ID with `+`, such as `137+140`, for higher-quality output with sound.
- Use `bestvideo+bestaudio/best` when the user asks for the best available result without codec or container constraints.
- Prefer formats matching explicit resolution, codec, container, HDR, language, or file-size requirements over a generic "best" choice.
- Do not force a YouTube `player_client`; let current yt-dlp defaults handle client selection because hard-coding clients can hide formats.

Explain briefly when a selected high-resolution format is video-only and therefore needs a separate audio ID.

## Download

Download the best video and audio when no format was specified:

```bash
python <skill-dir>/scripts/download.py "<url>" \
  --output "<workspace>/%(title)s [%(id)s].%(ext)s"
```

Download a chosen format or combination:

```bash
python <skill-dir>/scripts/download.py "<url>" "137+140" \
  --output "<workspace>/%(title)s [%(id)s].%(ext)s"
```

Set a destination with a yt-dlp output template:

```bash
python <skill-dir>/scripts/download.py "<url>" "137+140" \
  --output "<workspace>/downloads/%(title)s [%(id)s].%(ext)s"
```

Use `ffmpeg` for merging separate video and audio streams. If it is missing, report that prerequisite rather than silently choosing a lower-quality combined format.

## Runtime And Access

- Use Python 3.10 or newer. Before the first run, install the bundled requirements into the active environment:

  ```bash
  python -m pip install -r <skill-dir>/requirements.txt
  ```

- Reuse an existing environment when `yt-dlp` is already installed; do not reinstall dependencies on every invocation.
- Let the scripts use Node automatically when it is on `PATH`; yt-dlp can otherwise use its supported fallback behavior.
- Inherit `http_proxy` and `https_proxy` from the environment. Do not embed proxy addresses in the skill.
- Keep inspection anonymous by default. Omit `--cookies` unless the user explicitly requests authenticated access and provides a cookie file.
- Pass an explicit Mozilla/Netscape-format cookie file when authentication is required:

  ```bash
  python <skill-dir>/scripts/list_formats.py "<url>" --cookies "<workspace>/cookies.txt"
  python <skill-dir>/scripts/download.py "<url>" "<format>" \
    --cookies "<workspace>/cookies.txt" \
    --output "<workspace>/%(title)s [%(id)s].%(ext)s"
  ```

- Treat cookie files as secrets: do not display, copy, modify, commit, or include their contents in logs or responses.
- Do not scan browser profiles or use `cookies-from-browser`. If the user has no exported cookie file, explain how to supply one without accessing the browser on their behalf.
- Do not download when the user only asked to inspect or compare formats.

After a successful download, the script prints `Download complete: <absolute-path>` after merging and other post-processing. Report that path together with the selected format ID or combination. On failure, surface yt-dlp's relevant error and recommend updating yt-dlp or checking proxy, Node/EJS, ffmpeg, authentication, and format availability as applicable.
