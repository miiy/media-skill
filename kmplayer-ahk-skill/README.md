# kmplayer-ahk-skill

English | [简体中文](README.zh-CN.md)

Create video grids through KMPlayer's capture dialog using AutoHotkey v2. Supports a single video or recursive directory processing.

## Requirements And Installation

Windows with an interactive desktop, Python 3.10+, `psutil`, AutoHotkey v2, and KMPlayer. Copy this directory into your agent runtime's Skill search path; `SKILL.md` is the entry point.

```powershell
python -m pip install -r "<skill-dir>/requirements.txt"
```

The bundled AHK script uses `C:\KMPlayer\KMPlayer.exe` and the capture directory `C:\KMPlayer\Capture`. KMPlayer must save `<video-stem>.JPG` there. Capture layout and size follow KMPlayer's settings. The window classes and controls used by the script must match your KMPlayer installation.

## Usage

```powershell
python "<skill-dir>/scripts/create_video_grid.py" --input "<workspace>/video.mp4" --output "<workspace>/grids"

python "<skill-dir>/scripts/create_video_grid.py" --input "<workspace>/videos" --output "<workspace>/grids" --ahk "C:/Program Files/AutoHotkey/v2/AutoHotkey.exe"
```

- `--input`: video file or directory; directory scans include subdirectories.
- `--output`: destination directory, default `./output` relative to the working directory.
- `--ahk`: AutoHotkey v2 executable, default `C:\Program Files\AutoHotkey\v2\AutoHotkey.exe`.

The workflow opens KMPlayer, uses Ctrl+Shift+S and the capture dialogs, moves `<video-stem>.JPG` into the output directory, and appends to `log.txt`. Existing target JPGs are overwritten; videos with matching stems share a destination. The workflow closes existing KMPlayer windows and may forcibly close the player after capture. Process videos sequentially.

Verify captures using `log.txt` and the actual output files and modification times. A zero exit code or Python success message alone does not establish success. Run from your workspace; outputs, logs, and environments belong there or at a requested location. This GUI workflow cannot run on macOS or Linux.
