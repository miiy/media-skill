#!/usr/bin/env python3
"""Download a selected media format from a video URL."""

import argparse
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Optional


DEFAULT_FORMAT = "bestvideo+bestaudio/best"


def report_output_path(filename: str) -> None:
    print(f"Download complete: {Path(filename).expanduser().resolve()}")


def cookie_file(value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"Cookie file does not exist: {path}")
    return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download media, optionally with a selected format ID."
    )
    parser.add_argument("url", help="media URL to download")
    parser.add_argument(
        "format",
        nargs="?",
        default=DEFAULT_FORMAT,
        help=(
            "format ID or combination, such as 137, 140, or 137+140 "
            f"(default: {DEFAULT_FORMAT})"
        ),
    )
    parser.add_argument(
        "-o",
        "--output",
        default="%(title)s [%(id)s].%(ext)s",
        help="output filename template",
    )
    parser.add_argument(
        "--cookies",
        type=cookie_file,
        metavar="FILE",
        help="Netscape-format Cookie file (not used by default)",
    )
    return parser.parse_args()


def ydl_options(
    format_selector: str,
    output: str,
    cookie_path: Optional[str] = None,
) -> Dict[str, Any]:
    options: Dict[str, Any] = {
        "format": format_selector,
        "outtmpl": output,
        "noplaylist": True,
        "post_hooks": [report_output_path],
    }
    if cookie_path:
        options["cookiefile"] = cookie_path
    if node_path := shutil.which("node"):
        options["js_runtimes"] = {"node": {"path": node_path}}
    return options


def download(
    url: str,
    format_selector: str,
    output: str,
    cookie_path: Optional[str] = None,
) -> None:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise RuntimeError(
            "yt-dlp is not installed; run: python -m pip install -r requirements.txt"
        ) from exc

    with YoutubeDL(ydl_options(format_selector, output, cookie_path)) as ydl:
        error_code = ydl.download([url])
    if error_code:
        raise RuntimeError(f"yt-dlp returned error code {error_code}")


def main() -> int:
    args = parse_args()
    try:
        download(args.url, args.format, args.output, args.cookies)
    except Exception as exc:
        print(f"Download failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
