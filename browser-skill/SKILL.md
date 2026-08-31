---
name: browser-skill
description: Inspect and test web pages with Playwright, including local development sites and explicit HTTP, HTTPS, or file URLs. Use whenever the user asks to open a page in a real browser, verify rendered content or navigation, capture a full-page or viewport screenshot, extract visible text or a page title, wait for dynamic content, or automate a focused browser interaction. Do not use for downloading media, scraping credentials or browser profiles, bypassing access controls, or testing an API that does not require browser rendering.
compatibility: Requires Python 3.10 or newer, the bundled pip requirements, and a Playwright Chromium installation.
---

# Browser

Use Playwright for deterministic browser inspection and focused UI checks. Resolve bundled resources relative to this `SKILL.md` and treat the Skill directory as read-only.

## Runtime Boundaries

- Run commands with the process working directory set to the user's workspace.
- Read scripts and requirements from `<skill-dir>`, but keep screenshots, extracted text, test scripts, traces, and other runtime data in `<workspace>` or another user-requested location.
- Never create virtual environments, browser downloads, profiles, caches, outputs, or persistent temporary files under `<skill-dir>`.
- Use an isolated Playwright browser context. Do not inspect installed browser profiles, copy cookies, discover credentials, or persist authenticated state unless the user explicitly supplies a test fixture intended for that purpose.
- Restrict actions to the URL and workflow requested by the user. Do not submit purchases, publish content, send messages, or perform other real-world side effects without explicit confirmation.

## Prepare The Runtime

Install the Python package into the active environment when unavailable:

```bash
python -m pip install -r <skill-dir>/requirements.txt
python -m playwright install chromium
```

Reuse an existing compatible Chromium installation when possible. If browser installation is blocked by permissions or network access, report the missing prerequisite.

## Inspect A Page

Use the bundled script for page titles, visible text, selector-scoped text, and screenshots:

```bash
python <skill-dir>/scripts/browser_snapshot.py "https://example.com"
```

Capture a full-page screenshot and save visible page text:

```bash
python <skill-dir>/scripts/browser_snapshot.py "http://127.0.0.1:3000" \
  --screenshot "<workspace>/home.png" --full-page \
  --text-output "<workspace>/home.txt"
```

Wait for dynamic content and extract only a relevant region:

```bash
python <skill-dir>/scripts/browser_snapshot.py "http://127.0.0.1:3000/dashboard" \
  --wait-for "[data-testid='summary']" --selector "main" \
  --screenshot "<workspace>/dashboard.png" --json
```

The script accepts explicit `http`, `https`, and `file` URLs. It runs headless by default, uses a 1280x720 viewport, waits for `domcontentloaded`, and refuses to replace screenshot or text files unless `--overwrite` is supplied.

## Automate An Interaction

For clicks, form entry, navigation assertions, or multi-step workflows that the snapshot script cannot express, write a focused Playwright script in the user workspace:

- Prefer accessible locators such as `get_by_role`, `get_by_label`, and `get_by_text`; use test IDs or CSS selectors only when the accessible UI does not identify the target reliably.
- Wait for a specific visible state or URL instead of adding arbitrary sleeps.
- Assert the requested user-visible outcome after each important action.
- Use clearly synthetic test data. Do not print secrets, tokens, cookies, passwords, or full storage state.
- Keep the browser headless unless the user asks to watch or manually assist with the flow.
- Close the browser in a `finally` block and save requested artifacts under the workspace.

When the user asks to test a local application, confirm that its server is running and use its actual reported URL rather than guessing a port.

## Report Results

Report the requested URL, final URL after redirects, page title, verified conditions, and artifact paths. Distinguish successful checks from skipped existing outputs and failures. Surface navigation timeouts, missing selectors, browser launch failures, console errors relevant to the requested flow, and failed assertions instead of claiming that the page passed.
