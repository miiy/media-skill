#!/usr/bin/env python3
"""Concatenate local videos with lossless or normalized precise processing."""

from __future__ import annotations

import argparse
import json
import math
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional, Sequence

if __package__:
    from .media_utils import (
        OutputExistsError,
        add_faststart,
        atomic_destination,
        check_external_tools,
        ffmpeg_base_command,
        parse_size,
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
        parse_size,
        positive_float,
        probe_media,
        run_command,
        validate_output_path,
    )


@dataclass(frozen=True)
class ConcatResult:
    inputs: list[str]
    output: str
    status: str
    mode: str
    error: Optional[str] = None


def argparse_positive_float(value: str) -> float:
    try:
        return positive_float(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def argparse_size(value: str) -> tuple[int, int]:
    try:
        return parse_size(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(str(exc)) from exc


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Concatenate local videos in order with ffmpeg."
    )
    parser.add_argument("inputs", nargs="+", type=Path, help="main video files")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--intro", type=Path, help="video to prepend")
    parser.add_argument("--outro", type=Path, help="video to append")
    parser.add_argument(
        "--mode",
        choices=("precise", "lossless"),
        default="precise",
        help="normalize and re-encode or require compatible streams and copy",
    )
    parser.add_argument(
        "--size",
        type=argparse_size,
        metavar="WIDTHxHEIGHT",
        help="precise-mode canvas size; defaults to the first main video",
    )
    parser.add_argument(
        "--fps",
        type=argparse_positive_float,
        help="precise-mode constant frame rate; defaults to the first main video",
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


def ordered_inputs(args: argparse.Namespace) -> list[Path]:
    paths = []
    if args.intro:
        paths.append(args.intro)
    paths.extend(args.inputs)
    if args.outro:
        paths.append(args.outro)
    return [path.expanduser().resolve() for path in paths]


def escape_concat_path(path: Path) -> str:
    return str(path.resolve()).replace("'", r"'\''")


def write_concat_list(paths: Sequence[Path], list_path: Path) -> None:
    content = "".join(f"file '{escape_concat_path(path)}'\n" for path in paths)
    list_path.write_text(content, encoding="utf-8", newline="\n")


def video_signature(info) -> tuple:
    video = info.video
    if video is None:
        return ()
    return (
        video.codec,
        video.width,
        video.height,
        video.pixel_format,
        video.frame_rate,
    )


def audio_signature(info) -> tuple:
    audio = info.audio
    if audio is None:
        return ()
    return (
        audio.codec,
        audio.sample_rate,
        audio.channels,
        audio.channel_layout,
    )


def validate_lossless_compatibility(infos: Sequence, remove_audio: bool) -> None:
    first = infos[0]
    if first.video is None:
        raise ValueError(f"no video stream found in: {first.path}")
    expected_video = video_signature(first)
    expected_audio = audio_signature(first)
    for info in infos[1:]:
        if video_signature(info) != expected_video:
            raise ValueError(
                "lossless concat requires matching video codec, size, pixel format, "
                f"and frame rate; incompatible input: {info.path}"
            )
        if not remove_audio and audio_signature(info) != expected_audio:
            raise ValueError(
                "lossless concat requires matching audio presence, codec, sample rate, "
                f"channels, and layout; incompatible input: {info.path}"
            )


def concat_from_list(
    list_path: Path,
    output_path: Path,
    remove_audio: bool,
) -> None:
    command = ffmpeg_base_command()
    command.extend(
        [
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(list_path),
            "-map",
            "0:v:0",
        ]
    )
    if remove_audio:
        command.append("-an")
    else:
        command.extend(["-map", "0:a:0?"])
    command.extend(["-sn", "-dn", "-c", "copy", "-avoid_negative_ts", "make_zero"])
    add_faststart(command, output_path)
    command.append(str(output_path))
    run_command(command)


def normalize_segment(
    info,
    output_path: Path,
    width: int,
    height: int,
    fps: float,
    remove_audio: bool,
    args: argparse.Namespace,
) -> None:
    if info.video is None:
        raise ValueError(f"no video stream found in: {info.path}")

    command = ffmpeg_base_command()
    command.extend(["-i", str(info.path)])
    silent_audio_input = info.audio is None and not remove_audio
    if silent_audio_input:
        command.extend(
            [
                "-f",
                "lavfi",
                "-t",
                f"{info.duration:.6f}",
                "-i",
                "anullsrc=channel_layout=stereo:sample_rate=48000",
            ]
        )

    command.extend(["-map", "0:v:0"])
    if remove_audio:
        command.append("-an")
    elif info.audio is not None:
        command.extend(["-map", "0:a:0"])
    else:
        command.extend(["-map", "1:a:0", "-shortest"])

    video_filter = ",".join(
        [
            (
                f"scale={width}:{height}:force_original_aspect_ratio=decrease:"
                "flags=lanczos"
            ),
            f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black",
            "setsar=1",
            f"fps={fps:.8g}",
            "format=yuv420p",
        ]
    )
    command.extend(["-vf", video_filter])
    if not remove_audio:
        command.extend(
            [
                "-af",
                "aresample=48000,aformat=sample_fmts=fltp:channel_layouts=stereo",
                "-c:a",
                args.audio_codec,
                "-b:a",
                args.audio_bitrate,
            ]
        )

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
            "-fps_mode",
            "cfr",
            "-t",
            f"{info.duration:.6f}",
            str(output_path),
        ]
    )
    run_command(command)


def concat_videos(args: argparse.Namespace) -> ConcatResult:
    check_external_tools()
    sources = ordered_inputs(args)
    destination = validate_output_path(args.output)
    if destination.exists() and not args.overwrite:
        return ConcatResult(
            [str(path) for path in sources],
            str(destination),
            "skipped",
            args.mode,
        )
    if len(sources) < 2:
        raise ValueError("concatenation requires at least two input videos")
    if args.mode == "lossless" and (args.size or args.fps):
        raise ValueError("lossless mode cannot apply --size or --fps")

    infos = [probe_media(path) for path in sources]
    if not infos:
        raise ValueError("at least one input video is required")
    if any(info.video is None for info in infos):
        missing = next(info.path for info in infos if info.video is None)
        raise ValueError(f"no video stream found in: {missing}")

    with tempfile.TemporaryDirectory(prefix="video-concat-") as temp_name:
        temp_dir = Path(temp_name)
        if args.mode == "lossless":
            validate_lossless_compatibility(infos, args.remove_audio)
            concat_sources = sources
        else:
            main_info_index = 1 if args.intro else 0
            main_video = infos[main_info_index].video
            assert main_video is not None
            if args.size:
                width, height = args.size
            else:
                width = math.ceil(main_video.width / 2) * 2
                height = math.ceil(main_video.height / 2) * 2
            fps = args.fps or main_video.fps or 30.0
            concat_sources = []
            for index, info in enumerate(infos):
                normalized = temp_dir / f"segment-{index:04d}.mp4"
                normalize_segment(
                    info,
                    normalized,
                    width,
                    height,
                    fps,
                    args.remove_audio,
                    args,
                )
                concat_sources.append(normalized)

        concat_list = temp_dir / "inputs.txt"
        write_concat_list(concat_sources, concat_list)
        with atomic_destination(destination, args.overwrite) as temporary_output:
            concat_from_list(concat_list, temporary_output, args.remove_audio)

    return ConcatResult(
        [str(path) for path in sources],
        str(destination),
        "succeeded",
        args.mode,
    )


def print_result(result: ConcatResult, as_json: bool) -> None:
    if as_json:
        print(json.dumps(asdict(result), ensure_ascii=False, indent=2))
        return
    print(f"[{result.status}] {len(result.inputs)} inputs -> {result.output} ({result.mode})")
    if result.error:
        print(f"  {result.error}")


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    sources = ordered_inputs(args)
    try:
        result = concat_videos(args)
    except (OSError, RuntimeError, ValueError, OutputExistsError) as exc:
        result = ConcatResult(
            [str(path) for path in sources],
            str(args.output.expanduser().resolve()),
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
