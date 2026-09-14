---
name: kmplayer-ahk-skill
description: Automate KMPlayer video grid captures on Windows using AutoHotkey v2, for one local video or a directory of videos. Use when the user requests KMPlayer screenshots, its capture dialog, or the AHK grid workflow; not for ordinary single-frame thumbnails or FFmpeg contact sheets.
---

# KMPlayer AHK

Use the Python entry point and bundled `ahk_scripts/kmplayer_grid.ahk` to drive KMPlayer's capture dialog.

## Runtime

Requires Python 3.10+, `psutil`, Windows with an interactive desktop, AutoHotkey v2, and KMPlayer. The GUI workflow cannot run on macOS or Linux.

Resolve bundled resources relative to this `SKILL.md`. Run from the user's workspace and store outputs and logs there or at the requested location. Treat the skill installation as read-only. If needed, install dependencies into the active environment:

```powershell
python -m pip install -r "<skill-dir>/requirements.txt"
```

The AHK script uses `C:\KMPlayer\KMPlayer.exe` and `C:\KMPlayer\Capture`. The AutoHotkey executable defaults to `C:\Program Files\AutoHotkey\v2\AutoHotkey.exe`; override it with `--ahk`. KMPlayer must save captures under the configured capture directory as `<video-stem>.JPG`, and its window classes and controls must match the bundled script. Capture layout and dimensions come from KMPlayer's capture settings.

## Run

For a single video:

```powershell
python "<skill-dir>/scripts/create_video_grid.py" --input "<workspace>/video.mp4" --output "<workspace>/grids"
```

For a directory, the script recursively collects videos using MIME types and processes them sequentially:

```powershell
python "<skill-dir>/scripts/create_video_grid.py" --input "<workspace>/videos" --output "<workspace>/grids" --ahk "C:/Program Files/AutoHotkey/v2/AutoHotkey.exe"
```

`--output` is a directory, defaulting to `./output`. The script writes `<video-stem>.JPG` and appends to `log.txt`; same-stem videos share an output name and existing targets are replaced.

The AHK workflow closes any existing KMPlayer window, opens the video, sends Ctrl+Shift+S, confirms capture dialogs, moves the captured JPG, then closes KMPlayer. It may forcibly close an unresponsive player. Run jobs sequentially because they share player windows and the capture directory.

## Verify Results

Inspect `log.txt` and check that each expected JPG exists, is non-empty, and was created or updated during the run. Python success messages and zero process exit codes alone do not prove a capture succeeded: the AHK script logs several failures without a nonzero exit, and the Python loop prints success after the AHK process returns. Report confirmed outputs and capture failures separately. Do not claim Windows GUI validation when only Python checks were run elsewhere.
