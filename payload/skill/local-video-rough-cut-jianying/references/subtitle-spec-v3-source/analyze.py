# -*- coding: utf-8 -*-
import json, collections, statistics, re

rows = json.load(open(r"D:\字幕模版获取\extract\segments.json", encoding="utf-8"))

TYPE_MAP = {
    ("6月17日", "8F1E3D34-726C-4197-B663-C0665A12997A"): "干货教学",
    ("7月11日 (1)", "A2B44418-1F36-46dc-8FE8-D011A743C9B7"): "干货教学",
    ("9月10日", "52FD20D6-0A88-4829-96F5-A7FF7ADB3DDC"): "干货教学",
    ("9月10日", "92E6790A-AD66-46bf-A0C2-53A2B1CBC3E3"): "干货教学",
    ("9月10日", "BCFCD284-0873-4dd1-A5BA-FB66BBBF4878"): "干货教学",
    ("9月10日", "C0FF194B-8B15-4101-BAE6-5305D690DB8D"): "干货教学",
    ("9月10日", "E3FCDE3D-C1FC-4b4c-956D-4090A290094F"): "干货教学",
    ("9月10日-副本", "48569EAE-5F06-489f-A44B-74D56DBE47F7"): "干货教学",
    ("9月10日-副本", "C6901B12-5403-4b39-9E9E-A7C63DDC3F66"): "干货教学",
    ("9月18日 - 副本", "42D16E27-C604-413a-A4D3-6B77FDE95809"): "干货教学",
    ("4月23日", "EB66886E-98F8-40a7-8089-EF292FB67BC5"): "剧情演绎",
    ("4月8日", "43977914-88F0-4990-9C0B-2AC022232184"): "剧情演绎",
    ("9月11日杨总", "3758242B-8011-42f9-90E4-3F35F55040F5"): "剧情演绎",
    ("7月11日", "344BB881-F287-42f7-B160-514B9C5AC8DF"): "招商发布",
    ("7月11日", "A2A861AC-2A4C-4e1a-BABA-6DD18837F682"): "招商发布",
    ("9月22日 (4)", "EE046D3C-28A5-4df8-82CB-6B85B4C60CC4"): "活动促销",
    ("9月16日 (2)", "FC315B19-696C-44c7-8879-6B7190389752"): "活动促销",
    ("9月30日", "297F617C-CECA-44f0-9CBB-77A86180CF0C"): "活动促销",
    ("9月30日", "BA79C7E1-BB07-435d-ABF4-4149F569D972"): "品牌情感",
    ("9月30日", "D382E8D7-0EEA-4898-8CBA-186FB059E6FA"): "品牌情感",
    ("9月30日", "2A95AA9B-23B0-4438-B83C-0149FE2728D0"): "模板特效",
    ("9月5日", "A8F897AB-29FC-475d-AE7C-02E97205B74C"): "测评挑战",
    ("9月5日", "A84A9B80-A8AE-46ff-A00F-706FFB091709"): "测评挑战",
    ("10月21日", "147EED61-9A5B-4984-A87A-694FD06016C6"): "产品细节",
}
for r in rows:
    r["type"] = TYPE_MAP.get((r["draft"], r["timeline"]), "未分类")


def pct(x, n):
    return round(100.0 * x / n, 1) if n else 0.0


def q(vals, p):
    if not vals:
        return None
    vals = sorted(vals)
    k = (len(vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (k - lo), 2)


def stats(rs):
    n = len(rs)
    fs = [r["font_size"] for r in rs if r["font_size"]]
    chars = [r["chars"] for r in rs]
    ys = [r["y"] for r in rs if r["y"] is not None]
    xs = [r["x"] for r in rs if r["x"] is not None]
    dur = [r["dur_s"] for r in rs]
    colors = collections.Counter(r["text_color"].lower() for r in rs)
    white = colors.get("#ffffff", 0)
    colored = n - white - colors.get("", 0)
    anim = [r for r in rs if r["animations"]]
    return {
        "n": n,
        "font_size_median": q(fs, .5),
        "font_size_p10": q(fs, .1),
        "font_size_p90": q(fs, .9),
        "font_size_min": min(fs) if fs else None,
        "font_size_max": max(fs) if fs else None,
        "font_size_mode": collections.Counter(fs).most_common(3),
        "chars_median": q(chars, .5),
        "chars_p10": q(chars, .1),
        "chars_p90": q(chars, .9),
        "chars_min": min(chars) if chars else None,
        "chars_max": max(chars) if chars else None,
        "chars_buckets": {
            "<=4": sum(1 for c in chars if c <= 4),
            "5-8": sum(1 for c in chars if 5 <= c <= 8),
            "9-12": sum(1 for c in chars if 9 <= c <= 12),
            "13-16": sum(1 for c in chars if 13 <= c <= 16),
            ">16": sum(1 for c in chars if c > 16),
        },
        "dur_median": q(dur, .5),
        "dur_p90": q(dur, .9),
        "y_median": q(ys, .5),
        "y_p10": q(ys, .1),
        "y_p90": q(ys, .9),
        "screen_below_center_pct": round(-q(ys, .5) * 50, 1) if ys else None,
        "x_median": q(xs, .5),
        "white_pct": pct(white, n),
        "colored_pct": pct(colored, n),
        "color_top": colors.most_common(6),
        "shadow_pct": pct(sum(1 for r in rs if r["shadow"]), n),
        "stroke_pct": pct(sum(1 for r in rs if r["border_color"]), n),
        "bg_pct": pct(sum(1 for r in rs if r["background_color"]), n),
        "scale_gt1_pct": pct(sum(1 for r in rs if (r["scale"] or 1) > 1.05), n),
        "anim_pct": pct(len(anim), n),
        "anim_dur_median": q([a["duration_ms"] for r in anim for a in r["animations"]], .5),
        "fonts": collections.Counter(r["font_title"] for r in rs if r["font_title"]).most_common(4),
        "template_pct": pct(sum(1 for r in rs if r["template_name"]), n),
        "align": collections.Counter(r["alignment"] for r in rs).most_common(3),
    }


by_type = collections.defaultdict(list)
for r in rows:
    by_type[r["type"]].append(r)

report = {"types": {}, "drafts": {}, "anims": {}, "colors_by_type": {}}
for t, rs in by_type.items():
    report["types"][t] = stats(rs)
    c = collections.Counter()
    for r in rs:
        for a in r["animations"]:
            c[(a["type"], a["name"], a["duration_ms"])] += 1
    report["anims"][t] = [{"dir": d, "name": nm, "ms": ms, "n": c2} for (d, nm, ms), c2 in c.most_common(12)]

by_draft = collections.defaultdict(list)
for r in rows:
    by_draft[r["draft"]].append(r)
for d, rs in by_draft.items():
    report["drafts"][d] = stats(rs)

# semantic categories (exclude template subtitles)
SEM = {
    "数字/价格/时间": r"\d|元|折|号|岁|平|份|天",
    "疑问句": r"[?？]|吗|呢|什么|怎么|多少|哪|是不是|对不对",
    "否定/转折": r"不是|不|别|但是|却|反而|而是|其实|只是",
    "序号/清单": r"第[一二三四五六七八九十]|^\d+[\.、]|首先|其次|最后",
    "行动号召": r"关注|点赞|留言|评论|转发|到店|私信|收藏|进店|来找我|评论区",
    "对比结构": r"不是.{0,12}(是|而是)|而是|与其|不如|既.*又",
}
plain = [r for r in rows if not r["template_name"] and r["material_type"] != "text_template_subtitle"]
sem_report = {}
for name, pat in SEM.items():
    sel = [r for r in plain if re.search(pat, r["text"])]
    n = len(sel)
    if not n:
        continue
    # compare against per-draft median font size for relative size
    big = 0
    for r in sel:
        rs = by_draft[r["draft"]]
        med = q([x["font_size"] for x in rs if x["font_size"]], .5) or 0
        if r["font_size"] and med and r["font_size"] > med * 1.15:
            big += 1
    sem_report[name] = {
        "n": n,
        "share_pct": pct(n, len(plain)),
        "colored_pct": pct(sum(1 for r in sel if r["text_color"].lower() not in ("#ffffff", "")), n),
        "anim_pct": pct(sum(1 for r in sel if r["animations"]), n),
        "bigger_pct": pct(big, n),
        "stroke_pct": pct(sum(1 for r in sel if r["border_color"]), n),
        "median_chars": q([r["chars"] for r in sel], .5),
        "sample": [r["text"] for r in sel[:3]],
    }
report["semantic"] = sem_report
report["plain_n"] = len(plain)
report["total"] = len(rows)

json.dump(report, open(r"D:\字幕模版获取\extract\report.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok")
