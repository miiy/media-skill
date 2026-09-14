"""Check the Python entry point without opening a GUI or launching AutoHotkey."""

import importlib.util
from pathlib import Path
import subprocess
from types import SimpleNamespace


SCRIPT = Path(__file__).resolve().parents[1] / "scripts/create_video_grid.py"
SPEC = importlib.util.spec_from_file_location("kmplayer_grid", SCRIPT)
grid = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(grid)


def test_main_passes_absolute_paths_and_creates_output(tmp_path, monkeypatch):
    video = tmp_path / "video input.mp4"
    video.write_bytes(b"test fixture")
    executable = tmp_path / "AutoHotkey.exe"
    executable.write_bytes(b"test placeholder; never executed")
    output = tmp_path / "grids"
    calls = []
    monkeypatch.setattr(grid.sys, "platform", "win32")
    monkeypatch.setattr(grid, "generate_video_grid", lambda *args: calls.append(args))
    status = grid.main(["--input", str(video), "--output", str(output), "--ahk", str(executable)])
    assert status == 0
    assert output.is_dir()
    assert calls == [(str(executable.resolve()), video.resolve(), output.resolve())]


def test_non_windows_stops_before_output_or_gui(tmp_path, monkeypatch, capsys):
    output = tmp_path / "output"
    monkeypatch.setattr(grid.sys, "platform", "darwin")
    status = grid.main(["--input", str(tmp_path), "--output", str(output)])
    assert status == 1
    assert "requires Windows" in capsys.readouterr().err
    assert not output.exists()


def test_recursive_video_dispatch_and_waiting(tmp_path, monkeypatch):
    inputs = tmp_path / "videos"
    nested = inputs / "nested"
    nested.mkdir(parents=True)
    videos = {inputs / "first.mp4", nested / "second.mov"}
    for video in videos:
        video.write_bytes(b"test fixture")
    (inputs / "ignore.txt").write_text("ignore")
    output = tmp_path / "grids"
    output.mkdir()
    events = []

    def fake_run(command, check):
        assert check is True
        assert command[0] == "AutoHotkey.exe"
        assert Path(command[1]) == SCRIPT.parents[1] / "ahk_scripts/kmplayer_grid.ahk"
        assert Path(command[3]) == output
        events.append(("capture", Path(command[2])))
        return subprocess.CompletedProcess(command, 0)

    def fake_wait(timeout):
        events.append(("wait", timeout))
        return True

    monkeypatch.setattr(grid.subprocess, "run", fake_run)
    monkeypatch.setattr(grid, "wait_for_kmplayer_exit", fake_wait)
    grid.generate_video_grid("AutoHotkey.exe", inputs, output)
    assert {path for event, path in events if event == "capture"} == videos
    assert [event for event, _ in events] == ["capture", "wait", "capture", "wait"]
    assert [timeout for event, timeout in events if event == "wait"] == [15, 15]


def test_capture_process_failure_stops_batch(tmp_path, monkeypatch):
    for name in ("first.mp4", "second.mp4"):
        (tmp_path / name).write_bytes(b"test fixture")
    calls = []

    def fake_run(command, check):
        calls.append(command)
        raise subprocess.CalledProcessError(1, command)

    monkeypatch.setattr(grid.subprocess, "run", fake_run)
    grid.generate_video_grid("AutoHotkey.exe", tmp_path, tmp_path / "output")
    assert len(calls) == 1


def test_wait_ignores_unrelated_processes(monkeypatch):
    monkeypatch.setattr(grid.psutil, "process_iter", lambda fields: [
        SimpleNamespace(info={"name": "python.exe"}), SimpleNamespace(info={"name": None}),
    ])
    assert grid.wait_for_kmplayer_exit() is True
