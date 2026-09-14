#!/usr/bin/env python3
"""Generate JPEG thumbnails from local images with configurable height and hash naming."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import sys
import tempfile

import cv2
import numpy as np


DEFAULT_HEIGHT = 180
IMAGE_EXTENSIONS = {".bmp", ".dib", ".jpeg", ".jpg", ".jpe", ".jp2", ".png", ".webp", ".pbm", ".pgm", ".ppm", ".pnm", ".tif", ".tiff"}


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


def generate_image_thumbnail(image_path: str, height: int = 180) -> bytes | None:
    """
    Generate a thumbnail for an image (configurable height, keep aspect ratio).

    Args:
        image_path: Path to the image file.
        height: Thumbnail height in pixels (default: 180).

    Returns:
        Encoded JPEG bytes, or None if failed.
    """
    try:
        with open(image_path, "rb") as f:
            file_bytes = np.frombuffer(f.read(), np.uint8)
    except FileNotFoundError:
        return None

    img = cv2.imdecode(file_bytes, cv2.IMREAD_COLOR)
    if img is None:
        return None

    # Resize to the requested height while keeping aspect ratio
    h, w = img.shape[:2]
    scale = height / h
    new_w = max(int(w * scale), 1)  # Prevent width from becoming 0
    resized = cv2.resize(img, (new_w, height), interpolation=cv2.INTER_AREA)

    success, buffer = cv2.imencode(".jpg", resized)
    if not success:
        return None

    return buffer.tobytes()


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


def positive_int(value: str) -> int:
    try:
        parsed = int(value)
    except ValueError:
        raise argparse.ArgumentTypeError("height must be a positive integer") from None
    if parsed <= 0:
        raise argparse.ArgumentTypeError("height must be a positive integer")
    return parsed


def process_image(
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
        if destination.resolve() == path.resolve():
            raise ValueError("Output must not replace the source image")
        if destination.exists() and not overwrite:
            result["status"] = "skipped"
            return result
        jpeg = generate_image_thumbnail(str(path), height=height)
        if jpeg is None:
            raise ValueError("Cannot decode image or encode JPEG thumbnail")
        result["status"] = "succeeded" if write_output(destination, jpeg, overwrite) else "skipped"
    except (OSError, ValueError, cv2.error) as exc:
        result["error"] = str(exc)
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="local image or directory")
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
            files = sorted(
                path for path in candidates
                if path.is_file() and path.suffix.lower() in IMAGE_EXTENSIONS
                and not (output != source and output.is_relative_to(source)
                         and path.resolve().is_relative_to(output))
            )
        else:
            raise ValueError(f"Input is not a regular file or directory: {source}")
        if not files:
            raise ValueError("No supported image files found")
        if output.exists() and not output.is_dir():
            raise ValueError(f"Output must be a directory: {output}")
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    results = [
        process_image(path, output, args.overwrite, args.height, args.hash_mode)
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
