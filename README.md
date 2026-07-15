# Media Skills

English | [Simplified Chinese](README.zh-CN.md)

A collection of media-processing Skills for agent runtimes. Each Skill
lives in its own top-level directory and uses `SKILL.md` as the entry point;
scripts, dependencies, and bundled resources are managed inside that directory.

Installed Skill directories should contain only instructions, scripts,
dependency manifests, and bundled resources. At runtime, commands should use the
user workspace as the working directory. Inputs, outputs, local models,
downloads, and other runtime data should stay in the user workspace or another
location explicitly requested by the user, not in the Skill installation
directory.

## Skills

- [`transcribe-skill`](transcribe-skill/README.md): transcribe local audio and
  video into SRT subtitles
- [`video-grid-skill`](video-grid-skill/README.md): sample frames evenly from
  local videos and create contact sheets
- [`yt-dlp-skill`](yt-dlp-skill/README.md): inspect media formats and download
  audio or video

See each Skill's `README.md` for installation details and command examples.
