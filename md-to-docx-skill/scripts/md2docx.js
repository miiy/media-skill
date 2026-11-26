#!/usr/bin/env node
// Markdown to delivery-grade docx: A4, SimSun 12pt body at 1.5 line spacing, SimHei
// headings, 10.5pt tables, document name in the header, page numbers in the footer,
// cover page + revision record + TOC field, mermaid blocks rendered to images.
// Markdown parsing is delegated to markdown-it; this file only maps tokens to docx.
// Typography defaults live in references/format-spec.md and in the constants below.

const fs = require("fs");
const path = require("path");
const { execFileSync } = require("child_process");
const crypto = require("crypto");
// Resolve dependencies from the working directory or the skill directory; the
// skill itself ships no node_modules.
function req(name) {
  try { return require(require.resolve(name, { paths: [process.cwd(), __dirname, path.join(__dirname, "..")] })); }
  catch {
    console.error(`Missing dependency ${name}. Run "npm install ${name}" in the working directory.` + (name.includes("mermaid") ? " Setting a registry mirror first (npm config set registry https://registry.npmmirror.com) avoids download stalls." : ""));
    process.exit(1);
  }
}
const {
  AlignmentType, BorderStyle, Document, Footer, FootnoteReferenceRun, Header, HeadingLevel, ImageRun, LevelFormat,
  LineRuleType, PageBreak, PageNumber, Packer, Paragraph, ShadingType, Table, TableLayoutType,
  TableCell, TableOfContents, TableRow, TextRun, WidthType,
} = req("docx");
const MarkdownIt = req("markdown-it");
const footnotePlugin = req("markdown-it-footnote");
// html stays on only so inline <br> can become a line break; other raw HTML is ignored.
const md = new MarkdownIt({ html: true, linkify: false, typographer: false }).use(footnotePlugin);

// Usage: node md2docx.js [src-dir|file.md...] [-o out-dir] [-m meta.json]
const ROOT = process.cwd();
const argv = process.argv.slice(2);
const argOpts = {};
const argInputs = [];
for (let i = 0; i < argv.length; i++) {
  if (argv[i] === "-o" || argv[i] === "--out") argOpts.out = argv[++i];
  else if (argv[i] === "-m" || argv[i] === "--meta") argOpts.meta = argv[++i];
  else if (argv[i] === "--clear-cache") argOpts.clearCache = true;
  else argInputs.push(argv[i]);
}
const SRC = argInputs.length && argInputs[0].endsWith(".md") ? ROOT : (argInputs[0] ? path.resolve(argInputs[0]) : (fs.existsSync(path.join(ROOT, "docs")) ? path.join(ROOT, "docs") : ROOT));
const OUT = path.resolve(argOpts.out || path.join(ROOT, "docx-out"));
const MERMAID_CACHE = path.join(ROOT, ".md2docx-cache");
const IMG_MAX_W = 580; // px, roughly the A4 text column width at 96 dpi
if (fs.existsSync("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome") && !fs.existsSync(path.join(ROOT, "puppeteer-config.json"))) {
  fs.writeFileSync(path.join(ROOT, "puppeteer-config.json"), '{\n  "executablePath": "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"\n}\n');
}

// Font sizes in half-points: title 18pt=36, h1 16pt=32, h2 14pt=28, body 12pt=24, table 10.5pt=21, small 9pt=18
const F = { h1: 32, h2: 28, h3: 24, body: 24, table: 21, small: 18, title: 36 };
const SONG = { ascii: "Times New Roman", hAnsi: "Times New Roman", eastAsia: "宋体" };
const HEI = { ascii: "SimHei", hAnsi: "SimHei", eastAsia: "黑体" };
const KAI = { ascii: "Times New Roman", hAnsi: "Times New Roman", eastAsia: "楷体" };
const MONO = { ascii: "Consolas", hAnsi: "Consolas", eastAsia: "宋体" };

let meta = {};
const metaPath = argOpts.meta ? path.resolve(argOpts.meta) : path.join(ROOT, "doc-meta.json");
if (fs.existsSync(metaPath)) { try { meta = JSON.parse(fs.readFileSync(metaPath, "utf8")); } catch {} }
const META = {
  project: meta.project || "＿＿＿＿＿＿＿＿＿＿",
  org: meta.org || "＿＿＿＿＿＿＿＿＿＿",
  contract: meta.contract || "＿＿＿＿＿＿＿＿＿＿",
  date: meta.date || new Date().toISOString().slice(0, 10),
  version: meta.version || "V1.0",
};

// Directory of the markdown being converted, used to resolve relative image paths.
let CURRENT_DIR = ROOT;

// ---------- Markdown tokens -> block list ----------
function inlineText(token) {
  return (token && token.children ? token.children : []).map((c) => c.content || "").join("");
}

function blocksFrom(tokens) {
  const blocks = [];
  let i = 0;
  while (i < tokens.length) {
    const t = tokens[i];
    if (t.type === "heading_open") {
      blocks.push({ type: "h", level: Number(t.tag.slice(1)), inline: tokens[i + 1] });
      i += 3;
    } else if (t.type === "paragraph_open") {
      blocks.push({ type: "p", inline: tokens[i + 1] });
      i += 3;
    } else if (t.type === "fence" || t.type === "code_block") {
      const lang = (t.info || "").trim().toLowerCase();
      if (lang === "mermaid") blocks.push({ type: "mermaid", text: t.content });
      else blocks.push({ type: "code", lines: t.content.replace(/\n+$/, "").split("\n") });
      i += 1;
    } else if (t.type === "bullet_list_open" || t.type === "ordered_list_open") {
      const { block, next } = readList(tokens, i);
      blocks.push(block);
      i = next;
    } else if (t.type === "table_open") {
      const { block, next } = readTable(tokens, i);
      blocks.push(block);
      i = next;
    } else if (t.type === "blockquote_open") {
      const { lines, next } = readQuote(tokens, i);
      if (lines.length) blocks.push({ type: "quote", lines });
      i = next;
    } else if (t.type === "hr") {
      blocks.push({ type: "hr" });
      i += 1;
    } else {
      i += 1; // html_block and anything else we do not render
    }
  }
  return blocks;
}

// Nesting depth comes from the parser, so 2-space and 4-space styles both work.
// Anything a list item carries besides its first paragraph (code, tables, quotes,
// extra paragraphs) is collected into `extra` so it is not silently dropped.
function readList(tokens, start) {
  const ordered = tokens[start].type === "ordered_list_open";
  const first = Number((tokens[start].attrGet && tokens[start].attrGet("start")) || 1) || 1;
  const items = [];
  let depth = 0;
  let cur = null;
  let expectFirst = false;
  let i = start + 1;
  while (i < tokens.length) {
    const t = tokens[i];
    if (t.type === "bullet_list_open" || t.type === "ordered_list_open") { depth++; i++; continue; }
    if (t.type === "bullet_list_close" || t.type === "ordered_list_close") {
      if (depth === 0) { i++; break; }
      depth--;
      i++;
      continue;
    }
    if (t.type === "list_item_open") {
      cur = { inline: null, level: Math.min(depth, 2), extra: [] };
      items.push(cur);
      expectFirst = true;
      i++;
      continue;
    }
    if (t.type === "list_item_close") { cur = null; i++; continue; }
    if (t.type === "paragraph_open") {
      const inline = tokens[i + 1];
      if (expectFirst && cur && !cur.inline) { cur.inline = inline; expectFirst = false; }
      else if (cur) cur.extra.push({ type: "p", inline });
      i += 3;
      continue;
    }
    if (t.type === "fence" || t.type === "code_block") {
      const lang = (t.info || "").trim().toLowerCase();
      if (cur) cur.extra.push(lang === "mermaid"
        ? { type: "mermaid", text: t.content }
        : { type: "code", lines: t.content.replace(/\n+$/, "").split("\n") });
      i++;
      continue;
    }
    if (t.type === "table_open") {
      const r = readTable(tokens, i);
      if (cur) cur.extra.push(r.block);
      i = r.next;
      continue;
    }
    if (t.type === "blockquote_open") {
      const r = readQuote(tokens, i);
      if (cur && r.lines.length) cur.extra.push({ type: "quote", lines: r.lines });
      i = r.next;
      continue;
    }
    if (t.type === "hr") {
      if (cur) cur.extra.push({ type: "hr" });
      i++;
      continue;
    }
    i++;
  }
  return { block: { type: ordered ? "ol" : "ul", items, start: first }, next: i };
}

function readTable(tokens, start) {
  const header = [];
  const aligns = [];
  const rows = [];
  let inBody = false;
  let row = null;
  let i = start + 1;
  for (; i < tokens.length; i++) {
    const t = tokens[i];
    if (t.type === "tbody_open") inBody = true;
    else if (t.type === "tr_open") row = [];
    else if (t.type === "tr_close") { if (inBody && row) rows.push(row); row = null; }
    else if (t.type === "th_open" || t.type === "td_open") {
      const style = (t.attrGet && t.attrGet("style")) || "";
      const align = /center/.test(style) ? AlignmentType.CENTER : /right/.test(style) ? AlignmentType.RIGHT : AlignmentType.LEFT;
      const inline = tokens[i + 1];
      if (inBody) { if (row) row.push(inline); }
      else { header.push(inline); aligns.push(align); }
    } else if (t.type === "table_close") { i++; break; }
  }
  return { block: { type: "table", header, aligns, rows }, next: i };
}

function readQuote(tokens, start) {
  const lines = [];
  let i = start + 1;
  for (; i < tokens.length; i++) {
    const t = tokens[i];
    if (t.type === "inline") lines.push(t);
    else if (t.type === "blockquote_close") { i++; break; }
  }
  return { lines, next: i };
}

// Task list items keep their marker: "[ ] x" becomes a checkbox glyph.
function takeTaskMark(inline) {
  const first = inline.children && inline.children[0];
  if (!first || first.type !== "text") return "";
  const m = first.content.match(/^\[([ xX])\]\s+/);
  if (!m) return "";
  first.content = first.content.slice(m[0].length);
  return m[1].toLowerCase() === "x" ? "☒ " : "☐ ";
}

// Footnote definitions live at the end of the token stream. Lift them out so they can
// become real docx footnotes and drop the wrapper tokens from the body.
function splitFootnotes(tokens) {
  const defs = [];
  const body = [];
  let cur = null;
  for (const t of tokens) {
    if (t.type === "footnote_block_open" || t.type === "footnote_block_close") continue;
    if (t.type === "footnote_open") { cur = t.meta.id; if (!defs[cur]) defs[cur] = []; continue; }
    if (t.type === "footnote_close") { cur = null; continue; }
    if (cur !== null) {
      if (t.type === "inline") defs[cur].push(t);
      continue;
    }
    body.push(t);
  }
  return { body, defs };
}

// ---------- Images ----------
function imageSize(file) {
  const b = fs.readFileSync(file);
  if (b.length > 24 && b.readUInt32BE(0) === 0x89504e47) return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
  if (b[0] === 0xff && b[1] === 0xd8) {
    let i = 2;
    while (i + 9 < b.length) {
      if (b[i] !== 0xff) { i++; continue; }
      const marker = b[i + 1];
      const len = b.readUInt16BE(i + 2);
      if (marker >= 0xc0 && marker <= 0xcf && marker !== 0xc4 && marker !== 0xc8 && marker !== 0xcc) {
        return { w: b.readUInt16BE(i + 7), h: b.readUInt16BE(i + 5) };
      }
      i += 2 + len;
    }
  }
  return null;
}

function imageRun(token, base) {
  const src = (token.attrGet && token.attrGet("src")) || "";
  const alt = inlineText(token);
  // Relative paths resolve against the markdown file first, then the working directory.
  const file = [src, path.resolve(CURRENT_DIR, src), path.resolve(ROOT, src)]
    .find((p) => /\.(png|jpe?g)$/i.test(p) && fs.existsSync(p));
  const size = file ? imageSize(file) : null;
  if (!file || !size) {
    return new TextRun({ text: `［图片：${alt || src}］`, size: base.size, font: base.font, color: "777777" });
  }
  const width = Math.min(size.w, IMG_MAX_W);
  const height = Math.round((size.h * width) / size.w);
  return new ImageRun({
    type: /\.png$/i.test(file) ? "png" : "jpg",
    data: fs.readFileSync(file),
    transformation: { width, height },
  });
}

// ---------- Inline tokens -> runs ----------
function inlineRuns(inline, base) {
  const out = [];
  let bold = !!base.bold;
  let italics = false;
  let strike = false;
  let href = null;
  const push = (text, extra) => {
    if (!text) return;
    out.push(new TextRun({ text, size: base.size, bold, italics, strike, color: base.color, font: base.font, ...extra }));
  };
  for (const c of inline.children || []) {
    switch (c.type) {
      case "strong_open": bold = true; break;
      case "strong_close": bold = !!base.bold; break;
      case "em_open": italics = true; break;
      case "em_close": italics = false; break;
      case "s_open": strike = true; break;
      case "s_close": strike = false; break;
      case "code_inline": out.push(new TextRun({ text: c.content, size: Math.max(base.size - 3, 16), font: MONO })); break;
      case "text": push(c.content); break;
      case "softbreak": push(" "); break;
      case "hardbreak": out.push(new TextRun({ break: 1 })); break;
      case "footnote_ref": if (c.meta) out.push(new FootnoteReferenceRun(c.meta.id + 1)); break;
      case "html_inline":
        if (/^<br\s*\/?>$/i.test(c.content.trim())) out.push(new TextRun({ break: 1 }));
        break;
      case "image": out.push(imageRun(c, base)); break;
      case "link_open": href = (c.attrGet && c.attrGet("href")) || ""; break;
      case "link_close": if (href && /^https?:/i.test(href)) push(`（${href}）`); href = null; break;
      default: if (c.content) push(c.content);
    }
  }
  return out;
}

// ---------- mermaid rendering (mmdc -> PNG, cached by content hash) ----------
let mermaidFailures = 0;
function renderMermaid(code) {
  fs.mkdirSync(MERMAID_CACHE, { recursive: true });
  const hash = crypto.createHash("sha1").update(code).digest("hex").slice(0, 12);
  const png = path.join(MERMAID_CACHE, `${hash}.png`);
  if (!fs.existsSync(png)) {
    const mmd = path.join(MERMAID_CACHE, `${hash}.mmd`);
    fs.writeFileSync(mmd, code);
    const mmdc = [path.join(ROOT, "node_modules", ".bin", "mmdc"), path.join(__dirname, "..", "node_modules", ".bin", "mmdc")]
      .find((p) => fs.existsSync(p));
    const pconf = path.join(ROOT, "puppeteer-config.json");
    const args = ["-i", mmd, "-o", png, "-s", "2", "-b", "white"];
    if (fs.existsSync(pconf)) args.push("-p", pconf);
    execFileSync(mmdc, args, { stdio: "pipe" });
  }
  return png;
}
function pngSize(file) {
  const b = fs.readFileSync(file);
  return { w: b.readUInt32BE(16), h: b.readUInt32BE(20) };
}

// ---------- Blocks -> docx elements ----------
function tableBlock(b) {
  const n = b.header.length;
  const cell = (inline, c, head) => new TableCell({
    shading: head ? { type: ShadingType.CLEAR, fill: "EFEFEF" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: b.aligns[c] || AlignmentType.LEFT,
      spacing: { line: 260, lineRule: LineRuleType.AUTO, before: 20, after: 20 },
      children: inlineRuns(inline, { size: F.table, bold: head, font: SONG }),
    })],
  });
  return new Table({
    layout: TableLayoutType.AUTOFIT,
    width: { size: 100, type: WidthType.PERCENTAGE },
    borders: {
      top: { style: BorderStyle.SINGLE, size: 6, color: "666666" },
      bottom: { style: BorderStyle.SINGLE, size: 6, color: "666666" },
      left: { style: BorderStyle.SINGLE, size: 4, color: "999999" },
      right: { style: BorderStyle.SINGLE, size: 4, color: "999999" },
      insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: "999999" },
      insideVertical: { style: BorderStyle.SINGLE, size: 4, color: "999999" },
    },
    rows: [
      new TableRow({ tableHeader: true, children: b.header.map((t, c) => cell(t, c, true)) }),
      ...b.rows.map((r) => new TableRow({ children: Array.from({ length: n }, (_, c) => cell(r[c], c, false)) })),
    ],
  });
}

function toElements(blocks) {
  const out = [];
  for (const b of blocks) {
    if (b.type === "h") {
      const map = { 1: [HeadingLevel.TITLE, F.title, HEI], 2: [HeadingLevel.HEADING_1, F.h1, HEI], 3: [HeadingLevel.HEADING_2, F.h2, HEI], 4: [HeadingLevel.HEADING_3, F.h3, SONG] };
      const [level, size, font] = map[Math.min(b.level, 4)] || map[4];
      out.push(new Paragraph({
        heading: level,
        pageBreakBefore: b.level === 2 && !b.noBreak,
        spacing: { before: 240, after: 160, line: 360, lineRule: LineRuleType.AUTO },
        alignment: b.level === 1 ? AlignmentType.CENTER : AlignmentType.LEFT,
        children: inlineRuns(b.inline, { size, bold: true, font }),
      }));
    } else if (b.type === "p") {
      const text = inlineText(b.inline);
      const isCaption = /^图\s*\d+/.test(text);
      out.push(new Paragraph({
        alignment: isCaption ? AlignmentType.CENTER : AlignmentType.LEFT,
        indent: isCaption ? undefined : { firstLine: 480 },
        spacing: { line: 360, lineRule: LineRuleType.AUTO, after: isCaption ? 160 : 80 },
        children: inlineRuns(b.inline, { size: isCaption ? F.table : F.body, bold: isCaption, font: isCaption ? HEI : SONG }),
      }));
    } else if (b.type === "mermaid") {
      let png = null;
      try {
        png = renderMermaid(b.text);
      } catch (e) {
        mermaidFailures++;
        console.warn(`! mermaid render failed, falling back to a code block: ${String(e).split("\n")[0]}`);
      }
      if (png) {
        const { w, h } = pngSize(png);
        const width = Math.min(w, IMG_MAX_W);
        const height = Math.round((h * width) / w);
        out.push(new Paragraph({
          alignment: AlignmentType.CENTER,
          spacing: { before: 160, after: 60 },
          children: [new ImageRun({ type: "png", data: fs.readFileSync(png), transformation: { width, height } })],
        }));
        out.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
      } else {
        for (const l of b.text.split("\n")) out.push(new Paragraph({
          spacing: { line: 240, lineRule: LineRuleType.AUTO },
          shading: { type: ShadingType.CLEAR, fill: "F6F6F6" },
          indent: { left: 240 },
          children: [new TextRun({ text: l || " ", size: F.small, font: MONO })],
        }));
        out.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
      }
    } else if (b.type === "quote") {
      for (const line of b.lines) out.push(new Paragraph({
        indent: { left: 480 },
        spacing: { line: 300, lineRule: LineRuleType.AUTO, after: 40 },
        border: { left: { style: BorderStyle.SINGLE, size: 12, color: "AAAAAA", space: 8 } },
        children: inlineRuns(line, { size: F.table, font: KAI, color: "444444" }),
      }));
    } else if (b.type === "code") {
      b.lines.forEach((l) => out.push(new Paragraph({
        spacing: { line: 240, lineRule: LineRuleType.AUTO },
        shading: { type: ShadingType.CLEAR, fill: "F6F6F6" },
        indent: { left: 240 },
        children: [new TextRun({ text: l || " ", size: F.small, font: MONO })],
      })));
      out.push(new Paragraph({ spacing: { after: 80 }, children: [] }));
    } else if (b.type === "table") {
      out.push(tableBlock(b));
      out.push(new Paragraph({ spacing: { after: 120 }, children: [] }));
    } else if (b.type === "ul" || b.type === "ol") {
      const reference = b.type === "ul" ? "bullet" : `ordered-${b.olIndex}`;
      for (const it of b.items) {
        const mark = it.inline ? takeTaskMark(it.inline) : "";
        const runs = it.inline ? inlineRuns(it.inline, { size: F.body, font: SONG }) : [];
        out.push(new Paragraph({
          numbering: { reference, level: it.level },
          spacing: { line: 360, lineRule: LineRuleType.AUTO, after: 40 },
          children: mark ? [new TextRun({ text: mark, size: F.body, font: SONG }), ...runs] : runs,
        }));
        if (it.extra && it.extra.length) out.push(...toElements(it.extra));
      }
    } else if (b.type === "hr") {
      out.push(new Paragraph({
        border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "BBBBBB", space: 4 } },
        spacing: { before: 120, after: 120 }, children: [],
      }));
    }
  }
  return out;
}

function coverAndToc(title, docNo) {
  const line = (t, size, font, bold, before) => new Paragraph({
    alignment: AlignmentType.CENTER,
    spacing: { before: before || 120, line: 360, lineRule: LineRuleType.AUTO },
    children: [new TextRun({ text: t, size, font, bold })],
  });
  const cell = (t, head) => new TableCell({
    shading: head ? { type: ShadingType.CLEAR, fill: "EFEFEF" } : undefined,
    margins: { top: 60, bottom: 60, left: 100, right: 100 },
    children: [new Paragraph({
      alignment: AlignmentType.CENTER,
      spacing: { line: 260, lineRule: LineRuleType.AUTO },
      children: [new TextRun({ text: t, size: F.table, bold: head, font: SONG })],
    })],
  });
  return [
    line(META.project, F.h2, HEI, true, 1500),
    ...(meta.subtitle ? [line(meta.subtitle, F.h2, HEI, false, 200)] : []),
    line(title, F.title, HEI, true, 800),
    line(`文档编号：${docNo}    版本：${META.version}`, F.body, KAI, false, 600),
    line(`编制单位：${META.org}`, F.body, KAI, false, 100),
    ...(meta.contract ? [line(`合同编号：${META.contract}`, F.body, KAI, false, 100)] : []),
    line(`编制日期：${META.date}`, F.body, KAI, false, 100),
    new Paragraph({ spacing: { before: 500 }, children: [] }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 200, after: 120 },
      children: [new TextRun({ text: "编  制：＿＿＿＿＿＿＿＿        审  核：＿＿＿＿＿＿＿＿", size: F.body, font: KAI })],
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 120 },
      children: [new TextRun({ text: "批  准：＿＿＿＿＿＿＿＿        日  期：＿＿＿＿＿＿＿＿", size: F.body, font: KAI })],
    }),
    new Paragraph({ children: [new PageBreak()] }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 200, after: 200 },
      children: [new TextRun({ text: "版本修订记录", size: F.h1, font: HEI, bold: true })],
    }),
    new Table({
      layout: TableLayoutType.AUTOFIT,
      width: { size: 100, type: WidthType.PERCENTAGE },
      borders: {
        top: { style: BorderStyle.SINGLE, size: 6, color: "666666" },
        bottom: { style: BorderStyle.SINGLE, size: 6, color: "666666" },
        left: { style: BorderStyle.SINGLE, size: 4, color: "999999" },
        right: { style: BorderStyle.SINGLE, size: 4, color: "999999" },
        insideHorizontal: { style: BorderStyle.SINGLE, size: 4, color: "999999" },
        insideVertical: { style: BorderStyle.SINGLE, size: 4, color: "999999" },
      },
      rows: [
        new TableRow({ tableHeader: true, children: ["版本", "日期", "修订人", "修订内容"].map((t) => cell(t, true)) }),
        new TableRow({ children: [cell(META.version, false), cell(META.date, false), cell("", false), cell("初稿发布", false)] }),
        new TableRow({ children: [cell("", false), cell("", false), cell("", false), cell("", false)] }),
      ],
    }),
    new Paragraph({ children: [new PageBreak()] }),
    new Paragraph({
      alignment: AlignmentType.CENTER, spacing: { before: 240, after: 240 },
      children: [new TextRun({ text: "目  录", size: F.h1, font: HEI, bold: true })],
    }),
    new TableOfContents("目录", { hyperlink: true, headingStyleRange: "1-3" }),
    new Paragraph({ children: [new PageBreak()] }),
  ];
}

async function convert(file) {
  const name = path.basename(file, ".md");
  CURRENT_DIR = path.dirname(path.resolve(file));
  // Drop a leading YAML frontmatter block: it is metadata, not document content.
  let lines = fs.readFileSync(file, "utf8").split(/\r?\n/);
  if (/^---\s*$/.test(lines[0] || "")) {
    const end = lines.findIndex((l, i) => i > 0 && /^---\s*$/.test(l));
    if (end > 0) lines = lines.slice(end + 1);
  }
  const tokens = md.parse(lines.join("\n"), {});

  // The first level-1 heading becomes the cover title and is removed from the body.
  let title = name;
  const h1 = tokens.findIndex((t) => t.type === "heading_open" && t.tag === "h1");
  if (h1 !== -1 && tokens[h1 + 1]) {
    title = inlineText(tokens[h1 + 1]).trim() || name;
    tokens.splice(h1, 3);
  }

  const { body: bodyTokens, defs: footnoteDefs } = splitFootnotes(tokens);
  const blocks = blocksFrom(bodyTokens);
  // The cover consumes the first heading, so a document that opens with an intro
  // paragraph would otherwise get a page holding two lines. Keep that intro on the
  // same page as the chapter heading that follows it.
  const firstChapter = blocks.findIndex((b) => b.type === "h" && b.level === 2);
  if (firstChapter > 0 && blocks.slice(0, firstChapter).every((b) => b.type === "p")) {
    const introChars = blocks.slice(0, firstChapter).reduce((n, b) => n + inlineText(b.inline).length, 0);
    if (introChars <= 600) blocks[firstChapter].noBreak = true;
  }

  const ols = blocks.filter((b) => b.type === "ol");
  ols.forEach((b, idx) => { b.olIndex = idx; });
  const olCount = ols.length;

  // Document number: doc-meta.json docNo, else the filename's leading digits, else a blank rule
  const nameNum = name.match(/^(\d+)/);
  const docNo = meta.docNo || (nameNum ? `DOC-${nameNum[1].padStart(2, "0")}` : "＿＿＿＿＿＿");

  const footnotes = {};
  footnoteDefs.forEach((inlines, id) => {
    footnotes[id + 1] = { children: inlines.map((inline) => new Paragraph({
      spacing: { line: 240, lineRule: LineRuleType.AUTO },
      children: inlineRuns(inline, { size: F.small, font: SONG }),
    })) };
  });

  const doc = new Document({
    ...(Object.keys(footnotes).length ? { footnotes } : {}),
    numbering: {
      config: [
        { reference: "bullet", levels: [
          { level: 0, format: LevelFormat.BULLET, text: "\u2022", style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
          { level: 1, format: LevelFormat.BULLET, text: "\u25e6", style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
          { level: 2, format: LevelFormat.BULLET, text: "\u25aa", style: { paragraph: { indent: { left: 2160, hanging: 360 } } } },
        ] },
        // One numbering instance per ordered list, so every list restarts where it starts.
        ...ols.map((b, k) => ({
          reference: `ordered-${k}`,
          levels: [
            { level: 0, start: b.start || 1, format: LevelFormat.DECIMAL, text: "%1.", style: { paragraph: { indent: { left: 720, hanging: 360 } } } },
            { level: 1, format: LevelFormat.DECIMAL, text: "%1.%2", style: { paragraph: { indent: { left: 1440, hanging: 360 } } } },
            { level: 2, format: LevelFormat.DECIMAL, text: "%1.%2.%3", style: { paragraph: { indent: { left: 2160, hanging: 360 } } } },
          ],
        })),
      ],
    },
    styles: {
      default: { document: { run: { font: SONG, size: F.body } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: HEI, size: F.h1, bold: true } },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: HEI, size: F.h2, bold: true } },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, run: { font: SONG, size: F.h3, bold: true } },
      ],
    },
    sections: [{
      properties: { page: { margin: { top: 1418, bottom: 1418, left: 1587, right: 1587 } }, titlePage: true },
      headers: {
        default: new Header({ children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          border: { bottom: { style: BorderStyle.SINGLE, size: 4, color: "999999", space: 2 } },
          children: [new TextRun({ text: meta.project ? `${META.project}　·　${title}` : title, size: F.small, font: SONG, color: "555555" })],
        })] }),
        first: new Header({ children: [] }),
      },
      footers: {
        default: new Footer({ children: [new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            new TextRun({ text: "第 ", size: F.small, font: SONG }),
            new TextRun({ children: [PageNumber.CURRENT], size: F.small, font: SONG }),
            new TextRun({ text: " 页　共 ", size: F.small, font: SONG }),
            new TextRun({ children: [PageNumber.TOTAL_PAGES], size: F.small, font: SONG }),
            new TextRun({ text: " 页", size: F.small, font: SONG }),
          ],
        })] }),
        first: new Footer({ children: [] }),
      },
      children: [...coverAndToc(title, docNo), ...toElements(blocks)],
    }],
  });

  const buf = await Packer.toBuffer(doc);
  const outPath = path.join(OUT, `${name}.docx`);
  fs.writeFileSync(outPath, buf);
  console.log(`✓ ${path.relative(ROOT, outPath)} (${(buf.length / 1024).toFixed(0)} KB)`);
}

(async () => {
  if (argOpts.clearCache) {
    fs.rmSync(MERMAID_CACHE, { recursive: true, force: true });
    console.log(`✓ cleared ${path.relative(ROOT, MERMAID_CACHE) || MERMAID_CACHE}`);
    if (!argInputs.length) return;
  }
  fs.mkdirSync(OUT, { recursive: true });
  const files = argInputs.length
    ? argInputs.flatMap((f) => fs.statSync(f).isDirectory()
        ? fs.readdirSync(f).filter((x) => x.endsWith(".md")).sort().map((x) => path.join(f, x))
        : [path.resolve(f)])
    : fs.readdirSync(SRC).filter((f) => f.endsWith(".md")).sort().map((f) => path.join(SRC, f));
  for (const f of files) await convert(f);
  if (mermaidFailures) {
    console.warn(`! ${mermaidFailures} mermaid block(s) fell back to code blocks. Check that @mermaid-js/mermaid-cli is installed and that a Chrome build is reachable (puppeteer-config.json).`);
    process.exitCode = 2;
  }
})().catch((e) => { console.error(e); process.exit(1); });
