# video-grid-skill

[English](README.md) | 中文

`video-grid-skill` 用于从本地视频均匀抽帧并生成带时间戳的视频网格图（contact sheet）。既可处理单个视频，也可批量处理目录。

## 功能

- 按视频时长在起止边界内均匀抽取浮点时间点，短视频也不会因整秒取整而重复抽帧
- 默认使用 `0.5` 缩放比例、白色头部和白字黑描边时间戳样式
- 自动优先使用系统中的 Microsoft YaHei，否则依次尝试常见系统字体和 Pillow 默认字体
- 在每帧上标注时间戳，并在顶部写入文件名、大小、分辨率和时长
- 支持单文件、目录、递归目录和并发批处理
- 默认跳过已有输出，使用 `--overwrite` 后才覆盖
- 批量输出到单独目录时保留源目录结构
- 支持人类可读结果和 `--json` 结构化结果

## 依赖

- Python 3.9 或更高版本
- `ffmpeg` 和 `ffprobe`，且已经加入 `PATH`
- Pillow

使用 pip 安装 Python 依赖：

```bash
python -m pip install -r <skill-dir>/requirements.txt
```

## 安装为 Skill

将 `video-grid-skill` 目录复制或链接到智能体运行时支持的 Skill 搜索目录。
不同智能体的安装位置和发现机制不同；安装后应保持本目录结构完整，并确保运行时
能够读取 `SKILL.md`。

Skill 标识为 `video-grid-skill`。

## 运行目录

Skill 安装目录只用于读取 `SKILL.md`、脚本和依赖清单，运行时不应修改。
执行命令时使用用户工作区作为工作目录；源视频、生成的网格图和其他运行数据保存在
用户工作区或用户明确指定的位置。处理中产生的临时帧使用操作系统临时目录。

下文用 `<skill-dir>` 表示 Skill 安装目录，用 `<workspace>` 表示用户工作区。

## 单视频

```bash
python <skill-dir>/scripts/create_video_grid.py <workspace>/video.mp4
```

默认在源视频旁生成 `<视频名>_grid.jpg`。自定义布局和输出路径：

```bash
python <skill-dir>/scripts/create_video_grid.py <workspace>/video.mp4 \
  --rows 3 \
  --columns 5 \
  --scale-ratio 0.4 \
  --output <workspace>/contact-sheet.jpg
```

## 批量处理

```bash
python <skill-dir>/scripts/create_video_grid.py <workspace>/videos --recursive
```

将结果写入独立目录并保留原始子目录：

```bash
python <skill-dir>/scripts/create_video_grid.py <workspace>/videos \
  --recursive \
  --output <workspace>/grids \
  --jobs 4
```

## 常用参数

- `INPUT`：必填，本地视频文件或目录
- `-o, --output`：单视频时为输出图片；目录模式时为输出目录
- `-r, --rows`：行数，默认 `4`
- `-c, --columns, --cols`：列数，默认 `4`
- `-s, --scale-ratio, --ratio`：缩略图相对原始帧的比例，默认 `0.5`
- `-w, --thumbnail-width`：显式指定缩略图宽度；与 `--scale-ratio` 互斥
- `--suffix`：默认输出后缀，默认 `_grid.jpg`
- `--font`：自定义 TrueType/OpenType 字体文件；不传时自动选择系统字体
- `--recursive`：递归扫描输入目录
- `--overwrite`：覆盖已有输出
- `-j, --jobs`：并发处理数量，默认 `1`
- `--json`：输出 JSON 结果

支持的输入扩展名包括 `.mp4`、`.mov`、`.mkv`、`.avi`、`.wmv`、`.flv`、`.m4v`、`.ts`、`.mts`、`.m2ts`、`.webm`、`.mpeg` 和 `.mpg`。

## 目录结构

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
