#!/usr/bin/env python3
"""Generate one JPEG per local video with configurable height, skipping black frames."""

from __future__ import annotations

import argparse
import hashlib
from contextlib import redirect_stdout
import json
import re
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

import cv2
import numpy as np


DEFAULT_HEIGHT = 180

VIDEO_EXTENSIONS = {
    ".avi", ".flv", ".m2ts", ".m4v", ".mkv", ".mov", ".mp4",
    ".mpeg", ".mpg", ".mts", ".ts", ".webm", ".wmv",
}


def compute_file_hash(
    file_path: str,
    algorithm: str = "sha256",
    chunk_size: int = 8 * 1024 * 1024
) -> str:
    """
    Compute the full hash of a file.

    Suitable for small to medium files where 100% uniqueness is required.
    Reads the file in chunks to avoid high memory usage.

    Args:
        file_path: Path to the file.
        algorithm: Hash algorithm ('md5', 'sha1', 'sha256', etc.).
        chunk_size: Read size per iteration (default 8 MB).

    Returns:
        Hexadecimal hash string.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    try:
        hasher = hashlib.new(algorithm)
    except ValueError:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(chunk_size), b""):
            hasher.update(chunk)

    return hasher.hexdigest()


def compute_file_fingerprint(
    file_path: str,
    sample_size: int = 2 * 1024 * 1024,
    algorithm: str = "sha256"
) -> str:
    """
    Compute a fast fingerprint for large files (e.g., videos, images).

    Instead of hashing the entire file, this function:
      - Hashes the file size (to add uniqueness)
      - Reads the first and last `sample_size` bytes
      - Uses the specified hash algorithm to combine them

    Much faster for large files with minimal collision risk.

    Args:
        file_path: Path to the file.
        sample_size: Number of bytes to read from both the start and end.
        algorithm: Hash algorithm ('sha256' by default).

    Returns:
        Hexadecimal fingerprint string.
    """
    if not os.path.isfile(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")

    st = os.stat(file_path)
    file_size = st.st_size

    try:
        hasher = hashlib.new(algorithm)
    except ValueError:
        raise ValueError(f"Unsupported algorithm: {algorithm}")

    with open(file_path, "rb") as f:
        if file_size <= 2 * sample_size:
            # Small file: hash the entire content
            hasher.update(f.read())
        else:
            # Add file size to strengthen uniqueness
            hasher.update(str(file_size).encode("utf-8"))

            # Read the first sample
            hasher.update(f.read(sample_size))

            # Read the last sample
            f.seek(-sample_size, os.SEEK_END)
            hasher.update(f.read(sample_size))

    return hasher.hexdigest()


def get_video_duration(video_path: str) -> tuple[float, str]:
    """
    Get the duration of a video in seconds and formatted time (HH:MM:SS).

    Args:
        video_path: Path to the video file.

    Returns:
        (duration_seconds, formatted_time)
    """
    result = subprocess.run(
        ['ffmpeg', '-i', video_path],
        stderr=subprocess.PIPE,
        stdout=subprocess.PIPE
    )
    output = result.stderr.decode('utf-8')

    match = re.search(r'Duration: (\d+):(\d+):(\d+\.\d+)', output)
    if match:
        hours, minutes, seconds = match.groups()
        seconds = float(seconds)
        total_seconds = int(hours) * 3600 + int(minutes) * 60 + seconds
        formatted = f"{int(hours)}:{int(minutes):02}:{int(seconds):02}"
        return total_seconds, formatted
    return 0, "0:00:00"


def is_black_frame(image, threshold: float = 0.80) -> bool:
    """
    Determine whether an image is mostly black.

    Args:
        image: Input image (BGR format).
        threshold: Percentage of dark pixels to consider as black (default: 0.8).

    Returns:
        True if the image is considered black, otherwise False.
    """
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    black_pixels = np.sum(gray < 50)
    total_pixels = gray.size
    black_ratio = black_pixels / total_pixels
    return black_ratio > threshold


def generate_video_thumbnail(video_path: str, height: int = 180) -> bytes | None:
    """
    Generate a thumbnail for a video based on duration and brightness.

    The function:
        - Determines video duration
        - Chooses a frame (skipping black frames)
        - Scales it to the requested height (default: 180px)
        - Returns binary JPEG data

    Args:
        video_path: Path to the video file.
        height: Thumbnail height in pixels (default: 180).

    Returns:
        JPEG binary bytes or None if failed.
    """
    duration, formatted_duration = get_video_duration(video_path)
    print(f"Video duration: {formatted_duration}")

    file_size = os.path.getsize(video_path)

    # less 100MB or less 20 minute
    if file_size < 100 * 1024 * 1024 or int(duration) <= 60 * 20:
        seek_time = 0
    else:
        seek_time = 5

    with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as tmp:
        temp_frame_path = tmp.name

    while seek_time < duration:
        cmd = [
            'ffmpeg', '-y', '-ss', str(seek_time), '-i', video_path,
            '-frames:v', '1', '-vf', f'scale=-1:{height}', '-q:v', '3', temp_frame_path
        ]
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

        frame = cv2.imread(temp_frame_path)

        if frame is None:
            print("Cannot read frame, possible video corruption.")
            break

        if is_black_frame(frame):
            print(f"Frame at {seek_time}s is black, trying next second...")
            seek_time += 1
        else:
            print(f"Thumbnail found at {seek_time}s.")
            with open(temp_frame_path, "rb") as f:
                image_bytes = f.read()
            os.remove(temp_frame_path)
            return image_bytes

    os.remove(temp_frame_path)
    return None


def write_output(destination: Path, data: bytes, overwrite: bool) -> bool:
    """Publish complete bytes; do not replace an existing file by default."""
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=destination.parent, suffix=".tmp", delete=False) as tmp:
        temporary = Path(tmp.name)
        try:
            tmp.write(data)
        except BaseException:
            temporary.unlink(missing_ok=True)
            raise
    try:
        if overwrite:
            os.replace(temporary, destination)
        else:
            try:
                os.link(temporary, destination)
            except FileExistsError:
                return False
        return True
    finally:
        temporary.unlink(missing_ok=True)


def process_video(
    path: Path,
    output_dir: Path,
    overwrite: bool = False,
    height: int = DEFAULT_HEIGHT,
    hash_mode: str = "fingerprint",
) -> dict:
    result = {"input": str(path), "output": None, "status": "failed"}
    try:
        if hash_mode == "fingerprint":
            digest = compute_file_fingerprint(path)
        elif hash_mode == "full":
            digest = compute_file_hash(path)
        else:
            raise ValueError(f"Unsupported hash mode: {hash_mode}")
        destination = output_dir / f"{digest}.jpg"
        result["output"] = str(destination)
        if destination.exists() and not overwrite:
            result["status"] = "skipped"
            return result
        if destination.resolve() == path.resolve():
            raise ValueError("Output must not replace the source video")
        with redirect_stdout(sys.stderr):
            jpeg = generate_video_thumbnail(str(path), height=height)
        if jpeg is None:
            raise ValueError("No thumbnail generated: duration unavailable, frame unreadable, or all sampled frames black")
        if write_output(destination, jpeg, overwrite):
            result["status"] = "succeeded"
        else:
            result["status"] = "skipped"
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        result["error"] = str(exc)
    return result


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("height must be a positive integer") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("height must be a positive integer")
    return parsed


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="local video or directory")
    parser.add_argument("--output", type=Path, default=Path("output"), help="output directory (default: ./output)")
    parser.add_argument("--height", type=positive_int, default=DEFAULT_HEIGHT,
                        help=f"thumbnail height in pixels (default: {DEFAULT_HEIGHT}); width scales proportionally")
    parser.add_argument("--hash-mode", choices=("fingerprint", "full"), default="fingerprint",
                        help="filename hashing: sampled fingerprint (default) or full-file SHA-256")
    parser.add_argument("--recursive", action="store_true", help="include subdirectories")
    parser.add_argument("--overwrite", action="store_true", help="replace existing thumbnails")
    parser.add_argument("--json", action="store_true", help="print a JSON array of per-file results")
    args = parser.parse_args(argv)
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    try:
        if not source.exists():
            raise ValueError(f"Input does not exist: {source}")
        if source.is_file():
            files = [source]
        elif source.is_dir():
            candidates = source.rglob("*") if args.recursive else source.iterdir()
            files = sorted(p for p in candidates if p.is_file() and p.suffix.lower() in VIDEO_EXTENSIONS)
        else:
            raise ValueError(f"Input is not a regular file or directory: {source}")
        if not files:
            raise ValueError("No supported video files found")
        if output.exists() and not output.is_dir():
            raise ValueError(f"Output must be a directory: {output}")
        missing = [name for name in ("ffmpeg",) if not shutil.which(name)]
        if missing:
            raise ValueError(f"Missing prerequisites on PATH: {', '.join(missing)}")
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    results = [
        process_video(path, output, args.overwrite, height=args.height, hash_mode=args.hash_mode)
        for path in files
    ]
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(f"{result['status']}: {result['input']} -> {result['output']}"
                  + (f" ({result['error']})" if "error" in result else ""))
    return int(any(result["status"] == "failed" for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
