# -*- coding: utf-8 -*-
"""Extract subtitle segment data from JianyingPro draft template.json files."""
import json, glob, os, re, csv, sys

ROOT = r"D:\草稿\JianyingPro Drafts"
OUT = r"D:\字幕模版获取\extract"
os.makedirs(OUT, exist_ok=True)


def load(p):
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def parse_content(m):
    raw = m.get("content") or ""
    txt, styles = "", []
    if raw.strip().startswith("{"):
        try:
            c = json.loads(raw)
            txt = c.get("text", "")
            styles = c.get("styles", []) or []
        except Exception:
            txt = m.get("recognize_text", "")
    else:
        txt = raw
    if not txt:
        txt = m.get("recognize_text", "") or m.get("merge_content", "")
    return txt, styles


def style_info(m, styles):
    st = styles[0] if styles else {}
    fill = ((st.get("fill") or {}).get("content") or {}).get("solid") or {}
    color = fill.get("color")
    if isinstance(color, list):
        color = "#" + "".join("%02X" % round(max(0, min(1, c)) * 255) for c in color[:3])
    else:
        color = m.get("text_color", "")
    return {
        "style_size": st.get("size"),
        "style_color": color,
        "style_font_path": (st.get("font") or {}).get("path", ""),
        "has_stroke": bool(st.get("strokes")),
        "has_shadow_style": bool(st.get("shadows")),
    }


def anim_info(refs, allm):
    items = []
    for r in refs or []:
        kind, it = allm.get(r, (None, None))
        if kind == "material_animations":
            for a in it.get("animations") or []:
                items.append({
                    "type": a.get("type", ""),
                    "name": a.get("name", ""),
                    "duration_ms": round((a.get("duration") or 0) / 1000, 1),
                    "category_id": a.get("category_id", ""),
                    "resource_id": a.get("resource_id", ""),
                })
    return items


rows = []
drafts = []
for d in sorted(os.listdir(ROOT)):
    dpath = os.path.join(ROOT, d)
    if not os.path.isdir(dpath):
        continue
    tls = glob.glob(os.path.join(dpath, "Timelines", "*", "template.json"))
    if not tls:
        continue
    samples = []
    start_idx = len(rows)
    for tl in tls:
        try:
            j = load(tl)
        except Exception as e:
            continue
        mats = j.get("materials", {})
        allm = {}
        for k, v in mats.items():
            if isinstance(v, list):
                for it in v:
                    if isinstance(it, dict) and it.get("id"):
                        allm[it["id"]] = (k, it)
        texts = {}
        for coll in ("texts", "text_templates"):
            for t in mats.get(coll, []) or []:
                if isinstance(t, dict) and "id" in t:
                    texts[t["id"]] = t
        canvas = j.get("canvas_config") or {}
        for tr in j.get("tracks", []):
            if tr.get("type") != "text":
                continue
            for s in tr.get("segments", []):
                m = texts.get(s.get("material_id"))
                if not m:
                    continue
                txt, styles = parse_content(m)
                txt = (txt or "").strip()
                if not txt:
                    continue
                si = style_info(m, styles)
                tr_ = s.get("target_timerange") or {}
                clip = s.get("clip") or {}
                tf = clip.get("transform") or {}
                sc = clip.get("scale") or {}
                lines = [ln for ln in txt.replace("\r", "").split("\n")]
                fonts = m.get("fonts") or []
                font_title = fonts[0].get("title", "") if fonts else ""
                anims = anim_info(s.get("extra_material_refs"), allm)
                rows.append({
                    "draft": d,
                    "timeline": os.path.basename(os.path.dirname(tl)),
                    "seg_id": s.get("id", ""),
                    "material_type": m.get("type", ""),
                    "start_s": round((tr_.get("start") or 0) / 1e6, 3),
                    "dur_s": round((tr_.get("duration") or 0) / 1e6, 3),
                    "text": txt,
                    "chars": len(txt.replace("\n", "")),
                    "n_lines": len(lines),
                    "line_chars": [len(x) for x in lines],
                    "font_size": m.get("font_size"),
                    "text_size": m.get("text_size"),
                    "font_title": font_title,
                    "font_path": m.get("font_path", ""),
                    "text_color": m.get("text_color", ""),
                    "alignment": m.get("alignment"),
                    "line_spacing": m.get("line_spacing"),
                    "letter_spacing": m.get("letter_spacing"),
                    "line_max_width": m.get("line_max_width"),
                    "x": tf.get("x"),
                    "y": tf.get("y"),
                    "scale": sc.get("x"),
                    "rotation": clip.get("rotation"),
                    "shadow": m.get("has_shadow"),
                    "shadow_alpha": m.get("shadow_alpha"),
                    "shadow_distance": m.get("shadow_distance"),
                    "shadow_angle": m.get("shadow_angle"),
                    "shadow_smoothing": m.get("shadow_smoothing"),
                    "border_width": m.get("border_width"),
                    "border_color": m.get("border_color", ""),
                    "border_alpha": m.get("border_alpha"),
                    "background_color": m.get("background_color", ""),
                    "background_style": m.get("background_style"),
                    "template_name": m.get("name", "") if m.get("type") == "text_template_subtitle" else "",
                    "template_resource_id": m.get("resource_id", "") if m.get("type") == "text_template_subtitle" else "",
                    "animations": anims,
                    "canvas_w": canvas.get("width"),
                    "canvas_h": canvas.get("height"),
                })
                if len(samples) < 8:
                    samples.append(txt)
    drafts.append({"draft": d, "timelines": len(tls), "rows": len(rows) - start_idx, "samples": samples})

with open(os.path.join(OUT, "segments.json"), "w", encoding="utf-8") as f:
    json.dump(rows, f, ensure_ascii=False, indent=1)
with open(os.path.join(OUT, "drafts.json"), "w", encoding="utf-8") as f:
    json.dump(drafts, f, ensure_ascii=False, indent=1)

cols = list(rows[0].keys()) if rows else []
with open(os.path.join(OUT, "segments.csv"), "w", encoding="utf-8-sig", newline="") as f:
    w = csv.DictWriter(f, fieldnames=cols)
    w.writeheader()
    for r in rows:
        w.writerow({k: (json.dumps(v, ensure_ascii=False) if isinstance(v, (list, dict)) else v) for k, v in r.items()})

print("segments:", len(rows), "drafts:", len(drafts))
