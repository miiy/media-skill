"""Check unified dispatch for image and video inputs."""

import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import cv2
import numpy as np


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/create_thumbnail.py"


def test_unified_entrypoint_processes_images(tmp_path):
    source = tmp_path / "photo.png"
    image = np.full((100, 200, 3), 120, dtype=np.uint8)
    success, encoded = cv2.imencode(".png", image)
    assert success
    source.write_bytes(encoded.tobytes())
    output = tmp_path / "thumbnails"
    result = subprocess.run([
        sys.executable, str(SCRIPT), "--input", str(source), "--output", str(output),
        "--height", "90", "--json",
    ], capture_output=True, text=True, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    item, = json.loads(result.stdout)
    assert item["media_type"] == "image"
    thumbnail = cv2.imdecode(np.frombuffer(Path(item["output"]).read_bytes(), np.uint8), cv2.IMREAD_COLOR)
    assert thumbnail.shape == (90, 180, 3)


def test_media_type_classification_and_extensionless_override():
    spec = importlib.util.spec_from_file_location("create_thumbnail", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.classify(Path("clip.MP4"), "all") == "video"
    assert module.classify(Path("photo.PNG"), "all") == "image"
    assert module.classify(Path("without-extension"), "all") is None
    assert module.classify(Path("without-extension"), "video") == "video"
    assert module.classify(Path("without-extension"), "image") == "image"
