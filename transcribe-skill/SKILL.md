---
name: transcribe-skill
description: Transcribe speech from local audio or video files into timestamped SRT subtitles with faster-whisper. Use whenever the user asks to generate captions, subtitles, speech-to-text, transcripts with timestamps, translate spoken audio into English subtitles, or batch-transcribe a directory of local media. Accepts local files and directories only and does not download remote URLs. Do not use for speaker diarization or when the user only wants media metadata.
compatibility: Requires Python 3.10 or newer and the bundled pip requirements. Named models require network access on first use; local CTranslate2 model directories work offline.
---

# Transcribe

Use the bundled script for deterministic local media transcription. Resolve bundled resources relative to this `SKILL.md` and treat the Skill directory as read-only.

## Runtime Boundaries

- Run commands with the process working directory set to the user's workspace.
- Read the script and requirements from `<skill-dir>`, but do not create or modify files there.
- Keep source media, generated subtitles, explicitly downloaded models, logs, and other runtime data in `<workspace>` or another path requested by the user.
- Let named models use the normal per-user Hugging Face cache. Never create virtual environments, model directories, caches, outputs, or temporary files under `<skill-dir>`.

## Prepare The Runtime

Install the Python dependencies into the active environment when they are unavailable:

```bash
python -m pip install -r <skill-dir>/requirements.txt
```

Before running transcription, confirm that the input is a local file or directory. This Skill does not download remote URLs; when given a URL, report that a local media path is required.

## Select A Model

Use `small` by default because it balances speed and accuracy. A model name is downloaded from Hugging Face on first use and then reused from the local cache.

- Use `tiny` or `base` only when the user prioritizes speed or a low-resource machine needs a smaller model.
- Use a larger model when the user prioritizes accuracy and the machine has enough memory.
- Pass an existing CTranslate2 model directory to `--model` for offline execution.
- Add `--local-files-only` when network access must be prohibited. A named model must already exist in the local cache for this to work.
- Keep `--device auto --compute-type default` unless the user provides hardware requirements. On CPU, `--device cpu --compute-type int8` can reduce memory use.

Model loading can consume substantial memory. Keep batch processing at `--jobs 1` unless the user explicitly requests concurrency and the machine can hold one model instance per worker.

## Pre-download A Model

When a target machine cannot access Hugging Face, download the complete model directory on a connected machine and copy that directory to the offline machine. If the `hf` command is unavailable, install or update Hugging Face Hub with pip:

```bash
python -m pip install -U huggingface_hub
```

Download a faster-whisper CTranslate2 model into an explicit local directory:

```bash
hf download Systran/faster-whisper-small \
  --local-dir "<workspace>/models/faster-whisper-small"
```

Copy the complete `models/faster-whisper-small` directory into the offline user's workspace. Then use the local directory and prohibit network access explicitly:

```bash
python <skill-dir>/scripts/transcribe_media.py "<workspace>/media.mp4" \
  --model "<workspace>/models/faster-whisper-small" \
  --output "<workspace>/media_asr.srt" \
  --local-files-only --language zh
```

## Transcribe One File

Create `<media-name>_asr.srt` beside a local audio or video file:

```bash
python <skill-dir>/scripts/transcribe_media.py "<workspace>/media.mp4"
```

Set a known language to avoid automatic language detection, or omit it when the language is unknown:

```bash
python <skill-dir>/scripts/transcribe_media.py "<workspace>/media.mp4" \
  --language zh --model small --output "<workspace>/subtitles.srt"
```

Add `--vad-filter` for media with long silent sections. Use `--task translate` only when the user wants spoken language translated into English subtitles; the default task preserves the spoken language.

Do not add `--overwrite` unless the user explicitly wants to replace an existing subtitle file. Without it, existing outputs are reported as skipped.

## Transcribe A Directory

Pass a directory to process supported audio and video files. Use `--recursive` only when subdirectories should be included:

```bash
python <skill-dir>/scripts/transcribe_media.py "<workspace>/media" --recursive
```

Preserve source-relative subdirectories under a separate output directory:

```bash
python <skill-dir>/scripts/transcribe_media.py "<workspace>/media" \
  --recursive --output "<workspace>/subtitles" --language zh
```

Use `--json` when another tool needs structured per-file statuses and detected languages. Human-readable output is more concise for interactive use.

## Report Results

After processing, report each created SRT path, skipped output, and failed input. Include the detected language when available. Surface model download, model compatibility, decoding, and empty-speech errors instead of claiming that a subtitle was generated.
