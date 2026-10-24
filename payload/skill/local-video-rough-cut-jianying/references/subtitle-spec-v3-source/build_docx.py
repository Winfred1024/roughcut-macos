# -*- coding: utf-8 -*-
"""Build the subtitle-spec DOCX from extracted JianyingPro draft data."""
import json
from docx import Document
from docx.shared import Pt, Cm, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT, WD_ALIGN_VERTICAL
from docx.oxml.ns import qn
from docx.oxml import OxmlElement

NAVY = RGBColor(0x1F, 0x38, 0x64)
BLUE = RGBColor(0x2E, 0x5C, 0x8A)
GREY = RGBColor(0x59, 0x59, 0x59)
AMBER = RGBColor(0xB4, 0x53, 0x0A)
WHITE = RGBColor(0xFF, 0xFF, 0xFF)
BODY_FONT = "微软雅黑"

doc = Document()

# ---------- page setup ----------
sec = doc.sections[0]
sec.page_width, sec.page_height = Cm(21.0), Cm(29.7)
sec.top_margin, sec.bottom_margin = Cm(2.2), Cm(2.0)
sec.left_margin, sec.right_margin = Cm(2.4), Cm(2.2)
sec.different_first_page_header_footer = True

# ---------- base styles ----------
normal = doc.styles["Normal"]
normal.font.name = BODY_FONT
normal.font.size = Pt(10.5)
normal.font.color.rgb = RGBColor(0x26, 0x26, 0x26)
normal.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
normal.paragraph_format.space_after = Pt(4)
normal.paragraph_format.line_spacing = 1.32

for name, size, color, before, after in [
    ("Heading 1", 16, NAVY, 20, 8),
    ("Heading 2", 12.5, BLUE, 14, 5),
    ("Heading 3", 11, RGBColor(0x33, 0x33, 0x33), 10, 3),
]:
    st = doc.styles[name]
    st.font.name = BODY_FONT
    st.font.size = Pt(size)
    st.font.bold = True
    st.font.color.rgb = color
    st.element.rPr.rFonts.set(qn("w:eastAsia"), BODY_FONT)
    st.paragraph_format.space_before = Pt(before)
    st.paragraph_format.space_after = Pt(after)
    st.paragraph_format.keep_with_next = True


def run_font(run, size=None, bold=None, color=None, name=BODY_FONT):
    run.font.name = name
    run._element.rPr.rFonts.set(qn("w:eastAsia"), name)
    if size:
        run.font.size = Pt(size)
    if bold is not None:
        run.font.bold = bold
    if color is not None:
        run.font.color.rgb = color
    return run


def para(text="", size=10.5, bold=False, color=None, align=None,
         before=0, after=4, indent=None, spacing=1.32):
    p = doc.add_paragraph()
    if text:
        run_font(p.add_run(text), size, bold, color)
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = spacing
    if align is not None:
        p.alignment = align
    if indent is not None:
        pf.left_indent = Cm(indent)
    return p


def rich(parts, size=10.5, before=0, after=4, indent=None, spacing=1.32):
    """parts: list of (text, bold, color) tuples."""
    p = doc.add_paragraph()
    for text, bold, color in parts:
        run_font(p.add_run(text), size, bold, color)
    pf = p.paragraph_format
    pf.space_before = Pt(before)
    pf.space_after = Pt(after)
    pf.line_spacing = spacing
    if indent is not None:
        pf.left_indent = Cm(indent)
    return p


def bullet(parts, size=10.5, level=0):
    if isinstance(parts, str):
        parts = [(parts, False, None)]
    p = doc.add_paragraph(style="List Bullet")
    for text, bold, color in parts:
        run_font(p.add_run(text), size, bold, color)
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(2.5)
    pf.line_spacing = 1.28
    pf.left_indent = Cm(0.75 + 0.55 * level)
    pf.first_line_indent = Cm(-0.35)
    return p


def numbered(parts, size=10.5):
    if isinstance(parts, str):
        parts = [(parts, False, None)]
    p = doc.add_paragraph(style="List Number")
    for text, bold, color in parts:
        run_font(p.add_run(text), size, bold, color)
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(2.5)
    pf.left_indent = Cm(0.85)
    pf.first_line_indent = Cm(-0.4)
    return p


def num_item(n, parts, size=10.5):
    """Manually numbered list item (avoids Word list continuation across sections)."""
    if isinstance(parts, str):
        parts = [(parts, False, None)]
    p = doc.add_paragraph()
    pf = p.paragraph_format
    pf.space_before = Pt(0)
    pf.space_after = Pt(3)
    pf.left_indent = Cm(0.85)
    pf.first_line_indent = Cm(-0.55)
    pf.line_spacing = 1.3
    run_font(p.add_run(f"{n}.  "), size, True, NAVY)
    for text, bold, color in parts:
        run_font(p.add_run(text), size, bold, color)
    return p


def shade(cell, hex_fill):
    tcPr = cell._tc.get_or_add_tcPr()
    shd = OxmlElement("w:shd")
    shd.set(qn("w:val"), "clear")
    shd.set(qn("w:color"), "auto")
    shd.set(qn("w:fill"), hex_fill)
    tcPr.append(shd)


def cell_margins(table, top=60, bottom=60, left=90, right=90):
    tblPr = table._tbl.tblPr
    mar = OxmlElement("w:tblCellMar")
    for tag, val in (("top", top), ("bottom", bottom), ("left", left), ("right", right)):
        el = OxmlElement(f"w:{tag}")
        el.set(qn("w:w"), str(val))
        el.set(qn("w:type"), "dxa")
        mar.append(el)
    tblPr.append(mar)


def repeat_header(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:tblHeader")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def no_split(row):
    trPr = row._tr.get_or_add_trPr()
    el = OxmlElement("w:cantSplit")
    el.set(qn("w:val"), "true")
    trPr.append(el)


def no_borders(table):
    tblPr = table._tbl.tblPr
    borders = OxmlElement("w:tblBorders")
    for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    tblPr.append(borders)


def clear_cell_borders(table):
    for row in table.rows:
        for cell in row.cells:
            tcPr = cell._tc.get_or_add_tcPr()
            borders = OxmlElement("w:tcBorders")
            for side in ("top", "left", "bottom", "right", "insideH", "insideV"):
                el = OxmlElement(f"w:{side}")
                el.set(qn("w:val"), "nil")
                el.set(qn("w:sz"), "0")
                borders.append(el)
            tcPr.append(borders)


def add_table(headers, rows, widths, font_size=9, header_fill="1F3864",
              first_col_bold=False, align_center_cols=None, band=True):
    table = doc.add_table(rows=1, cols=len(headers))
    table.style = "Table Grid"
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    table.autofit = False
    cell_margins(table)
    align_center_cols = align_center_cols or []

    hdr = table.rows[0]
    repeat_header(hdr)
    no_split(hdr)
    for i, h in enumerate(headers):
        c = hdr.cells[i]
        c.width = Cm(widths[i])
        c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
        shade(c, header_fill)
        p = c.paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_before = Pt(1)
        p.paragraph_format.space_after = Pt(1)
        run_font(p.add_run(h), font_size, True, WHITE)

    for ri, row in enumerate(rows):
        new_row = table.add_row()
        no_split(new_row)
        keep = (len(rows) <= 6) or (ri == len(rows) - 1)
        cells = new_row.cells
        for ci, val in enumerate(row):
            c = cells[ci]
            c.width = Cm(widths[ci])
            c.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            if band and ri % 2 == 1:
                shade(c, "F2F5FA")
            p = c.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.line_spacing = 1.15
            if keep:
                p.paragraph_format.keep_with_next = True
            if ci in align_center_cols:
                p.alignment = WD_ALIGN_PARAGRAPH.CENTER
            bold = first_col_bold and ci == 0
            run_font(p.add_run(str(val)), font_size, bold)
    # keep table with following paragraph
    return table


def caption(text):
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.LEFT
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(9)
    run_font(p.add_run(text), 8.5, False, GREY)


def callout(title, text, fill="FFF4E2", bar="B4530A"):
    t = doc.add_table(rows=1, cols=1)
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    c = t.rows[0].cells[0]
    c.width = Cm(16.2)
    shade(c, fill)
    no_split(t.rows[0])
    c.paragraphs[0].paragraph_format.keep_with_next = True
    tcPr = c._tc.get_or_add_tcPr()
    borders = OxmlElement("w:tcBorders")
    for side in ("top", "bottom", "right"):
        el = OxmlElement(f"w:{side}")
        el.set(qn("w:val"), "nil")
        borders.append(el)
    left = OxmlElement("w:left")
    left.set(qn("w:val"), "single")
    left.set(qn("w:sz"), "18")
    left.set(qn("w:color"), bar)
    borders.append(left)
    tcPr.append(borders)
    p = c.paragraphs[0]
    p.paragraph_format.space_before = Pt(3)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.3
    run_font(p.add_run(title + "　"), 9.5, True, RGBColor(0x8A, 0x3B, 0x00))
    run_font(p.add_run(text), 9.5, False, RGBColor(0x33, 0x33, 0x33))
    spacer = doc.add_paragraph()
    spacer.paragraph_format.space_after = Pt(4)
    spacer.paragraph_format.line_spacing = 0.6


def hrule(color="1F3864", size=8):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(6)
    pPr = p._p.get_or_add_pPr()
    pbdr = OxmlElement("w:pBdr")
    bottom = OxmlElement("w:bottom")
    bottom.set(qn("w:val"), "single")
    bottom.set(qn("w:sz"), str(size))
    bottom.set(qn("w:space"), "1")
    bottom.set(qn("w:color"), color)
    pbdr.append(bottom)
    pPr.append(pbdr)


def add_page_field(paragraph, instr):
    run = paragraph.add_run()
    fld_begin = OxmlElement("w:fldChar")
    fld_begin.set(qn("w:fldCharType"), "begin")
    instr_el = OxmlElement("w:instrText")
    instr_el.set(qn("xml:space"), "preserve")
    instr_el.text = instr
    fld_sep = OxmlElement("w:fldChar")
    fld_sep.set(qn("w:fldCharType"), "separate")
    t = OxmlElement("w:t")
    t.text = "1"
    fld_end = OxmlElement("w:fldChar")
    fld_end.set(qn("w:fldCharType"), "end")
    run._r.append(fld_begin)
    run._r.append(instr_el)
    run._r.append(fld_sep)
    run._r.append(t)
    run._r.append(fld_end)
    run_font(run, 8.5, False, GREY)


# ---------- header / footer ----------
hdr_p = sec.header.paragraphs[0]
hdr_p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
run_font(hdr_p.add_run("剪映工程 · 字幕呈现规范"), 8.5, False, GREY)

ftr = sec.footer.paragraphs[0]
ftr.alignment = WD_ALIGN_PARAGRAPH.CENTER
run_font(ftr.add_run("第 "), 8.5, False, GREY)
add_page_field(ftr, " PAGE ")
run_font(ftr.add_run(" 页 / 共 "), 8.5, False, GREY)
add_page_field(ftr, " NUMPAGES ")
run_font(ftr.add_run(" 页"), 8.5, False, GREY)

# =====================================================================
# COVER
# =====================================================================
for _ in range(3):
    para("", after=0)

p = doc.add_paragraph()
p.paragraph_format.space_after = Pt(6)
run_font(p.add_run("SUBTITLE  SYSTEM  SPEC"), 9, True, RGBColor(0x9A, 0x9A, 0x9A))

p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(2)
p.paragraph_format.space_after = Pt(6)
run_font(p.add_run("剪映工程字幕呈现规范"), 30, True, NAVY)

p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(0)
p.paragraph_format.space_after = Pt(16)
run_font(p.add_run("从 14 个本地工程、24 条时间线、1,157 条字幕中提取的版式、断句与动效规则"),
         12, False, RGBColor(0x44, 0x44, 0x44))

hrule("1F3864", 12)

for _ in range(2):
    para("", after=0)

meta_rows = [
    ("数据来源", "D:\\草稿\\JianyingPro Drafts（剪映专业版 11.6.0.14552 本地草稿）"),
    ("解析对象", "Timelines/<时间线ID>/template.json 中的 materials.texts、text_templates 与 tracks"),
    ("样本规模", "14 个工程 / 24 条时间线 / 1,157 条字幕片段"),
    ("覆盖类型", "干货教学、剧情演绎、测评挑战、活动促销、品牌情感、招商发布、产品细节、模板特效"),
    ("生成日期", "2026-10-21"),
]
t = doc.add_table(rows=0, cols=2)
t.autofit = False
no_borders(t)
cell_margins(t, 50, 50, 0, 100)
for k, v in meta_rows:
    cells = t.add_row().cells
    no_split(t.rows[-1])
    cells[0].width, cells[1].width = Cm(3.0), Cm(13.0)
    p0 = cells[0].paragraphs[0]
    p0.paragraph_format.space_after = Pt(3)
    run_font(p0.add_run(k), 9.5, True, NAVY)
    p1 = cells[1].paragraphs[0]
    p1.paragraph_format.space_after = Pt(3)
    run_font(p1.add_run(v), 9.5, False, RGBColor(0x33, 0x33, 0x33))

clear_cell_borders(t)

for _ in range(6):
    para("", after=0)

callout("阅读提示",
        "本文所有数值均来自工程文件的实测统计，不是主观建议。第五章的“规范”是拟合现状后的可执行参数；"
        "第六章之后是在现状基础上补齐的语义化规则。若制作新的台本，可直接从第八章的预设开始。")

doc.add_page_break()

# =====================================================================
# CONTENTS
# =====================================================================
p = doc.add_paragraph()
p.paragraph_format.space_before = Pt(6)
p.paragraph_format.space_after = Pt(2)
run_font(p.add_run("目　录"), 18, True, NAVY)
hrule("BFBFBF", 6)

toc = [
    ("一", "结论摘要", "这套字幕系统的 7 条硬结论"),
    ("二", "数据来源与解析方法", "工程结构、字段口径、样本边界"),
    ("三", "台本类型划分", "7 类台本的识别特征与样本量"),
    ("四", "全局版式规范", "三区结构、位置、字号、字体、行长、基础样式"),
    ("五", "分类型字幕规范", "每一类台本的参数表与写法要点"),
    ("六", "语义关系与对比手段", "什么语义用什么视觉手段，以及实测依据"),
    ("七", "动画规范", "入场/出场白名单、时长、节奏与禁忌"),
    ("八", "可执行的样式预设", "5 套可直接套用的字幕预设"),
    ("九", "生产检查清单", "交付前逐项自检"),
    ("十", "附录", "工程清单、颜色表、字段说明"),
]
for num, title, desc in toc:
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(7)
    p.paragraph_format.space_after = Pt(1)
    run_font(p.add_run(f"{num}　"), 12, True, AMBER)
    run_font(p.add_run(title), 12, True, NAVY)
    p2 = doc.add_paragraph()
    p2.paragraph_format.left_indent = Cm(0.85)
    p2.paragraph_format.space_after = Pt(2)
    run_font(p2.add_run(desc), 9, False, GREY)

doc.add_page_break()

# =====================================================================
# 1 SUMMARY
# =====================================================================
doc.add_heading("一、结论摘要", level=1)

para("先给结论，后面每一章都有对应的数据与推导。")
para("")

bullet([("形态高度统一：", True, NAVY),
        ("92.6% 的字幕落在底部字幕区，99.8% 为单行，水平居中；垂直位置中位数 y = −0.29，"
         "即画面中心向下 14.5% 画面高度处。", False, None)])
bullet([("字号收敛在 11–13：", True, NAVY),
        ("13 号 325 条、11 号 242 条、12 号 216 条，合计占 68%；中位数 12，约为剪映默认字号 15 的 80%。"
         "16 号以上只出现在标题、花字和价格强调。", False, None)])
bullet([("断句按语义短句切：", True, NAVY),
        ("中位数 7 字，5–8 字占 52.7%，9–12 字占 23.2%，13 字以上只有 1.9%；"
         "单条停留 1.4 秒，语速 4.7 字/秒。", False, None)])
bullet([("可读性靠“白字 + 黑投影”打底：", True, NAVY),
        ("98.2% 的底部字幕带黑色投影；只有背景噪声大的干货类才加 0.08 的描边（20.8%）。", False, None)])
bullet([("强调手段有明确优先级：", True, NAVY),
        ("局部变色 30.1%、放大 17.8%、入场动画 33.4%（按条计）；但动画分布极不均匀——"
         "有的工程全片 0 条，有的几乎逐条加，详见第七章。", False, None)])
bullet([("不同台本的差异是系统性的：", True, NAVY),
        ("剧情类字号 13 / 11、几乎不用颜色和动画（4月23日 y = −0.21，9月11日 −0.56）；干货类字号 12、描边与动画使用率最高；"
         "活动促销字号 8–12、放大率 59.6%；招商类整体上移到画面中部。", False, None)])
bullet([("语义化程度仍然偏低：", True, NAVY),
        ("颜色和放大主要由“视频类型 + 关键词”决定，真正的语义对比（“不是 X，而是 Y”）只覆盖 1.1% 的片段。"
         "这意味着新台本有系统化提升空间——第六章给出了完整映射。", False, None)])

callout("一句话总结",
        "现有工程已经形成“单行、底部、11–13 号、白字黑影”的稳定底盘；真正决定质感的是"
        "“按台本类型换字体与位置、按关键词换颜色、极少用动画”这三件事。")

# =====================================================================
# 2 DATA
# =====================================================================
doc.add_heading("二、数据来源与解析方法", level=1)

doc.add_heading("2.1 工程结构", level=2)
para("本机剪映专业版为 11.6.0.14552，草稿根目录被设置到 D:\\草稿\\JianyingPro Drafts（非默认路径）。"
     "每个工程目录的与字幕相关的文件如下：")

add_table(
    ["文件", "状态", "内容"],
    [
        ["draft_content.json", "加密（Base64 密文）", "当前时间线全量数据，含字幕材质与动画"],
        ["draft_meta_info.json", "加密", "工程元信息、素材清单"],
        ["Timelines/<ID>/template.json", "明文 JSON", "时间线快照：texts、text_templates、tracks、animations"],
        ["Timelines/<ID>/common_attachment/*.json", "明文", "字幕识别标记、脚本同步状态等"],
        ["Cache/artistEffect/<ID>/<hash>/", "明文资源包", "花字模板：content.json、config.json、main.js"],
    ],
    widths=[6.2, 3.6, 6.4],
    font_size=8.8,
    align_center_cols=[1],
)
caption("表 2-1　字幕数据的载体。加密文件无法直接读取，因此本次全部统计基于 template.json 快照。")

doc.add_heading("2.2 字段口径", level=2)
add_table(
    ["字段", "含义", "本次用法"],
    [
        ["materials.texts[].content", "富文本 JSON（text + styles）", "取纯文本、行数、每行字数；颜色优先级最低"],
        ["font_size", "剪映字号（相对单位）", "统计字号；该单位跨分辨率一致，可直接横向比较"],
        ["clip.transform.y", "垂直位置，−1～1，相对半屏高", "y = −0.29 即中心下方 14.5% 画面高度"],
        ["clip.scale", "缩放倍数", ">1.05 记为“放大强调”"],
        ["extra_material_refs → material_animations", "入场/出场动画", "统计 type（in/out）、name、duration"],
        ["text_color / border_* / shadow_*", "颜色、描边、投影", "判断对比手段"],
        ["target_timerange", "起止时间（微秒）", "计算单条时长与语速 CPS"],
    ],
    widths=[4.6, 5.0, 6.6],
    font_size=8.8,
)

doc.add_heading("2.3 统计口径与边界", level=2)
bullet([("快照而非当前状态：", True, None),
        ("template.json 是剪映写入时间线目录的明文副本，可能落后于最后一次编辑；但字幕文本与样式在快照中完整，"
         "足以做规范统计。", False, None)])
bullet([("行业样本单一：", True, None),
        ("14 个工程全部属于服装工厂 / 女装实体店垂类，结论对同类账号可直接复用；跨行业需重新校准字号与颜色。", False, None)])
bullet([("字号是相对单位：", True, None),
        ("同一字号在 1080×1920 与 3840×6826 画布上视觉占比一致，因此本文只给“剪映字号”，不给像素值，避免误导。", False, None)])
bullet([("动画统计范围：", True, None),
        ("只统计文字片段自身的入场/出场动画，不含花字模板内部的关键帧动效（那部分由模板资源包控制）。", False, None)])

# =====================================================================
# 3 TYPES
# =====================================================================
doc.add_heading("三、台本类型划分", level=1)
para("按“台本目的 + 句式结构”把 24 条时间线归为 8 类（其中“模板特效”不是独立台本，而是节日节点的花字方案）。"
     "分类依据是该时间线字幕文本的句式，而不是工程名。")

add_table(
    ["类型", "识别特征（台本句式）", "代表工程", "条数"],
    [
        ["干货教学", "清单、步骤、避坑；“第一…第二…”“不要…要…”", "9月10日、6月17日、7月11日(1)、9月18日", "544"],
        ["剧情演绎", "角色对话、冲突、跟拍；短句多、口语词多", "4月23日、9月11日杨总、4月8日", "308"],
        ["测评挑战", "挑战设定、实测过程、对比结论", "9月5日（31 天 31 套）", "153"],
        ["活动促销", "福利、价格、时间、地点、领取方式", "9月22日(4)、9月16日(2)、9月30日", "48"],
        ["品牌情感", "价值观陈述、金句、第一人称抒情", "9月30日（我卖的不是衣服 / 热爱）", "36"],
        ["招商发布", "会议信息、政策、名额、报名动作", "7月11日（连云港订货会）", "28"],
        ["产品细节", "单点卖点拆解、连续追问式测评", "10月21日（衣服细节）", "19"],
        ["模板特效", "节日热点花字，整段套模板", "9月30日（国庆旗帜字幕）", "21"],
    ],
    widths=[2.6, 6.4, 5.0, 1.7],
    font_size=8.8,
    align_center_cols=[3],
)
caption("表 3-1　台本类型与样本分布。合计 1,157 条，覆盖 14 个工程、24 条时间线。")

para("分类不是目的，目的是让“同一类台本共用一套字幕参数”。第四章给所有类型的共同底盘，"
     "第五章给每一类的差异化参数。")

# =====================================================================
# 4 GLOBAL LAYOUT
# =====================================================================
doc.add_heading("四、全局版式规范", level=1)

doc.add_heading("4.1 三区结构", level=2)
para("所有字幕在垂直方向只落在三个区间，边界由 y 值划分：y ≤ −0.15 为底部字幕区，−0.15 < y < 0.15 为中部信息区，"
     "y ≥ 0.15 为顶部标题区。")
add_table(
    ["区域", "占比", "字号中位", "y 中位", "放大率", "动画率", "用途"],
    [
        ["底部字幕区", "92.6%", "12", "−0.29", "17.8%", "32.9%", "口播字幕、对话字幕（主战场）"],
        ["中部信息区", "4.3%", "8", "−0.05", "28.0%", "46.0%", "招商信息、活动规则等信息条"],
        ["顶部标题区", "3.1%", "14", "0.64", "47.2%", "33.3%", "标题、章节名、人物身份"],
    ],
    widths=[3.0, 1.8, 2.0, 1.8, 1.9, 1.9, 5.0],
    font_size=8.8,
    align_center_cols=[1, 2, 3, 4, 5],
)
caption("表 4-1　三区结构。换算公式：画面纵向位置 = 50% + y × 50%。")

callout("位置换算示例",
        "y = −0.29 → 画面顶部往下 64.5% 处；y = −0.21 → 60.5%；y = −0.39 → 69.5%；y = 0.64 → 18%（顶部）。"
        "短视频底部通常有 8%–12% 的 UI 遮挡区，字幕最低不要低于 y = −0.45（72.5%）。")

doc.add_heading("4.2 垂直位置", level=2)
para("底部字幕区的实测分布：中位 −0.29，P10 −0.56，P90 −0.21。去掉极端值后，稳定的落点是 −0.21 ～ −0.39，"
     "即画面高度的 60.5% ～ 69.5% 之间。这一带既在人物胸口以下、又不压底部操作栏。")
bullet([("常态：", True, None), ("y = −0.29（14.5% 中心下方）——剧情、测评、产品细节、模板均落在此处。", False, None)])
bullet([("更低：", True, None), ("y = −0.37 ～ −0.39——活动促销、品牌情感，为画面中部的主体信息让位。", False, None)])
bullet([("更高：", True, None), ("y = −0.21——剧情演绎，给下方留出字幕之外的字幕组/花字空间。", False, None)])
bullet([("例外：", True, None), ("招商发布整体上移到 y = −0.05，作为画面中部的信息条使用。", False, None)])

doc.add_heading("4.3 字号", level=2)
para("字号分布高度集中：13 号 325 条（28.1%）、11 号 242 条（20.9%）、12 号 216 条（18.7%），三档合计 67.7%。"
     "中位 12，对应剪映默认字号 15 的 80%。")
add_table(
    ["字号", "条数", "占比", "典型用途"],
    [
        ["8", "55", "4.8%", "招商信息条、活动补充说明（次要信息）"],
        ["11", "242", "20.9%", "产品细节、部分剧情/干货（画面较满时）"],
        ["12", "216", "18.7%", "干货教学、品牌情感（默认档）"],
        ["13", "325", "28.1%", "剧情、测评（最常用）"],
        ["14–16", "84", "7.3%", "标题、章节名、价格强调"],
        ["18 以上", "30", "2.6%", "顶部大标题、花字、金额"],
    ],
    widths=[2.4, 2.2, 2.0, 9.6],
    font_size=8.8,
    align_center_cols=[0, 1, 2],
)
caption("表 4-2　字号分布。字号为剪映相对单位，同一字号在不同画布上的视觉占比一致。")

doc.add_heading("4.4 字体", level=2)
para("字体以无衬线粗黑为主，全篇通常只用 1 种，最多 2 种。")
add_table(
    ["字体", "主要使用场景", "出现条数"],
    [
        ["字语云黑宋", "干货教学、活动促销、品牌情感（信息密度高，字形稳）", "约 246"],
        ["新青年体", "剧情演绎、干货（偏年轻、口语感）", "约 300"],
        ["抖音美好体", "产品细节、剧情、招商（平台默认观感）", "约 250"],
        ["金陵体", "招商发布、测评（偏正式/记录感）", "约 60"],
        ["后现代体 / 俊雅体 / 雅月体", "标题、品牌情感、测评（做气质区分）", "约 60"],
    ],
    widths=[4.4, 9.6, 2.2],
    font_size=8.8,
    align_center_cols=[2],
)
caption("表 4-3　字体使用。字体资源位于 Cache/effect/<字体ID>/ 下，可离线复用。")

doc.add_heading("4.5 行长、断句与节奏", level=2)
para("字幕几乎不换行：1,157 条里只有 5 条为多行（0.2%），且都出现在信息不可拆的场景（地址、时间、福利清单）。"
     "因此“每行多少字”实际上等于“每条多少字”。")
add_table(
    ["字数区间", "条数", "占比", "判断"],
    [
        ["1–4 字", "257", "22.2%", "短促强调、序号、语气词（“第一”“喂”“然后”）"],
        ["5–8 字", "610", "52.7%", "主力区间，一个语义短语"],
        ["9–12 字", "268", "23.2%", "上限区间，通常是完整分句"],
        ["13–16 字", "15", "1.3%", "已需要拆句，或改双行"],
        ["17 字以上", "7", "0.6%", "例外：活动信息、模板花字"],
    ],
    widths=[3.2, 2.2, 2.2, 8.6],
    font_size=8.8,
    align_center_cols=[1, 2],
)
caption("表 4-4　单条字数分布。中位 7 字，P10 = 3 字，P90 = 10 字。")

para("节奏指标：单条时长中位 1.43 秒，语速（CPS）中位 4.7 字/秒，P10 = 2.4、P90 = 8.0。"
     "换算成可执行规则：")
bullet([("一条字幕 = 一个语义短语，7 字左右，停留 1.2–1.6 秒。", True, None)])
bullet([("超过 12 字必须拆成两条，或改为双行（每行 ≤ 12 字）。", True, None)])
bullet([("CPS 控制在 4–6；超过 8 说明字幕在追语速，观众读不完。", True, None)])
bullet([("1–4 字的短句只用于序号、强调词、语气词，不要连续出现三条以上。", True, None)])

doc.add_heading("4.6 基础样式", level=2)
add_table(
    ["样式项", "实测取值", "使用率", "说明"],
    [
        ["文字颜色", "#FFFFFF", "68.8%", "白色是绝对底色，其余颜色只作局部强调"],
        ["投影", "黑色、距离 5、角度 −45°、透明度 0.6–0.9", "98.2%", "默认开启，是底部字幕可读性的基础"],
        ["描边", "0.08、黑色", "20.8%（仅干货）", "背景噪声大时才加，正常画面不加"],
        ["背景框", "黑色、圆角", "0.3%", "几乎不用，会压缩画面"],
        ["对齐", "居中", "≈90%", "少量信息条用左对齐"],
        ["行距", "0.02（剪映默认）", "90%+", "单行字幕下不生效，双行时保持默认"],
    ],
    widths=[2.8, 6.0, 2.6, 4.8],
    font_size=8.8,
    align_center_cols=[2],
)
caption("表 4-5　基础样式。投影是必选项，描边是条件项，背景框基本不用。")


# =====================================================================
# 5 PER-TYPE
# =====================================================================
doc.add_heading("五、分类型字幕规范", level=1)
para("每一类台本给一张参数表、一段写法要点和工程里的真实例句。参数取该类“底部字幕区”的中位数，"
     "个别项标注了范围。")

TYPE_SPECS = [
    {
        "name": "5.1 干货教学（544 条 / 8 条时间线）",
        "table": [
            ["字号", "12（11–13）", "位置 y", "−0.32"],
            ["每行字数", "中位 7，P90 10", "单条时长", "1.5 秒 / CPS 4.5"],
            ["字体", "字语云黑宋 / 新青年体", "颜色", "白字 + 关键词变色（30.7%）"],
            ["描边", "0.08 黑边（20.8%）", "放大", "29.2% 的条目放大 1.1–1.5×"],
            ["入场动画", "59.7%", "出场动画", "少量渐隐（500ms）"],
        ],
        "points": [
            "信息密度最高的一类，字幕承担“讲义”功能：每一条都是一个可独立理解的要点。",
            "序号（第一/第二/第三）单独成条，仅 2–3 字，常用金色或放大，作为章节锚点。",
            "同一段里连续条目保持字号与颜色一致，只让“结论句”变色或放大，避免整段花。",
            "描边只在高噪背景（街拍、档口）出现，室内口播不加描边。",
            "动画做法分成两派：9月18日 一类只用 4 种效果、集中在段落首条；9月10日 系列几乎逐条加动画（单条时间线出现 12–35 种）。"
            "建议按第七章的克制路线执行。",
        ],
        "examples": ["“第一 / 确认市场 / 第二 / 根据店铺面积 / 第三 / 先定主推品类”",
                     "“不是价格高了 / 而是第一批货拿错了”",
                     "“比你装老手好用10倍”（整句金色 + 放大）"],
    },
    {
        "name": "5.2 剧情演绎（308 条 / 3 条时间线）",
        "table": [
            ["字号", "13 或 11（分工程固定）", "位置 y", "−0.21 / −0.56（随机位）"],
            ["每行字数", "中位 7，P90 10", "单条时长", "1.17 秒 / CPS 5.7"],
            ["字体", "新青年体 / 抖音美好体", "颜色", "几乎纯白（0.7% 变色）"],
            ["描边", "不用", "放大", "不用"],
            ["入场动画", "2.4%", "出场动画", "几乎不用"],
        ],
        "points": [
            "字幕完全服务于对话节奏，不做任何视觉强调，避免抢演员表演。",
            "字号与位置在单个工程内固定：4月23日 13 号 / y −0.21（室内对话）；9月11日 11 号 / y −0.56（跟拍机位更低）。",
            "断句跟着“气口”走：一句话切成 3–7 字的短块，语速最快（5.7 字/秒）。",
            "口语词照实上屏（“然后”“就是”“喂”），不做书面化改写，保留真实感。",
            "唯一允许的变化是角色身份/姓名条，出现在顶部或侧边，用金色小字。",
        ],
        "examples": ["“杨总杨总等一下 / 你看一下 / 这个西安的王总催这个809”",
                     "“喂 / 你上次说来我们女装工厂店 / 是真的吗”",
                     "“孙杨照 / 鸭鸭苏北分公司总经理”（金色身份条）"],
    },
    {
        "name": "5.3 测评挑战（153 条 / 2 条时间线）",
        "table": [
            ["字号", "13", "位置 y", "−0.29"],
            ["每行字数", "中位 7，P90 9", "单条时长", "1.57 秒 / CPS 4.1"],
            ["字体", "金陵体 / 雅月体 / 新青年体", "颜色", "97.2% 带色（#FFF589 为主）"],
            ["描边", "不用", "放大", "5.6%"],
            ["入场动画", "14.6%", "出场动画", "渐隐 500ms"],
        ],
        "points": [
            "整类字幕默认就是淡黄色（#FFF589），形成“测评/Vlog”的频道识别色。",
            "挑战规则、天数、数量用数字句，字号不变但整句着色，靠颜色而非大小区分。",
            "对话段与旁白段共用一套样式，不切换字体，保证连贯。",
            "语速最慢（4.1 字/秒），因为画面信息多，观众需要时间看。",
        ],
        "examples": ["“挑战 / 这个月 / 定了一个 / 31天试穿31套”",
                     "“拿货不要只看新鲜感”",
                     "“长期合作看稳定”（整句淡黄）"],
    },
    {
        "name": "5.4 活动促销（48 条 / 3 条时间线）",
        "table": [
            ["字号", "8–12（两档：信息条 8 / 主字幕 12）", "位置 y", "−0.37（最低）"],
            ["每行字数", "中位 8，P90 11", "单条时长", "1.57 秒 / CPS 4.8"],
            ["字体", "字语云黑宋 / 新青年体", "颜色", "白字 + 金色数字（21.3%）"],
            ["描边", "不用", "放大", "59.6%（最高）"],
            ["入场动画", "8.5%", "出场动画", "少量"],
        ],
        "points": [
            "字幕位置压到 −0.37，把画面中部让给商品和价格牌。",
            "价格、折扣、日期一律用金色（#FFDE00 / #FFBF17）并放大 1.2–1.5×，是全片唯一的强对比点。",
            "信息条（地址、时间、领取方式）字号降到 8，允许双行，靠“小”来区分层级。",
            "放大是主要手段，动画反而少——促销信息要“稳”，不要跳。",
        ],
        "examples": ["“第一好货一折起 / 5折封顶”（金色 + 放大）",
                     "“10000份伴手礼 / 到店即可领取”（信息条，8 号双行）",
                     "“活动时间就在9月25号开始 / 持续三天”"],
    },
    {
        "name": "5.5 品牌情感（36 条 / 2 条时间线）",
        "table": [
            ["字号", "12（金句段 18）", "位置 y", "−0.39（最低）"],
            ["每行字数", "中位 5，P90 11", "单条时长", "1.17 秒 / CPS 5.2"],
            ["字体", "字语云黑宋 / 俊雅体", "颜色", "白 + 金/米色关键词（35.5%）"],
            ["描边", "不用", "放大", "3.2%"],
            ["入场动画", "35.5%（渐显/向右露出）", "出场动画", "渐隐 500ms"],
        ],
        "points": [
            "短句为主（中位 5 字），一句一行，靠留白和停顿制造情绪，而不是靠样式。",
            "关键词用暖金或米色（#FFBF17 / #F9F3C4），与白字形成低对比的“柔光”效果，不用红。",
            "金句段单独放大到 18 号，并可上移到画面中部，作为一次视觉呼吸。",
            "动画只用最轻的渐显、向右露出、生长，300ms，不用位移大的效果。",
        ],
        "examples": ["“我卖的不是衣服 / 是身上的底气”（后半句金色）",
                     "“大处见版型 / 小处见真章”",
                     "“不想在行业里内卷”"],
    },
    {
        "name": "5.6 招商发布（28 条 / 1 条时间线）",
        "table": [
            ["字号", "8（主打档）", "位置 y", "−0.05（画面中部）"],
            ["每行字数", "中位 9.5，P90 15", "单条时长", "1.8 秒 / 长句 3.6 秒"],
            ["字体", "金陵体 / 抖音美好体", "颜色", "白 + 金色关键信息（14.3%）"],
            ["描边", "不用", "放大", "不用"],
            ["入场动画", "14.3%（向右滑动/渐显 500ms）", "出场动画", "渐隐 500ms"],
        ],
        "points": [
            "唯一不放在底部的类型：字幕作为“会议信息条”居中排布，与舞台画面平行。",
            "字号小、字距松，信息完整（时间、地点、政策、名额），允许一条 15 字。",
            "品牌名、人名、职务用金色（#FFF589），是画面里唯一的彩色元素。",
            "动画偏“正式”：向右滑动、渐显，500ms，比口播类慢一档。",
        ],
        "examples": ["“苏北地区做服装的老板们 / 注意了国民品牌鸭鸭”",
                     "“将在7月19日-21日的连云港 / 发布2026秋冬新款及拿货政策”",
                     "“仁维团队2026最新打法 / 就在连云港20号订货会”（双行）"],
    },
    {
        "name": "5.7 产品细节（19 条 / 1 条时间线）",
        "table": [
            ["字号", "11（全片统一）", "位置 y", "−0.29"],
            ["每行字数", "中位 5，P90 8", "单条时长", "1.53 秒 / CPS 4.8"],
            ["字体", "抖音美好体", "颜色", "纯白"],
            ["描边", "不用", "放大", "不用"],
            ["入场动画", "不用", "出场动画", "不用"],
        ],
        "points": [
            "极简参数：11 号、纯白、无动画，所有注意力交给特写画面。",
            "断句极短（5 字），一问一答式推进：“扣子用的是什么料 / 缝的牢不牢”。",
            "适合“单点拆解”型台本；如果要强调，优先用画面运镜而不是字幕特效。",
        ],
        "examples": ["“大家一般买衣服 / 都只看面料”",
                     "“扣子和拉链的细节”",
                     "“大处见版型 / 小处见真章”"],
    },
    {
        "name": "5.8 模板特效（21 条 / 1 条时间线）",
        "table": [
            ["字号", "由模板控制（工程内为空）", "位置 y", "−0.25"],
            ["每行字数", "中位 10，P90 16", "单条时长", "1.07 秒 / CPS 9.4"],
            ["字体", "随模板（本例字语云黑宋）", "颜色", "随模板（渐变/描边/发光）"],
            ["描边", "模板内置", "放大", "21.1%"],
            ["入场动画", "模板内置（光线划过等）", "出场动画", "模板内置"],
        ],
        "points": [
            "节日节点（国庆、开业、周年）专用：整段套用花字模板，字幕不再是“信息”而是“装饰”。",
            "模板自带逐字/逐词动效，CPS 高达 9.4，因此文本必须短（10 字左右）。",
            "只在片头/片尾或转场使用，不与口播字幕混排。",
            "同一条视频最多用 1 个模板，避免风格打架。",
        ],
        "examples": ["“祝祖国繁荣昌盛” / “人民有信仰” / “国家有力量”",
                     "“店铺马上开业 / 期待与你相遇”",
                     "模板：节日热点-国庆旗帜红黄变色字幕（resource 7550547583941283134）"],
    },
]

for spec in TYPE_SPECS:
    doc.add_heading(spec["name"], level=2)
    rows = [[a, b, c, d] for a, b, c, d in spec["table"]]
    t = doc.add_table(rows=0, cols=4)
    t.style = "Table Grid"
    t.alignment = WD_TABLE_ALIGNMENT.CENTER
    t.autofit = False
    cell_margins(t)
    for a, b, c, d in spec["table"]:
        new_row = t.add_row()
        no_split(new_row)
        cells = new_row.cells
        for i, val in enumerate((a, b, c, d)):
            cell = cells[i]
            cell.width = Cm([2.6, 5.4, 2.8, 5.4][i])
            cell.vertical_alignment = WD_ALIGN_VERTICAL.CENTER
            p = cell.paragraphs[0]
            p.paragraph_format.space_before = Pt(1)
            p.paragraph_format.space_after = Pt(1)
            p.paragraph_format.keep_with_next = True
            if i % 2 == 0:
                shade(cell, "EDF1F8")
                run_font(p.add_run(val), 8.8, True, NAVY)
            else:
                run_font(p.add_run(val), 8.8, False, None)
    para("", after=2)
    for pt in spec["points"]:
        bullet(pt, size=9.8)
    para("", after=0)
    rich([("工程实例：", True, AMBER), ("　".join(spec["examples"]), False, GREY)], size=8.8, after=10)

# =====================================================================
# 6 SEMANTICS
# =====================================================================
doc.add_heading("六、语义关系与对比手段", level=1)
para("这一章回答两个问题：现有工程在什么语义上用了什么视觉手段？以及，新台本应该怎么定规则？")

doc.add_heading("6.1 现状：手段与语义的关联度", level=2)
para("把 1,139 条非模板字幕按语义角色打标，统计它们在颜色、放大、动画上的使用率。基线取底部字幕区的"
     "变色率 30.1%、放大率 17.8%、动画率 32.9%。")
add_table(
    ["语义角色", "识别信号", "占比", "变色率", "放大率", "动画率", "结论"],
    [
        ["数字 / 价格 / 时间", "数字、元、折、号、天", "9.6%", "33.9%", "11.0%", "22.0%", "变色略高于基线，放大反而低于基线"],
        ["疑问句", "？、吗、什么、怎么", "6.9%", "31.6%", "8.9%", "39.2%", "靠动画而非颜色制造“追问感”"],
        ["否定 / 转折", "不是、别、但是、而是", "15.6%", "32.6%", "17.4%", "35.4%", "与基线接近，说明尚未被单独强调"],
        ["序号 / 清单", "第一、第二、首先", "5.6%", "17.2%", "14.1%", "34.4%", "颜色偏少，靠独立成条区分"],
        ["行动号召", "评论区、关注、点赞", "1.9%", "36.4%", "18.2%", "13.6%", "变色+放大，动画少（要稳）"],
        ["对比结构", "不是X而是Y、与其…不如", "1.1%", "23.1%", "23.1%", "61.5%", "动画最高，是唯一被系统强调的语义"],
    ],
    widths=[3.2, 4.0, 1.5, 1.6, 1.6, 1.7, 3.5],
    font_size=8.3,
    align_center_cols=[2, 3, 4, 5],
)
caption("表 6-1　语义角色与视觉手段的实测关联。放大率按“相对本工程字号中位数 ×1.15”计算。")

callout("读表要点",
        "现有工程的颜色和放大是“类型级”的（整类统一色），不是“语义级”的；真正的逐句强调只发生在"
        "“对比结构”和“行动号召”上（放大率 23.1% / 18.2%，动画率 61.5%）。这正是新规范可以系统化的地方。")

doc.add_heading("6.2 对比手段工具箱", level=2)
para("工程里实际出现过、且可复用的 7 种手段，按“侵入性”从低到高排列：")
add_table(
    ["手段", "参数", "适用", "注意"],
    [
        ["① 白字 + 黑投影", "#FFFFFF；阴影距离 5、角度 −45°、透明度 0.6–0.9", "所有字幕的默认底盘", "不要关阴影，除非背景是纯色卡"],
        ["② 局部变色", "#FFF589 关键词 / #FFBF17 金 / #FE8A80 警告红", "关键词、数字、结论", "一句最多 1 个色块，全片 ≤ 2 种强调色"],
        ["③ 描边", "0.08、黑色", "高噪背景（街拍、档口、人群）", "室内口播不加，会显脏"],
        ["④ 放大", "1.1–1.5×，锚点保持基线", "标题、价格、口号", "放大后要检查是否压到画面主体"],
        ["⑤ 入场动画", "渐显/向右露出/向上露出，300ms", "段落切换、新要点", "逐条加会“跳”，建议只在段落首条"],
        ["⑥ 位置分层", "顶部标题 / 中部信息条 / 底部字幕", "章节名、身份、活动信息", "同屏最多两层文字"],
        ["⑦ 花字模板", "节日/开业/周年模板包", "片头片尾、转场", "一条视频最多 1 个模板"],
    ],
    widths=[3.2, 6.6, 4.0, 4.4],
    font_size=8.5,
)
caption("表 6-2　对比手段工具箱。")

doc.add_heading("6.3 语义 → 手段映射（建议规则）", level=2)
para("在现状基础上，把“什么话该被看见”写成可执行规则。每条规则都能在剪映里用 2–3 步实现。")
add_table(
    ["语义角色", "推荐手段", "具体做法", "强度"],
    [
        ["数字 / 价格 / 时间", "金色 + 放大", "数字所在短句整体 #FFDE00，放大 1.2×，不换字体", "强"],
        ["否定 / 转折（不是…而是…）", "双色对撞", "前半句白/灰，后半句 #FFF589 或 #FFBF17，仅后半句放大 1.1×", "强"],
        ["序号 / 清单（第一/第二）", "独立成条 + 金色序号", "序号单独一条 2 字，金色；条目正文回到白色 12 号", "中"],
        ["疑问句", "白字 + 轻动画", "保持白色；问句入场用 300ms 渐显，不加色", "弱"],
        ["行动号召（评论/关注）", "高饱和色 + 放大 + 弹入", "#FFBF17 或 #FE8A80，放大 1.2×，入场用“放大”300ms", "强"],
        ["结论 / 金句", "升字号 + 换位", "单独一条，字号 +2～4，可上移到中部，配 300ms 渐显", "强"],
        ["专有名词 / 身份", "小字金色", "顶部或侧边，8–10 号，#FFF589，不加动画", "弱"],
        ["口语填充词（然后/就是）", "不上屏或降级", "能删则删；保留时用 11 号、纯白、无动画", "无"],
    ],
    widths=[4.0, 3.4, 7.2, 1.4],
    font_size=8.5,
    align_center_cols=[3],
)
caption("表 6-3　语义到视觉的映射表。强度＝观众感知到的强调程度，建议单条视频“强”级不超过 5 次。")

doc.add_heading("6.4 组合禁忌", level=2)
bullet([("不要同时用三种以上手段：", True, None), ("变色 + 放大 + 动画 + 描边叠在一句上，会变成“花字”，失去信息层级。", False, None)])
bullet([("一条视频的强调色不超过 2 种：", True, None), ("工程里累计出现过 9 种颜色，但单个项目通常只用 1–2 种。", False, None)])
bullet([("不要给每一句都加入场动画：", True, None), ("实测 67% 的字幕没有动画；动画是“段落标记”，不是“逐条装饰”。", False, None)])
bullet([("不要用红字表达正面信息：", True, None), ("#FE5252/#B71C1C 在样本中只用于“不允许”“调货”等负面/警示语境。", False, None)])


# =====================================================================
# 7 ANIMATION
# =====================================================================
doc.add_heading("七、动画规范", level=1)

doc.add_heading("7.1 使用现状（两极分化）", level=2)
para("1,157 条字幕中 387 条带入场/出场动画（33.4%），其中入场 386 次、出场仅 20 次，"
     "时长高度集中在 300ms（入场）与 500ms（出场）。但“33.4%”这个平均数掩盖了真实情况——"
     "不同工程的动画密度差了两个数量级：")
add_table(
    ["做法", "代表工程", "动画覆盖", "单条时间线效果种类"],
    [
        ["克制派", "9月18日 - 副本", "70 / 72 条", "4 种"],
        ["克制派", "9月11日杨总", "9 / 139 条", "3 种"],
        ["克制派", "4月23日、10月21日", "5 / 164 条、0 / 19 条", "1–5 种 / 0"],
        ["装饰派", "9月10日（主时间线）", "104 / 139 条", "35 种"],
        ["装饰派", "9月10日（其余 4 条）", "54 / 62、28 / 31、24 / 38、22 / 35 条", "24、13、15、12 种"],
    ],
    widths=[2.4, 5.4, 4.4, 5.2],
    font_size=8.6,
    align_center_cols=[0, 2, 3],
)
caption("表 7-1　两种动画做法的实测对比。同样是干货教学，动画密度可以从 0 到 75%。")
para("使用最多的效果（全样本合计）：")
add_table(
    ["效果", "次数", "方向", "典型时长", "定位"],
    [
        ["渐显", "104", "入场", "300–333ms", "默认首选，几乎无感"],
        ["向右露出", "28", "入场", "300ms", "干货类段落切换"],
        ["向上露出", "24", "入场", "300–500ms", "新要点出现"],
        ["向上滑动", "23", "入场", "300–500ms", "条目递进"],
        ["放大", "16", "入场", "300ms", "价格、口号"],
        ["渐隐", "13", "出场", "500ms", "段落结束"],
        ["缩小", "11", "入场", "300ms", "收束、结束感"],
        ["向右模糊 II", "10", "入场", "300ms", "转场"],
    ],
    widths=[3.6, 1.8, 2.0, 3.4, 5.4],
    font_size=8.8,
    align_center_cols=[1, 2, 3],
)
caption("表 7-2　动画效果使用频次（Top 8）。")

callout("关键判断",
        "装饰派（逐条加不同效果）在成片里会显得“热闹”，但风格不统一、观众注意力被抢；"
        "克制派用 3–4 种效果覆盖全片，反而更像一个品牌。本规范取克制路线：动画是“段落标记”，"
        "不是“逐条装饰”。")

doc.add_heading("7.2 白名单与参数", level=2)
add_table(
    ["动画", "方向", "时长", "使用条件", "禁止场景"],
    [
        ["渐显", "入场", "300ms", "默认；任何类型都可用", "无"],
        ["向右露出 / 向上露出", "入场", "300ms", "干货、情感的段落首条", "连续三条以上"],
        ["向上滑动 / 向下滑动", "入场", "300–500ms", "清单递进、测评过程", "与画面运动同向时"],
        ["放大 / 轻微放大", "入场", "300ms", "价格、口号、CTA", "正文信息"],
        ["文字渐显", "入场", "300ms", "标题、金句", "长句（>12 字）"],
        ["渐隐", "出场", "500ms", "段落结束", "每条都加"],
        ["打字机 / 打字光标", "入场", "1.5–3s", "仅标题、片头", "口播字幕"],
    ],
    widths=[3.6, 1.8, 2.2, 5.4, 3.2],
    font_size=8.6,
    align_center_cols=[1, 2],
)
caption("表 7-3　动画白名单。白名单之外的效果（光效、抖动、3D 翻转）在样本中未出现，不建议引入。")

doc.add_heading("7.3 分类型动画策略", level=2)
para("下表的“入场率”是该类型全部条目的平均值，容易被装饰派拉高，使用时结合 7.1 的两种做法一起看。")
add_table(
    ["类型", "入场率", "推荐策略", "时长"],
    [
        ["干货教学", "59.7%", "9月10日 系列拉高了均值；建议只保留章节首条的渐显/向右露出，其余不加", "300ms"],
        ["品牌情感", "35.5%", "金句用渐显，情绪段落用向右露出", "300–500ms"],
        ["测评挑战", "14.6%", "仅挑战规则、结论出现时用", "500ms"],
        ["招商发布", "14.3%", "正式感：向右滑动、渐显", "500ms"],
        ["活动促销", "8.5%", "价格出现时用放大，其余不加", "300ms"],
        ["剧情演绎", "2.4%", "几乎不用；只在身份条出现时渐显", "300ms"],
        ["产品细节", "0%", "完全不用", "—"],
        ["模板特效", "模板内置", "由花字模板决定，不手工加", "—"],
    ],
    widths=[3.2, 2.2, 8.4, 2.4],
    font_size=8.6,
    align_center_cols=[1, 3],
)
caption("表 7-4　按类型的动画使用率与建议。")

doc.add_heading("7.4 节奏规则", level=2)
bullet([("入场 300ms、出场 500ms 是安全值：", True, None), ("短于 200ms 会“闪”，长于 600ms 会拖慢口播节奏。", False, None)])
bullet([("同一屏不要叠加两种动画：", True, None), ("标题入场 + 字幕入场同时发生，观众不知道该看哪里。", False, None)])
bullet([("动画方向要和画面运动一致：", True, None), ("镜头向右摇，字幕就不要向左滑。", False, None)])
bullet([("一条视频的动画种类 ≤ 2 种：", True, None), ("克制派工程实际做到 4 种以内；装饰派用到 12–35 种，属于反例，不建议模仿。", False, None)])
bullet([("模板花字不叠加手工动画：", True, None), ("模板内部已有逐字动效，再加入场会打架。", False, None)])

# =====================================================================
# 8 PRESETS
# =====================================================================
doc.add_heading("八、可执行的样式预设", level=1)
para("把前面的规则压缩成 5 套预设。新建台本时先选预设，再只改文本，不逐条调样式。")

add_table(
    ["参数", "A 干货口播", "B 剧情对话", "C 活动促销", "D 品牌情感", "E 招商信息"],
    [
        ["字号", "12", "13", "主 12 / 信息条 8", "12（金句 18）", "8"],
        ["字体", "字语云黑宋", "新青年体", "字语云黑宋", "字语云黑宋 / 俊雅体", "金陵体"],
        ["位置 y", "−0.32", "−0.21", "−0.37", "−0.39", "−0.05"],
        ["字色", "白 + #FFF589 关键词", "纯白", "白 + #FFDE00 数字", "白 + #FFBF17 关键词", "白 + #FFF589 名称"],
        ["描边", "0.08（仅高噪背景）", "无", "无", "无", "无"],
        ["放大", "关键词 1.2×", "无", "价格 1.3×", "金句 1.0（改字号）", "无"],
        ["入场动画", "渐显 300ms（章节首条）", "无", "放大 300ms（价格）", "渐显/向右露出 300ms", "向右滑动 500ms"],
        ["出场动画", "渐隐 500ms", "无", "无", "渐隐 500ms", "渐隐 500ms"],
        ["断句", "5–10 字，序号独立成条", "3–7 字，跟气口", "8–11 字，信息可双行", "4–6 字，一句一行", "9–15 字，可双行"],
        ["语速 CPS", "4.5", "5.7", "4.8", "5.2", "5.0"],
    ],
    widths=[2.4, 3.0, 2.8, 3.0, 3.0, 2.6],
    font_size=8.0,
    first_col_bold=True,
    align_center_cols=[1, 2, 3, 4, 5],
)
caption("表 8-1　5 套字幕预设。全部参数来自对应类型的实测中位数，可直接在剪映里复刻。")

para("使用方式：")
num_item(1, [("判定台本类型", True, None), ("（参照表 3-1 的句式特征），选对应预设。", False, None)])
num_item(2, [("按预设建一条字幕样式", True, None), ("，后续所有条目复制该样式，只改文字。", False, None)])
num_item(3, [("按第六章的语义映射", True, None), ("给关键词换色/放大——这是唯一允许的逐条改动。", False, None)])
num_item(4, [("动画只加在段落首条", True, None), ("，其余条目保持无动画。", False, None)])

callout("关于混用",
        "一条视频只用一个预设。如果台本里既有干货又有促销，按“主要目的”选，促销段用 C 的数字样式局部覆盖，"
        "不要整体切换字体和位置。")

# =====================================================================
# 9 CHECKLIST
# =====================================================================
doc.add_heading("九、生产检查清单", level=1)
para("交付前逐项检查。每一条都对应前面的实测规则，任何一项不通过都建议返工。")

checks = [
    ("形态", "全部字幕单行；没有为了排版而硬换行（除地址/时间等信息条）。"),
    ("字数", "单条 5–10 字为主；没有超过 12 字的单行；1–4 字短句不超过连续三条。"),
    ("语速", "每条停留 1.2–1.6 秒；CPS 在 4–6 之间。"),
    ("位置", "底部字幕 y 在 −0.21 ～ −0.39；没有压到底部 UI 遮挡区（y < −0.45）。"),
    ("字号", "全片字号不超过 3 档；正文与标题差距 ≥ 2 号。"),
    ("字体", "全片 1 种字体，最多 2 种；没有混用衬线与无衬线。"),
    ("颜色", "强调色 ≤ 2 种；没有整段变色；红色只用于负面/警示。"),
    ("投影", "所有字幕开启黑色投影；高噪背景加了 0.08 描边，室内没有加。"),
    ("强调密度", "“强”级强调（变色+放大/动画）全片 ≤ 5 处；没有一句同时叠 3 种手段。"),
    ("动画", "动画只出现在段落首条；入场 300ms、出场 500ms；种类 ≤ 2 种。"),
    ("一致性", "同一类型段落的字号、位置、颜色完全一致；没有中途改样式。"),
    ("模板", "花字模板只用于片头/片尾/转场；一条视频 ≤ 1 个模板；未叠加手工动画。"),
]

for i, (k, v) in enumerate(checks, 1):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(2)
    p.paragraph_format.space_after = Pt(2)
    p.paragraph_format.left_indent = Cm(0.3)
    run_font(p.add_run("□  "), 11, False, NAVY)
    run_font(p.add_run(f"{k}　"), 9.8, True, NAVY)
    run_font(p.add_run(v), 9.8, False, None)

para("")
para("落地顺序建议：", size=10.5, bold=True, color=NAVY, before=8, after=3)
num_item(1, [("先在剪映里把 5 套预设各建一条样式", True, None), ("（表 8-1），存成常用，避免每次重调。", False, None)])
num_item(2, [("拿一条旧台本做 A/B", True, None), ("：同一段口播分别套 A、C 两套预设导出，对比完播与评论，确认哪套更适合你的账号。", False, None)])
num_item(3, [("把检查清单固化成交付动作", True, None), ("：导出前 5 分钟过一遍第九章，重点看字数、CPS、位置、强调密度。", False, None)])

callout("规范是默认值，不是铁律",
        "表中的字号、位置、CPS 来自现有工程的中位数，能保证“不出错”；如果某条视频有明确的视觉目标"
        "（例如新品发布要更强的冲击），可以突破 1–2 个参数，但不要同时打破三条以上，否则会回到“每期都不一样”的状态。")

# =====================================================================
# 10 APPENDIX
# =====================================================================
doc.add_page_break()
doc.add_heading("十、附录", level=1)

doc.add_heading("附录 A　工程清单与逐工程参数", level=2)
rows = json.load(open(r"D:\字幕模版获取\extract\segments.json", encoding="utf-8"))
type_map = {
    "10月21日": "产品细节", "4月23日": "剧情演绎", "4月8日": "剧情演绎", "6月17日": "干货教学",
    "7月11日": "招商发布", "7月11日 (1)": "干货教学", "9月10日": "干货教学", "9月10日-副本": "干货教学",
    "9月11日杨总": "剧情演绎", "9月16日 (2)": "活动促销", "9月18日 - 副本": "干货教学",
    "9月22日 (4)": "活动促销", "9月30日": "多类型", "9月5日": "测评挑战",
}
import collections


def med(vals):
    vals = sorted(v for v in vals if v is not None)
    return vals[len(vals) // 2] if vals else None


by_draft = collections.defaultdict(list)
for r in rows:
    by_draft[r["draft"]].append(r)

app_rows = []
for d in sorted(by_draft):
    rs = by_draft[d]
    fs = med([r["font_size"] for r in rs])
    ys = med([r["y"] for r in rs])
    fonts = collections.Counter(r["font_title"] for r in rs if r["font_title"]).most_common(1)
    colored = round(100 * sum(1 for r in rs if r["text_color"].lower() not in ("#ffffff", "")) / len(rs))
    anim = round(100 * sum(1 for r in rs if r["animations"]) / len(rs))
    app_rows.append([d, type_map.get(d, "—"), str(len(rs)),
                     f"{fs:g}" if fs else "—",
                     f"{ys:.2f}" if ys is not None else "—",
                     fonts[0][0] if fonts else "—",
                     f"{colored}%", f"{anim}%"])

add_table(
    ["工程", "类型", "条数", "字号中位", "y 中位", "主字体", "变色率", "动画率"],
    app_rows,
    widths=[3.6, 2.4, 1.6, 1.9, 1.7, 3.2, 1.6, 1.6],
    font_size=8.2,
    align_center_cols=[2, 3, 4, 5, 6, 7],
)
caption("表 A-1　14 个工程的逐项参数。同一工程含多条时间线时合并统计。")

doc.add_heading("附录 B　强调色对照表", level=2)
add_table(
    ["色值", "名称", "出现次数", "工程中的典型用法"],
    [
        ["#FFFFFF", "纯白", "796", "默认字色"],
        ["#FFF589", "淡黄", "214", "关键词、身份、频道识别色（测评类几乎全用）"],
        ["#FE8A80", "珊瑚红", "32", "否定、提醒、“新手第一次”"],
        ["#F9F3C4", "米黄", "21", "柔和强调、补充说明"],
        ["#FFBF17", "金黄", "19", "序号、身份、CTA"],
        ["#FFDE00", "亮黄", "16", "价格、折扣、活动时间"],
        ["#FE5252", "警示红", "10", "“不允许”“调货”等负面语境"],
        ["#B71C1C", "深红", "9", "强警示"],
        ["#469DF3", "蓝", "8", "信息条、链接提示"],
    ],
    widths=[2.6, 2.2, 2.2, 9.4],
    font_size=8.5,
    align_center_cols=[2],
)
caption("表 B-1　工程中出现过的强调色。单条视频建议只取 1–2 种。")

doc.add_heading("附录 C　字段与术语", level=2)
add_table(
    ["术语 / 字段", "解释"],
    [
        ["CPS", "Characters Per Second，每秒字数，衡量字幕阅读压力"],
        ["y 值", "clip.transform.y，−1～1，相对画面半高；画面纵向位置 = 50% + y×50%"],
        ["底部字幕区", "y ≤ −0.15，画面 57.5% 以下"],
        ["中部信息区", "−0.15 < y < 0.15"],
        ["顶部标题区", "y ≥ 0.15"],
        ["font_size", "剪映字号，相对单位，跨分辨率一致"],
        ["template.json", "剪映写入 Timelines/<ID>/ 的明文时间线快照"],
        ["material_animations", "文字片段的入场/出场动画容器，type 为 in/out"],
        ["text_template_subtitle", "花字模板字幕材质，样式由模板资源包控制"],
    ],
    widths=[4.4, 11.8],
    font_size=8.5,
)
caption("表 C-1　术语表。")

para("")
para("— 文档结束 —", size=9, color=GREY, align=WD_ALIGN_PARAGRAPH.CENTER, before=10)

# ---------- normalize OOXML child order (Word is strict about it) ----------
ORDER = {
    "tblPr": ["tblStyle", "tblpPr", "tblOverlap", "bidiVisual", "tblStyleRowBandSize",
              "tblStyleColBandSize", "tblW", "jc", "tblCellSpacing", "tblInd", "tblBorders",
              "shd", "tblLayout", "tblCellMar", "tblLook", "tblCaption", "tblDescription"],
    "trPr": ["cnfStyle", "divId", "gridBefore", "gridAfter", "wBefore", "wAfter",
             "cantSplit", "trHeight", "tblHeader", "tblCellSpacing", "jc", "hidden"],
    "tcPr": ["cnfStyle", "tcW", "gridSpan", "hMerge", "vMerge", "tcBorders", "shd",
             "noWrap", "tcMar", "textDirection", "tcFitText", "vAlign", "hideMark"],
}
for t in doc.tables:
    for el in t._tbl.iter():
        tag = el.tag.split("}")[-1]
        if tag in ORDER:
            idx = {name: i for i, name in enumerate(ORDER[tag])}
            children = list(el)
            children.sort(key=lambda c: idx.get(c.tag.split("}")[-1], 99))
            for c in children:
                el.remove(c)
            for c in children:
                el.append(c)

doc.save(r"D:\字幕模版获取\剪映字幕呈现规范.docx")
print("saved")

