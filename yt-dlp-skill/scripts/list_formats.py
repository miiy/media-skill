#!/usr/bin/env python3
"""List the downloadable media formats for a media URL."""

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple


def cookie_file(value: str) -> str:
    path = Path(value).expanduser()
    if not path.is_file():
        raise argparse.ArgumentTypeError(f"Cookie file does not exist: {path}")
    return str(path)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect a media URL and list all downloadable formats."
    )
    parser.add_argument("url", help="media URL to inspect")
    parser.add_argument("--json", action="store_true", help="print JSON output")
    parser.add_argument(
        "--cookies",
        type=cookie_file,
        metavar="FILE",
        help="Netscape-format Cookie file (not used by default)",
    )
    return parser.parse_args()


def ydl_options(cookie_path: Optional[str] = None) -> Dict[str, Any]:
    options: Dict[str, Any] = {
        "quiet": True,
        "no_warnings": False,
        "skip_download": True,
        "noplaylist": True,
    }
    if cookie_path:
        options["cookiefile"] = cookie_path
    if node_path := shutil.which("node"):
        options["js_runtimes"] = {"node": {"path": node_path}}
    return options


def resolution_key(video_format: Dict[str, Any]) -> Tuple[float, float, float, float]:
    def number(name: str) -> float:
        value = video_format.get(name)
        return float(value) if isinstance(value, (int, float)) else 0

    width = number("width")
    height = number("height")
    return width * height, height, number("fps"), number("tbr")


def is_media_format(media_format: Dict[str, Any]) -> bool:
    return any(
        codec and codec != "none"
        for codec in (media_format.get("vcodec"), media_format.get("acodec"))
    )


def downloadable_formats(formats: Iterable[Dict[str, Any]]) -> List[Dict[str, Any]]:
    return [media_format for media_format in formats if is_media_format(media_format)]


def get_best_resolution(formats: Iterable[Dict[str, Any]]) -> Optional[str]:
    video_formats = [
        media_format
        for media_format in formats
        if media_format.get("vcodec") not in (None, "none")
        and isinstance(media_format.get("height"), (int, float))
        and media_format["height"] > 0
    ]
    if not video_formats:
        return None

    best_format = max(video_formats, key=resolution_key)
    width = best_format.get("width")
    height = int(best_format["height"])
    if isinstance(width, (int, float)) and width > 0:
        return f"{int(width)}x{height}"
    return f"{height}p"


def extract_info(url: str, cookie_path: Optional[str] = None) -> Dict[str, Any]:
    try:
        from yt_dlp import YoutubeDL
    except ImportError as exc:
        raise RuntimeError(
            "yt-dlp is not installed; run: python -m pip install -r requirements.txt"
        ) from exc

    with YoutubeDL(ydl_options(cookie_path)) as ydl:
        info = ydl.extract_info(url, download=False)

    if not info:
        raise ValueError("unable to retrieve media information")
    return info


def media_type(media_format: Dict[str, Any]) -> str:
    has_video = media_format.get("vcodec") not in (None, "none")
    has_audio = media_format.get("acodec") not in (None, "none")
    if has_video and has_audio:
        return "video+audio"
    return "video" if has_video else "audio"


def duration_text(seconds: Any) -> str:
    if not isinstance(seconds, (int, float)):
        return "unknown"
    total_seconds = int(seconds)
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:d}:{seconds:02d}"


def print_table(info: Dict[str, Any], formats: List[Dict[str, Any]]) -> None:
    from yt_dlp import YoutubeDL

    print(f"Title: {info.get('title') or 'unknown'}")
    print(f"Media ID: {info.get('id') or 'unknown'}")
    print(f"Duration: {duration_text(info.get('duration'))}")
    print(f"Uploader: {info.get('uploader') or info.get('channel') or 'unknown'}")
    print(f"Best resolution: {get_best_resolution(formats) or 'audio only'}")
    print(f"Downloadable formats: {len(formats)}")
    print()

    table_info = {**info, "formats": formats}
    with YoutubeDL({"quiet": True}) as ydl:
        table = ydl.render_formats_table(table_info)
    if not table:
        raise ValueError("unable to render the format table")
    print(table)


def json_output(info: Dict[str, Any], formats: List[Dict[str, Any]]) -> Dict[str, Any]:
    fields = (
        "format_id",
        "ext",
        "width",
        "height",
        "resolution",
        "fps",
        "vcodec",
        "acodec",
        "audio_channels",
        "tbr",
        "filesize",
        "filesize_approx",
        "protocol",
        "format_note",
        "language",
        "dynamic_range",
    )
    return {
        "id": info.get("id"),
        "title": info.get("title"),
        "duration": info.get("duration"),
        "uploader": info.get("uploader") or info.get("channel"),
        "webpage_url": info.get("webpage_url"),
        "best_resolution": get_best_resolution(formats),
        "formats": [
            {
                **{field: media_format.get(field) for field in fields},
                "type": media_type(media_format),
            }
            for media_format in formats
        ],
    }


def main() -> int:
    args = parse_args()
    try:
        info = extract_info(args.url, args.cookies)
        formats = downloadable_formats(info.get("formats") or [])
        if not formats:
            raise ValueError("no downloadable audio or video formats found")
        if args.json:
            print(
                json.dumps(json_output(info, formats), ensure_ascii=False, indent=2)
            )
        else:
            print_table(info, formats)
    except Exception as exc:
        print(f"Inspection failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
