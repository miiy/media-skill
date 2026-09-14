# thumbnail-skill

English | [简体中文](README.zh-CN.md)

Generate JPEG thumbnails from local videos and images with one unified command.

## Requirements

Python 3.10+, OpenCV, and NumPy. FFmpeg is also required when processing videos. Install Python dependencies with:

```bash
python -m pip install -r <skill-dir>/requirements.txt
```

Run from the workspace and keep outputs there or at a requested location.

## Usage

```bash
python <skill-dir>/scripts/create_thumbnail.py \
  --input "<workspace>/media.mp4" --output "<workspace>/thumbnails"

python <skill-dir>/scripts/create_thumbnail.py \
  --input "<workspace>/media" --output "<workspace>/thumbnails" \
  --recursive --height 360 --hash-mode full --json
```

The unified entry point uses `--media-type all` by default and detects videos and images by extension. Use `--media-type video` or `--media-type image` to process only one type, or for an extensionless single file. `--height` is a positive integer and defaults to `180`; width scales proportionally. `--hash-mode` is `fingerprint` by default or `full` for complete-file SHA-256. Existing `<hash>.jpg` outputs are skipped unless `--overwrite` is supplied. A batch continues after individual failures and returns a nonzero exit code if any fail.

Video processing keeps the original FFmpeg extraction and OpenCV/NumPy black-frame selection. Image processing keeps the original OpenCV color decode, `INTER_AREA` resize, and JPEG encoding. Image transparency is not retained. For video contact sheets, use `video-grid-skill`.
