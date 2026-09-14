# thumbnail-skill

[English](README.md) | 中文

使用统一命令为本地视频和图片生成 JPEG 缩略图。

## 依赖

需要 Python 3.10+、OpenCV 和 NumPy；处理视频时还需要 FFmpeg。安装 Python 依赖：

```bash
python -m pip install -r <skill-dir>/requirements.txt
```

从用户工作区运行，输出放在工作区或指定位置。

## 使用

```bash
python <skill-dir>/scripts/create_thumbnail.py \
  --input "<workspace>/media.mp4" --output "<workspace>/thumbnails"

python <skill-dir>/scripts/create_thumbnail.py \
  --input "<workspace>/media" --output "<workspace>/thumbnails" \
  --recursive --height 360 --hash-mode full --json
```

统一入口默认使用 `--media-type all`，按扩展名自动识别视频和图片。使用 `--media-type video` 或 `--media-type image` 可只处理一种类型，也可处理无扩展名的单文件。`--height` 为正整数，默认 `180`，宽度按比例缩放。`--hash-mode` 默认为 `fingerprint`，也可使用 `full` 计算完整文件 SHA-256。已有 `<hash>.jpg` 默认跳过，使用 `--overwrite` 替换。批量处理会继续处理其他文件，任一文件失败时最终退出码非零。

视频处理沿用原 FFmpeg 抽帧和 OpenCV/NumPy 黑帧选择算法；图片处理沿用原 OpenCV 彩色解码、`INTER_AREA` 缩放和 JPEG 编码，图片透明通道不会保留。视频网格图请使用 `video-grid-skill`。
