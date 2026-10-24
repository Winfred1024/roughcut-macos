# 文字轨必须是剪映「字幕」（不是「文本」）

这份文件解决一个交付级问题：自动粗剪出来的草稿，用户选中字幕后**只能看到「文本」面板**（基础 / 气泡 / 花字 + 单条样式），
看不到剪映的「字幕」面板（字幕 1..N 列表 + 搜索字幕 + 朗读 + 数字人 + 整体样式修改）。用户要批量改字幕样式时只能一条条点。

## 1. 判定依据：素材的 `type`

剪映专业版按 `draft_content.json` → `materials.texts[i].type` 决定给哪个面板（11.6.0 实测）：

| 素材 `type` | 选中时左侧面板 | 典型来源 |
|---|---|---|
| `"text"` | 「文本」：基础 / 气泡 / 花字 + 字体 / 字号 / 样式 / 颜色 / 字间距 / 行间距 | 手动添加的文字、`TextStyle()` 默认导出 |
| `"subtitle"` | 「字幕」：**字幕 1..N 列表**、搜索字幕、朗读、数字人、整段样式 | 剪映「识别字幕」/ 导入 srt |

`pyJianYingDraft` 里这个开关是 `TextStyle.auto_wrapping`（`text_segment.py` 中 `"type": "subtitle" if self.style.auto_wrapping else "text"`）。
所以**光把轨道命名成「字幕」没用**，必须让素材本身是 subtitle 型。

## 2. `type="subtitle"` 还不够：补齐「识别字幕」的伴生字段

本机从 15 个剪映工程的明文 `template.json` 里反查到剪映自己「识别字幕」素材的真实结构（124 条 subtitle 素材抽样），
除 `type` 外还有：

| 字段 | 值 | 作用 |
|---|---|---|
| `add_type` | `1` | 标记「自动添加的字幕」 |
| `group_id` | `"Auto_<毫秒时间戳>"` | **同一次识别出来的字幕共用一个 group_id**，面板按组列出成一条列表 |
| `recognize_text` | 该条字幕原文 | 字幕编辑框回显 |
| `words` | `{"start_time": [...], "end_time": [...], "text": [...]}` | 逐字时间（毫秒、相对片段头），用于卡拉 OK 式高亮 |
| `text_color` / `font_size` | `"#FFFFFF"` / 整数 | 面板顶部色块与字号回显 |
| `check_flag` / `line_spacing` / `initial_scale` / `layer_weight` / `border_width` | `39` / `0.02` / `1` / `1` / `0.08` | 渲染标记 |
| `caption_template_info` / `lyrics_template` / `combo_info` / `current_words` / `subtitle_keywords` | 空壳（`{"path": "", "resource_id": ""}` 或 `{}`） | 字幕专用槽位 |

`words.text` 直接拼接必须**原样等于** `content.text`（含空格），否则剪映还原字幕文本会对不上。

## 3. 用法：`scripts/subtitle_module.py`

生成期（推荐）：

```python
import sys
sys.path.insert(0, r"C:\Users\lr286\.agents\skills\local-video-rough-cut-jianying\scripts")
import pyJianYingDraft as draft
from subtitle_module import SUBTITLE_TRACK, promote_draft_to_subtitles, subtitle_style, verify_subtitle_draft

script.append_tracks([draft.TrackSpec(draft.TrackType.video, "视频"),
                      draft.TrackSpec(draft.TrackType.text, SUBTITLE_TRACK)])
style = subtitle_style(size=11, align=1, max_line_width=0.82)   # 内部就是 auto_wrapping=True
script.add_segment(draft.TextSegment(text, trange(...), style=style,
                                     clip_settings=draft.ClipSettings(transform_y=-0.34)), SUBTITLE_TRACK)
script.save()

rep = promote_draft_to_subtitles(draft_dir)     # 补 add_type/group_id/recognize_text/words + 自动换行
print(rep.as_dict())
assert verify_subtitle_draft(draft_dir)["ok"]
```

已有明文草稿补刀：

```powershell
& E:\auto_cut\tools\jyenv\Scripts\python.exe `
  C:\Users\lr286\.agents\skills\local-video-rough-cut-jianying\scripts\subtitle_module.py `
  "E:\草稿\JianyingPro Drafts\<草稿名>"
& ...\subtitle_module.py "E:\草稿\JianyingPro Drafts\<草稿名>" --verify
```

常用参数：`--group-id`（固定字幕组 id）、`--all-text-tracks`（连非「字幕」轨的文本一起升级）、
`--keep-track-names`、`--line-max-width 0.82`、`--no-line-wrap`、`--dry-run`、`--verify`。

## 4. 硬限制

- 只能改**明文** `draft_content.json`。剪映打开过（或存过）的草稿是密文，模块会直接报错——只能用原生成脚本重新生成，再在打开剪映之前跑。
- 生成后不要先开剪映再补字段：顺序必须是 `script.save()` → `promote_draft_to_subtitles()` → 交付。
- 本模块不改轨道数量与样式（字号 / 颜色 / 行内分段强调）——那些仍按 `subtitle-presentation-spec.md` 走。

## 5. 自查清单

- [ ] `python subtitle_module.py <草稿目录> --verify` 输出 `"ok": true`；
- [ ] 所有文字素材 `type = "subtitle"`；
- [ ] `group_id` 全片一个值，形如 `Auto_1792573624065`；
- [ ] 每条都有 `recognize_text` 和 `words`，且 `"".join(words.text)` 等于原文；
- [ ] `force_apply_line_max_width = true`、`line_feed = 1`、`line_max_width = 0.82`；
- [ ] 在剪映里选中任一字幕，左侧是「字幕」面板且能看到 N 条列表（这一步只能人工目检，脚本不做承诺）。

## 6. 实测记录（2026-10-21）

- 反查样本：`E:\草稿\JianyingPro Drafts\9月10日\Timelines\*\template.json`（明文，139 条文本素材：124 subtitle + 15 text）。
- 同一工程里 text 型素材（手动添加的红色标题）无 `add_type/group_id/recognize_*`，与 subtitle 型字段差异即上表。
- `10月5日_气口粗剪_可精剪` 的明文 load 备份显示：`auto_wrapping=True` 产出的素材已是 `type="subtitle"`，剪映能正常加载、继续编辑、保存，说明该类型不会破坏草稿。
