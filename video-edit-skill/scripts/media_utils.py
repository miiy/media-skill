#!/usr/bin/env python3
"""Shared ffmpeg helpers for the video editing skill."""

from __future__ import annotations

import json
import math
import os
import re
import shutil
import stat
import subprocess
import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path
from typing import Iterator, Optional, Sequence, Tuple


OUTPUT_EXTENSIONS = {".mkv", ".mov", ".mp4", ".ts", ".webm"}


@dataclass(frozen=True)
class VideoStream:
    codec: str
    width: int
    height: int
    pixel_format: Optional[str]
    frame_rate: Optional[str]
    fps: Optional[float]


@dataclass(frozen=True)
class AudioStream:
    codec: str
    sample_rate: Optional[int]
    channels: Optional[int]
    channel_layout: Optional[str]


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    duration: float
    video: Optional[VideoStream]
    audio: Optional[AudioStream]


class OutputExistsError(ValueError):
    """Raised when an output exists and overwrite was not requested."""


def check_external_tools() -> None:
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        raise RuntimeError(f"required command not found on PATH: {', '.join(missing)}")


def run_command(command: Sequence[str]) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            list(command),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip().splitlines()
        message = "\n".join(details[-8:]) if details else f"exit code {exc.returncode}"
        raise RuntimeError(f"{Path(command[0]).name} failed:\n{message}") from exc


def parse_time(value: str) -> float:
    """Parse seconds, MM:SS, or HH:MM:SS into non-negative seconds."""
    text = value.strip()
    if not text:
        raise ValueError("time value cannot be empty")

    parts = text.split(":")
    if len(parts) > 3:
        raise ValueError(f"invalid time value: {value}")
    try:
        if len(parts) == 1:
            seconds = float(parts[0])
        elif len(parts) == 2:
            minutes = int(parts[0])
            second_part = float(parts[1])
            if minutes < 0 or not 0 <= second_part < 60:
                raise ValueError
            seconds = minutes * 60 + second_part
        else:
            hours = int(parts[0])
            minutes = int(parts[1])
            second_part = float(parts[2])
            if hours < 0 or not 0 <= minutes < 60 or not 0 <= second_part < 60:
                raise ValueError
            seconds = hours * 3600 + minutes * 60 + second_part
    except (TypeError, ValueError) as exc:
        raise ValueError(f"invalid time value: {value}") from exc

    if not math.isfinite(seconds) or seconds < 0:
        raise ValueError(f"invalid time value: {value}")
    return seconds


def positive_float(value: str) -> float:
    try:
        parsed = float(value)
    except ValueError as exc:
        raise ValueError(f"value must be a positive number: {value}") from exc
    if not math.isfinite(parsed) or parsed <= 0:
        raise ValueError(f"value must be a positive number: {value}")
    return parsed


def parse_size(value: str) -> Tuple[int, int]:
    match = re.fullmatch(r"(\d+)[x:](\d+)", value.strip(), re.IGNORECASE)
    if not match:
        raise ValueError("size must use WIDTHxHEIGHT, for example 1920x1080")
    width, height = (int(item) for item in match.groups())
    if width <= 0 or height <= 0:
        raise ValueError("width and height must be greater than 0")
    if width % 2 or height % 2:
        raise ValueError("width and height must be even for yuv420p output")
    return width, height


def parse_crop(value: str) -> Tuple[int, int, int, int]:
    text = value.strip()
    match = re.fullmatch(r"(\d+)[x:](\d+)[+:](\d+)[+:](\d+)", text)
    if not match:
        raise ValueError(
            "crop must use WIDTHxHEIGHT+X+Y or WIDTH:HEIGHT:X:Y"
        )
    width, height, x, y = (int(item) for item in match.groups())
    if width <= 0 or height <= 0:
        raise ValueError("crop width and height must be greater than 0")
    if width % 2 or height % 2:
        raise ValueError("crop width and height must be even for yuv420p output")
    return width, height, x, y


def _fraction_to_float(value: Optional[str]) -> Optional[float]:
    if not value or value in {"0/0", "N/A"}:
        return None
    try:
        result = float(Fraction(value))
    except (ValueError, ZeroDivisionError):
        return None
    return result if math.isfinite(result) and result > 0 else None


def probe_media(path: Path) -> MediaInfo:
    resolved = path.expanduser().resolve()
    if not resolved.is_file():
        raise ValueError(f"input media not found: {resolved}")

    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            (
                "format=duration:stream=codec_type,codec_name,width,height,"
                "pix_fmt,avg_frame_rate,r_frame_rate,sample_rate,channels,"
                "channel_layout,duration"
            ),
            "-of",
            "json",
            str(resolved),
        ]
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ffprobe returned invalid JSON for: {resolved}") from exc

    streams = data.get("streams") or []
    video_data = next(
        (stream for stream in streams if stream.get("codec_type") == "video"),
        None,
    )
    audio_data = next(
        (stream for stream in streams if stream.get("codec_type") == "audio"),
        None,
    )

    duration = None
    duration_values = [(data.get("format") or {}).get("duration")]
    duration_values.extend(stream.get("duration") for stream in streams)
    for raw_duration in duration_values:
        try:
            candidate = float(raw_duration)
        except (TypeError, ValueError):
            continue
        if math.isfinite(candidate) and candidate > 0:
            duration = candidate
            break
    if duration is None:
        raise ValueError(f"media duration must be greater than 0: {resolved}")

    video = None
    if video_data is not None:
        try:
            width = int(video_data["width"])
            height = int(video_data["height"])
        except (KeyError, TypeError, ValueError) as exc:
            raise ValueError(f"incomplete video stream metadata: {resolved}") from exc
        frame_rate = video_data.get("r_frame_rate") or video_data.get("avg_frame_rate")
        video = VideoStream(
            codec=str(video_data.get("codec_name") or "unknown"),
            width=width,
            height=height,
            pixel_format=video_data.get("pix_fmt"),
            frame_rate=frame_rate,
            fps=_fraction_to_float(frame_rate),
        )

    audio = None
    if audio_data is not None:
        try:
            sample_rate = int(audio_data["sample_rate"])
        except (KeyError, TypeError, ValueError):
            sample_rate = None
        try:
            channels = int(audio_data["channels"])
        except (KeyError, TypeError, ValueError):
            channels = None
        audio = AudioStream(
            codec=str(audio_data.get("codec_name") or "unknown"),
            sample_rate=sample_rate,
            channels=channels,
            channel_layout=audio_data.get("channel_layout"),
        )

    return MediaInfo(resolved, duration, video, audio)


def validate_output_path(path: Path) -> Path:
    resolved = path.expanduser().resolve()
    if resolved.suffix.lower() not in OUTPUT_EXTENSIONS:
        supported = ", ".join(sorted(OUTPUT_EXTENSIONS))
        raise ValueError(f"unsupported output extension; choose one of: {supported}")
    return resolved


@contextmanager
def atomic_destination(output_path: Path, overwrite: bool) -> Iterator[Path]:
    output = validate_output_path(output_path)
    if output.exists() and not overwrite:
        raise OutputExistsError(f"output already exists: {output}")

    output.parent.mkdir(parents=True, exist_ok=True)
    output_mode = stat.S_IMODE(output.stat().st_mode) if output.exists() else 0o644
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{output.stem}-",
        suffix=output.suffix,
        dir=str(output.parent),
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        yield temp_path
        if not temp_path.is_file() or temp_path.stat().st_size == 0:
            raise RuntimeError("ffmpeg did not create a non-empty output file")
        temp_path.replace(output)
        output.chmod(output_mode)
    finally:
        temp_path.unlink(missing_ok=True)


def ffmpeg_base_command() -> list[str]:
    return ["ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin", "-y"]


def add_faststart(command: list[str], output_path: Path) -> None:
    if output_path.suffix.lower() in {".mp4", ".mov"}:
        command.extend(["-movflags", "+faststart"])
