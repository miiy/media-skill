# transcribe-skill

English | [Simplified Chinese](README.zh-CN.md)

`transcribe-skill` uses `faster-whisper` to transcribe local audio or video files
into timestamped SRT subtitles. It supports single files, directories, recursive
directory scans, and batch processing.

## Features

- Process common local audio and video formats
- Produce UTF-8 SRT subtitles
- Detect the spoken language automatically, or set it with `--language`
- Transcribe speech, or translate speech to English subtitles with
  `--task translate`
- Support VAD silence filtering
- Support Hugging Face model names, local CTranslate2 model directories, and
  strict offline mode
- Process only local files or directories; remote URLs are not downloaded
- Skip existing outputs by default and overwrite only with `--overwrite`
- Preserve source-relative directory structure for batch output directories
- Support both human-readable output and structured `--json` output

## Requirements

- Python 3.10 or newer
- `faster-whisper` and its Python dependencies

Install with pip:

```bash
python -m pip install -r <skill-dir>/requirements.txt
```

## Install As A Skill

Copy or symlink the `transcribe-skill` directory into the Skill search path
supported by your agent runtime. Installation paths and discovery mechanisms
vary between agents; keep this directory structure intact and ensure the runtime
can read `SKILL.md`.

The Skill identifier is `transcribe-skill`.

## Runtime Directory

Treat the installed Skill directory as read-only. Run commands from the user's
workspace; keep media files, subtitles, local models, and other runtime data in
the user workspace or another location explicitly requested by the user. Models
downloaded by name use the normal per-user Hugging Face cache and do not create
model or cache directories inside the Skill directory.

The examples below use `<skill-dir>` for the installed Skill directory and
`<workspace>` for the user workspace.

Inputs must be local files or directories. If the user provides a remote URL,
ask for a local media path first; this Skill does not download media.

## Models

The default model is `small`. When a model name is provided, the first run
downloads it from Hugging Face and later runs reuse the local cache:

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media.mp4 --model small
```

Offline environments can use an existing CTranslate2 model directory:

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media.mp4 \
  --model <workspace>/models/faster-whisper-small \
  --local-files-only
```

If a model name is used with `--local-files-only`, that model must already exist
in the local cache.

### Pre-download A Model

When the target machine cannot access Hugging Face, download the model on a
connected machine first, then copy the complete model directory to the offline
machine.

If the `hf` command is unavailable, install or update Hugging Face Hub with pip:

```bash
python -m pip install -U huggingface_hub
```

Download a faster-whisper CTranslate2 model:

```bash
hf download Systran/faster-whisper-small \
  --local-dir <workspace>/models/faster-whisper-small
```

After the download finishes, copy the complete `models/faster-whisper-small`
directory to the offline machine's user workspace.

Use the local model on the offline machine and explicitly prohibit network
downloads:

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media.mp4 \
  --model <workspace>/models/faster-whisper-small \
  --output <workspace>/media_asr.srt \
  --local-files-only \
  --language zh
```

## Single File

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media.mp4
```

By default, the script creates `<file-name>_asr.srt` beside the source file. Set
the language, model, and output path explicitly:

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media.mp4 \
  --language zh \
  --model small \
  --output <workspace>/subtitles.srt
```

Enable VAD for recordings with long silent sections:

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/audio.m4a --vad-filter
```

Translate non-English speech into English subtitles:

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media.mp4 --task translate
```

## Batch Processing

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media --recursive
```

Write subtitles to a separate directory and preserve source-relative
subdirectories:

```bash
python <skill-dir>/scripts/transcribe_media.py <workspace>/media \
  --recursive \
  --output <workspace>/subtitles \
  --language zh
```

ASR models can use substantial memory, so batch processing defaults to
`--jobs 1`. Increase concurrency only when the machine has enough memory for one
model instance per worker.

## Common Options

- `INPUT`: required local media file or directory
- `-o, --output`: SRT path for a single file, or output directory for directory
  mode
- `--model`: model name or local model directory; default is `small`
- `--language`: language code such as `zh` or `en`; omitted means auto-detect
- `--task`: `transcribe` or `translate`; default is `transcribe`
- `--device`: inference device; default is `auto`
- `--compute-type`: compute precision; default is `default`
- `--vad-filter`: filter long silent sections
- `--local-files-only`: disable model downloads and use only a local directory
  or cache
- `--recursive`: scan input directories recursively
- `--overwrite`: replace existing subtitles
- `-j, --jobs`: number of concurrent workers; default is `1`
- `--suffix`: batch output filename suffix; default is `_asr.srt`
- `--json`: print JSON results

Directory mode supports common audio formats such as `.mp3`, `.m4a`, `.wav`,
`.flac`, `.aac`, `.ogg`, and `.opus`, plus video formats such as `.mp4`, `.mov`,
`.mkv`, `.avi`, `.webm`, and `.ts`. Single-file mode only requires the backend
to decode the file and does not restrict the extension.

## Structure

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
