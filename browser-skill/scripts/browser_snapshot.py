#!/usr/bin/env python3
"""Inspect a rendered web page and optionally save its text and screenshot."""

from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
from pathlib import Path
from typing import Any, Optional, Sequence
from urllib.parse import urlsplit

SCREENSHOT_EXTENSIONS = {".jpeg", ".jpg", ".png"}
WAIT_UNTIL_VALUES = ("commit", "domcontentloaded", "load", "networkidle")


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("value must be greater than 0")
    return parsed


def validate_url(value: str) -> str:
    parsed = urlsplit(value)
    if parsed.scheme not in {"http", "https", "file"}:
        raise argparse.ArgumentTypeError(
            "URL must use an explicit http, https, or file scheme"
        )
    if parsed.scheme in {"http", "https"} and not parsed.netloc:
        raise argparse.ArgumentTypeError("HTTP URL must include a host")
    if parsed.scheme == "file" and not parsed.path:
        raise argparse.ArgumentTypeError("file URL must include a path")
    return value


def screenshot_path(value: str) -> Path:
    path = Path(value).expanduser()
    if path.suffix.lower() not in SCREENSHOT_EXTENSIONS:
        supported = ", ".join(sorted(SCREENSHOT_EXTENSIONS))
        raise argparse.ArgumentTypeError(
            f"screenshot must use a supported extension: {supported}"
        )
    return path


def parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Inspect a rendered page with Playwright Chromium."
    )
    parser.add_argument("url", type=validate_url, help="explicit HTTP, HTTPS, or file URL")
    parser.add_argument("--screenshot", type=screenshot_path, help="PNG or JPEG output path")
    parser.add_argument("--text-output", type=Path, help="UTF-8 visible-text output path")
    parser.add_argument("--selector", default="body", help="locator used for text extraction")
    parser.add_argument("--wait-for", help="locator that must become visible")
    parser.add_argument(
        "--wait-until",
        choices=WAIT_UNTIL_VALUES,
        default="domcontentloaded",
        help="navigation readiness event (default: domcontentloaded)",
    )
    parser.add_argument(
        "--timeout",
        type=positive_int,
        default=30_000,
        help="navigation and locator timeout in milliseconds (default: 30000)",
    )
    parser.add_argument("--viewport-width", type=positive_int, default=1280)
    parser.add_argument("--viewport-height", type=positive_int, default=720)
    parser.add_argument("--full-page", action="store_true", help="capture the full page")
    parser.add_argument("--headed", action="store_true", help="show the browser window")
    parser.add_argument("--overwrite", action="store_true", help="replace existing outputs")
    parser.add_argument("--json", action="store_true", help="print structured JSON")
    return parser.parse_args(argv)


def existing_outputs(paths: Sequence[Optional[Path]]) -> list[Path]:
    return [path for path in paths if path is not None and path.exists()]


def write_text_atomic(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.name}.", suffix=".tmp", dir=path.parent
    )
    temp_path = Path(temp_name)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(content)
            if content and not content.endswith("\n"):
                handle.write("\n")
        os.chmod(temp_path, 0o644)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def save_screenshot_atomic(page: Any, path: Path, full_page: bool) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temp_name = tempfile.mkstemp(
        prefix=f".{path.stem}.", suffix=path.suffix, dir=path.parent
    )
    os.close(descriptor)
    temp_path = Path(temp_name)
    try:
        page.screenshot(path=str(temp_path), full_page=full_page)
        os.chmod(temp_path, 0o644)
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def skipped_result(args: argparse.Namespace, paths: Sequence[Path]) -> dict[str, Any]:
    return {
        "status": "skipped",
        "requested_url": args.url,
        "final_url": None,
        "title": None,
        "text": None,
        "screenshot": str(args.screenshot.resolve()) if args.screenshot else None,
        "text_output": str(args.text_output.resolve()) if args.text_output else None,
        "existing_outputs": [str(path.resolve()) for path in paths],
    }


def inspect_page(args: argparse.Namespace) -> dict[str, Any]:
    outputs = existing_outputs((args.screenshot, args.text_output))
    if outputs and not args.overwrite:
        return skipped_result(args, outputs)

    from playwright.sync_api import sync_playwright

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(headless=not args.headed)
        try:
            context = browser.new_context(
                viewport={"width": args.viewport_width, "height": args.viewport_height}
            )
            page = context.new_page()
            page.goto(args.url, wait_until=args.wait_until, timeout=args.timeout)
            if args.wait_for:
                page.locator(args.wait_for).first.wait_for(
                    state="visible", timeout=args.timeout
                )
            text = page.locator(args.selector).first.inner_text(timeout=args.timeout)
            title = page.title()
            final_url = page.url
            if args.text_output:
                write_text_atomic(args.text_output, text)
            if args.screenshot:
                save_screenshot_atomic(page, args.screenshot, args.full_page)
        finally:
            browser.close()

    return {
        "status": "succeeded",
        "requested_url": args.url,
        "final_url": final_url,
        "title": title,
        "text": text,
        "screenshot": str(args.screenshot.resolve()) if args.screenshot else None,
        "text_output": str(args.text_output.resolve()) if args.text_output else None,
        "existing_outputs": [],
    }


def print_human_result(result: dict[str, Any]) -> None:
    print(f"Status: {result['status']}")
    print(f"Requested URL: {result['requested_url']}")
    if result["final_url"]:
        print(f"Final URL: {result['final_url']}")
        print(f"Title: {result['title']}")
    if result["screenshot"]:
        print(f"Screenshot: {result['screenshot']}")
    if result["text_output"]:
        print(f"Text output: {result['text_output']}")
    if result["existing_outputs"]:
        print("Existing outputs: " + ", ".join(result["existing_outputs"]))
    if result["text"] is not None and not result["text_output"]:
        print("\nVisible text:\n" + result["text"])


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = parse_args(argv)
    try:
        result = inspect_page(args)
    except Exception as error:
        if args.json:
            print(json.dumps({"status": "failed", "error": str(error)}, ensure_ascii=False))
        else:
            print(f"Browser inspection failed: {error}", file=sys.stderr)
        return 1

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print_human_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
