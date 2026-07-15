import stat
import tempfile
import unittest
from pathlib import Path

from scripts.transcribe_media import (
    ProcessResult,
    TranscriberConfig,
    batch_output_path,
    build_jobs,
    collect_media_paths,
    default_output_path,
    format_srt_timestamp,
    normalize_transcription_result,
    process_jobs,
    render_srt,
    result_payload,
    transcribe_media,
)


class FakeTranscriber:
    def __init__(self):
        self.calls = []

    def transcribe(
        self,
        media_path,
        language=None,
        task="transcribe",
        vad_filter=False,
    ):
        self.calls.append((media_path, language, task, vad_filter))
        return {
            "text": "hello world",
            "language": language or "en",
            "language_probability": 0.99,
            "segments": [
                {"start": 0.25, "end": 1.5, "text": "hello"},
                {"start": 1.5, "end": 2.0, "text": "world"},
            ],
        }


class TranscribeSkillTests(unittest.TestCase):
    def test_timestamp_format(self):
        self.assertEqual(format_srt_timestamp(3661.2345), "01:01:01,234")

    def test_normalize_sorts_segments_and_repairs_end_time(self):
        result = normalize_transcription_result(
            {
                "segments": [
                    {"start": 2, "end": 1, "text": "second"},
                    {"start": -1, "end": 0, "text": "first"},
                ]
            }
        )

        self.assertEqual(
            [segment["text"] for segment in result["segments"]],
            ["first", "second"],
        )
        self.assertGreater(result["segments"][0]["end"], result["segments"][0]["start"])
        self.assertGreater(result["segments"][1]["end"], result["segments"][1]["start"])

    def test_render_srt(self):
        content = render_srt(
            [{"start": 0.0, "end": 1.25, "text": "hello"}]
        )

        self.assertEqual(
            content,
            "1\n00:00:00,000 --> 00:00:01,250\nhello\n",
        )

    def test_transcribe_media_writes_srt_with_readable_permissions(self):
        with tempfile.TemporaryDirectory() as temp_name:
            directory = Path(temp_name)
            source = directory / "input.any"
            output = directory / "output.srt"
            source.touch()
            transcriber = FakeTranscriber()

            result = transcribe_media(
                source,
                output,
                transcriber,
                language="zh",
                vad_filter=True,
            )

            content = output.read_text(encoding="utf-8")
            mode = stat.S_IMODE(output.stat().st_mode)

        self.assertEqual(result["language"], "zh")
        self.assertIn("00:00:00,250 --> 00:00:01,500", content)
        self.assertEqual(mode, 0o644)
        self.assertEqual(transcriber.calls[0][1:], ("zh", "transcribe", True))

    def test_collect_media_paths_includes_audio_and_video(self):
        with tempfile.TemporaryDirectory() as temp_name:
            directory = Path(temp_name)
            (directory / "b.mp4").touch()
            (directory / "a.MP3").touch()
            (directory / "notes.txt").touch()

            paths = collect_media_paths(directory, recursive=False)

        self.assertEqual([path.name for path in paths], ["a.MP3", "b.mp4"])

    def test_output_paths(self):
        self.assertEqual(
            default_output_path(Path("/tmp/lesson.final.m4a")),
            Path("/tmp/lesson.final_asr.srt"),
        )
        self.assertEqual(
            batch_output_path(
                Path("/media/course/lesson.mp4"),
                Path("/media"),
                Path("/subtitles"),
                "_asr.srt",
            ),
            Path("/subtitles/course/lesson_asr.srt"),
        )

    def test_single_file_accepts_unknown_extension(self):
        with tempfile.TemporaryDirectory() as temp_name:
            source = Path(temp_name) / "recording.media"
            source.touch()

            jobs = build_jobs(source, None, "_asr.srt", recursive=False)

        self.assertEqual(jobs[0][1].name, "recording_asr.srt")

    def test_existing_output_is_skipped_without_loading_model(self):
        with tempfile.TemporaryDirectory() as temp_name:
            directory = Path(temp_name)
            source = directory / "input.mp3"
            output = directory / "input_asr.srt"
            source.touch()
            output.write_text("existing", encoding="utf-8")

            results = process_jobs(
                [(source, output)],
                config=TranscriberConfig(model="missing-model"),
                language=None,
                task="transcribe",
                vad_filter=False,
                overwrite=False,
                workers=1,
            )

        self.assertEqual(results[0].status, "skipped")

    def test_result_payload(self):
        payload = result_payload(
            [
                ProcessResult("a.mp3", "a.srt", "succeeded", language="en"),
                ProcessResult("b.mp4", "b.srt", "failed", error="bad media"),
            ]
        )

        self.assertEqual(payload["processed"], 2)
        self.assertEqual(payload["succeeded"], 1)
        self.assertEqual(payload["failed"], 1)


if __name__ == "__main__":
    unittest.main()
