# kmplayer-ahk-skill

[English](README.md) | 中文

通过 AutoHotkey v2 操作 KMPlayer 的截图对话框生成视频网格图，支持单视频和目录递归批量处理。

## 依赖与安装

需要具备交互桌面的 Windows、Python 3.10+、`psutil`、AutoHotkey v2 和 KMPlayer。将本目录复制到智能体运行时的 Skill 搜索路径，入口为 `SKILL.md`。

```powershell
python -m pip install -r "<skill-dir>/requirements.txt"
```

AHK 脚本使用 `C:\KMPlayer\KMPlayer.exe`，截图目录为 `C:\KMPlayer\Capture`。KMPlayer 需要在该目录生成 `<视频名>.JPG`。网格布局和尺寸由 KMPlayer 的截图设置决定；窗口类名和控件需要与脚本匹配。

## 使用

```powershell
python "<skill-dir>/scripts/create_video_grid.py" --input "<workspace>/video.mp4" --output "<workspace>/grids"

python "<skill-dir>/scripts/create_video_grid.py" --input "<workspace>/videos" --output "<workspace>/grids" --ahk "C:/Program Files/AutoHotkey/v2/AutoHotkey.exe"
```

- `--input`：视频文件或目录，目录默认递归扫描子目录。
- `--output`：输出目录，默认是当前工作目录下的 `output`。
- `--ahk`：AutoHotkey v2 可执行文件路径，默认 `C:\Program Files\AutoHotkey\v2\AutoHotkey.exe`。

脚本启动 KMPlayer，发送 Ctrl+Shift+S，确认截图对话框，将 `<视频名>.JPG` 移动到输出目录，并追加写入 `log.txt`。目标 JPG 已存在时会覆盖，不同目录中的同名视频会使用同一输出路径。流程会关闭已有 KMPlayer 窗口，截图后也会关闭播放器，未响应时可能强制关闭。批量任务按顺序执行。

完成后需结合 `log.txt`、实际输出文件及修改时间确认截图成功，不能仅依据 Python 的成功提示或进程退出码。运行时以用户工作区为当前目录，输出、日志和环境放在工作区或指定位置。本 GUI 流程无法在 macOS 或 Linux 上运行。
