# transcribe-skill

[English](README.md) | 中文

`transcribe-skill` 使用 `faster-whisper` 将本地音频或视频转写为带时间戳的 SRT 字幕。支持单文件、目录、递归目录和批量处理。

## 功能

- 处理常见本地音视频格式
- 输出 UTF-8 SRT 字幕
- 支持自动语言检测或通过 `--language` 指定语言
- 支持语音转写，以及通过 `--task translate` 翻译为英文字幕
- 支持 VAD 静音过滤
- 支持 Hugging Face 模型名、本地 CTranslate2 模型目录和严格离线模式
- 只处理本地文件或目录，不下载远程 URL
- 默认跳过已有输出，使用 `--overwrite` 后才覆盖
- 批量输出到独立目录时保留源目录结构
- 支持人类可读结果和 `--json` 结构化结果

## 依赖

- Python 3.10 或更高版本
- faster-whisper 及其 Python 依赖

使用 pip 安装：

```bash
python -m pip install -r <skill-dir>/requirements.txt
```

## 安装为 Skill

将 `transcribe-skill` 目录复制或链接到智能体运行时支持的 Skill 搜索目录。不同智能体的安装位置和发现机制不同；安装后应保持本目录结构完整，并确保运行时能够读取 `SKILL.md`。

Skill 标识为 `transcribe-skill`。

## 运行目录

Skill 安装目录只用于读取 `SKILL.md`、脚本和依赖清单，运行时不应修改。执行命令时
使用用户工作区作为工作目录；媒体文件、字幕、本地模型和其他运行数据保存在用户
工作区或用户明确指定的位置。通过模型名自动下载的模型使用 Hugging Face 的用户级
缓存，不在 Skill 目录中创建模型或缓存目录。

下文用 `<skill-dir>` 表示 Skill 安装目录，用 `<workspace>` 表示用户工作区。

输入必须是本地文件或目录。如果收到远程 URL，应提示用户先提供本地媒体路径；本
Skill 不执行下载。

## 模型

默认模型是 `small`。传入模型名时，首次运行会从 Hugging Face 下载模型，之后复用本地缓存：

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media.mp4 --model small
```

离线环境可传入现有的 CTranslate2 模型目录：

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media.mp4 \
  --model <workspace>/models/faster-whisper-small \
  --local-files-only
```

如果使用模型名并加上 `--local-files-only`，该模型必须已经存在于本地缓存中。

### 手动下载模型

如果目标机器不能访问 Hugging Face，可以先在能联网的机器上把模型下载到独立目录，再把整个模型目录复制到离线机器。

如果 `hf` 命令不可用，使用 pip 安装或更新 Hugging Face Hub：

```bash
python -m pip install -U huggingface_hub
```

下载 faster-whisper 的 CTranslate2 模型：

```bash
hf download Systran/faster-whisper-small \
  --local-dir <workspace>/models/faster-whisper-small
```

下载完成后，将整个 `models/faster-whisper-small` 目录复制到离线机器的用户工作区。

在离线机器上使用本地模型，并显式禁止网络下载：

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media.mp4 \
  --model <workspace>/models/faster-whisper-small \
  --output <workspace>/media_asr.srt \
  --local-files-only \
  --language zh
```

## 单文件

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media.mp4
```

默认在源文件旁生成 `<文件名>_asr.srt`。指定语言、模型和输出路径：

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media.mp4 \
  --language zh \
  --model small \
  --output <workspace>/subtitles.srt
```

长时间静音的录音可启用 VAD：

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/audio.m4a --vad-filter
```

将非英语语音翻译成英文字幕：

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media.mp4 --task translate
```

## 批量处理

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media --recursive
```

将字幕写入独立目录并保留原始子目录结构：

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media \
  --recursive \
  --output <workspace>/subtitles \
  --language zh
```

ASR 模型占用内存较多，批处理默认 `--jobs 1`。只有在内存足够容纳每个 worker 的独立模型实例时才应提高并发数。

## 常用参数

- `INPUT`：必填，本地媒体文件或目录
- `-o, --output`：单文件时为 SRT 路径；目录模式时为输出目录
- `--model`：模型名或本地模型目录，默认 `small`
- `--language`：语言代码，例如 `zh`、`en`；不传时自动检测
- `--task`：`transcribe` 或 `translate`，默认 `transcribe`
- `--device`：推理设备，默认 `auto`
- `--compute-type`：计算精度，默认 `default`
- `--vad-filter`：过滤长静音片段
- `--local-files-only`：禁止模型下载，只使用本地目录或缓存
- `--recursive`：递归扫描输入目录
- `--overwrite`：覆盖已有字幕
- `-j, --jobs`：并发处理数量，默认 `1`
- `--suffix`：批量输出文件后缀，默认 `_asr.srt`
- `--json`：输出 JSON 结果

目录模式支持常见音频格式（如 `.mp3`、`.m4a`、`.wav`、`.flac`、`.aac`、`.ogg`、`.opus`）和视频格式（如 `.mp4`、`.mov`、`.mkv`、`.avi`、`.webm`、`.ts`）。单文件模式只要求后端能够解码该文件，不限制扩展名。

## 目录结构

```text
transcribe-skill/
|-- SKILL.md
|-- README.md
|-- README.zh-CN.md
|-- requirements.txt
|-- evals/
|   `-- evals.json
|-- scripts/
|   `-- transcribe_media.py
`-- tests/
    `-- test_transcribe_media.py
```
