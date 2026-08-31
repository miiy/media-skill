import argparse
import stat
import tempfile
import unittest
from pathlib import Path

from scripts.browser_snapshot import (
    existing_outputs,
    inspect_page,
    parse_args,
    screenshot_path,
    validate_url,
    write_text_atomic,
)


class BrowserSnapshotTests(unittest.TestCase):
    def test_validate_url_accepts_explicit_web_and_file_urls(self):
        self.assertEqual(validate_url("https://example.com/a"), "https://example.com/a")
        self.assertEqual(validate_url("http://127.0.0.1:3000"), "http://127.0.0.1:3000")
        self.assertEqual(validate_url("file:///tmp/page.html"), "file:///tmp/page.html")

    def test_validate_url_rejects_implicit_or_unsafe_schemes(self):
        for value in ("example.com", "javascript:alert(1)", "data:text/html,hello"):
            with self.subTest(value=value), self.assertRaises(argparse.ArgumentTypeError):
                validate_url(value)

    def test_screenshot_path_requires_supported_extension(self):
        self.assertEqual(screenshot_path("capture.PNG"), Path("capture.PNG"))
        with self.assertRaises(argparse.ArgumentTypeError):
            screenshot_path("capture.webp")

    def test_parse_args_sets_safe_defaults(self):
        args = parse_args(["https://example.com"])

        self.assertEqual(args.selector, "body")
        self.assertEqual(args.wait_until, "domcontentloaded")
        self.assertEqual(args.timeout, 30_000)
        self.assertEqual((args.viewport_width, args.viewport_height), (1280, 720))
        self.assertFalse(args.headed)
        self.assertFalse(args.overwrite)

    def test_existing_outputs_filters_missing_paths(self):
        with tempfile.TemporaryDirectory() as temp_name:
            directory = Path(temp_name)
            existing = directory / "existing.txt"
            missing = directory / "missing.png"
            existing.touch()

            result = existing_outputs((existing, missing, None))

        self.assertEqual(result, [existing])

    def test_write_text_atomic_adds_newline_and_readable_permissions(self):
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "nested" / "page.txt"

            write_text_atomic(output, "hello")

            content = output.read_text(encoding="utf-8")
            mode = stat.S_IMODE(output.stat().st_mode)

        self.assertEqual(content, "hello\n")
        self.assertEqual(mode, 0o644)

    def test_existing_output_skips_before_playwright_is_needed(self):
        with tempfile.TemporaryDirectory() as temp_name:
            screenshot = Path(temp_name) / "page.png"
            screenshot.touch()
            args = parse_args(
                ["https://example.com", "--screenshot", str(screenshot), "--json"]
            )

            result = inspect_page(args)

        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["existing_outputs"], [str(screenshot.resolve())])
        self.assertIsNone(result["final_url"])


if __name__ == "__main__":
    unittest.main()
