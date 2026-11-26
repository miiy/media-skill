# md-to-docx-skill

[English](README.md) | 中文

把 markdown 源稿转成中文 Word 正式文档，排版规范内置且可调：封面、目录域、页眉页脚、宋体小四 1.5 倍行距正文、黑体标题、表格自动列宽、mermaid 图嵌入。docx 是主产物，PDF 是可选的收尾一步。

## 依赖

Node.js 18+ 与 npm。转换器依赖 `docx`、`markdown-it` 与 `@mermaid-js/mermaid-cli`，mermaid 渲染还需系统 Chrome。markdown 解析交给 markdown-it，嵌套列表、表格、图片、任务项这些都由库负责，脚本只做 token → docx 映射。

先设一次镜像源，再装依赖：

```bash
cd <skill-dir>
npm config set registry https://registry.npmmirror.com
npm install docx markdown-it markdown-it-footnote @mermaid-js/mermaid-cli
```

依赖装一次即可；之后从用户工作区运行，源稿与输出都留在工作区，技能目录只读。

## 使用

```bash
node <skill-dir>/scripts/md2docx.js [源目录|md文件...] [-o <输出目录>] [-m <元信息json>]
```

不带路径时读取 `./docs` 下全部 `.md`（没有则读当前目录），每份 md 生成一份 docx，输出到 `./docx-out`。

项目相关的可变信息（项目名、单位、合同号、日期、版本）放 `doc-meta.json`，同一份源稿可以按项目重复出稿：

```json
{ "project": "项目名称", "org": "编制单位", "contract": "合同编号", "docNo": "文档编号", "date": "2026-11-19", "version": "V1.0" }
```

`subtitle`、`contract` 为可选项，不填则封面不显示该行；其余缺字段渲染为下划线占位，回填后重跑即全量替换封面、页眉、修订记录表。

## 校验

```bash
unzip -l out.docx | grep media     # 图片已嵌入
pandoc -t markdown out.docx | head # 内容完整
```

提醒用户在 Word 里按 F9 刷新目录域——页码来自域，不刷就没有。LibreOffice 导 PDF 不会更新域，所以 `docx2pdf.sh` 出的 PDF 目录没有页码。

## 测试

```bash
cd <skill-dir> && npm install docx markdown-it markdown-it-footnote @mermaid-js/mermaid-cli
node tests/smoke.test.js
```

8 项断言：封面信息、frontmatter 剥离、斜体/删除线、嵌套列表层级、任务项、有序列表起始号、图片嵌入、真脚注。图片用脚本内生成的 PNG，不需要二进制测试数据。

## 常见坑

- 表格宽度保持自动（`TableLayoutType.AUTOFIT` + 表级百分比宽度），不要给单元格写死 DXA 列宽。
- `PageBreak` 必须包在 `Paragraph` 里；换行用多个 Paragraph 而不是 `\n`；`ImageRun` 要带 `type: "png"`。
- 没有纯 npm 的 docx→PDF 渲染器。让用户在 Word 里 F9 后另存，或装了 LibreOffice 时用 `bash <skill-dir>/scripts/docx2pdf.sh`。

## 文件

- [`SKILL.md`](SKILL.md)：运行时指令本体。
- [`references/format-spec.md`](references/format-spec.md)：默认排版规范与字号速查。
- `scripts/md2docx.js`（`--clear-cache` 清 mermaid 缓存）、`scripts/docx2pdf.sh`（`--overwrite` 覆盖已有 PDF）。
- `tests/smoke.test.js`。
- [`evals/evals.json`](evals/evals.json)：示例任务与预期结果。
