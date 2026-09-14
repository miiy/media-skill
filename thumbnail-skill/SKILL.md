---
name: thumbnail-skill
description: Generate JPEG thumbnails from local video and image files, individually or in batches, with configurable height and sampled fingerprint or full-file hash naming. Automatically skip black video frames. Use for media-library previews, not contact sheets or designed artwork.
---

# Thumbnail

Use `scripts/create_thumbnail.py` for a unified video and image workflow. The default thumbnail height is 180 pixels; width scales proportionally.

## Runtime

Requires Python 3.10+, OpenCV, NumPy, and FFmpeg for video inputs. Run from the user's workspace, keep outputs and caches there or at a requested location, and treat the skill directory as read-only. Install Python dependencies into the active environment when needed:

```bash
python -m pip install -r <skill-dir>/requirements.txt
```

## Generate Thumbnails

For one video or image, use an output directory:

```bash
python <skill-dir>/scripts/create_thumbnail.py \
  --input "<workspace>/media.mp4" --output "<workspace>/thumbnails"
```

Set another height or use the full-file hash:

```bash
python <skill-dir>/scripts/create_thumbnail.py \
  --input "<workspace>/photo.png" --output "<workspace>/thumbnails-360" \
  --height 360 --hash-mode full
```

For a mixed directory, add `--recursive` when subdirectories should be included:

```bash
python <skill-dir>/scripts/create_thumbnail.py \
  --input "<workspace>/media" --output "<workspace>/thumbnails" --recursive --json
```

`--media-type all` is the default and classifies files by extension. Use `--media-type video` or `--media-type image` to process only one type, or to process a single file with no recognized extension. Directory scans include supported video and image extensions; unsupported files are skipped. A distinct output subdirectory is excluded from recursive scans.

## Processing Rules

- Video processing uses the original FFmpeg duration parsing, temporary-JPEG extraction, OpenCV/NumPy black-frame detection, and one-second retry logic. The starting seek is 0 seconds for files below 100 MiB or integer duration at most 20 minutes, otherwise 5 seconds.
- Image processing uses OpenCV color decoding, `INTER_AREA` resizing, and default JPEG encoding. Transparency is not retained.
- `--height` accepts a positive integer and defaults to 180. It applies to both media types.
- `--hash-mode fingerprint` is the default. Files up to 4 MiB use full SHA-256; larger files hash the decimal byte size and first/last 2 MiB. `--hash-mode full` hashes every byte in 8 MiB chunks. Both produce `<hash>.jpg` names.
- Existing outputs are skipped. Use `--overwrite` to replace them. Height does not affect names, so use a separate output directory for another size or overwrite existing files.

## Report Results

`--json` prints `input`, `output`, `status`, and `media_type`; failures include `error`. A batch continues after individual failures and returns nonzero if any file fails. Verify successful output files exist and are non-empty.
