#!/usr/bin/env node
// Smoke test for md2docx.js. Run from anywhere after installing the skill's dependencies:
//   cd <skill-dir> && npm install docx markdown-it markdown-it-footnote @mermaid-js/mermaid-cli
//   node tests/smoke.test.js
// Needs the `unzip` command to inspect the generated package; assertions that depend on it
// are skipped when it is missing.

const fs = require("fs");
const os = require("os");
const path = require("path");
const zlib = require("zlib");
const assert = require("assert");
const { execFileSync } = require("child_process");

const SKILL_DIR = path.resolve(__dirname, "..");
const SCRIPT = path.join(SKILL_DIR, "scripts", "md2docx.js");

// ---------- tiny PNG writer (4x4 red square) so the test needs no binary fixtures ----------
const CRC_TABLE = Array.from({ length: 256 }, (_, n) => {
  let c = n;
  for (let k = 0; k < 8; k++) c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
  return c >>> 0;
});
function crc32(buf) {
  let c = 0xffffffff;
  for (const b of buf) c = CRC_TABLE[(c ^ b) & 0xff] ^ (c >>> 8);
  return (c ^ 0xffffffff) >>> 0;
}
function chunk(type, data) {
  const len = Buffer.alloc(4);
  len.writeUInt32BE(data.length);
  const body = Buffer.concat([Buffer.from(type, "ascii"), data]);
  const crc = Buffer.alloc(4);
  crc.writeUInt32BE(crc32(body));
  return Buffer.concat([len, body, crc]);
}
function makePng(size = 4) {
  const ihdr = Buffer.alloc(13);
  ihdr.writeUInt32BE(size, 0);
  ihdr.writeUInt32BE(size, 4);
  ihdr[8] = 8; // bit depth
  ihdr[9] = 2; // truecolor
  const raw = Buffer.alloc(size * (1 + size * 3));
  for (let y = 0; y < size; y++) {
    const row = y * (1 + size * 3);
    raw[row] = 0;
    for (let x = 0; x < size; x++) {
      raw[row + 1 + x * 3] = 0xcc;
      raw[row + 2 + x * 3] = 0x33;
      raw[row + 3 + x * 3] = 0x33;
    }
  }
  return Buffer.concat([
    Buffer.from([0x89, 0x50, 0x4e, 0x47, 0x0d, 0x0a, 0x1a, 0x0a]),
    chunk("IHDR", ihdr),
    chunk("IDAT", zlib.deflateSync(raw)),
    chunk("IEND", Buffer.alloc(0)),
  ]);
}

const FIXTURE = `---
name: fixture
description: frontmatter must not leak into the document body
---

# 冒烟测试文档

段落含 *斜体*、**加粗**、~~删除线~~、\`行内代码\` 和 [链接](https://example.com)。

## 列表

- 一级
  - 二级
    - 三级
- [ ] 待办项

5. 从五开始
6. 第六项

## 图片

![红块](dot.png)

## 脚注

正文脚注[^n]。

[^n]: 脚注内容。
`;

function haveUnzip() {
  try {
    execFileSync("unzip", ["-v"], { stdio: "ignore" });
    return true;
  } catch {
    return false;
  }
}

function main() {
  const work = fs.mkdtempSync(path.join(os.tmpdir(), "md2docx-smoke-"));
  const docs = path.join(work, "docs");
  fs.mkdirSync(docs);
  fs.writeFileSync(path.join(docs, "smoke.md"), FIXTURE);
  fs.writeFileSync(path.join(docs, "dot.png"), makePng());
  fs.writeFileSync(path.join(work, "doc-meta.json"), JSON.stringify({
    project: "冒烟项目", org: "测试组", docNo: "SMOKE-01", date: "2026-01-01", version: "V0.1",
  }));

  const out = path.join(work, "out");
  execFileSync(process.execPath, [SCRIPT, "docs", "-o", out], { cwd: work, stdio: "pipe" });
  const docx = path.join(out, "smoke.docx");
  assert.ok(fs.existsSync(docx), "docx was not produced");
  assert.ok(fs.statSync(docx).size > 10_000, "docx looks too small to contain content");

  const checks = [];
  const check = (name, fn) => checks.push({ name, fn });
  check("cover carries project and doc number", () => {
    const xml = unzipEntry(docx, "word/document.xml");
    assert.ok(xml.includes("冒烟项目"), "project name missing from cover");
    assert.ok(xml.includes("SMOKE-01"), "document number missing from cover");
  });
  check("frontmatter is dropped", () => {
    const xml = unzipEntry(docx, "word/document.xml");
    assert.ok(!xml.includes("frontmatter must not leak"), "YAML frontmatter leaked into the body");
  });
  check("inline emphasis survives", () => {
    const xml = unzipEntry(docx, "word/document.xml");
    assert.ok(/<w:i\/>/.test(xml), "italic run missing");
    assert.ok(/<w:strike\/>/.test(xml), "strike run missing");
  });
  check("nested list levels reach 2", () => {
    const xml = unzipEntry(docx, "word/document.xml");
    assert.ok(xml.includes('<w:ilvl w:val="2"/>'), "third list level missing");
  });
  check("task list becomes a checkbox", () => {
    assert.ok(unzipEntry(docx, "word/document.xml").includes("☐"), "task marker missing");
  });
  check("ordered list honours its start number", () => {
    assert.ok(unzipEntry(docx, "word/numbering.xml").includes('<w:start w:val="5"/>'), "start value not applied");
  });
  check("short intro stays on the first chapter page", () => {
    const xml = unzipEntry(docx, "word/document.xml");
    const breaks = (xml.match(/pageBreakBefore/g) || []).length;
    // The fixture has three "##" chapters; the first one must not force a page break.
    assert.strictEqual(breaks, 2, `expected 2 chapter page breaks, found ${breaks}`);
  });
  check("image is embedded", () => {
    const list = execFileSync("unzip", ["-l", docx]).toString();
    assert.ok(/word\/media\/[^ ]+\.png/.test(list), "no PNG in word/media");
  });
  check("footnote becomes a real footnote", () => {
    const list = execFileSync("unzip", ["-l", docx]).toString();
    assert.ok(list.includes("word/footnotes.xml"), "footnotes.xml missing");
    assert.ok(unzipEntry(docx, "word/footnotes.xml").includes("脚注内容"), "footnote text missing");
  });

  const runnable = haveUnzip() ? checks : [];
  if (!haveUnzip()) console.warn("! unzip not found: skipping package inspection checks");

  let failed = 0;
  for (const { name, fn } of runnable) {
    try {
      fn();
      console.log(`✓ ${name}`);
    } catch (e) {
      failed++;
      console.error(`✗ ${name}: ${e.message}`);
    }
  }
  console.log(`\n${runnable.length - failed}/${runnable.length} checks passed (workdir: ${work})`);
  process.exit(failed ? 1 : 0);
}

function unzipEntry(docx, entry) {
  return execFileSync("unzip", ["-p", docx, entry], { maxBuffer: 32 * 1024 * 1024 }).toString();
}

main();
