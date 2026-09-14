#!/usr/bin/env python3
"""Summarize the files and directories immediately under a directory."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Dict, List


Result = Dict[str, object]


def format_size(size_bytes: int) -> str:
    """Return a compact IEC-style size such as ``1.25 MB``."""
    units = ("B", "KB", "MB", "GB", "TB", "PB")
    size = float(size_bytes)
    for unit in units:
        if size < 1024 or unit == units[-1]:
            return f"{size:.2f} {unit}"
        size /= 1024
    return f"{size_bytes} B"


def collect_dir_stats(directory: Path) -> tuple[int, int]:
    """Return total regular-file bytes and count below ``directory``."""
    total_size = 0
    file_count = 0
    for path in directory.rglob("*"):
        if not path.is_file():
            continue
        try:
            total_size += path.stat().st_size
            file_count += 1
        except OSError:
            # An unreadable entry should not prevent the rest of the report.
            continue
    return total_size, file_count


def analyze_top_level(target_dir: Path) -> List[Result]:
    """Analyze each file or directory directly contained by ``target_dir``."""
    results: List[Result] = []
    for entry in target_dir.iterdir():
        if entry.is_file():
            try:
                size = entry.stat().st_size
            except OSError:
                size = 0
            results.append(
                {
                    "name": entry.name,
                    "type": "file",
                    "size_bytes": size,
                    "file_count": 1,
                }
            )
        elif entry.is_dir():
            size, file_count = collect_dir_stats(entry)
            results.append(
                {
                    "name": entry.name,
                    "type": "dir",
                    "size_bytes": size,
                    "file_count": file_count,
                }
            )
    return sorted(results, key=lambda item: (-int(item["size_bytes"]), str(item["name"]).casefold()))


def print_table(results: List[Result], target_dir: Path) -> None:
    """Print the human-readable report."""
    print(f"Target directory: {target_dir.resolve()}")
    print()
    if not results:
        print("No immediate files or directories found.")
        return

    name_width = max(len("Name"), *(len(str(item["name"])) for item in results))
    size_width = max(
        len("Total Size"), *(len(format_size(int(item["size_bytes"]))) for item in results)
    )
    count_width = max(len("File Count"), *(len(str(item["file_count"])) for item in results))
    header = (
        f"{'Name':<{name_width}}  {'Type':<4}  "
        f"{'Total Size':>{size_width}}  {'File Count':>{count_width}}"
    )
    print(header)
    print("-" * len(header))
    for item in results:
        print(
            f"{str(item['name']):<{name_width}}  {str(item['type']):<4}  "
            f"{format_size(int(item['size_bytes'])):>{size_width}}  "
            f"{str(item['file_count']):>{count_width}}"
        )


def write_csv(results: List[Result], output_path: Path) -> None:
    """Write the report as an Excel-friendly UTF-8 CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as csvfile:
        writer = csv.writer(csvfile)
        writer.writerow(["Name", "Type", "Total Size (Bytes)", "Total Size", "File Count"])
        for item in results:
            writer.writerow(
                [
                    item["name"],
                    item["type"],
                    item["size_bytes"],
                    format_size(int(item["size_bytes"])),
                    item["file_count"],
                ]
            )


def parse_args(argv: List[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Analyze the total size and file count of immediate directory entries."
    )
    parser.add_argument(
        "directory",
        nargs="?",
        default=".",
        help="directory to analyze (default: current working directory)",
    )
    parser.add_argument(
        "--csv",
        default="analysis_result.csv",
        help="CSV output path (default: analysis_result.csv in the working directory)",
    )
    return parser.parse_args(argv)


def main(argv: List[str] | None = None) -> int:
    args = parse_args(argv)
    target_dir = Path(args.directory).expanduser()
    if not target_dir.exists():
        print(f"Directory does not exist: {target_dir}")
        return 1
    if not target_dir.is_dir():
        print(f"Path is not a directory: {target_dir}")
        return 1

    try:
        results = analyze_top_level(target_dir)
    except OSError as exc:
        print(f"Unable to read directory contents: {target_dir}: {exc}")
        return 1
    print_table(results, target_dir)
    output_path = Path(args.csv).expanduser()
    try:
        write_csv(results, output_path)
    except OSError as exc:
        print(f"Unable to write CSV: {output_path}: {exc}")
        return 1
    print()
    print(f"CSV written to: {output_path.resolve()}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
