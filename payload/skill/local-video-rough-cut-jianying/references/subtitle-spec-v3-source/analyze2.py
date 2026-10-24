# -*- coding: utf-8 -*-
import json, collections, statistics, re

rows = json.load(open(r"D:\字幕模版获取\extract\segments.json", encoding="utf-8"))
rep = json.load(open(r"D:\字幕模版获取\extract\report.json", encoding="utf-8"))
for r in rows:
    r["type"] = next((t for t in rep["types"] if (r["draft"], r["timeline"]) in [(k[0], k[1]) for k in []]), None)
# re-apply type map from analyze.py by reading report types via draft+timeline mapping file
tm = {}
for t, st in rep["types"].items():
    pass
# rebuild mapping from analyze.py constants
import importlib.util
spec = importlib.util.spec_from_file_location("an", r"D:\字幕模版获取\analyze.py")

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
    r["cps"] = round(r["chars"] / r["dur_s"], 2) if r["dur_s"] else None
    y = r["y"]
    if y is None:
        zone = "未设"
    elif y <= -0.15:
        zone = "底部字幕区"
    elif y < 0.15:
        zone = "中部"
    else:
        zone = "顶部标题区"
    r["zone"] = zone


def q(vals, p):
    vals = sorted(v for v in vals if v is not None)
    if not vals:
        return None
    k = (len(vals) - 1) * p
    lo, hi = int(k), min(int(k) + 1, len(vals) - 1)
    return round(vals[lo] + (vals[hi] - vals[lo]) * (k - lo), 2)


out = {"zone": {}, "type_zone": {}, "cps": {}, "color_semantics": {}}
for z in ["底部字幕区", "中部", "顶部标题区", "未设"]:
    rs = [r for r in rows if r["zone"] == z]
    if not rs:
        continue
    out["zone"][z] = {
        "n": len(rs),
        "share_pct": round(100 * len(rs) / len(rows), 1),
        "font_median": q([r["font_size"] for r in rs], .5),
        "font_p10": q([r["font_size"] for r in rs], .1),
        "font_p90": q([r["font_size"] for r in rs], .9),
        "y_median": q([r["y"] for r in rs], .5),
        "scale_gt1_pct": round(100 * sum(1 for r in rs if (r["scale"] or 1) > 1.05) / len(rs), 1),
        "anim_pct": round(100 * sum(1 for r in rs if r["animations"]) / len(rs), 1),
    }

for t in rep["types"]:
    rs = [r for r in rows if r["type"] == t]
    out["type_zone"][t] = {z: sum(1 for r in rs if r["zone"] == z) for z in ["底部字幕区", "中部", "顶部标题区", "未设"]}

bottom = [r for r in rows if r["zone"] == "底部字幕区"]
out["bottom_overall"] = {
    "n": len(bottom),
    "font_median": q([r["font_size"] for r in bottom], .5),
    "font_mode": collections.Counter(r["font_size"] for r in bottom if r["font_size"]).most_common(5),
    "chars_median": q([r["chars"] for r in bottom], .5),
    "chars_p10": q([r["chars"] for r in bottom], .1),
    "chars_p90": q([r["chars"] for r in bottom], .9),
    "chars_max": max(r["chars"] for r in bottom),
    "cps_median": q([r["cps"] for r in bottom], .5),
    "cps_p10": q([r["cps"] for r in bottom], .1),
    "cps_p90": q([r["cps"] for r in bottom], .9),
    "dur_median": q([r["dur_s"] for r in bottom], .5),
    "y_median": q([r["y"] for r in bottom], .5),
    "y_p10": q([r["y"] for r in bottom], .1),
    "y_p90": q([r["y"] for r in bottom], .9),
    "x_nonzero_pct": round(100 * sum(1 for r in bottom if abs(r["x"] or 0) > 0.05) / len(bottom), 1),
    "multi_line_pct": round(100 * sum(1 for r in bottom if r["n_lines"] > 1) / len(bottom), 1),
    "colored_pct": round(100 * sum(1 for r in bottom if r["text_color"].lower() not in ("#ffffff", "")) / len(bottom), 1),
    "shadow_pct": round(100 * sum(1 for r in bottom if r["shadow"]) / len(bottom), 1),
}

for t in rep["types"]:
    rs = [r for r in rows if r["type"] == t and r["zone"] == "底部字幕区"]
    if not rs:
        continue
    out["cps"][t] = {
        "n": len(rs),
        "chars_median": q([r["chars"] for r in rs], .5),
        "chars_p10": q([r["chars"] for r in rs], .1),
        "chars_p90": q([r["chars"] for r in rs], .9),
        "cps_median": q([r["cps"] for r in rs], .5),
        "dur_median": q([r["dur_s"] for r in rs], .5),
    }

# what text gets colored
for color in ["#fff589", "#fe8a80", "#ffbf17", "#ffde00", "#f9f3c4", "#fe5252"]:
    sel = [r["text"] for r in rows if r["text_color"].lower() == color]
    out["color_semantics"][color] = {"n": len(sel), "examples": sel[:12]}

json.dump(out, open(r"D:\字幕模版获取\extract\report2.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok")
