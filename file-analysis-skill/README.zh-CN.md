# file-analysis-skill

[English](README.md) | 中文

`file-analysis-skill` 用于只读分析本地目录：统计一级文件和子目录的递归总大小、文件数量，打印按大小排序的表格，并导出适合 Excel 打开的 UTF-8 CSV 报告。

## 功能

- 只读取本地文件系统，不修改被分析文件
- 统计一级子目录下所有普通文件的递归总大小和数量
- 终端输出人类可读表格，并按总大小从大到小排序
- 使用带 BOM 的 UTF-8 CSV，方便 Excel 识别中文
- 支持自定义输入目录和 CSV 输出路径
- 对路径不存在或不是目录给出明确错误

## 依赖

- Python 3.10 或更高版本
- 不需要第三方 Python 包

## 安装为 Skill

将 `file-analysis-skill` 目录复制或链接到智能体运行时使用的 Skill 搜索目录，保持目录结构完整，确保运行时可以读取 `SKILL.md`。

Skill 标识为 `file-analysis-skill`。

## 使用

分析指定目录，默认在当前工作目录生成 `analysis_result.csv`：

```bash
python <skill-dir>/scripts/analyze_top_level.py <workspace>/media
```

指定 CSV 输出位置：

```bash
python <skill-dir>/scripts/analyze_top_level.py <workspace>/media \
  --csv <workspace>/reports/media-analysis.csv
```

CSV 第一列是每个一级文件或目录的名称，来自文件系统目录项本身，不读取输入 CSV 的文件名，也不会因为源 CSV 某个字段为空而留空。

## CSV 列

| 列 | 含义 |
| --- | --- |
| `Name` | 一级文件或目录名称 |
| `Type` | `file` 或 `dir` |
| `Total Size (Bytes)` | 精确字节数 |
| `Total Size` | 人类可读的大小 |
| `File Count` | 文件为 `1`，目录为递归普通文件数量 |
