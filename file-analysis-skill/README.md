# file-analysis-skill

[English](README.md) | [Simplified Chinese](README.zh-CN.md)

`file-analysis-skill` summarizes the immediate files and directories inside a local directory, recursively totals directory sizes and file counts, prints a readable table, and exports an Excel-friendly UTF-8 CSV report.

## Features

- Read-only analysis of local filesystem paths
- Recursive byte totals and regular-file counts for immediate subdirectories
- Human-readable terminal table sorted by size
- UTF-8-with-BOM CSV output for spreadsheet applications
- Configurable input directory and CSV destination
- Clear errors for missing paths and non-directory inputs

## Requirements

- Python 3.10 or newer
- No third-party Python packages

## Install As A Skill

Copy or symlink the `file-analysis-skill` directory into the Skill search path used by the agent runtime. Keep the directory structure intact so the runtime can read `SKILL.md`.

The Skill identifier is `file-analysis-skill`.

## Usage

```bash
python <skill-dir>/scripts/analyze_top_level.py <workspace>/media
```

By default the report is written to `analysis_result.csv` relative to the command's working directory. Choose another destination with `--csv`:

```bash
python <skill-dir>/scripts/analyze_top_level.py <workspace>/media \
  --csv <workspace>/reports/media-analysis.csv
```

The first CSV column is the name of each immediate filesystem entry. It is not taken from an input CSV filename or from a possibly blank source field.

## Directory Structure

```text
file-analysis-skill/
|-- SKILL.md
|-- README.md
|-- README.zh-CN.md
|-- requirements.txt
|-- evals/
|   `-- evals.json
|-- scripts/
|   |-- __init__.py
|   `-- analyze_top_level.py
`-- tests/
    `-- test_analyze_top_level.py
```
