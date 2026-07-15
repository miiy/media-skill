#!/usr/bin/env python3
"""Transcribe local audio or video files into timestamped SRT subtitles."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import math
import os
import stat
import sys
import tempfile
import threading
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple


DEFAULT_MODEL = "small"
DEFAULT_DEVICE = "auto"
DEFAULT_COMPUTE_TYPE = "default"
DEFAULT_TASK = "transcribe"
DEFAULT_OUTPUT_SUFFIX = "_asr.srt"
DEFAULT_JOBS = 1

MEDIA_EXTENSIONS = {
    ".aac",
    ".aiff",
    ".alac",
    ".avi",
    ".flac",
    ".flv",
    ".m2ts",
    ".m4a",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".ogg",
    ".opus",
    ".ts",
    ".wav",
    ".webm",
    ".wma",
    ".wmv",
}

THREAD_STATE = threading.local()


@dataclass(frozen=True)
class TranscriberConfig:
    model: str = DEFAULT_MODEL
    device: str = DEFAULT_DEVICE
    compute_type: str = DEFAULT_COMPUTE_TYPE
    local_files_only: bool = False


@dataclass(frozen=True)
class ProcessResult:
    input: str
    output: str
    status: str
    language: Optional[str] = None
    error: Optional[str] = None


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def subtitle_suffix(value: str) -> str:
    if not value.lower().endswith(".srt"):
        raise argparse.ArgumentTypeError("subtitle suffix must end with .srt")
    return value


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Transcribe local audio or video files into SRT subtitles."
    )
    parser.add_argument("input", type=Path, help="input media file or directory")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output SRT for a file, or output directory for a directory input",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"faster-whisper model name or local directory (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--language",
        help="spoken-language code such as zh or en (default: auto-detect)",
    )
    parser.add_argument(
        "--task",
        choices=("transcribe", "translate"),
        default=DEFAULT_TASK,
        help="preserve the spoken language or translate speech to English",
    )
    parser.add_argument(
        "--device",
        default=DEFAULT_DEVICE,
        help=f"inference device (default: {DEFAULT_DEVICE})",
    )
    parser.add_argument(
        "--compute-type",
        default=DEFAULT_COMPUTE_TYPE,
        help=f"CTranslate2 compute type (default: {DEFAULT_COMPUTE_TYPE})",
    )
    parser.add_argument(
        "--vad-filter",
        action="store_true",
        help="filter long non-speech sections before transcription",
    )
    parser.add_argument(
        "--local-files-only",
        action="store_true",
        help="disable model downloads and use only a local directory or cache",
    )
    parser.add_argument(
        "--suffix",
        type=subtitle_suffix,
        default=DEFAULT_OUTPUT_SUFFIX,
        help=f"default subtitle filename suffix (default: {DEFAULT_OUTPUT_SUFFIX})",
    )
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="scan subdirectories when the input is a directory",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace existing subtitle files",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=positive_int,
        default=DEFAULT_JOBS,
        help=f"media files to process concurrently (default: {DEFAULT_JOBS})",
    )
    parser.add_argument("--json", action="store_true", help="print JSON results")
    return parser.parse_args(argv)


def default_output_path(
    media_path: Path, suffix: str = DEFAULT_OUTPUT_SUFFIX
) -> Path:
    return media_path.with_name(f"{media_path.stem}{suffix}")


def looks_like_explicit_path(value: str) -> bool:
    return Path(value).is_absolute() or value.startswith((".", "~"))


def build_model_load_error(
    model: str, local_files_only: bool, exc: Exception
) -> str:
    message = str(exc).strip() or exc.__class__.__name__
    candidate = Path(model).expanduser()

    if candidate.is_dir():
        return (
            f"unable to load local CTranslate2 model directory: {candidate.resolve()}\n"
            f"backend error: {message}"
        )

    if looks_like_explicit_path(model):
        return (
            f"local model directory not found: {candidate.resolve()}\n"
            "pass an existing CTranslate2 faster-whisper model directory"
        )

    if local_files_only:
        return (
            f"model '{model}' is not available locally and downloads are disabled\n"
            "provide a local CTranslate2 model directory or pre-populate the "
            "model cache\n"
            f"backend error: {message}"
        )

    return (
        f"unable to load faster-whisper model '{model}'. Named models are downloaded "
        "from Hugging Face on first use. Check network access, or pass a local "
        "CTranslate2 model directory with --local-files-only.\n"
        f"backend error: {message}"
    )


class FasterWhisperTranscriber:
    def __init__(self, config: TranscriberConfig):
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise RuntimeError(
                "faster-whisper is not installed; run: "
                "python -m pip install -r requirements.txt"
            ) from exc

        candidate = Path(config.model).expanduser()
        if looks_like_explicit_path(config.model) and not candidate.is_dir():
            message = build_model_load_error(
                config.model,
                True,
                FileNotFoundError(),
            )
            raise ValueError(message)

        resolved_model = (
            str(candidate.resolve()) if candidate.is_dir() else config.model
        )
        try:
            self.model = WhisperModel(
                resolved_model,
                device=config.device,
                compute_type=config.compute_type,
                local_files_only=config.local_files_only,
            )
        except Exception as exc:
            raise RuntimeError(
                build_model_load_error(config.model, config.local_files_only, exc)
            ) from exc

    def transcribe(
        self,
        media_path: Path,
        language: Optional[str] = None,
        task: str = DEFAULT_TASK,
        vad_filter: bool = False,
    ) -> Dict[str, Any]:
        segments, info = self.model.transcribe(
            str(media_path),
            language=language,
            task=task,
            vad_filter=vad_filter,
        )
        timed_segments = []
        text_parts = []
        for segment in segments:
            text = (segment.text or "").strip()
            if not text:
                continue
            text_parts.append(segment.text)
            timed_segments.append(
                {
                    "start": float(segment.start),
                    "end": float(segment.end),
                    "text": text,
                }
            )

        transcript = "".join(text_parts).strip()
        if not transcript or not timed_segments:
            raise ValueError(f"no speech transcript generated for: {media_path}")

        return {
            "text": transcript,
            "segments": timed_segments,
            "language": getattr(info, "language", None),
            "language_probability": getattr(info, "language_probability", None),
            "duration": getattr(info, "duration", None),
        }


def build_transcriber(config: TranscriberConfig) -> FasterWhisperTranscriber:
    return FasterWhisperTranscriber(config)


def normalize_transcription_result(result: Any) -> Dict[str, Any]:
    if not isinstance(result, dict):
        raise ValueError("transcriber must return a dictionary with timed segments")

    raw_segments = result.get("segments") or []
    normalized_segments = []
    for index, segment in enumerate(raw_segments, 1):
        if not isinstance(segment, dict):
            raise ValueError(f"segment {index} must be a dictionary")
        if "start" not in segment or "end" not in segment:
            raise ValueError(f"segment {index} must include start and end values")

        text = str(segment.get("text", "")).replace("\r\n", "\n").strip()
        if not text:
            continue
        try:
            start = max(0.0, float(segment["start"]))
            end = float(segment["end"])
        except (TypeError, ValueError) as exc:
            raise ValueError(f"segment {index} has invalid timestamps") from exc
        if not math.isfinite(start) or not math.isfinite(end):
            raise ValueError(f"segment {index} has non-finite timestamps")
        normalized_segments.append(
            {
                "start": start,
                "end": max(start + 0.001, end),
                "text": text,
            }
        )

    normalized_segments.sort(key=lambda segment: (segment["start"], segment["end"]))
    if not normalized_segments:
        raise ValueError("transcription did not contain any timed speech segments")

    transcript = str(result.get("text", "")).strip()
    if not transcript:
        transcript = " ".join(segment["text"] for segment in normalized_segments)

    language_value = result.get("language")
    language = str(language_value) if language_value else None
    probability_value = result.get("language_probability")
    try:
        language_probability = (
            float(probability_value) if probability_value is not None else None
        )
    except (TypeError, ValueError):
        language_probability = None

    return {
        "text": transcript,
        "segments": normalized_segments,
        "language": language,
        "language_probability": language_probability,
        "duration": result.get("duration"),
    }


def format_srt_timestamp(seconds: float) -> str:
    total_milliseconds = max(0, round(seconds * 1000))
    hours, remainder = divmod(total_milliseconds, 3_600_000)
    minutes, remainder = divmod(remainder, 60_000)
    seconds_part, milliseconds = divmod(remainder, 1000)
    return f"{hours:02d}:{minutes:02d}:{seconds_part:02d},{milliseconds:03d}"


def render_srt(segments: Iterable[Dict[str, Any]]) -> str:
    blocks = []
    for index, segment in enumerate(segments, 1):
        blocks.append(
            "\n".join(
                [
                    str(index),
                    (
                        f"{format_srt_timestamp(segment['start'])} --> "
                        f"{format_srt_timestamp(segment['end'])}"
                    ),
                    str(segment["text"]),
                ]
            )
        )
    if not blocks:
        raise ValueError("subtitle output requires timed speech segments")
    return "\n\n".join(blocks) + "\n"


def write_text_atomic(output_path: Path, content: str) -> None:
    if output_path.suffix.lower() != ".srt":
        raise ValueError("output path must end with .srt")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_mode = (
        stat.S_IMODE(output_path.stat().st_mode) if output_path.exists() else 0o644
    )
    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}-",
        suffix=output_path.suffix,
        dir=str(output_path.parent),
        text=True,
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(file_descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
        temp_path.replace(output_path)
        output_path.chmod(output_mode)
    finally:
        temp_path.unlink(missing_ok=True)


def transcribe_media(
    input_path: Path,
    output_path: Path,
    transcriber: Any,
    language: Optional[str] = None,
    task: str = DEFAULT_TASK,
    vad_filter: bool = False,
) -> Dict[str, Any]:
    if not input_path.is_file():
        raise ValueError(f"input media not found: {input_path}")
    if not hasattr(transcriber, "transcribe"):
        raise ValueError("transcriber must define a transcribe method")

    result = normalize_transcription_result(
        transcriber.transcribe(
            input_path,
            language=language,
            task=task,
            vad_filter=vad_filter,
        )
    )
    write_text_atomic(output_path, render_srt(result["segments"]))
    return result


def is_media_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in MEDIA_EXTENSIONS


def collect_media_paths(input_dir: Path, recursive: bool) -> List[Path]:
    candidates = input_dir.rglob("*") if recursive else input_dir.iterdir()
    return sorted(
        (path for path in candidates if is_media_file(path)),
        key=lambda path: str(path).casefold(),
    )


def batch_output_path(
    media_path: Path,
    input_dir: Path,
    output_dir: Optional[Path],
    suffix: str,
) -> Path:
    if output_dir is None:
        return default_output_path(media_path, suffix)
    relative_path = media_path.relative_to(input_dir)
    return output_dir / relative_path.parent / f"{media_path.stem}{suffix}"


def build_jobs(
    input_path: Path,
    output_path: Optional[Path],
    suffix: str,
    recursive: bool,
) -> List[Tuple[Path, Path]]:
    if input_path.is_file():
        destination = output_path or default_output_path(input_path, suffix)
        if destination.suffix.lower() != ".srt":
            raise ValueError("output path must end with .srt")
        return [(input_path, destination)]

    if not input_path.is_dir():
        raise ValueError(f"input path not found: {input_path}")

    media_paths = collect_media_paths(input_path, recursive)
    if not media_paths:
        raise ValueError(f"no supported audio or video files found in: {input_path}")

    jobs = [
        (media, batch_output_path(media, input_path, output_path, suffix))
        for media in media_paths
    ]
    output_counts: Dict[Path, int] = {}
    for _, destination in jobs:
        output_counts[destination] = output_counts.get(destination, 0) + 1
    collisions = [path for path, count in output_counts.items() if count > 1]
    if collisions:
        raise ValueError(
            f"multiple media files map to the same output path: {collisions[0]}"
        )
    return jobs


def get_thread_transcriber(config: TranscriberConfig) -> FasterWhisperTranscriber:
    if getattr(THREAD_STATE, "config", None) != config:
        THREAD_STATE.transcriber = build_transcriber(config)
        THREAD_STATE.config = config
    return THREAD_STATE.transcriber


def execute_job(
    source: Path,
    destination: Path,
    config: TranscriberConfig,
    language: Optional[str],
    task: str,
    vad_filter: bool,
) -> ProcessResult:
    try:
        transcriber = get_thread_transcriber(config)
        result = transcribe_media(
            source,
            destination,
            transcriber,
            language=language,
            task=task,
            vad_filter=vad_filter,
        )
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError("subtitle file was not created")
    except Exception as exc:
        return ProcessResult(
            str(source),
            str(destination),
            "failed",
            error=str(exc),
        )
    return ProcessResult(
        str(source),
        str(destination),
        "succeeded",
        language=result.get("language"),
    )


def process_jobs(
    jobs: Sequence[Tuple[Path, Path]],
    config: TranscriberConfig,
    language: Optional[str],
    task: str,
    vad_filter: bool,
    overwrite: bool,
    workers: int,
) -> List[ProcessResult]:
    results = []
    pending = []
    for source, destination in jobs:
        if destination.exists() and not overwrite:
            results.append(ProcessResult(str(source), str(destination), "skipped"))
        else:
            pending.append((source, destination))

    with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
        futures = [
            executor.submit(
                execute_job,
                source,
                destination,
                config,
                language,
                task,
                vad_filter,
            )
            for source, destination in pending
        ]
        for future in concurrent.futures.as_completed(futures):
            results.append(future.result())

    return sorted(results, key=lambda result: result.input.casefold())


def result_payload(results: Sequence[ProcessResult]) -> Dict[str, Any]:
    counts = {
        status: sum(result.status == status for result in results)
        for status in ("succeeded", "skipped", "failed")
    }
    return {
        "processed": len(results),
        **counts,
        "results": [asdict(result) for result in results],
    }


def print_results(results: Sequence[ProcessResult], as_json: bool) -> None:
    payload = result_payload(results)
    if as_json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return

    for result in results:
        print(f"[{result.status}] {result.input} -> {result.output}")
        if result.language:
            print(f"  language: {result.language}")
        if result.error:
            print(f"  {result.error}")
    print(
        "Processed: {processed} | Succeeded: {succeeded} | "
        "Skipped: {skipped} | Failed: {failed}".format(**payload)
    )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    input_path = args.input.expanduser().resolve()
    output_path = args.output.expanduser().resolve() if args.output else None
    model_candidate = Path(args.model).expanduser()
    model = str(model_candidate.resolve()) if model_candidate.is_dir() else args.model
    config = TranscriberConfig(
        model=model,
        device=args.device,
        compute_type=args.compute_type,
        local_files_only=args.local_files_only,
    )

    try:
        jobs = build_jobs(input_path, output_path, args.suffix, args.recursive)
        results = process_jobs(
            jobs,
            config=config,
            language=args.language,
            task=args.task,
            vad_filter=args.vad_filter,
            overwrite=args.overwrite,
            workers=args.jobs,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"transcribe: {exc}", file=sys.stderr)
        return 1

    print_results(results, args.json)
    return 1 if any(result.status == "failed" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
