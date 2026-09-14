---
name: file-analysis-skill
description: Analyze a local directory's immediate files and subdirectories, summarize recursive byte sizes and file counts, print a readable table, and export a UTF-8 CSV report. Use whenever the user asks to inspect disk usage, compare top-level folders, count files by folder, inventory a directory, or generate a CSV size report from local files. This Skill handles local filesystem paths only and does not delete, rename, or modify the files being analyzed.
compatibility: Requires Python 3.10 or newer. No third-party Python packages are required.
---

# File Analysis

Use the bundled script for a deterministic, read-only summary of a local directory. Resolve the script relative to this `SKILL.md` and treat the Skill directory as read-only.

## Runtime Boundaries

- Run commands with the process working directory set to the user's workspace.
- Analyze only the local directory path the user provides; do not scan unrelated paths.
- The script reads file metadata and recursively counts regular files inside each immediate subdirectory. It does not alter analyzed files.
- Write the CSV to the user's workspace or another explicitly requested location. Do not put reports or temporary data in the Skill installation directory unless it is the requested output location.

## Analyze A Directory

Analyze the current workspace directory and create `analysis_result.csv`:

```bash
python <skill-dir>/scripts/analyze_top_level.py
```

Analyze a specific directory and choose the output path:

```bash
python <skill-dir>/scripts/analyze_top_level.py "<workspace>/media" \
  --csv "<workspace>/reports/media-analysis.csv"
```

The terminal report and CSV contain one row per immediate file or directory. Directory rows include the recursive total size and recursive regular-file count; file rows contain that file's size and a count of `1`. Rows are sorted by total size, largest first.

## CSV Format

The CSV is written as UTF-8 with a BOM so spreadsheet applications recognize Chinese headers. The columns are:

| Column | Meaning |
| --- | --- |
| `Name` | Immediate file or directory name |
| `Type` | `file` or `dir` |
| `Total Size (Bytes)` | Exact size in bytes |
| `Total Size` | Human-readable IEC-style size |
| `File Count` | `1` for a file, or recursive regular-file count for a directory |

The first column is intentionally populated from each filesystem entry's name. An input CSV's own filename or a missing CSV field is not used as the entry name.

## Report Results

Report the resolved CSV path and summarize the largest entries. For an empty directory, report that no immediate entries were found while still noting the CSV path. Surface missing paths, non-directory inputs, and filesystem errors instead of claiming that analysis completed.

## Limitations

- Directory totals include regular files below the directory, including nested directories, but not directory metadata itself.
- Unreadable entries are skipped so the rest of the report can complete.
- The script does not calculate file hashes, inspect file contents, or analyze remote storage.
