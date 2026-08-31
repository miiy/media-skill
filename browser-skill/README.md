# browser-skill

English | [Simplified Chinese](README.zh-CN.md)

`browser-skill` uses Playwright Chromium to inspect rendered web pages, extract visible text, capture screenshots, and guide focused browser interaction tests.

## Features

- Open explicit HTTP, HTTPS, and local `file` URLs in Chromium
- Report the requested URL, final URL after redirects, and rendered page title
- Extract visible text from the whole page or a selected region
- Wait for dynamic content before collecting results
- Capture viewport or full-page PNG/JPEG screenshots
- Use headless Chromium by default with configurable viewport and timeout
- Skip existing output files by default and overwrite only with `--overwrite`
- Support human-readable and structured JSON output
- Keep browser contexts isolated from installed browser profiles and cookies

## Requirements

- Python 3.10 or newer
- Playwright for Python
- Playwright Chromium

Install the Python dependency and browser runtime:

```bash
python -m pip install -r <skill-dir>/requirements.txt
python -m playwright install chromium
```

## Install As A Skill

Copy or symlink the `browser-skill` directory into the Skill search path supported by your agent runtime. Keep the directory structure intact and ensure the runtime can read `SKILL.md`.

The Skill identifier is `browser-skill`.

## Runtime Directory

Treat the installed Skill directory as read-only. Run commands from the user's workspace and keep screenshots, extracted text, test scripts, traces, and other runtime artifacts in the workspace or another explicitly requested location.

The examples below use `<skill-dir>` for the installed Skill directory and `<workspace>` for the user workspace.

## Inspect A Page

Print the title and visible body text:

```bash
python <skill-dir>/scripts/browser_snapshot.py "https://example.com"
```

Extract visible text from a page region and return JSON:

```bash
python <skill-dir>/scripts/browser_snapshot.py "https://example.com" \
  --selector "main" --json
```

## Capture A Screenshot

Capture the current viewport:

```bash
python <skill-dir>/scripts/browser_snapshot.py "http://127.0.0.1:3000" \
  --screenshot "<workspace>/home.png"
```

Wait for dynamic content, capture the full page, and save visible text:

```bash
python <skill-dir>/scripts/browser_snapshot.py "http://127.0.0.1:3000/dashboard" \
  --wait-for "[data-testid='summary']" --selector "main" \
  --screenshot "<workspace>/dashboard.png" --full-page \
  --text-output "<workspace>/dashboard.txt"
```

Existing screenshot and text outputs are skipped unless `--overwrite` is present.

## Focused Interactions

The bundled script handles read-only inspection. For clicks, form entry, and multi-step assertions, create a focused Playwright script in the user workspace. Prefer accessible locators, explicit state or URL waits, synthetic test data, and user-visible assertions. Do not inspect installed browser profiles or print credentials, cookies, tokens, or storage state.

## Common Options

- `URL`: required explicit HTTP, HTTPS, or file URL
- `--screenshot`: output `.png`, `.jpg`, or `.jpeg` path
- `--text-output`: UTF-8 visible-text output path
- `--selector`: locator used for text extraction; default is `body`
- `--wait-for`: locator that must become visible before extraction
- `--wait-until`: `commit`, `domcontentloaded`, `load`, or `networkidle`
- `--timeout`: navigation and locator timeout in milliseconds; default is `30000`
- `--viewport-width`, `--viewport-height`: viewport dimensions; defaults are `1280x720`
- `--full-page`: capture the full scrollable page
- `--headed`: display the browser window
- `--overwrite`: replace existing outputs
- `--json`: print structured results

## Structure

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
