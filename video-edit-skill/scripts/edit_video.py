#!/usr/bin/env python3
"""Trim and transform one local video with ffmpeg."""

from __future__ import annotations

import argparse
import json
import math
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Sequence, Tuple

if __package__:
    from .media_utils import (
        OutputExistsError,
        add_faststart,
        atomic_destination,
        check_external_tools,
        ffmpeg_base_command,
        parse_crop,
        parse_size,
        parse_time,
        positive_float,
        probe_media,
        run_command,
        validate_output_path,
    )
else:
    from media_utils import (  # type: ignore
        OutputExistsError,
        add_faststart,
        atomic_destination,
        check_external_tools,
        ffmpeg_base_command,
        parse_crop,
        parse_size,
        parse_time,
        positive_float,
        probe_media,
        run_command,
        validate_output_path,
    )


DEFAULT_SUFFIX = "_edited.mp4"


@dataclass(frozen=True)
class EditResult:
    input: str
    output: str
    status: str
    mode: str
    error: Optional[str] = None


def argparse_time(value: str) -> float:
    try:
        return parse_time(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def argparse_positive_float(value: str) -> float:
    try:
        return positive_float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def argparse_size(value: str) -> Tuple[int, int]:
    try:
        return parse_size(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def argparse_crop(value: str) -> Tuple[int, int, int, int]:
    try:
        return parse_crop(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Trim or transform one local video with ffmpeg."
    )
    parser.add_argument("input", type=Path, help="input video file")
    parser.add_argument("-o", "--output", type=Path, help="output video path")
    parser.add_argument(
        "--mode",
        choices=("precise", "lossless"),
        default="precise",
        help="frame-accurate re-encode or keyframe-aligned stream copy",
    )
    parser.add_argument("--start", type=argparse_time, default=0.0)
    trim_group = parser.add_mutually_exclusive_group()
    trim_group.add_argument("--end", type=argparse_time)
    trim_group.add_argument("--duration", type=argparse_time)
    parser.add_argument(
        "--speed",
        type=argparse_positive_float,
        default=1.0,
        help="playback speed multiplier, for example 0.5 or 2",
    )
    parser.add_argument(
        "--crop",
        type=argparse_crop,
        metavar="WIDTHxHEIGHT+X+Y",
        help="crop rectangle, also accepts WIDTH:HEIGHT:X:Y",
    )
    parser.add_argument(
        "--scale",
        type=argparse_size,
        metavar="WIDTHxHEIGHT",
        help="exact output frame size",
    )
    parser.add_argument(
        "--rotate",
        choices=("cw", "ccw", "180"),
        help="rotate clockwise, counter-clockwise, or 180 degrees",
    )
    parser.add_argument("--remove-audio", action="store_true")
    parser.add_argument("--video-codec", default="libx264")
    parser.add_argument("--audio-codec", default="aac")
    parser.add_argument("--crf", type=int, default=18)
    parser.add_argument("--preset", default="medium")
    parser.add_argument("--audio-bitrate", default="192k")
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--json", action="store_true", help="print JSON result")
    return parser.parse_args(argv)


def default_output_path(input_path: Path) -> Path:
    return input_path.with_name(f"{input_path.stem}{DEFAULT_SUFFIX}")


def atempo_filters(speed: float) -> list[str]:
    factors = []
    remaining = speed
    while remaining > 2.0 + 1e-9:
        factors.append(2.0)
        remaining /= 2.0
    while remaining < 0.5 - 1e-9:
        factors.append(0.5)
        remaining /= 0.5
    if not math.isclose(remaining, 1.0, rel_tol=1e-9, abs_tol=1e-9):
        factors.append(remaining)
    return [f"atempo={factor:.8g}" for factor in factors]


def trim_duration(
    source_duration: float,
    start: float,
    end: Optional[float],
    duration: Optional[float],
) -> Optional[float]:
    if start >= source_duration:
        raise ValueError(
            f"start time {start:.3f}s is outside the {source_duration:.3f}s video"
        )
    if end is not None:
        if end <= start:
            raise ValueError("end time must be greater than start time")
        return min(end, source_duration) - start
    if duration is not None:
        if duration <= 0:
            raise ValueError("duration must be greater than 0")
        return min(duration, source_duration - start)
    if start > 0:
        return source_duration - start
    return None


def validate_mode_options(args: argparse.Namespace) -> None:
    if args.mode != "lossless":
        return
    requested_filters = []
    if not math.isclose(args.speed, 1.0):
        requested_filters.append("--speed")
    if args.crop:
        requested_filters.append("--crop")
    if args.scale:
        requested_filters.append("--scale")
    if args.rotate:
        requested_filters.append("--rotate")
    if requested_filters:
        raise ValueError(
            "lossless mode cannot apply filters: " + ", ".join(requested_filters)
        )


def build_edit_command(
    args: argparse.Namespace,
    input_path: Path,
    output_path: Path,
    has_audio: bool,
    clip_duration: Optional[float],
) -> list[str]:
    command = ffmpeg_base_command()
    if args.start > 0:
        command.extend(["-ss", f"{args.start:.6f}"])
    if clip_duration is not None:
        command.extend(["-t", f"{clip_duration:.6f}"])
    command.extend(["-i", str(input_path)])
    command.extend(["-map", "0:v:0"])
    if has_audio and not args.remove_audio:
        command.extend(["-map", "0:a:0"])
    else:
        command.append("-an")
    command.extend(["-sn", "-dn", "-map_metadata", "0"])

    if args.mode == "lossless":
        command.extend(["-c", "copy", "-avoid_negative_ts", "make_zero"])
        add_faststart(command, output_path)
        command.append(str(output_path))
        return command

    video_filters = []
    if args.crop:
        width, height, x, y = args.crop
        video_filters.append(f"crop={width}:{height}:{x}:{y}")
    if args.scale:
        width, height = args.scale
        video_filters.append(f"scale={width}:{height}:flags=lanczos")
    if args.rotate == "cw":
        video_filters.append("transpose=clock")
    elif args.rotate == "ccw":
        video_filters.append("transpose=cclock")
    elif args.rotate == "180":
        video_filters.extend(["hflip", "vflip"])
    if not math.isclose(args.speed, 1.0):
        video_filters.append(f"setpts=PTS/{args.speed:.8g}")
    video_filters.extend(["pad=ceil(iw/2)*2:ceil(ih/2)*2", "format=yuv420p"])
    command.extend(["-vf", ",".join(video_filters)])

    if has_audio and not args.remove_audio:
        audio_filters = atempo_filters(args.speed)
        if audio_filters:
            command.extend(["-af", ",".join(audio_filters)])
        command.extend(["-c:a", args.audio_codec, "-b:a", args.audio_bitrate])

    command.extend(
        [
            "-c:v",
            args.video_codec,
            "-preset",
            args.preset,
            "-crf",
            str(args.crf),
            "-pix_fmt",
            "yuv420p",
        ]
    )
    add_faststart(command, output_path)
    command.append(str(output_path))
    return command


def edit_video(args: argparse.Namespace) -> EditResult:
    check_external_tools()
    validate_mode_options(args)
    source = args.input.expanduser().resolve()
    info = probe_media(source)
    if info.video is None:
        raise ValueError(f"no video stream found in: {source}")
    destination = validate_output_path(
        args.output.expanduser().resolve() if args.output else default_output_path(source)
    )
    duration = trim_duration(info.duration, args.start, args.end, args.duration)

    if destination.exists() and not args.overwrite:
        return EditResult(str(source), str(destination), "skipped", args.mode)

    with atomic_destination(destination, args.overwrite) as temporary_output:
        command = build_edit_command(
            args,
            source,
            temporary_output,
            has_audio=info.audio is not None,
            clip_duration=duration,
        )
        run_command(command)

    return EditResult(str(source), str(destination), "succeeded", args.mode)


def print_result(result: EditResult, as_json: bool) -> None:
    if as_json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return
    print(f"[{result.status}] {result.input} -> {result.output} ({result.mode})")
    if result.error:
        print(f"  {result.error}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        result = edit_video(args)
    except (OSError, RuntimeError, ValueError, OutputExistsError) as exc:
        result = EditResult(
            str(args.input.expanduser().resolve()),
            str(
                (args.output or default_output_path(args.input))
                .expanduser()
                .resolve()
            ),
            "failed",
            args.mode,
            str(exc),
        )
        print_result(result, args.json)
        return 1
    print_result(result, args.json)
    return 0


if __name__ == "__main__":
    sys.exit(main())
