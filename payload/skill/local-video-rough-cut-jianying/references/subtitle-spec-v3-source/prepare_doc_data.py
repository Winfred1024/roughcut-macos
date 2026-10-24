# -*- coding: utf-8 -*-
import json, collections

rows = json.load(open(r"D:\字幕模版获取\extract\segments.json", encoding="utf-8"))
rep = json.load(open(r"D:\字幕模版获取\extract\report.json", encoding="utf-8"))
rep2 = json.load(open(r"D:\字幕模版获取\extract\report2.json", encoding="utf-8"))

tm = {
 ("6月17日","8F1E3D34-726C-4197-B663-C0665A12997A"):"干货教学",("7月11日 (1)","A2B44418-1F36-46dc-8FE8-D011A743C9B7"):"干货教学",
 ("9月10日","52FD20D6-0A88-4829-96F5-A7FF7ADB3DDC"):"干货教学",("9月10日","92E6790A-AD66-46bf-A0C2-53A2B1CBC3E3"):"干货教学",
 ("9月10日","BCFCD284-0873-4dd1-A5BA-FB66BBBF4878"):"干货教学",("9月10日","C0FF194B-8B15-4101-BAE6-5305D690DB8D"):"干货教学",
 ("9月10日","E3FCDE3D-C1FC-4b4c-956D-4090A290094F"):"干货教学",("9月10日-副本","48569EAE-5F06-489f-A44B-74D56DBE47F7"):"干货教学",
 ("9月10日-副本","C6901B12-5403-4b39-9E9E-A7C63DDC3F66"):"干货教学",("9月18日 - 副本","42D16E27-C604-413a-A4D3-6B77FDE95809"):"干货教学",
 ("4月23日","EB66886E-98F8-40a7-8089-EF292FB67BC5"):"剧情演绎",("4月8日","43977914-88F0-4990-9C0B-2AC022232184"):"剧情演绎",
 ("9月11日杨总","3758242B-8011-42f9-90E4-3F35F55040F5"):"剧情演绎",("7月11日","344BB881-F287-42f7-B160-514B9C5AC8DF"):"招商发布",
 ("7月11日","A2A861AC-2A4C-4e1a-BABA-6DD18837F682"):"招商发布",("9月22日 (4)","EE046D3C-28A5-4df8-82CB-6B85B4C60CC4"):"活动促销",
 ("9月16日 (2)","FC315B19-696C-44c7-8879-6B7190389752"):"活动促销",("9月30日","297F617C-CECA-44f0-9CBB-77A86180CF0C"):"活动促销",
 ("9月30日","BA79C7E1-BB07-435d-ABF4-4149F569D972"):"品牌情感",("9月30日","D382E8D7-0EEA-4898-8CBA-186FB059E6FA"):"品牌情感",
 ("9月30日","2A95AA9B-23B0-4438-B83C-0149FE2728D0"):"模板特效",("9月5日","A8F897AB-29FC-475d-AE7C-02E97205B74C"):"测评挑战",
 ("9月5日","A84A9B80-A8AE-46ff-A00F-706FFB091709"):"测评挑战",("10月21日","147EED61-9A5B-4984-A87A-694FD06016C6"):"产品细节",
}
for r in rows:
    r["type"] = tm.get((r["draft"], r["timeline"]), "未分类")
    r["zone"] = "底部" if (r["y"] or 0) <= -0.15 else ("中部" if (r["y"] or 0) < 0.15 else "顶部")

D = {}
D["total"] = len(rows)
D["drafts"] = sorted(set(r["draft"] for r in rows))
D["timelines"] = len(set((r["draft"], r["timeline"]) for r in rows))
D["font_dist"] = collections.Counter(r["font_size"] for r in rows if r["font_size"]).most_common(10)
D["color_dist"] = collections.Counter((r["text_color"] or "未指定").lower() for r in rows).most_common(10)
D["chars_buckets"] = {
    "1-4字": sum(1 for r in rows if r["chars"] <= 4),
    "5-8字": sum(1 for r in rows if 5 <= r["chars"] <= 8),
    "9-12字": sum(1 for r in rows if 9 <= r["chars"] <= 12),
    "13-16字": sum(1 for r in rows if 13 <= r["chars"] <= 16),
    "17字以上": sum(1 for r in rows if r["chars"] > 16),
}
D["longest"] = [{"t": r["text"], "n": r["chars"], "draft": r["draft"]} for r in sorted(rows, key=lambda x: -x["chars"])[:6]]
D["shortest"] = [{"t": r["text"], "n": r["chars"]} for r in rows if r["chars"] <= 2][:8]
D["anim_total"] = sum(1 for r in rows if r["animations"])
D["anim_by_dir"] = collections.Counter(a["type"] for r in rows for a in r["animations"]).most_common()
D["anim_names"] = collections.Counter(a["name"] for r in rows for a in r["animations"]).most_common(10)
D["type_n"] = {t: sum(1 for r in rows if r["type"] == t) for t in ["干货教学","剧情演绎","招商发布","活动促销","品牌情感","测评挑战","产品细节","模板特效"]}
D["zone"] = rep2["zone"]
D["type_zone"] = rep2["type_zone"]
D["cps"] = rep2["cps"]
D["bottom_overall"] = rep2["bottom_overall"]
D["colors_sem"] = rep2["color_semantics"]
D["semantic"] = rep["semantic"]
D["anims_by_type"] = rep["anims"]
D["type_stats"] = rep["types"]

json.dump(D, open(r"D:\字幕模版获取\extract\doc_data.json", "w", encoding="utf-8"), ensure_ascii=False, indent=1)
print("ok", D["total"], D["timelines"])
