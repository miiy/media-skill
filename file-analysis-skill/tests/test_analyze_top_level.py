import csv
import tempfile
import unittest
from pathlib import Path

from scripts.analyze_top_level import (
    analyze_top_level,
    format_size,
    parse_args,
    write_csv,
)


class FileAnalysisTests(unittest.TestCase):
    def test_format_size(self):
        self.assertEqual(format_size(0), "0.00 B")
        self.assertEqual(format_size(1536), "1.50 KB")

    def test_analyze_top_level_counts_nested_files_and_sorts_by_size(self):
        with tempfile.TemporaryDirectory() as temp_name:
            root = Path(temp_name)
            (root / "small.txt").write_bytes(b"1")
            nested = root / "nested"
            nested.mkdir()
            (nested / "a.bin").write_bytes(b"1234")
            (nested / "b.bin").write_bytes(b"12")

            results = analyze_top_level(root)

        self.assertEqual([item["name"] for item in results], ["nested", "small.txt"])
        self.assertEqual(results[0]["size_bytes"], 6)
        self.assertEqual(results[0]["file_count"], 2)
        self.assertEqual(results[1]["file_count"], 1)

    def test_write_csv_uses_entry_name_as_first_column(self):
        with tempfile.TemporaryDirectory() as temp_name:
            output = Path(temp_name) / "reports" / "result.csv"
            write_csv(
                [
                    {
                        "name": "docs",
                        "type": "dir",
                        "size_bytes": 1024,
                        "file_count": 1,
                    }
                ],
                output,
            )
            raw = output.read_bytes()
            with output.open("r", encoding="utf-8-sig", newline="") as handle:
                rows = list(csv.reader(handle))

        self.assertTrue(raw.startswith(b"\xef\xbb\xbf"))
        self.assertEqual(rows[1][0], "docs")
        self.assertEqual(rows[1][2], "1024")

    def test_parse_args_defaults(self):
        args = parse_args([])
        self.assertEqual(args.directory, ".")
        self.assertEqual(args.csv, "analysis_result.csv")


if __name__ == "__main__":
    unittest.main()
