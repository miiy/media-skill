#!/usr/bin/env python3
"""Create timestamped contact sheets from one video or a directory of videos."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Sequence, Tuple

from PIL import Image, ImageDraw, ImageFont


DEFAULT_ROWS = 4
DEFAULT_COLUMNS = 4
DEFAULT_SCALE_RATIO = 0.5
DEFAULT_OUTPUT_SUFFIX = "_grid.jpg"
DEFAULT_JOBS = 1

FRAME_GAP = 5
OUTER_PADDING = 5
HEADER_HEIGHT = 100
FONT_SIZE = 18

PREFERRED_FONT_FILENAMES = (
    "msyh.ttc",
    "msyh.ttf",
    "msyhl.ttc",
    "msyhbd.ttc",
    "Microsoft YaHei.ttf",
    "Microsoft YaHei UI.ttf",
)
FALLBACK_FONT_FILENAMES = (
    "PingFang.ttc",
    "Hiragino Sans GB.ttc",
    "STHeiti Medium.ttc",
    "Arial Unicode.ttf",
    "NotoSansCJK-Regular.ttc",
    "NotoSansCJKsc-Regular.otf",
    "NotoSansSC-Regular.otf",
    "simhei.ttf",
    "simsun.ttc",
    "segoeui.ttf",
    "DejaVuSans.ttf",
    "LiberationSans-Regular.ttf",
    "Arial.ttf",
    "Helvetica.ttc",
)

VIDEO_EXTENSIONS = {
    ".avi",
    ".flv",
    ".m2ts",
    ".m4v",
    ".mkv",
    ".mov",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".mts",
    ".ts",
    ".webm",
    ".wmv",
}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


@dataclass(frozen=True)
class VideoInfo:
    path: Path
    width: int
    height: int
    duration_seconds: float
    size_bytes: int


@dataclass(frozen=True)
class ProcessResult:
    input: str
    output: str
    status: str
    error: Optional[str] = None


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def image_suffix(value: str) -> str:
    if Path(value).suffix.lower() not in IMAGE_EXTENSIONS:
        supported = ", ".join(sorted(IMAGE_EXTENSIONS))
        raise argparse.ArgumentTypeError(
            f"suffix must end with a supported image extension: {supported}"
        )
    return value


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create timestamped contact sheets from local video files."
    )
    parser.add_argument("input", type=Path, help="input video file or directory")
    parser.add_argument(
        "-o",
        "--output",
        type=Path,
        help="output image for a video, or output directory for a directory input",
    )
    parser.add_argument(
        "-r",
        "--rows",
        type=positive_int,
        default=DEFAULT_ROWS,
        help=f"grid rows (default: {DEFAULT_ROWS})",
    )
    parser.add_argument(
        "-c",
        "--columns",
        "--cols",
        dest="columns",
        type=positive_int,
        default=DEFAULT_COLUMNS,
        help=f"grid columns (default: {DEFAULT_COLUMNS})",
    )
    size_group = parser.add_mutually_exclusive_group()
    size_group.add_argument(
        "-s",
        "--scale-ratio",
        "--ratio",
        dest="scale_ratio",
        type=positive_float,
        default=DEFAULT_SCALE_RATIO,
        help=f"resize ratio for each frame (default: {DEFAULT_SCALE_RATIO})",
    )
    size_group.add_argument(
        "-w",
        "--thumbnail-width",
        type=positive_int,
        help="fixed thumbnail width in pixels instead of --scale-ratio",
    )
    parser.add_argument(
        "--suffix",
        type=image_suffix,
        default=DEFAULT_OUTPUT_SUFFIX,
        help=f"default output filename suffix (default: {DEFAULT_OUTPUT_SUFFIX})",
    )
    parser.add_argument("--font", type=Path, help="custom TrueType/OpenType font")
    parser.add_argument(
        "--recursive",
        action="store_true",
        help="scan subdirectories when the input is a directory",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="replace existing output images",
    )
    parser.add_argument(
        "-j",
        "--jobs",
        type=positive_int,
        default=DEFAULT_JOBS,
        help=f"videos to process concurrently (default: {DEFAULT_JOBS})",
    )
    parser.add_argument("--json", action="store_true", help="print JSON results")
    return parser.parse_args(argv)


def format_timestamp(seconds: float, include_tenths: bool = False) -> str:
    total_tenths = max(0, round(seconds * 10))
    whole_seconds, tenths = divmod(total_tenths, 10)
    hours, remainder = divmod(whole_seconds, 3600)
    minutes, seconds_part = divmod(remainder, 60)
    text = f"{hours:02d}:{minutes:02d}:{seconds_part:02d}"
    return f"{text}.{tenths}" if include_tenths else text


def format_file_size(size_bytes: int) -> str:
    if size_bytes >= 1024**3:
        return f"{size_bytes / (1024**3):.1f} GB"
    return f"{size_bytes / (1024**2):.1f} MB"


def sample_timestamps(duration_seconds: float, frame_count: int) -> List[float]:
    if duration_seconds <= 0:
        raise ValueError("video duration must be greater than 0")
    if frame_count <= 0:
        raise ValueError("frame count must be greater than 0")

    interval = duration_seconds / (frame_count + 1)
    return [interval * index for index in range(1, frame_count + 1)]


def default_output_path(video_path: Path, suffix: str = DEFAULT_OUTPUT_SUFFIX) -> Path:
    return video_path.with_name(f"{video_path.stem}{suffix}")


def run_command(command: Sequence[str]) -> subprocess.CompletedProcess:
    try:
        return subprocess.run(
            list(command),
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        details = (exc.stderr or exc.stdout or "").strip().splitlines()
        message = details[-1] if details else f"exit code {exc.returncode}"
        raise RuntimeError(f"{Path(command[0]).name} failed: {message}") from exc


def check_external_tools() -> None:
    missing = [name for name in ("ffmpeg", "ffprobe") if shutil.which(name) is None]
    if missing:
        raise RuntimeError(f"required command not found on PATH: {', '.join(missing)}")


def probe_video(video_path: Path) -> VideoInfo:
    if not video_path.is_file():
        raise ValueError(f"input video not found: {video_path}")

    result = run_command(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=width,height,duration:format=duration",
            "-of",
            "json",
            str(video_path),
        ]
    )
    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"ffprobe returned invalid JSON for: {video_path}") from exc

    streams = data.get("streams") or []
    if not streams:
        raise ValueError(f"no video stream found in: {video_path}")

    stream = streams[0]
    try:
        width = int(stream["width"])
        height = int(stream["height"])
    except (KeyError, TypeError, ValueError) as exc:
        raise ValueError(f"incomplete video metadata for: {video_path}") from exc

    duration_seconds = None
    for duration_value in (
        (data.get("format") or {}).get("duration"),
        stream.get("duration"),
    ):
        try:
            candidate = float(duration_value)
        except (TypeError, ValueError):
            continue
        if candidate > 0:
            duration_seconds = candidate
            break

    if width <= 0 or height <= 0:
        raise ValueError(f"invalid video dimensions for: {video_path}")
    if duration_seconds is None:
        raise ValueError(f"video duration must be greater than 0: {video_path}")

    return VideoInfo(
        path=video_path,
        width=width,
        height=height,
        duration_seconds=duration_seconds,
        size_bytes=video_path.stat().st_size,
    )


def system_font_directories() -> List[Path]:
    home = Path.home()
    directories = []

    if sys.platform == "win32":
        windows_dir = Path(os.environ.get("WINDIR", r"C:\Windows"))
        directories.append(windows_dir / "Fonts")
    elif sys.platform == "darwin":
        directories.extend(
            [
                home / "Library" / "Fonts",
                Path("/Library/Fonts"),
                Path("/System/Library/Fonts"),
            ]
        )
    else:
        directories.extend(
            [
                home / ".local" / "share" / "fonts",
                home / ".fonts",
                Path("/usr/local/share/fonts"),
                Path("/usr/share/fonts"),
            ]
        )

    return [directory for directory in directories if directory.is_dir()]


def find_system_font_paths(
    directories: Optional[Sequence[Path]] = None,
) -> List[Path]:
    roots = list(directories) if directories is not None else system_font_directories()
    paths_by_name = {}
    for root in roots:
        if not root.is_dir():
            continue
        for path in sorted(root.rglob("*"), key=lambda item: str(item).casefold()):
            if path.is_file():
                paths_by_name.setdefault(path.name.casefold(), path)

    ordered_paths = []
    for filename in PREFERRED_FONT_FILENAMES + FALLBACK_FONT_FILENAMES:
        if path := paths_by_name.get(filename.casefold()):
            ordered_paths.append(path)
    return ordered_paths


def load_font(font_path: Optional[Path], font_size: int = FONT_SIZE):
    if font_path is not None:
        resolved_path = font_path.expanduser()
        if not resolved_path.is_file():
            raise ValueError(f"font file not found: {resolved_path}")
        try:
            return ImageFont.truetype(str(resolved_path), font_size)
        except OSError as exc:
            raise ValueError(f"unable to load font: {resolved_path}") from exc

    for candidate in find_system_font_paths():
        try:
            return ImageFont.truetype(str(candidate), font_size)
        except OSError:
            continue

    try:
        return ImageFont.load_default(size=font_size)
    except TypeError:
        return ImageFont.load_default()


def extract_frames(
    video_path: Path,
    timestamps: Iterable[float],
    temp_dir: Path,
) -> List[Path]:
    frame_paths = []
    for index, timestamp in enumerate(timestamps, 1):
        output_path = temp_dir / f"frame-{index:04d}.jpg"
        run_command(
            [
                "ffmpeg",
                "-hide_banner",
                "-loglevel",
                "error",
                "-nostdin",
                "-ss",
                f"{timestamp:.6f}",
                "-i",
                str(video_path),
                "-frames:v",
                "1",
                "-q:v",
                "2",
                "-y",
                str(output_path),
            ]
        )
        if not output_path.is_file() or output_path.stat().st_size == 0:
            raise RuntimeError(f"ffmpeg did not create frame {index} for: {video_path}")
        frame_paths.append(output_path)
    return frame_paths


def annotate_timestamp(
    image: Image.Image, timestamp: float, font: ImageFont.FreeTypeFont
) -> Image.Image:
    draw = ImageDraw.Draw(image, "RGBA")
    text = format_timestamp(timestamp)
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]

    x = image.width - text_width - 8
    y = image.height - text_height - 8

    outer_offsets = (
        (-2, 0),
        (2, 0),
        (0, -2),
        (0, 2),
        (-1, -1),
        (-1, 1),
        (1, -1),
        (1, 1),
    )
    for offset_x, offset_y in outer_offsets:
        draw.text(
            (x + offset_x, y + offset_y),
            text,
            fill=(0, 0, 0, 120),
            font=font,
        )
    for offset_x, offset_y in ((-1, 0), (1, 0), (0, -1), (0, 1)):
        draw.text(
            (x + offset_x, y + offset_y),
            text,
            fill=(0, 0, 0, 200),
            font=font,
        )

    draw.text((x, y), text, fill=(255, 255, 255), font=font)
    return image


def load_annotated_frames(
    frame_paths: Iterable[Path],
    timestamps: Iterable[float],
    font: ImageFont.FreeTypeFont,
    scale_ratio: float,
    thumbnail_width: Optional[int],
) -> List[Image.Image]:
    resampling = getattr(Image, "Resampling", Image)
    resize_filter = resampling.LANCZOS
    frames = []
    for frame_path, timestamp in zip(frame_paths, timestamps):
        with Image.open(frame_path) as source:
            image = source.convert("RGB")
            width, height = image.size
            if thumbnail_width is not None:
                resize_ratio = thumbnail_width / width
            else:
                resize_ratio = scale_ratio
            resized_width = max(1, round(width * resize_ratio))
            resized_height = max(1, round(height * resize_ratio))
            resized = image.resize(
                (resized_width, resized_height),
                resize_filter,
            )
        frames.append(annotate_timestamp(resized, timestamp, font))
    return frames


def draw_header(
    canvas: Image.Image,
    info: VideoInfo,
    font: ImageFont.FreeTypeFont,
) -> None:
    draw = ImageDraw.Draw(canvas)
    x = OUTER_PADDING + FRAME_GAP
    line_gap = 22
    lines = [
        f"File Name: {info.path.name}",
        f"File Size: {format_file_size(info.size_bytes)} "
        f"({info.size_bytes:,} bytes)",
        f"Resolution: {info.width}x{info.height}",
        f"Duration: {format_timestamp(info.duration_seconds)}",
    ]

    content_height = len(lines) * line_gap
    inner_height = HEADER_HEIGHT - FRAME_GAP * 2
    if content_height < inner_height:
        y = OUTER_PADDING + (HEADER_HEIGHT - content_height) // 2
    else:
        y = OUTER_PADDING + FRAME_GAP

    for line in lines:
        draw.text((x, y), line, fill=(0, 0, 0), font=font)
        y += line_gap


def build_contact_sheet(
    frames: Sequence[Image.Image],
    info: VideoInfo,
    rows: int,
    columns: int,
    font: ImageFont.FreeTypeFont,
) -> Image.Image:
    expected_frames = rows * columns
    if len(frames) != expected_frames:
        raise ValueError(f"expected {expected_frames} frames, received {len(frames)}")

    thumbnail_width, thumbnail_height = frames[0].size
    if any(frame.size != frames[0].size for frame in frames):
        raise ValueError("extracted frames do not have consistent dimensions")

    grid_width = columns * thumbnail_width + (columns - 1) * FRAME_GAP
    grid_height = rows * thumbnail_height + (rows - 1) * FRAME_GAP
    canvas_width = grid_width + OUTER_PADDING * 2
    canvas_height = HEADER_HEIGHT + grid_height + OUTER_PADDING * 2

    canvas = Image.new("RGB", (canvas_width, canvas_height), "white")
    draw_header(canvas, info, font)

    grid_y = OUTER_PADDING + HEADER_HEIGHT
    for index, frame in enumerate(frames):
        row, column = divmod(index, columns)
        x = OUTER_PADDING + column * (thumbnail_width + FRAME_GAP)
        y = grid_y + row * (thumbnail_height + FRAME_GAP)
        canvas.paste(frame, (x, y))
    return canvas


def save_image_atomic(image: Image.Image, output_path: Path) -> None:
    if output_path.suffix.lower() not in IMAGE_EXTENSIONS:
        supported = ", ".join(sorted(IMAGE_EXTENSIONS))
        raise ValueError(
            f"unsupported output image extension; expected one of: {supported}"
        )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_mode = (
        stat.S_IMODE(output_path.stat().st_mode) if output_path.exists() else 0o644
    )
    file_descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{output_path.stem}-",
        suffix=output_path.suffix,
        dir=str(output_path.parent),
    )
    os.close(file_descriptor)
    temp_path = Path(temp_name)
    try:
        save_options = {}
        if output_path.suffix.lower() in {".jpg", ".jpeg", ".webp"}:
            save_options = {"quality": 92}
        image.save(temp_path, **save_options)
        temp_path.replace(output_path)
        output_path.chmod(output_mode)
    finally:
        temp_path.unlink(missing_ok=True)


def generate_video_grid(
    input_path: Path,
    output_path: Path,
    rows: int = DEFAULT_ROWS,
    columns: int = DEFAULT_COLUMNS,
    scale_ratio: float = DEFAULT_SCALE_RATIO,
    thumbnail_width: Optional[int] = None,
    font_path: Optional[Path] = None,
) -> Path:
    info = probe_video(input_path)
    timestamps = sample_timestamps(info.duration_seconds, rows * columns)
    font = load_font(font_path)

    with tempfile.TemporaryDirectory(prefix="video-grid-") as temp_name:
        frame_paths = extract_frames(
            input_path,
            timestamps,
            Path(temp_name),
        )
        frames = load_annotated_frames(
            frame_paths,
            timestamps,
            font,
            scale_ratio,
            thumbnail_width,
        )
        try:
            contact_sheet = build_contact_sheet(frames, info, rows, columns, font)
            try:
                save_image_atomic(contact_sheet, output_path)
            finally:
                contact_sheet.close()
        finally:
            for frame in frames:
                frame.close()
    return output_path


def is_video_file(path: Path) -> bool:
    return path.is_file() and path.suffix.lower() in VIDEO_EXTENSIONS


def collect_video_paths(input_dir: Path, recursive: bool) -> List[Path]:
    candidates = input_dir.rglob("*") if recursive else input_dir.iterdir()
    return sorted(
        (path for path in candidates if is_video_file(path)),
        key=lambda path: str(path).casefold(),
    )


def batch_output_path(
    video_path: Path,
    input_dir: Path,
    output_dir: Optional[Path],
    suffix: str,
) -> Path:
    if output_dir is None:
        return default_output_path(video_path, suffix)
    relative_path = video_path.relative_to(input_dir)
    return output_dir / relative_path.parent / f"{video_path.stem}{suffix}"


def build_jobs(
    input_path: Path,
    output_path: Optional[Path],
    suffix: str,
    recursive: bool,
) -> List[Tuple[Path, Path]]:
    if input_path.is_file():
        if input_path.suffix.lower() not in VIDEO_EXTENSIONS:
            extension = input_path.suffix or "(none)"
            raise ValueError(f"unsupported video extension: {extension}")
        return [(input_path, output_path or default_output_path(input_path, suffix))]

    if not input_path.is_dir():
        raise ValueError(f"input path not found: {input_path}")

    videos = collect_video_paths(input_path, recursive)
    if not videos:
        raise ValueError(f"no supported video files found in: {input_path}")

    jobs = [
        (video, batch_output_path(video, input_path, output_path, suffix))
        for video in videos
    ]
    output_counts = {}
    for _, destination in jobs:
        output_counts[destination] = output_counts.get(destination, 0) + 1
    collisions = [path for path, count in output_counts.items() if count > 1]
    if collisions:
        raise ValueError(
            f"multiple videos map to the same output path: {collisions[0]}"
        )
    return jobs


def execute_job(
    source: Path,
    destination: Path,
    rows: int,
    columns: int,
    scale_ratio: float,
    thumbnail_width: Optional[int],
    font_path: Optional[Path],
) -> ProcessResult:
    try:
        generate_video_grid(
            source,
            destination,
            rows=rows,
            columns=columns,
            scale_ratio=scale_ratio,
            thumbnail_width=thumbnail_width,
            font_path=font_path,
        )
        if not destination.is_file() or destination.stat().st_size == 0:
            raise RuntimeError("output image was not created")
    except Exception as exc:
        return ProcessResult(str(source), str(destination), "failed", str(exc))
    return ProcessResult(str(source), str(destination), "succeeded")


def process_jobs(
    jobs: Sequence[Tuple[Path, Path]],
    rows: int,
    columns: int,
    scale_ratio: float,
    thumbnail_width: Optional[int],
    font_path: Optional[Path],
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
        future_jobs = {
            executor.submit(
                execute_job,
                source,
                destination,
                rows,
                columns,
                scale_ratio,
                thumbnail_width,
                font_path,
            ): source
            for source, destination in pending
        }
        for future in concurrent.futures.as_completed(future_jobs):
            results.append(future.result())

    return sorted(results, key=lambda result: result.input.casefold())


def result_payload(results: Sequence[ProcessResult]) -> dict:
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
    font_path = args.font.expanduser().resolve() if args.font else None

    try:
        check_external_tools()
        jobs = build_jobs(input_path, output_path, args.suffix, args.recursive)
        results = process_jobs(
            jobs,
            rows=args.rows,
            columns=args.columns,
            scale_ratio=args.scale_ratio,
            thumbnail_width=args.thumbnail_width,
            font_path=font_path,
            overwrite=args.overwrite,
            workers=args.jobs,
        )
    except (OSError, RuntimeError, ValueError) as exc:
        print(f"video-grid: {exc}", file=sys.stderr)
        return 1

    print_results(results, args.json)
    return 1 if any(result.status == "failed" for result in results) else 0


if __name__ == "__main__":
    sys.exit(main())
