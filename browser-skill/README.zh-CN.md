# browser-skill

[English](README.md) | 中文

`browser-skill` 使用 Playwright Chromium 检查浏览器渲染后的网页、提取可见文本、生成截图，并指导执行范围明确的浏览器交互测试。

## 功能

- 使用 Chromium 打开明确的 HTTP、HTTPS 和本地 `file` URL
- 输出请求 URL、重定向后的最终 URL 和页面标题
- 提取整页或指定区域的可见文本
- 等待动态内容出现后再收集结果
- 生成当前视口或完整页面的 PNG/JPEG 截图
- 默认使用无头 Chromium，可配置视口和超时时间
- 默认跳过已有输出，仅在指定 `--overwrite` 时覆盖
- 支持人类可读输出和 JSON 结构化输出
- 使用隔离的浏览器上下文，不读取已安装浏览器的配置和 Cookie

## 依赖

- Python 3.10 或更高版本
- Playwright Python 包
- Playwright Chromium

安装 Python 依赖和浏览器运行时：

```bash
python -m pip install -r <skill-dir>/requirements.txt
python -m playwright install chromium
```

## 安装为 Skill

将 `browser-skill` 目录复制或链接到智能体运行时支持的 Skill 搜索目录。保持目录结构完整，并确保运行时能够读取 `SKILL.md`。

Skill 标识为 `browser-skill`。

## 运行目录

Skill 安装目录只用于读取说明、脚本和依赖清单。命令应在用户工作区中执行，截图、提取文本、测试脚本、trace 等运行产物保存在工作区或用户明确指定的位置。

下文用 `<skill-dir>` 表示 Skill 安装目录，用 `<workspace>` 表示用户工作区。

## 检查网页

输出页面标题和 `body` 中的可见文本：

```bash
python <skill-dir>/scripts/browser_snapshot.py "https://example.com"
```

提取指定区域的可见文本并输出 JSON：

```bash
python <skill-dir>/scripts/browser_snapshot.py "https://example.com" \
  --selector "main" --json
```

## 生成截图

截取当前视口：

```bash
python <skill-dir>/scripts/browser_snapshot.py "http://127.0.0.1:3000" \
  --screenshot "<workspace>/home.png"
```

等待动态内容，截取完整页面并保存可见文本：

```bash
python <skill-dir>/scripts/browser_snapshot.py "http://127.0.0.1:3000/dashboard" \
  --wait-for "[data-testid='summary']" --selector "main" \
  --screenshot "<workspace>/dashboard.png" --full-page \
  --text-output "<workspace>/dashboard.txt"
```

如果截图或文本文件已经存在，默认跳过；明确指定 `--overwrite` 后才会覆盖。

## 交互测试

内置脚本用于只读检查。点击、填写表单、多步跳转等任务，应在用户工作区创建范围明确的 Playwright 脚本。优先使用无障碍定位器、明确的状态或 URL 等待、合成测试数据和用户可见结果断言。不要读取已安装浏览器的配置，也不要输出凭据、Cookie、Token 或 storage state。

## 常用参数

- `URL`：必填，明确的 HTTP、HTTPS 或 file URL
- `--screenshot`：`.png`、`.jpg` 或 `.jpeg` 截图路径
- `--text-output`：UTF-8 可见文本输出路径
- `--selector`：提取文本的 locator，默认 `body`
- `--wait-for`：提取前必须变为可见的 locator
- `--wait-until`：`commit`、`domcontentloaded`、`load` 或 `networkidle`
- `--timeout`：导航和 locator 超时毫秒数，默认 `30000`
- `--viewport-width`、`--viewport-height`：视口尺寸，默认 `1280x720`
- `--full-page`：截取完整可滚动页面
- `--headed`：显示浏览器窗口
- `--overwrite`：覆盖已有输出
- `--json`：输出结构化结果

## 目录结构

```text
browser-skill/
|-- SKILL.md
|-- README.md
|-- README.zh-CN.md
|-- requirements.txt
|-- evals/
|   `-- evals.json
|-- scripts/
|   `-- browser_snapshot.py
`-- tests/
    `-- test_browser_snapshot.py
```
