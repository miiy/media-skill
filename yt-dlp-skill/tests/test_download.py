import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from scripts.download import DEFAULT_FORMAT, cookie_file, ydl_options


class DownloadTests(unittest.TestCase):
    def test_default_format_prefers_separate_video_and_audio(self):
        self.assertEqual(DEFAULT_FORMAT, "bestvideo+bestaudio/best")

    def test_options_are_single_item_and_anonymous_by_default(self):
        with patch("scripts.download.shutil.which", return_value=None):
            options = ydl_options("18", "/workspace/video.%(ext)s")

        self.assertTrue(options["noplaylist"])
        self.assertNotIn("cookiefile", options)
        self.assertNotIn("js_runtimes", options)

    def test_node_and_explicit_cookie_are_forwarded(self):
        with patch("scripts.download.shutil.which", return_value="/usr/bin/node"):
            options = ydl_options("18", "video.%(ext)s", "/tmp/cookies.txt")

        self.assertEqual(options["cookiefile"], "/tmp/cookies.txt")
        self.assertEqual(
            options["js_runtimes"],
            {"node": {"path": "/usr/bin/node"}},
        )

    def test_post_hook_reports_absolute_output_path(self):
        with tempfile.TemporaryDirectory() as temp_name:
            output_path = Path(temp_name) / "video.mp4"
            stream = io.StringIO()
            with patch("scripts.download.shutil.which", return_value=None):
                options = ydl_options("18", str(output_path))

            with redirect_stdout(stream):
                options["post_hooks"][0](str(output_path))

        self.assertEqual(
            stream.getvalue(),
            f"Download complete: {output_path.resolve()}\n",
        )

    def test_cookie_file_must_exist(self):
        with tempfile.TemporaryDirectory() as temp_name:
            path = Path(temp_name) / "cookies.txt"
            path.touch()

            self.assertEqual(cookie_file(str(path)), str(path))


if __name__ == "__main__":
    unittest.main()
