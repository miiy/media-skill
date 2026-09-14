#!/usr/bin/env python3
"""Generate JPEG thumbnails from local video and image files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from create_image_thumbnail import IMAGE_EXTENSIONS, process_image
from create_video_thumbnail import VIDEO_EXTENSIONS, process_video


MEDIA_TYPES = ("all", "video", "image")


def classify(path: Path, media_type: str) -> str | None:
    if media_type != "all":
        return media_type
    suffix = path.suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return "video"
    if suffix in IMAGE_EXTENSIONS:
        return "image"
    return None


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="local video/image file or directory")
    parser.add_argument("--output", type=Path, default=Path("output"), help="output directory (default: ./output)")
    parser.add_argument("--media-type", choices=MEDIA_TYPES, default="all",
                        help="process all supported media, only videos, or only images (default: all)")
    parser.add_argument("--height", type=int, default=180,
                        help="thumbnail height in pixels (default: 180)")
    parser.add_argument("--hash-mode", choices=("fingerprint", "full"), default="fingerprint",
                        help="filename hashing: sampled fingerprint (default) or full-file SHA-256")
    parser.add_argument("--recursive", action="store_true", help="include subdirectories")
    parser.add_argument("--overwrite", action="store_true", help="replace existing thumbnails")
    parser.add_argument("--json", action="store_true", help="print a JSON array of per-file results")
    args = parser.parse_args(argv)
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    if args.height <= 0:
        parser.error("height must be a positive integer")
    if not source.exists():
        print(f"Error: Input does not exist: {source}", file=sys.stderr)
        return 1
    if output.exists() and not output.is_dir():
        print(f"Error: Output must be a directory: {output}", file=sys.stderr)
        return 1

    if source.is_file():
        media_type = classify(source, args.media_type)
        files = [(source, media_type)] if media_type else []
    elif source.is_dir():
        candidates = source.rglob("*") if args.recursive else source.iterdir()
        files = [
            (path, classify(path, args.media_type))
            for path in sorted(candidates)
            if path.is_file()
            and not (output != source and output.is_relative_to(source)
                     and path.resolve().is_relative_to(output))
        ]
        files = [(path, media_type) for path, media_type in files if media_type]
    else:
        print(f"Error: Input is not a regular file or directory: {source}", file=sys.stderr)
        return 1
    if not files:
        print("Error: No supported video or image files found; use --media-type video or image for an extensionless file", file=sys.stderr)
        return 1

    results = []
    for path, media_type in files:
        if media_type == "video":
            result = process_video(path, output, args.overwrite, args.height, args.hash_mode)
        else:
            result = process_image(path, output, args.overwrite, args.height, args.hash_mode)
        result["media_type"] = media_type
        results.append(result)
    if args.json:
        print(json.dumps(results, ensure_ascii=False, indent=2))
    else:
        for result in results:
            print(f"{result['status']}: {result['input']} -> {result['output']}"
                  + (f" ({result['error']})" if "error" in result else ""))
    return int(any(result["status"] == "failed" for result in results))


if __name__ == "__main__":
    raise SystemExit(main())
