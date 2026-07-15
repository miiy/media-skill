import unittest

from scripts.list_formats import (
    downloadable_formats,
    get_best_resolution,
    json_output,
    media_type,
)


class ListFormatsTests(unittest.TestCase):
    def test_audio_only_media_has_no_best_resolution(self):
        formats = [
            {
                "format_id": "140",
                "ext": "m4a",
                "vcodec": "none",
                "acodec": "mp4a.40.2",
            }
        ]

        payload = json_output({"id": "audio", "title": "Audio"}, formats)

        self.assertIsNone(payload["best_resolution"])
        self.assertEqual(payload["formats"][0]["type"], "audio")

    def test_best_resolution_uses_largest_video_format(self):
        formats = [
            {"width": 1280, "height": 720, "fps": 30, "vcodec": "avc1"},
            {"width": 1920, "height": 1080, "fps": 30, "vcodec": "avc1"},
        ]

        self.assertEqual(get_best_resolution(formats), "1920x1080")

    def test_non_media_formats_are_filtered_out(self):
        formats = [
            {"format_id": "storyboard", "vcodec": "none", "acodec": "none"},
            {"format_id": "audio", "vcodec": "none", "acodec": "opus"},
        ]

        self.assertEqual(
            downloadable_formats(formats),
            [formats[1]],
        )
        self.assertEqual(media_type(formats[1]), "audio")


if __name__ == "__main__":
    unittest.main()
