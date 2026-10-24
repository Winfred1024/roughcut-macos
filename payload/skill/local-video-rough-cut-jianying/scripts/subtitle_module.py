# -*- coding: utf-8 -*-
"""字幕模块：把自动化粗剪草稿里的「文本」升级为剪映的「字幕」，让剪映出现图一那种字幕面板。

背景（本机实测，2026-10-21）
--------------------------------
剪映专业版把时间轴上的文字片段分成两类，判定依据是文本素材（`materials.texts[i]`）的 `type` 字段：

    文本素材 type = "text"      -> 选中时左侧是「文本」面板：基础 / 气泡 / 花字 + 字体 / 字号 / 样式 / 颜色 …
    文本素材 type = "subtitle"  -> 选中时左侧是「字幕」面板：字幕 1..N 列表（可搜索）+ 朗读 + 数字人 + 整体样式

自动粗剪以前用的是 `TextStyle(...)` 默认值，导出的素材 `type` 是 `"text"`，所以剪映只给「文本」面板，
没有字幕列表，也就无法像图一那样做整体修改。

剪映自己「识别字幕」产出的素材除了 `type: "subtitle"` 之外还带：
    add_type            = 1
    group_id            = "Auto_<毫秒时间戳>"   （同一次识别出来的字幕共用一个 group_id，面板按组列成一条列表）
    recognize_text      = 该条字幕文本
    words               = {"start_time": [...], "end_time": [...], "text": [...]}（逐字时间，毫秒，相对片段头）
    text_color          = "#FFFFFF"
    line_spacing        = 0.02
    check_flag          = 39
    caption_template_info / lyrics_template / combo_info / current_words / subtitle_keywords（空壳）
    initial_scale = 1, layer_weight = 1, border_width = 0.08

本模块做两件事：
1. `subtitle_style()` / `SUBTITLE_TRACK`：给 pyJianYingDraft 生成脚本用，直接产 `type="subtitle"` 的片段；
2. `promote_draft_to_subtitles()`：草稿已经生成（明文 `draft_content.json`）后做后处理，
   把所有文本素材补齐成剪映「识别字幕」的字段结构，并统一 group_id。

用法
----
生成时（推荐，两步都走）：

    import pyJianYingDraft as draft
    from subtitle_module import SUBTITLE_TRACK, subtitle_style
    script.append_tracks([
        draft.TrackSpec(draft.TrackType.video, "视频"),
        draft.TrackSpec(draft.TrackType.text, SUBTITLE_TRACK),
    ])
    script.add_segment(draft.TextSegment(text, trange(...), style=subtitle_style(size=11)), SUBTITLE_TRACK)
    script.save()
    promote_draft_to_subtitles(draft_dir)      # 必做：补 group_id / add_type / recognize_text / words

生成后补刀（草稿还是明文时）：

    python subtitle_module.py "E:\\草稿\\JianyingPro Drafts\\某个草稿"

注意：剪映打开过的草稿 `draft_content.json` 会被加密成密文，那时本模块无法再改，只能重新生成。
"""
from __future__ import annotations

import argparse
import json
import os
import tempfile
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

SUBTITLE_TRACK = "字幕"
"""字幕轨道的推荐名称（只是给人看的，剪映判定靠素材 type，不靠轨道名）。"""

SUBTITLE_MATERIAL_TYPE = "subtitle"
TEXT_MATERIAL_TYPE = "text"

# 剪映「识别字幕」素材里的空壳字段，缺了不一定会崩，但补齐后和剪映自己产出的结构一致，最稳
_EMPTY_TEMPLATE = {"path": "", "resource_id": ""}


# --------------------------------------------------------------------------------------
# 1. 生成期：给 pyJianYingDraft 用的样式
# --------------------------------------------------------------------------------------
def subtitle_style(**kwargs) -> Any:
    """返回一个 `auto_wrapping=True` 的 TextStyle。

    pyJianYingDraft 的 `TextSegment.export_material()` 里：
        "type": "subtitle" if self.style.auto_wrapping else "text"
    所以 `auto_wrapping=True` 是让素材一开始就是字幕类型的唯一开关。
    其余参数原样透传给 TextStyle。
    """
    import pyJianYingDraft as draft

    kwargs.pop("auto_wrapping", None)
    return draft.TextStyle(auto_wrapping=True, **kwargs)


# --------------------------------------------------------------------------------------
# 2. 后处理：把明文草稿里的文本升级成字幕
# --------------------------------------------------------------------------------------
@dataclass
class PromoteReport:
    draft_path: str
    group_id: str
    text_materials: int = 0
    promoted: int = 0
    already_subtitle: int = 0
    tracks: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)

    def as_dict(self) -> Dict[str, Any]:
        return {
            "draft_path": self.draft_path,
            "group_id": self.group_id,
            "text_materials": self.text_materials,
            "promoted": self.promoted,
            "already_subtitle": self.already_subtitle,
            "tracks": self.tracks,
            "warnings": self.warnings,
        }


def _draft_file(draft_dir: Path) -> Path:
    info = draft_dir / 'draft_info.json'
    return info if sys.platform == 'darwin' and info.exists() else draft_dir / 'draft_content.json'


def _read_draft(draft_dir: Path) -> Dict[str, Any]:
    dc = _draft_file(draft_dir)
    if not dc.exists():
        raise FileNotFoundError(f"找不到 {dc}")
    raw = dc.read_text(encoding="utf-8-sig")
    if not raw.lstrip().startswith("{"):
        raise ValueError(
            f"{dc} 不是明文 JSON（剪映打开过就会加密）。"
            "只能用原来的生成脚本重新生成草稿，再在剪映打开之前跑本模块。"
        )
    return json.loads(raw)


def _write_draft(draft_dir: Path, data: Dict[str, Any]) -> None:
    dc = _draft_file(draft_dir)
    out = json.dumps(data, ensure_ascii=False)
    fd, tmp = tempfile.mkstemp(prefix='.draft-', dir=draft_dir)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            f.write(out)
        os.replace(tmp, dc)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    # 有些草稿目录还有 .bak / template-2.tmp 之类的残留明文，一起同步，避免剪映读到旧副本
    mirrors = [dc.with_suffix('.json.bak'), draft_dir / 'template-2.tmp']
    if dc.name == 'draft_info.json':
        mirrors.append(draft_dir / 'draft_content.json')
    for extra in mirrors:
        if extra.exists() and extra != dc:
            try:
                if extra.read_text(encoding="utf-8-sig").lstrip().startswith("{"):
                    extra.write_text(out, encoding="utf-8")
            except Exception:
                pass


def _material_timeranges(data: Dict[str, Any]) -> Dict[str, Tuple[int, int]]:
    """material_id -> (target start, duration)，单位微秒。子片段时间轴上的位置上。"""
    out: Dict[str, Tuple[int, int]] = {}
    for track in data.get("tracks", []):
        for seg in track.get("segments", []):
            mid = seg.get("material_id")
            tr = seg.get("target_timerange") or {}
            if mid and tr:
                out.setdefault(mid, (int(tr.get("start", 0)), int(tr.get("duration", 0))))
    return out


def _word_times(text: str, duration_us: int) -> Dict[str, List[Any]]:
    """按字数把片段时长均分，产出剪映 words 结构（毫秒，相对片段头）。英文/数字按词切。"""
    tokens = [t for t in _tokenize(text)]
    if not tokens:
        return {"start_time": [], "end_time": [], "text": []}
    total_ms = max(int(duration_us // 1000), len(tokens))
    weights = [1.0 if len(t) > 1 or _is_cjk(t) else 0.5 for t in tokens]
    span = sum(weights) or 1.0
    starts: List[int] = []
    ends: List[int] = []
    acc = 0.0
    prev_end = 0
    for w in weights:
        s = int(round(total_ms * acc / span))
        acc += w
        e = int(round(total_ms * acc / span))
        starts.append(max(s, prev_end))
        ends.append(max(e, s + 1))
        prev_end = ends[-1]
    return {"start_time": starts, "end_time": ends, "text": tokens}


def _is_cjk(ch: str) -> bool:
    return "\u4e00" <= ch <= "\u9fff"


def _tokenize(text: str) -> Iterable[str]:
    """切词用于 words 结构：汉字按单字，连续非汉字按串。

    关键约束：所有 token 直接拼接必须**原样等于** text（空格挂在前一个 token 上），
    否则剪映按 words 还原字幕时会与 content.text 不一致。
    """
    tokens: List[str] = []
    buf = ""
    for ch in text:
        if ch.isspace():
            if buf:
                buf += ch          # 空格并入前一个 token，保证拼接后仍是原文
            elif tokens:
                tokens[-1] += ch
            else:
                buf = ch
            continue
        if _is_cjk(ch):
            if buf:
                tokens.append(buf)
                buf = ""
            tokens.append(ch)
        else:
            buf += ch
    if buf:
        tokens.append(buf)
    return tokens


def _first_fill_color(content: Dict[str, Any]) -> Optional[str]:
    try:
        styles = content.get("styles") or []
        solid = styles[0]["fill"]["content"]["solid"]["color"]
        r, g, b = [max(0.0, min(1.0, float(x))) for x in solid[:3]]
        return "#%02X%02X%02X" % (round(r * 255), round(g * 255), round(b * 255))
    except Exception:
        return None


def _first_font_size(content: Dict[str, Any]) -> Optional[int]:
    try:
        return int(round(float(content["styles"][0]["size"])))
    except Exception:
        return None


def promote_draft_to_subtitles(
    draft_dir: str | Path,
    *,
    group_id: Optional[str] = None,
    prefer_subtitle_tracks_only: bool = True,
    rename_tracks: bool = True,
    enforce_line_wrap: bool = True,
    line_max_width: float = 0.82,
    dry_run: bool = False,
) -> PromoteReport:
    """把草稿内所有文本素材升级成剪映「字幕」素材。

    Args:
        draft_dir: 草稿目录（含明文 draft_content.json）。
        group_id: 字幕组 id；同一组在剪映字幕面板里是一条列表。默认按毫秒时间戳新建 `Auto_<ms>`。
        prefer_subtitle_tracks_only: True 时只处理字幕轨（轨道名含「字幕」）里的文本；False 处理全部文本。
        rename_tracks: 把被升级的文本轨统一改名为「字幕」，方便在剪映里辨认。
        enforce_line_wrap: 强制打开「自动换行」（force_apply_line_max_width / line_feed / line_max_width），
            否则字幕在剪映里不折行、横向溢出画布。
        line_max_width: 自动换行的最大行宽占画布比例。
        dry_run: 只统计不落盘。
    """
    draft_dir = Path(draft_dir)
    data = _read_draft(draft_dir)
    group = group_id or "Auto_%d" % int(time.time() * 1000)
    report = PromoteReport(draft_path=str(draft_dir), group_id=group)

    tracks = data.get("tracks", [])
    texts = data.get("materials", {}).get("texts", [])
    report.text_materials = len(texts)
    if not texts:
        raise ValueError(f"{draft_dir} 里没有文本素材，没有可升级的字幕。")

    timeranges = _material_timeranges(data)

    # 找出要升级的 material_id
    target_ids: set[str] = set()
    for track in tracks:
        if track.get("type") != "text":
            continue
        name = str(track.get("name") or "")
        if prefer_subtitle_tracks_only and "字幕" not in name:
            continue
        report.tracks.append(name or "(未命名)")
        for seg in track.get("segments", []):
            mid = seg.get("material_id")
            if mid:
                target_ids.add(mid)
    if not target_ids and prefer_subtitle_tracks_only:
        raise ValueError("没有找到字幕轨；如需转换全部文本，请显式指定 --all-text-tracks")
    if not target_ids:
        for track in tracks:
            if track.get("type") == "text":
                report.tracks.append(str(track.get("name") or "(未命名)"))
                for seg in track.get("segments", []):
                    mid = seg.get("material_id")
                    if mid:
                        target_ids.add(mid)

    for mat in texts:
        if mat.get("id") not in target_ids:
            continue
        content_raw = mat.get("content") or "{}"
        try:
            content = json.loads(content_raw)
        except Exception:
            report.warnings.append(f"素材 {mat.get('id')} 的 content 不是 JSON，跳过")
            continue
        text = str(content.get("text") or "")

        if mat.get("type") == SUBTITLE_MATERIAL_TYPE:
            report.already_subtitle += 1
        report.promoted += 1

        mat["type"] = SUBTITLE_MATERIAL_TYPE
        mat["add_type"] = 1
        mat["group_id"] = group
        mat["recognize_text"] = text
        mat.setdefault("check_flag", 39)
        mat.setdefault("line_spacing", 0.02)
        mat.setdefault("initial_scale", 1)
        mat.setdefault("layer_weight", 1)
        mat.setdefault("border_width", 0.08)
        mat.setdefault("caption_template_info", dict(_EMPTY_TEMPLATE))
        mat.setdefault("lyrics_template", dict(_EMPTY_TEMPLATE))
        mat.setdefault("combo_info", {})
        mat.setdefault("current_words", {})
        mat.setdefault("subtitle_keywords", {})
        mat.setdefault("base_content", json.dumps(content, ensure_ascii=False))
        colour = _first_fill_color(content)
        if colour:
            mat.setdefault("text_color", colour)
        size = _first_font_size(content)
        if size:
            mat.setdefault("font_size", size)

        start, dur = timeranges.get(mat["id"], (0, 0))
        if dur <= 0:
            report.warnings.append(f"素材 {mat['id']} 在时间轴上找不到片段，words 用 1000ms 兜底")
            dur = 1_000_000
        words = _word_times(text, dur)
        if "".join(words["text"]) != text:
            report.warnings.append(f"素材 {mat['id']} 的 words 拼接与原文不一致，已丢弃 words")
            words = {"start_time": [], "end_time": [], "text": []}
        mat["words"] = words

        if enforce_line_wrap:
            mat["force_apply_line_max_width"] = True
            mat["line_max_width"] = line_max_width
            mat["line_feed"] = 1

    if rename_tracks and not dry_run:
        for track in tracks:
            if track.get("type") != "text":
                continue
            if prefer_subtitle_tracks_only and "字幕" not in str(track.get("name") or ""):
                continue
            if track.get("name") != SUBTITLE_TRACK:
                track["name"] = SUBTITLE_TRACK

    if not dry_run:
        _write_draft(draft_dir, data)
    return report


# --------------------------------------------------------------------------------------
# 3. 校验
# --------------------------------------------------------------------------------------
def verify_subtitle_draft(draft_dir: str | Path) -> Dict[str, Any]:
    """检查草稿里的文字素材是不是真的「字幕」结构，返回报告并给每项 ok/原因。"""
    draft_dir = Path(draft_dir)
    data = _read_draft(draft_dir)
    texts = data.get("materials", {}).get("texts", [])
    checks: List[Dict[str, Any]] = []

    def add(name: str, ok: bool, detail: str = "") -> None:
        checks.append({"check": name, "ok": bool(ok), "detail": detail})

    add("有文本素材", bool(texts), f"{len(texts)} 条")
    types = sorted({m.get("type") for m in texts})
    add("素材 type 全是 subtitle", types == [SUBTITLE_MATERIAL_TYPE], f"types={types}")
    groups = sorted({m.get("group_id") for m in texts if m.get("type") == SUBTITLE_MATERIAL_TYPE})
    add("字幕组 group_id 唯一", len(groups) <= 1, f"group_id={groups}")
    add("add_type=1", all(m.get("add_type") == 1 for m in texts if m.get("type") == SUBTITLE_MATERIAL_TYPE), "")
    missing_words = [m["id"] for m in texts if m.get("type") == SUBTITLE_MATERIAL_TYPE and not (m.get("words") or {}).get("text")]
    add("每条都有 words 逐字时间", not missing_words, f"缺 {len(missing_words)} 条")
    no_recognize = [m["id"] for m in texts if m.get("type") == SUBTITLE_MATERIAL_TYPE and not m.get("recognize_text")]
    add("每条都有 recognize_text", not no_recognize, f"缺 {len(no_recognize)} 条")

    text_tracks = [t for t in data.get("tracks", []) if t.get("type") == "text"]
    add("存在文本轨", bool(text_tracks), ", ".join(str(t.get("name")) for t in text_tracks))

    no_wrap = [m["id"] for m in texts
               if m.get("type") == SUBTITLE_MATERIAL_TYPE and not m.get("force_apply_line_max_width")]
    add("字幕已开自动换行", not no_wrap, f"缺 {len(no_wrap)} 条")

    joined_ok = True
    for m in texts:
        if m.get("type") != SUBTITLE_MATERIAL_TYPE:
            continue
        words = (m.get("words") or {}).get("text") or []
        try:
            original = json.loads(m.get("content") or "{}").get("text", "")
        except Exception:
            original = ""
        if words and "".join(words) != original:
            joined_ok = False
            break
    add("words 拼接等于字幕原文", joined_ok, "")

    return {
        "draft_path": str(draft_dir),
        "ok": all(c["ok"] for c in checks),
        "checks": checks,
        "subtitle_materials": sum(1 for m in texts if m.get("type") == SUBTITLE_MATERIAL_TYPE),
        "group_id": groups[0] if groups else None,
    }


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def _main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description="把剪映草稿的文本轨升级成字幕轨（出现字幕面板）")
    ap.add_argument("draft_dir", help="草稿目录（含明文 draft_content.json）")
    ap.add_argument("--group-id", default=None, help="指定字幕组 id，默认 Auto_<毫秒时间戳>")
    ap.add_argument("--all-text-tracks", action="store_true", help="连非字幕轨的文本一起升级")
    ap.add_argument("--keep-track-names", action="store_true", help="不改轨道名")
    ap.add_argument("--dry-run", action="store_true", help="只看统计不写文件")
    ap.add_argument("--line-max-width", type=float, default=0.82, help="自动换行最大行宽比例，默认 0.82")
    ap.add_argument("--no-line-wrap", action="store_true", help="不改动自动换行相关字段")
    ap.add_argument("--verify", action="store_true", help="只校验不修改")
    args = ap.parse_args(argv)

    if args.verify:
        rep = verify_subtitle_draft(args.draft_dir)
        print(json.dumps(rep, ensure_ascii=False, indent=2))
        return 0 if rep["ok"] else 1

    rep = promote_draft_to_subtitles(
        args.draft_dir,
        group_id=args.group_id,
        prefer_subtitle_tracks_only=not args.all_text_tracks,
        rename_tracks=not args.keep_track_names,
        enforce_line_wrap=not args.no_line_wrap,
        line_max_width=args.line_max_width,
        dry_run=args.dry_run,
    )
    print(json.dumps(rep.as_dict(), ensure_ascii=False, indent=2))
    if not args.dry_run:
        ver = verify_subtitle_draft(args.draft_dir)
        print(json.dumps(ver, ensure_ascii=False, indent=2))
        return 0 if ver["ok"] else 1
    return 0


if __name__ == "__main__":
    sys.exit(_main())
