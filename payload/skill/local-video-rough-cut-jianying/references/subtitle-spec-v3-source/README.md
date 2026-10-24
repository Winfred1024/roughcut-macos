# subtitle-spec-v3-source

字幕呈现规范 v3 的原始提取脚本与中间数据。**不是出片时读的东西**——出片看
`references\字幕呈现规范_v3.md`（正文）和 `references\subtitle-presets-v3.json`（5 套预设）。

放在这里是为了：规则要改、样本要加工程时，不用从零再写一遍提取与统计。

## 文件

| 文件 | 作用 |
|---|---|
| `extract_segments.py` | 从剪映草稿的 `Timelines/<ID>/template.json`（明文快照）里抽出每条字幕的样式与动画字段，输出 `extract\segments.json` / `.csv` |
| `analyze.py` | 主统计：字号分布、颜色、断句字数、CPS、语义角色、动画频次；内置 `TYPE_MAP`（草稿+时间线 → 8 类台本） |
| `analyze2.py` | 分区统计（底部字幕区 / 中部信息区 / 顶部标题区）、逐类型分区分布 |
| `prepare_doc_data.py` | 把统计结果压缩成 `doc_data.json`（文档里每张表的数据源） |
| `build_docx.py` | 用 `doc_data.json` 生成 `剪映字幕呈现规范_v3.docx`（正文在上层目录，改名加了 `_v3`） |
| `extract\segments.csv` | **1,157 条字幕逐条明细**（38 列，含字号/颜色/描边/X/Y/缩放/动画/画布）——`subtitle-style-details-v3.xlsx` 的「样式明细」表就是它 |
| `extract\segments.json` | 同上的 JSON 版（脚本的输入） |
| `extract\report.json` / `report2.json` / `overview.json` / `drafts.json` | 各级统计快照（类型 / 工程 / 时间线 / 语义 / 颜色 / 动画） |
| `extract\doc_data.json` | 文档渲染用的聚合数据 |

## 重跑前要改的路径

三个脚本里写死了上一台机器的路径，换机后先改这两处：

- `D:\草稿\JianyingPro Drafts` —— 剪映草稿根目录（本机见 `references\env-and-pitfalls.md` 第 1 节路径表，现在是 `E:\草稿\JianyingPro Drafts`）
- `D:\字幕模版获取\extract` —— 本包 `extract\` 的绝对路径

`TYPE_MAP` 里的 `(草稿名, 时间线GUID)` 键，换成新工程的组合即可；不认识的键会落到「未分类」。

## 样本口径

- 14 个工程 / 24 条时间线 / 1,157 条字幕片段（含字幕轨 1,051、文本轨 88、花字轨 18）
- 全部属于服装工厂 / 女装实体店垂类，跨行业需要重新校准字号与颜色
- 字号是剪映相对单位；`y` 是 `clip.transform.y`，画面纵向位置 = 50% + y×50%
