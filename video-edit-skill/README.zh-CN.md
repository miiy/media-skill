# video-edit-skill

[English](README.md) | 中文

`video-edit-skill` 提供基于 FFmpeg 的确定性脚本，用于剪切、变换和拼接本地视频。

## 功能

- 重编码实现帧级精确剪切
- 流复制实现快速、关键帧对齐的无损剪切
- 视频变速并同步处理音频
- 裁剪、指定尺寸缩放，以及顺时针、逆时针和 180 度旋转
- 去除音轨
- 精确拼接时统一不同输入的尺寸、帧率和音频格式
- 拼接兼容性校验后执行无损拼接
- 添加片头和片尾
- 原子输出、默认跳过已有文件和 JSON 状态

## 依赖

- Python 3.10 或更高版本
- `ffmpeg` 和 `ffprobe`，且已经加入 `PATH`
- 不需要第三方 Python 包

## 编辑单个视频

```bash
python <skill-dir>/scripts/edit_video.py <workspace>/input.mp4 \
  --start 12.5 --end 68 \
  --output <workspace>/trimmed.mp4
```

在一次编码中组合多个画面操作：

```bash
python <skill-dir>/scripts/edit_video.py <workspace>/input.mp4 \
  --speed 1.25 \
  --crop 1080x1080+420+0 \
  --scale 1080x1080 \
  --rotate cw \
  --output <workspace>/edited.mp4
```

使用流复制快速剪切，切点会受到源视频关键帧限制：

```bash
python <skill-dir>/scripts/edit_video.py <workspace>/input.mp4 \
  --start 30 --duration 45 --mode lossless \
  --output <workspace>/clip.mp4
```

## 拼接视频

统一不同输入的参数后拼接：

```bash
python <skill-dir>/scripts/concat_videos.py \
  <workspace>/part-1.mp4 <workspace>/part-2.mov \
  --output <workspace>/joined.mp4
```

添加片头和片尾：

```bash
python <skill-dir>/scripts/concat_videos.py <workspace>/main.mp4 \
  --intro <workspace>/intro.mp4 \
  --outro <workspace>/outro.mp4 \
  --output <workspace>/published.mp4
```

输入流参数完全一致时执行无损拼接：

```bash
python <skill-dir>/scripts/concat_videos.py \
  <workspace>/part-1.mp4 <workspace>/part-2.mp4 \
  --mode lossless --output <workspace>/joined.mp4
```

默认使用精确模式，并以第一个主视频的画布尺寸和帧率为准；也可用 `--size` 和
`--fps` 显式指定。无损模式不能应用滤镜，剪切位置也受到源视频关键帧限制。

两个脚本默认跳过已有输出，只有传入 `--overwrite` 才会替换。需要结构化结果时使用
`--json`。

## 目录结构

```text
video-edit-skill/
|-- SKILL.md
|-- README.md
|-- README.zh-CN.md
|-- requirements.txt
|-- evals/
|   `-- evals.json
|-- scripts/
|   |-- edit_video.py
|   |-- concat_videos.py
|   `-- media_utils.py
`-- tests/
    `-- test_video_edit.py
```
