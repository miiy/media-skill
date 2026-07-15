import stat
import tempfile
import unittest
from pathlib import Path

from PIL import Image

from scripts.create_video_grid import (
    ProcessResult,
    VideoInfo,
    batch_output_path,
    build_contact_sheet,
    collect_video_paths,
    default_output_path,
    find_system_font_paths,
    format_file_size,
    format_timestamp,
    load_font,
    result_payload,
    sample_timestamps,
    save_image_atomic,
)


class VideoGridTests(unittest.TestCase):
    def test_sampling_is_even_and_stays_inside_boundaries(self):
        timestamps = sample_timestamps(100.0, 9)

        self.assertEqual(
            timestamps,
            [10.0, 20.0, 30.0, 40.0, 50.0, 60.0, 70.0, 80.0, 90.0],
        )

    def test_short_video_sampling_does_not_repeat_or_use_boundaries(self):
        timestamps = sample_timestamps(5.0, 16)

        self.assertEqual(len(set(timestamps)), 16)
        self.assertTrue(all(0.0 < timestamp < 5.0 for timestamp in timestamps))

    def test_system_font_search_prefers_microsoft_yahei(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            fallback = root / "Arial.ttf"
            preferred = root / "nested" / "msyh.ttc"
            preferred.parent.mkdir()
            fallback.touch()
            preferred.touch()

            paths = find_system_font_paths([root])

        self.assertEqual(paths, [preferred, fallback])

    def test_default_output_path_replaces_video_extension(self):
        path = default_output_path(Path("/tmp/example.final.mp4"))

        self.assertEqual(path, Path("/tmp/example.final_grid.jpg"))

    def test_batch_output_preserves_relative_directory(self):
        path = batch_output_path(
            Path("/videos/course/lesson.mp4"),
            Path("/videos"),
            Path("/grids"),
            "_preview.png",
        )

        self.assertEqual(path, Path("/grids/course/lesson_preview.png"))

    def test_video_collection_is_filtered_and_sorted(self):
        with tempfile.TemporaryDirectory() as temp_name:
            directory = Path(temp_name)
            (directory / "b.MOV").touch()
            (directory / "a.mp4").touch()
            (directory / "notes.txt").touch()

            paths = collect_video_paths(directory, recursive=False)

        self.assertEqual([path.name for path in paths], ["a.mp4", "b.MOV"])

    def test_format_helpers(self):
        self.assertEqual(format_timestamp(3661.26), "01:01:01")
        self.assertEqual(format_file_size(1536), "0.0 MB")

    def test_default_portrait_grid_dimensions_and_background(self):
        frames = [Image.new("RGB", (360, 640), "red") for _ in range(9)]
        info = VideoInfo(
            path=Path("/tmp/024.mp4"),
            width=720,
            height=1280,
            duration_seconds=179.049,
            size_bytes=25_409_730,
        )
        font = load_font(None)
        canvas = build_contact_sheet(frames, info, 3, 3, font)
        try:
            self.assertEqual(canvas.size, (1100, 2040))
            self.assertEqual(canvas.getpixel((0, 0)), (255, 255, 255))
            self.assertEqual(canvas.getpixel((5, 105)), (255, 0, 0))
        finally:
            canvas.close()
            for frame in frames:
                frame.close()

    def test_result_payload_counts_statuses(self):
        payload = result_payload(
            [
                ProcessResult("a.mp4", "a.jpg", "succeeded"),
                ProcessResult("b.mp4", "b.jpg", "skipped"),
                ProcessResult("c.mp4", "c.jpg", "failed", "bad video"),
            ]
        )

        self.assertEqual(payload["processed"], 3)
        self.assertEqual(payload["succeeded"], 1)
        self.assertEqual(payload["skipped"], 1)
        self.assertEqual(payload["failed"], 1)

    def test_atomic_save_uses_readable_default_permissions(self):
        with tempfile.TemporaryDirectory() as temp_name:
            output_path = Path(temp_name) / "grid.jpg"
            image = Image.new("RGB", (2, 2), "white")
            try:
                save_image_atomic(image, output_path)
            finally:
                image.close()

            mode = stat.S_IMODE(output_path.stat().st_mode)

        self.assertEqual(mode, 0o644)


if __name__ == "__main__":
    unittest.main()
