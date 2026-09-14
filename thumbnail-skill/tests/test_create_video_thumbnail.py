"""Behavior checks using tiny generated videos; no user media is modified."""

import hashlib
import importlib.util
import json
from pathlib import Path
import shutil
import subprocess
import sys

import cv2
import numpy as np
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "create_video_thumbnail.py"
SPEC = importlib.util.spec_from_file_location("video_thumbnail", SCRIPT)
thumbnail = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(thumbnail)


def test_fingerprint_compatibility(tmp_path):
    small = tmp_path / "small.bin"
    small.write_bytes(b"original fingerprint")
    assert thumbnail.compute_file_fingerprint(small) == hashlib.sha256(small.read_bytes()).hexdigest()
    large = tmp_path / "large.bin"
    sample = 2 * 1024 * 1024
    large.write_bytes(b"a" * sample + b"middle" + b"z" * sample)
    expected = hashlib.sha256(str(large.stat().st_size).encode() + b"a" * sample + b"z" * sample)
    assert thumbnail.compute_file_fingerprint(large) == expected.hexdigest()


def test_selection_boundaries():
    frame = np.zeros((10, 10, 3), dtype=np.uint8)
    for index in range(20):
        frame[index // 10, index % 10] = 255
    assert not thumbnail.is_black_frame(frame)  # exactly 80% dark is allowed
    frame[0, 0] = 0
    assert thumbnail.is_black_frame(frame)
    assert not thumbnail.is_black_frame(np.full((10, 10, 3), 50, dtype=np.uint8))


def test_full_hash_detects_changes_outside_fingerprint_samples(tmp_path):
    path = tmp_path / "large.bin"
    sample = 2 * 1024 * 1024
    data = b"a" * sample + b"middle" + b"z" * sample
    path.write_bytes(data)
    fingerprint = thumbnail.compute_file_fingerprint(path)
    full_hash = thumbnail.compute_file_hash(path)
    assert full_hash == hashlib.sha256(data).hexdigest()
    assert thumbnail.compute_file_hash(path, algorithm="sha1", chunk_size=1024) == hashlib.sha1(data).hexdigest()
    with path.open("r+b") as file:
        file.seek(sample)
        file.write(b"MIDDLE")
    assert thumbnail.compute_file_fingerprint(path) == fingerprint
    assert thumbnail.compute_file_hash(path) != full_hash
    assert thumbnail.compute_file_hash(path) == hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize("hash_mode", [None, "fingerprint", "full"])
def test_cli_hash_mode_resolves_existing_output(tmp_path, hash_mode):
    source = tmp_path / "large.mp4"
    sample = 2 * 1024 * 1024
    data = b"a" * sample + b"middle" + b"z" * sample
    source.write_bytes(data)
    sampled = str(len(data)).encode() + data[:sample] + data[-sample:]
    digest = hashlib.sha256(data if hash_mode == "full" else sampled).hexdigest()
    output = tmp_path / "thumbnails"
    output.mkdir()
    existing = output / f"{digest}.jpg"
    existing.write_bytes(b"existing thumbnail")
    command = [sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output), "--json"]
    if hash_mode is not None:
        command.extend(["--hash-mode", hash_mode])
    result = subprocess.run(command, capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 0, result.stderr + result.stdout
    item, = json.loads(result.stdout)
    assert item["status"] == "skipped"
    assert Path(item["output"]) == existing
    assert existing.read_bytes() == b"existing thumbnail"


@pytest.mark.skipif(not shutil.which("ffmpeg"), reason="FFmpeg required")
@pytest.mark.parametrize("height, hash_mode", [(None, None), (360, "full")])
def test_cli_black_opening_batch_and_output_protection(tmp_path, height, hash_mode):
    inputs = tmp_path / "video input"
    nested = inputs / "nested"
    nested.mkdir(parents=True)
    video = nested / "black then red.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=320x240:r=10:d=1",
        "-f", "lavfi", "-i", "color=red:s=320x240:r=10:d=1",
        "-filter_complex", "[0:v][1:v]concat=n=2:v=1:a=0[v]", "-map", "[v]",
        "-c:v", "mpeg4", str(video),
    ], check=True, capture_output=True)
    original = video.read_bytes()
    output = tmp_path / "results"
    command = [sys.executable, str(SCRIPT), "--input", str(inputs), "--output", str(output), "--json"]
    if height is not None:
        command.extend(["--height", str(height)])
    if hash_mode is not None:
        command.extend(["--hash-mode", hash_mode])
    nonrecursive = subprocess.run(command, capture_output=True, text=True, cwd=tmp_path)
    assert nonrecursive.returncode == 1
    command.append("--recursive")
    first = subprocess.run(command, capture_output=True, text=True, cwd=tmp_path)
    assert first.returncode == 0, first.stderr + first.stdout
    result, = json.loads(first.stdout)
    assert result["status"] == "succeeded"
    assert "Thumbnail found at 1s." in first.stderr
    destination = Path(result["output"])
    assert destination.name == hashlib.sha256(original).hexdigest() + ".jpg"
    assert destination.read_bytes().startswith(b"\xff\xd8")
    frame = cv2.imdecode(np.frombuffer(destination.read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    expected_height = height or 180
    assert frame.shape[:2] == (expected_height, expected_height * 4 // 3)
    blue, green, red = frame[frame.shape[0] // 2, frame.shape[1] // 2]
    assert red > 200 and green < 30 and blue < 30
    destination.write_bytes(b"keep existing output")
    second = subprocess.run(command, capture_output=True, text=True, cwd=tmp_path)
    assert second.returncode == 0
    assert json.loads(second.stdout)[0]["status"] == "skipped"
    assert destination.read_bytes() == b"keep existing output"
    replaced = subprocess.run(command + ["--overwrite"], capture_output=True, text=True, cwd=tmp_path)
    assert replaced.returncode == 0
    assert json.loads(replaced.stdout)[0]["status"] == "succeeded"
    assert destination.read_bytes().startswith(b"\xff\xd8")
    assert video.read_bytes() == original

    dark = inputs / "dark.mp4"
    subprocess.run([
        "ffmpeg", "-v", "error", "-f", "lavfi", "-i", "color=black:s=32x24:r=10:d=1",
        "-c:v", "mpeg4", str(dark),
    ], check=True, capture_output=True)
    (inputs / "corrupt.mp4").write_bytes(b"not a video")
    failed = subprocess.run(command, capture_output=True, text=True, cwd=tmp_path)
    assert failed.returncode == 1
    results = {Path(item["input"]).name: item for item in json.loads(failed.stdout)}
    assert results["corrupt.mp4"]["status"] == "failed"
    assert "No thumbnail generated" in results["dark.mp4"]["error"]
    assert not Path(results["dark.mp4"]["output"]).exists()
    assert results["black then red.mp4"]["status"] == "skipped"
    assert len(list(output.iterdir())) == 1  # no leftover temporary files


@pytest.mark.parametrize("height", ["0", "-1", "1.5", "abc"])
def test_cli_rejects_invalid_height(tmp_path, height):
    output = tmp_path / "output"
    result = subprocess.run([
        sys.executable, str(SCRIPT), "--input", str(tmp_path),
        "--output", str(output), "--height", height,
    ], capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 2
    assert "height must be a positive integer" in result.stderr
    assert not output.exists()
