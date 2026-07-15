import shutil
import subprocess
import tempfile
import unittest
from pathlib import Path

from scripts.concat_videos import (
    concat_videos,
    ordered_inputs,
    parse_args as parse_concat_args,
    validate_lossless_compatibility,
)
from scripts.edit_video import (
    atempo_filters,
    build_edit_command,
    edit_video,
    parse_args as parse_edit_args,
    trim_duration,
    validate_mode_options,
)
from scripts.media_utils import (
    AudioStream,
    MediaInfo,
    VideoStream,
    parse_crop,
    parse_size,
    parse_time,
    probe_media,
)


class VideoEditUnitTests(unittest.TestCase):
    def test_time_parsing(self):
        self.assertEqual(parse_time("12.5"), 12.5)
        self.assertEqual(parse_time("01:02.5"), 62.5)
        self.assertEqual(parse_time("01:02:03.25"), 3723.25)
        with self.assertRaises(ValueError):
            parse_time("01:99")

    def test_geometry_parsing(self):
        self.assertEqual(parse_size("1920x1080"), (1920, 1080))
        self.assertEqual(parse_crop("1080x1080+420+0"), (1080, 1080, 420, 0))
        self.assertEqual(parse_crop("1080:1080:420:0"), (1080, 1080, 420, 0))
        with self.assertRaises(ValueError):
            parse_size("1919x1080")

    def test_atempo_chain_supports_large_and_small_speed_changes(self):
        self.assertEqual(atempo_filters(4.0), ["atempo=2", "atempo=2"])
        self.assertEqual(atempo_filters(0.25), ["atempo=0.5", "atempo=0.5"])
        self.assertEqual(atempo_filters(1.0), [])

    def test_trim_duration_validates_and_clamps(self):
        self.assertEqual(trim_duration(100, 10, 25, None), 15)
        self.assertEqual(trim_duration(100, 90, 120, None), 10)
        with self.assertRaises(ValueError):
            trim_duration(100, 100, None, None)

    def test_lossless_mode_rejects_filters(self):
        args = parse_edit_args(["input.mp4", "--mode", "lossless", "--speed", "2"])
        with self.assertRaisesRegex(ValueError, "lossless mode cannot apply filters"):
            validate_mode_options(args)

    def test_precise_command_combines_filters_in_one_pass(self):
        args = parse_edit_args(
            [
                "input.mp4",
                "--start",
                "2",
                "--speed",
                "2",
                "--crop",
                "100x80+10+20",
                "--scale",
                "80x60",
                "--rotate",
                "cw",
            ]
        )
        command = build_edit_command(
            args,
            Path("/tmp/input.mp4"),
            Path("/tmp/output.mp4"),
            has_audio=True,
            clip_duration=10,
        )
        rendered = " ".join(command)
        self.assertIn("crop=100:80:10:20", rendered)
        self.assertIn("scale=80:60:flags=lanczos", rendered)
        self.assertIn("transpose=clock", rendered)
        self.assertIn("setpts=PTS/2", rendered)
        self.assertIn("atempo=2", rendered)

    def test_intro_and_outro_wrap_main_inputs(self):
        args = parse_concat_args(
            [
                "main-1.mp4",
                "main-2.mp4",
                "--intro",
                "intro.mp4",
                "--outro",
                "outro.mp4",
                "--output",
                "joined.mp4",
            ]
        )
        self.assertEqual(
            [path.name for path in ordered_inputs(args)],
            ["intro.mp4", "main-1.mp4", "main-2.mp4", "outro.mp4"],
        )

    def test_lossless_concat_rejects_incompatible_video(self):
        video_a = VideoStream("h264", 1920, 1080, "yuv420p", "30/1", 30.0)
        video_b = VideoStream("h264", 1280, 720, "yuv420p", "30/1", 30.0)
        audio = AudioStream("aac", 48000, 2, "stereo")
        infos = [
            MediaInfo(Path("a.mp4"), 1.0, video_a, audio),
            MediaInfo(Path("b.mp4"), 1.0, video_b, audio),
        ]
        with self.assertRaisesRegex(ValueError, "lossless concat requires matching"):
            validate_lossless_compatibility(infos, remove_audio=False)

    def test_lossless_concat_rejects_normalization_options(self):
        args = parse_concat_args(
            [
                "a.mp4",
                "b.mp4",
                "--mode",
                "lossless",
                "--size",
                "1920x1080",
                "--output",
                "joined.mp4",
            ]
        )
        with tempfile.TemporaryDirectory() as temp_name:
            args.output = Path(temp_name) / "joined.mp4"
            with self.assertRaisesRegex(ValueError, "cannot apply --size or --fps"):
                concat_videos(args)


@unittest.skipUnless(
    shutil.which("ffmpeg") and shutil.which("ffprobe"),
    "ffmpeg and ffprobe are required for integration tests",
)
class VideoEditIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def make_video(
        self,
        path: Path,
        size: str = "160x120",
        fps: int = 10,
        duration: float = 1.0,
        audio: bool = True,
        color: str = "blue",
    ) -> None:
        command = [
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"color=c={color}:s={size}:r={fps}",
        ]
        if audio:
            command.extend(
                [
                    "-f",
                    "lavfi",
                    "-i",
                    "sine=frequency=440:sample_rate=48000",
                ]
            )
        command.extend(
            [
                "-t",
                str(duration),
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-pix_fmt",
                "yuv420p",
            ]
        )
        if audio:
            command.extend(["-c:a", "aac", "-shortest"])
        else:
            command.append("-an")
        command.append(str(path))
        subprocess.run(command, check=True, capture_output=True)

    def test_precise_edit_changes_duration_dimensions_and_audio(self):
        source = self.root / "source.mp4"
        output = self.root / "edited.mp4"
        self.make_video(source, duration=2.0)
        args = parse_edit_args(
            [
                str(source),
                "--output",
                str(output),
                "--start",
                "0.2",
                "--duration",
                "1.2",
                "--speed",
                "2",
                "--crop",
                "120x80+0+0",
                "--scale",
                "80x60",
                "--rotate",
                "cw",
                "--preset",
                "ultrafast",
            ]
        )

        result = edit_video(args)
        info = probe_media(output)

        self.assertEqual(result.status, "succeeded")
        self.assertEqual((info.video.width, info.video.height), (60, 80))
        self.assertIsNotNone(info.audio)
        self.assertGreater(info.duration, 0.45)
        self.assertLess(info.duration, 0.8)

    def test_existing_output_is_skipped_without_overwrite(self):
        source = self.root / "source.mp4"
        output = self.root / "existing.mp4"
        self.make_video(source)
        output.write_bytes(b"keep")
        args = parse_edit_args([str(source), "--output", str(output)])

        result = edit_video(args)

        self.assertEqual(result.status, "skipped")
        self.assertEqual(output.read_bytes(), b"keep")

    def test_lossless_trim_copies_video_and_removes_audio(self):
        source = self.root / "source.mp4"
        output = self.root / "lossless-muted.mp4"
        self.make_video(source, duration=2.0)
        args = parse_edit_args(
            [
                str(source),
                "--output",
                str(output),
                "--start",
                "0.2",
                "--duration",
                "0.8",
                "--mode",
                "lossless",
                "--remove-audio",
            ]
        )

        result = edit_video(args)
        info = probe_media(output)

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(info.video.codec, "h264")
        self.assertIsNone(info.audio)
        self.assertGreater(info.duration, 0.5)
        self.assertLess(info.duration, 1.1)

    def test_precise_concat_normalizes_intro_main_outro_and_missing_audio(self):
        intro = self.root / "intro.mp4"
        main = self.root / "main.mp4"
        outro = self.root / "outro.mp4"
        output = self.root / "published.mp4"
        self.make_video(intro, size="96x96", fps=12, duration=0.5, audio=False)
        self.make_video(main, size="160x120", fps=10, duration=0.8, color="red")
        self.make_video(outro, size="128x72", fps=15, duration=0.5, color="green")
        args = parse_concat_args(
            [
                str(main),
                "--intro",
                str(intro),
                "--outro",
                str(outro),
                "--size",
                "160x120",
                "--fps",
                "10",
                "--preset",
                "ultrafast",
                "--output",
                str(output),
            ]
        )

        result = concat_videos(args)
        info = probe_media(output)

        self.assertEqual(result.status, "succeeded")
        self.assertEqual([Path(path).name for path in result.inputs], ["intro.mp4", "main.mp4", "outro.mp4"])
        self.assertEqual((info.video.width, info.video.height), (160, 120))
        self.assertAlmostEqual(info.video.fps, 10.0, places=2)
        self.assertIsNotNone(info.audio)
        self.assertGreater(info.duration, 1.6)
        self.assertLess(info.duration, 2.1)

    def test_lossless_concat_copies_compatible_streams(self):
        source = self.root / "source.mp4"
        output = self.root / "joined.mp4"
        self.make_video(source, duration=0.6)
        args = parse_concat_args(
            [
                str(source),
                str(source),
                "--mode",
                "lossless",
                "--output",
                str(output),
            ]
        )

        result = concat_videos(args)
        info = probe_media(output)

        self.assertEqual(result.status, "succeeded")
        self.assertEqual(info.video.codec, "h264")
        self.assertEqual(info.audio.codec, "aac")
        self.assertGreater(info.duration, 1.0)


if __name__ == "__main__":
    unittest.main()
