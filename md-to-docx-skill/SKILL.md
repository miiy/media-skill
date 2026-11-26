---
name: md-to-docx-skill
description: 通用中文 Word 文档生产线：markdown 源稿转排版规范的 docx（封面、目录域、页眉页脚、宋体小四正文、黑体标题、表格自动宽度、mermaid 图嵌入），排版规范可调。凡用户要求「写 Word / 转 Word / 生成 docx / 排版 / 整理成正式文档」，或要把 markdown 变成任何中文 Word 文档时，使用本技能；要顺带出 PDF 时用本技能自带的 LibreOffice 转换脚本。
compatibility: node ≥18、npm（docx、markdown-it、markdown-it-footnote、@mermaid-js/mermaid-cli；mermaid 渲染需系统 Chrome）
---

# md-to-docx-skill

源稿始终是 markdown（好 diff 好维护），排版规范内置在转换器里，定稿一键转 docx；docx 是主产物，PDF 是可选收尾。排版默认值是中文正式文档的通用规范，可按用户要求调整（字号、边距、是否带封面等，直接改 `<skill-dir>/scripts/md2docx.js` 顶部常量或告知用户改法）。

## 工作流

1. **写源稿**：标题用 `#`/`##`/`###` 层级；表格用标准 md 表格；代码块围栏（允许缩进，列表里也能用）；图用 mermaid 块（渲染成 PNG），静态图用 `![说明](相对路径.png|jpg)`；图题单独一行写在图下方（以「图 N」开头会自动转图题样式）。文件开头的 YAML frontmatter 会自动丢弃，不会串进正文。可变信息（项目名 / 单位 / 日期等）不写死，放 `doc-meta.json`。
2. **转 docx**：
   ```bash
   # 首次：先设镜像源，再装依赖
   npm config set registry https://registry.npmmirror.com
   npm install docx markdown-it markdown-it-footnote @mermaid-js/mermaid-cli

   node <skill-dir>/scripts/md2docx.js [源目录|md文件...] [-o 输出目录] [-m 元信息json]
   ```
   默认读 `./docs`（无则当前目录）全部 .md，输出到 `./docx-out`；每个 md 生成一份独立 docx。
3. **校验**：`node <skill-dir>/tests/smoke.test.js` 跑冒烟测试（8 项断言：封面、frontmatter、斜体/删除线、嵌套列表、任务项、起始编号、图片、脚注）；手工检查用 `unzip -l out.docx | grep media` 看图、`pandoc -t markdown out.docx | head` 看内容；让用户在 Word 里翻版式并 **F9 刷新目录域**（域机制，不刷没有页码，提前告知）。
4. **清理缓存**：mermaid 图按内容哈希缓存在工作区 `.md2docx-cache/`，需要时 `node <skill-dir>/scripts/md2docx.js --clear-cache`。

## doc-meta.json

```json
{ "project": "项目名称", "org": "编制单位", "contract": "合同编号", "docNo": "文档编号", "date": "2026-11-19", "version": "V1.0" }
```
`subtitle`（封面副标题）、`contract`（合同编号）为可选项，不填则封面不显示该行。`docNo` 缺省时用文件名前导数字生成 `DOC-NN`，没有前导数字则留横线；`project`/`org`/`date`/`version` 缺省时同样以横线占位。回填后重跑即全量替换（封面、页眉、修订记录表）。

## 内置排版

A4、上下 2.5cm 左右 2.8cm；正文宋体小四 1.5 倍行距首行缩进 2 字符；标题黑体（一级三号分页起章、二级四号）；表格五号、表头灰底、**自动列宽**（autofit + 通栏）；代码块 Consolas 小五灰底；引用块楷体左线；页眉「项目名·文档名」（无项目名时只显示文档名）、页脚「第 X 页 共 Y 页」；封面（含签字栏）+ 版本修订记录页 + 目录域；mermaid 块渲染 PNG 居中嵌入（内容哈希缓存，失败自动降级为代码块）。详细排版规范见 `references/format-spec.md`。

## 实现要点

- **mermaid 渲染**：调 `mmdc` 把 mermaid 块转 PNG；运行目录有 `puppeteer-config.json` 时透传给 `mmdc`，检测到系统 Chrome 会自动生成该文件指向它。渲染失败自动降级为代码块，不中断出稿。
- **脚注**：`[^a]` + `[^a]: 正文` 由 `markdown-it-footnote` 解析，输出为 docx 真脚注（页底、自动编号）。
- **解析交给 markdown-it**：标题、段落、嵌套列表、任务项 `- [ ]`、表格、引用、代码围栏、行内（粗体 / 斜体 / 删除线 / 行内代码 / 链接 / 图片 / `<br>`）都由 `md.parse()` 出 token，本脚本只做 token → docx 映射；改语法支持时优先加 markdown-it 插件而不是改解析器。
- **分页**：每个 `##` 另起一页；但如果正文开头只有一小段引言（≤600 字）就紧跟第一章，第一章不再强制分页，避免目录后出现只剩两行的空白页。
- **列表层级**：层级来自解析器的嵌套深度（无序 `•/◦/▪`，有序 `1./1.1/1.1.1`）；每个有序列表用独立编号实例，跨列表不会连号；超过三级的缩进合并到第三级。
- **图片**：`![说明](路径)` 支持 PNG/JPEG，相对路径先按 md 所在目录找、再按工作目录找，超过版心宽（580px）等比缩到版心宽；找不到或格式不支持时退化为 `［图片：说明］` 文本。
- **docx-js 表格**：`layout: TableLayoutType.AUTOFIT` + 表级百分比宽度，**不要**给单元格写死 DXA 列宽（自动宽度是用户的普遍偏好）。
- **目录域**：依赖内置 HeadingLevel；Word 打开后 F9 才有页码。
- **docx-js 细节**：页码用 `PageNumber.CURRENT`/`TOTAL_PAGES` 的 children 形式；`PageBreak` 必须包在 Paragraph 里；换行用多个 Paragraph 不用 `\n`；`ImageRun` 必须带 `type: "png"`，图片按版心宽（580px@96dpi）等比缩放，PNG 尺寸直接读 IHDR 字节免装依赖。
- **docx→PDF 没有纯 npm 渲染器**：`docx2pdf`/`libreoffice-convert` 等包都是 Word/LibreOffice 的壳。用户要 PDF 时：系统是 Word 就让用户打开另存（先 F9）；装了 LibreOffice 则 `bash <skill-dir>/scripts/docx2pdf.sh <docx目录> -o <pdf目录>`。

## 排错

- **PDF 里目录没有页码**：目录是 Word 域，LibreOffice 导出不会更新。要么先在 Word 里 F9 再另存 PDF，要么接受 PDF 目录只有点线。
- **PDF 里中文变方框**：docx 指定的是 `宋体/黑体/楷体`，系统没有这些字体会被替换成无中日韩字形的字体。给 LibreOffice 指定一份包含系统字体目录的 `fonts.conf`（`FONTCONFIG_FILE=... bash scripts/docx2pdf.sh ...`），或让用户在 Word 里另存。
- **mermaid 没渲染出来**：会打印 `! mermaid render failed` 并在结束时汇总、退出码 2（docx 仍然生成，图退化为代码块）。先确认 `@mermaid-js/mermaid-cli` 与 Chrome 可用；受限环境（容器/沙箱）里 Chrome 需要 `--no-sandbox`，在运行目录的 `puppeteer-config.json` 里补 `"args": ["--no-sandbox"]`。
- **`docx2pdf.sh`**：默认跳过已存在的 PDF，加 `--overwrite` 才覆盖；输出 `converted N, skipped M, failed K`，有失败时退出码非零。

## 通用写作要点

- 图题在图下、表题在表上（表格如需编号标题，在表前写「表 N　…」行）。
- 单文档篇幅估算：字符数 ÷ 900 + 3 页前置（封面/修订/目录）；表格代码密集的文档上浮 20–40%。
