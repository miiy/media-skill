# Chinese Word Typography Spec

> Common conventions for formal Chinese documents. When a user or project specifies
> a different format, follow that instead — the defaults live in the constants at the
> top of `scripts/md2docx.js`.

## Typography

| Item | Requirement |
| --- | --- |
| Paper / orientation | A4 portrait; landscape pages for wide tables |
| Margins | 2.5 cm top and bottom, 2.8–3.0 cm left and right (binding edge slightly wider) |
| Body text | SimSun (宋体) or FangSong_GB2312 (仿宋), 12 pt, Times New Roman for Latin text; 1.5 line spacing, first line indented 2 characters |
| Heading levels | Level 1: SimHei (黑体) 16 pt, centered; level 2: 14 pt SimHei; level 3: 12 pt SimSun, bold |
| Tables | SimSun 10.5 pt, header row bold and centered; every table numbered and titled above it (`表 1`) |
| Figures | Every figure numbered and titled below it (`图 1`); screenshots complete and clear, with explanatory text |
| Header | Project name + document name, 9 pt |
| Footer | Page numbers centered (`第 X 页 共 Y 页`), 9 pt |
| Cover | Project name, document name, document number, version, authoring organization, date, signature blocks |
| Front matter | Revision history table (version / date / reviewer / change), table of contents (Word field, 3 levels) |
| Numbers and units | Versions as `V1.0`; dates as `2026-11-17`; consistent size units (GB/MB) |

Size names follow Word's Chinese naming (`小四` = 12 pt, `三号` = 16 pt, `五号` = 10.5 pt,
`小五` = 9 pt); the converter stores them as half-point values.
