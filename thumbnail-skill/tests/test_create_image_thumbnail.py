"""Check image outputs, CLI options, and source/output protection."""

import hashlib
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np
import pytest


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/create_image_thumbnail.py"
SPEC = importlib.util.spec_from_file_location("image_thumbnail", SCRIPT)
thumbnail = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(thumbnail)


def write_image(path, shape=(240, 320, 3)):
    pixels = np.full(shape, 100, dtype=np.uint8)
    success, encoded = cv2.imencode(".png", pixels)
    assert success
    path.write_bytes(encoded.tobytes())


def run_cli(source, output, *options):
    environment = os.environ.copy()
    environment["PATH"] = ""  # Image processing needs no external media binaries.
    return subprocess.run([
        sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output), "--json", *options,
    ], capture_output=True, text=True, cwd=source.parent, env=environment)


@pytest.mark.parametrize("height, shape", [(None, (240, 320, 3)), (360, (100, 50, 4)), (180, (1000, 1, 3))])
def test_cli_image_dimensions_and_overwrite(tmp_path, height, shape):
    source = tmp_path / "图片 sample.png"
    write_image(source, shape)
    before = source.read_bytes()
    output = tmp_path / "thumbnails"
    options = () if height is None else ("--height", str(height))
    result = run_cli(source, output, *options)
    assert result.returncode == 0, result.stderr
    item, = json.loads(result.stdout)
    assert item["status"] == "succeeded"
    destination = Path(item["output"])
    assert destination.name == hashlib.sha256(before).hexdigest() + ".jpg"
    data = destination.read_bytes()
    assert data.startswith(b"\xff\xd8")
    decoded = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    expected_height = height or 180
    assert decoded.shape == (expected_height, max(int(shape[1] * (expected_height / shape[0])), 1), 3)
    destination.write_bytes(b"existing file")
    skipped = run_cli(source, output, *options)
    assert json.loads(skipped.stdout)[0]["status"] == "skipped"
    assert destination.read_bytes() == b"existing file"
    replaced = run_cli(source, output, *options, "--overwrite")
    assert replaced.returncode == 0
    assert destination.read_bytes() == data
    assert source.read_bytes() == before


def test_batch_recursion_errors_and_nested_output_exclusion(tmp_path):
    source = tmp_path / "images"
    nested = source / "nested"
    nested.mkdir(parents=True)
    write_image(nested / "valid.PNG")
    (source / "corrupt.jpg").write_bytes(b"not an image")
    (source / "notes.txt").write_text("ignore")
    output = source / "thumbnails"
    first = run_cli(source, output)
    assert first.returncode == 1
    assert len(json.loads(first.stdout)) == 1
    recursive = run_cli(source, output, "--recursive")
    assert recursive.returncode == 1
    results = json.loads(recursive.stdout)
    assert sorted(item["status"] for item in results) == ["failed", "succeeded"]
    again = run_cli(source, output, "--recursive")
    results = json.loads(again.stdout)
    assert len(results) == 2
    assert sorted(item["status"] for item in results) == ["failed", "skipped"]
    assert len(list(output.iterdir())) == 1


def test_output_parent_does_not_exclude_source_images(tmp_path):
    source = tmp_path / "images"
    source.mkdir()
    write_image(source / "photo.png")
    result = run_cli(source, tmp_path, "--recursive")
    assert result.returncode == 0, result.stderr
    item, = json.loads(result.stdout)
    assert item["status"] == "succeeded"
    assert Path(item["output"]).parent == tmp_path


@pytest.mark.parametrize("hash_mode", ["fingerprint", "full"])
def test_cli_hash_naming_large_image(tmp_path, hash_mode):
    source = tmp_path / "large.bmp"
    pixels = np.full((1300, 1300, 3), 100, dtype=np.uint8)
    success, encoded = cv2.imencode(".bmp", pixels)
    assert success
    data = encoded.tobytes()
    source.write_bytes(data)
    sample = 2 * 1024 * 1024
    assert len(data) > 2 * sample
    digest_input = data if hash_mode == "full" else str(len(data)).encode() + data[:sample] + data[-sample:]
    result = run_cli(source, tmp_path / "output", "--hash-mode", hash_mode)
    assert result.returncode == 0, result.stderr
    item, = json.loads(result.stdout)
    assert item["status"] == "succeeded"
    assert Path(item["output"]).name == hashlib.sha256(digest_input).hexdigest() + ".jpg"


@pytest.mark.parametrize("height", ["0", "-1", "1.5", "abc"])
def test_invalid_height(tmp_path, height):
    result = run_cli(tmp_path, tmp_path / "output", "--height", height)
    assert result.returncode == 2
    assert "height must be a positive integer" in result.stderr
    assert not (tmp_path / "output").exists()
