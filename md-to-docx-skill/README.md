# md-to-docx-skill

English | [简体中文](README.zh-CN.md)

Turn markdown drafts into Chinese Word documents with a fixed, adjustable
typesetting profile: cover page, TOC field, header and footer, SimSun body text
at 12pt with 1.5 line spacing, Heiti headings, auto-width tables, and embedded
mermaid diagrams. The docx is the deliverable; PDF export through LibreOffice is
an optional final step.

## Requirements

Node.js 18 or newer plus npm. The converter depends on `docx`, `markdown-it`, and
`@mermaid-js/mermaid-cli`; mermaid rendering also needs a system Chrome. Markdown
parsing is delegated to markdown-it, so nested lists, tables, images, task lists, and
inline formatting come from the library instead of hand-written parsing code.

Set a registry mirror once, then install:

```bash
cd <skill-dir>
npm config set registry https://registry.npmmirror.com
npm install docx markdown-it markdown-it-footnote @mermaid-js/mermaid-cli
```

Install dependencies once, then run the converter from the user workspace and
keep sources and outputs there. Treat the skill directory as read-only.

## Usage

```bash
node <skill-dir>/scripts/md2docx.js [src-dir|file.md...] [-o <out-dir>] [-m <meta.json>]
```

The converter reads every `.md` under `./docs` when no path is given, falls back
to the current directory, and writes one `.docx` per source into `./docx-out`.

Project-specific values (project name, organization, contract number, date,
version) go in `doc-meta.json` so the same markdown can be re-rendered per
project:

```json
{ "project": "项目名称", "org": "编制单位", "contract": "合同编号", "docNo": "文档编号", "date": "2026-11-19", "version": "V1.0" }
```

`subtitle` and `contract` are optional and simply disappear from the cover when
absent. Missing required fields render as underlined placeholders; re-running
after filling them replaces the cover, header, and revision table in one pass.

## Checking the result

```bash
unzip -l out.docx | grep media     # images embedded
pandoc -t markdown out.docx | head # content intact
```

Ask the user to open the file in Word and press F9 to refresh the TOC field —
the page numbers come from the field, not from the converter. LibreOffice PDF
export does not refresh the field, so a PDF built with `docx2pdf.sh` has a TOC
without page numbers.

## Tests

```bash
cd <skill-dir> && npm install docx markdown-it markdown-it-footnote @mermaid-js/mermaid-cli
node tests/smoke.test.js
```

Eight assertions cover the cover page, frontmatter stripping, inline emphasis,
nested list levels, task markers, ordered-list start numbers, image embedding,
and real footnotes. Uses a generated PNG fixture, so no binary test data.

## Common pitfalls

- Table widths must stay automatic (`TableLayoutType.AUTOFIT` plus a
  table-level percentage width). Do not hard-code DXA cell widths.
- `PageBreak` must be wrapped in a `Paragraph`; use multiple paragraphs instead
  of `\n`; `ImageRun` needs `type: "png"`.
- There is no pure-npm docx→PDF renderer. Have the user export from Word after
  pressing F9, or use `bash <skill-dir>/scripts/docx2pdf.sh` when LibreOffice is
  installed.

## Files

- [`SKILL.md`](SKILL.md) — the instruction pack used at runtime.
- [`references/format-spec.md`](references/format-spec.md) — default typography
  spec and font-size cheat sheet.
- `scripts/md2docx.js` (`--clear-cache` prunes the mermaid cache),
  `scripts/docx2pdf.sh` (`--overwrite` to replace existing PDFs).
- `tests/smoke.test.js`.
- [`evals/evals.json`](evals/evals.json) — sample prompts with expected results.
