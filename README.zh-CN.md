# Media Skills

[English](README.md) | 中文

面向各类智能体的媒体处理 Skill 集合。每个可用 Skill 都放在独立的顶层目录中，
并以 `SKILL.md` 作为入口；脚本、依赖和资源也由该目录自行管理。

Skill 安装目录只存放说明、脚本、依赖清单和内置资源。运行时以用户工作区
作为工作目录，输入、输出、本地模型、下载文件等数据都保存在用户工作区或用户明确
指定的位置，不写入 Skill 安装目录。

## Skills

- [`transcribe-skill`](transcribe-skill/README.zh-CN.md)：将本地音视频转写为 SRT 字幕
- [`video-grid-skill`](video-grid-skill/README.zh-CN.md)：从本地视频均匀抽帧，生成视频网格图（contact sheet）
- [`yt-dlp-skill`](yt-dlp-skill/README.zh-CN.md)：查看媒体格式并下载音视频

各 Skill 的安装方式和命令示例见对应目录的 `README.md` 或 `README.zh-CN.md`。
