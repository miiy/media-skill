# yt-dlp-skill

[English](README.md) | 中文

`yt-dlp-skill` 用于通过 [yt-dlp](https://github.com/yt-dlp/yt-dlp) 查看可下载媒体格式，并下载选定的音频或视频流。

## 功能

- 使用 yt-dlp 原生表格布局列出可下载格式
- 输出适合自动化处理的结构化 JSON
- 显示分辨率、编解码器、码率、文件大小、协议和格式 ID
- 支持仅音频媒体，不要求存在视频分辨率
- 自动下载最佳可用视频和音频
- 下载指定格式，或组合 `137+140` 这类视频和音频 ID
- 当 `PATH` 中存在 Node 时自动使用 Node
- 继承环境中的 `http_proxy` 和 `https_proxy`
- 默认匿名访问，并支持显式提供 Cookie 文件

## 依赖

- Python 3.10 或更高版本
- pip
- 建议安装 Node.js 22 或更高版本，以完整支持 YouTube JavaScript challenge
- 合并独立视频流和音频流时需要 ffmpeg

## 安装依赖

在用户管理的已激活 Python 环境中安装内置依赖：

```bash
python -m pip install -r <skill-dir>/requirements.txt
```

`yt-dlp[default]` 依赖包含推荐的 Python 依赖和 `yt-dlp-ejs`。

## 安装为 Skill

将 `yt-dlp-skill` 目录复制或链接到智能体运行时支持的 Skill 搜索目录。不同智能体的安装位置和发现机制不同；安装后应保持本目录结构完整，并确保运行时能够读取 `SKILL.md`。

Skill 标识为 `yt-dlp-skill`。

## 运行目录

Skill 安装目录应视为只读。命令从用户工作区运行，从 `<skill-dir>` 读取脚本和依赖清单，并将下载文件、Cookie 文件、日志和其他运行数据保存在 `<workspace>` 或用户指定的其他位置。下面每个下载示例都使用显式的工作区输出模板。

## 查看格式

打印视频元数据和所有可下载的音视频格式：

```bash
python <skill-dir>/scripts/list_formats.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

改为输出 JSON：

```bash
python <skill-dir>/scripts/list_formats.py --json \
  "https://www.youtube.com/watch?v=VIDEO_ID"
```

表格使用与 `yt-dlp -F` 相同的列，包括 `ID`、`RESOLUTION`、编解码器、码率、大小、协议和 `MORE INFO`。
仅音频媒体会在人类可读摘要中显示 `audio only`，并在 JSON 中将 `best_resolution` 设为 `null`。

## 下载

下载最佳可用视频和音频：

```bash
python <skill-dir>/scripts/download.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --output "<workspace>/%(title)s [%(id)s].%(ext)s"
```

下载一个已合并格式：

```bash
python <skill-dir>/scripts/download.py "https://www.youtube.com/watch?v=VIDEO_ID" 18 \
  --output "<workspace>/%(title)s [%(id)s].%(ext)s"
```

组合一个纯视频格式和一个纯音频格式：

```bash
python <skill-dir>/scripts/download.py "https://www.youtube.com/watch?v=VIDEO_ID" "137+140" \
  --output "<workspace>/%(title)s [%(id)s].%(ext)s"
```

格式 ID 会因视频不同而变化。先运行 `list_formats.py`，不要假定示例 ID 一定可用。

设置自定义输出模板：

```bash
python <skill-dir>/scripts/download.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  "137+140" \
  --output "<workspace>/downloads/%(title)s [%(id)s].%(ext)s"
```

下载、合并和其他后处理完成后，脚本会将最终绝对路径打印为
`Download complete: <absolute-path>`。

## Proxy

脚本使用标准代理环境变量：

```bash
export https_proxy=http://127.0.0.1:7890
python <skill-dir>/scripts/list_formats.py "https://www.youtube.com/watch?v=VIDEO_ID"
```

## Cookies

内置脚本默认不读取浏览器配置或 Cookie。如需显式使用导出的 Mozilla/Netscape 格式 Cookie 文件：

```bash
python <skill-dir>/scripts/list_formats.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  --cookies "<workspace>/cookies.txt"

python <skill-dir>/scripts/download.py "https://www.youtube.com/watch?v=VIDEO_ID" \
  "137+140" \
  --cookies "<workspace>/cookies.txt" \
  --output "<workspace>/%(title)s [%(id)s].%(ext)s"
```

Cookie 文件包含账户凭据。不要提交、打印内容或分享。脚本不支持自动读取浏览器配置。

## 目录结构

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
