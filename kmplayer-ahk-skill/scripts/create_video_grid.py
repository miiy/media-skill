#!/usr/bin/env python3
"""Create video grids with KMPlayer and AutoHotkey v2 on Windows."""

import argparse
import mimetypes
import os
from pathlib import Path
import subprocess
import sys
import time

import psutil


def scan_files(folder_path):
    """
    Recursively collect file paths from a directory, including subdirectories.
    Include all file types.
    """
    file_list = []

    for root, _, files in os.walk(folder_path):
        for filename in files:
            file_path = os.path.join(root, filename)
            file_list.append(file_path)

    return file_list


def generate_video_grid(ahk_exe: str, input_path: Path, output_dir: Path):
    """
    Generate frame grids for one or multiple video files using AutoHotkey.
    """
    BASE_DIR = Path(__file__).resolve().parent.parent
    ahk_script = BASE_DIR / "ahk_scripts" / "kmplayer_grid.ahk"

    if not ahk_script.exists():
        print(f"❌ Error: AHK script not found at {ahk_script}")
        return

    input_path = input_path.resolve()
    output_dir = output_dir.resolve()

    # Collect all video files
    if input_path.is_file():
        video_files = [str(input_path)]
    else:
        video_files = [
            f for f in scan_files(str(input_path))
            if mimetypes.guess_type(f)[0] and mimetypes.guess_type(f)[0].startswith("video")
        ]

    if not video_files:
        print("⚠️ No video files found for grid generation.")
        return

    print(f"🎞️ Found {len(video_files)} video(s) to process.")


    # Process each video file
    for video_path in video_files:
        video_name = os.path.basename(video_path)
        print(f"\n📹 Processing: {video_name}")
        try:
            result = subprocess.run(
                [ahk_exe, str(ahk_script), video_path, str(output_dir)],
                check=True
            )
            print(result.stdout)
            print(result.stderr)
            
            # Wait until KMPlayer is fully closed before processing next video
            if not wait_for_kmplayer_exit(timeout=15):
                print("⚠️ KMPlayer did not exit in time, waiting a bit longer...")
                time.sleep(5)
            print(f"✅ Grid generated for {video_name}")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to process {video_name}: {e}")
            break


def wait_for_kmplayer_exit(timeout=10):
    """
    Wait until all KMPlayer processes have exited.
    Returns True if exited, False if timeout reached.
    """
    start_time = time.time()
    while time.time() - start_time < timeout:
        running = [p for p in psutil.process_iter(['name']) if p.info['name'] and p.info['name'].lower() == 'kmplayer.exe']
        if not running:
            return True
        time.sleep(0.2)  # check every 0.2s
    return False


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path, help="local video or directory; directories are scanned recursively")
    parser.add_argument("--output", type=Path, default=Path("output"), help="output directory (default: ./output)")
    parser.add_argument("--ahk", type=Path, default=Path(r"C:\Program Files\AutoHotkey\v2\AutoHotkey.exe"),
                        help="path to the AutoHotkey v2 executable")
    args = parser.parse_args(argv)
    if sys.platform != "win32":
        print("Error: This workflow requires Windows, AutoHotkey v2, and KMPlayer.", file=sys.stderr)
        return 1
    source = args.input.expanduser().resolve()
    output = args.output.expanduser().resolve()
    ahk = args.ahk.expanduser().resolve()
    try:
        if not source.is_file() and not source.is_dir():
            raise ValueError(f"Input is not a file or directory: {source}")
        if not ahk.is_file():
            raise ValueError(f"AutoHotkey executable not found: {ahk}")
        output.mkdir(parents=True, exist_ok=True)
        generate_video_grid(str(ahk), source, output)
    except (OSError, ValueError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
