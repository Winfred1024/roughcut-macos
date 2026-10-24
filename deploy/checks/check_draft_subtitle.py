# -*- coding: utf-8 -*-
"""字幕链路自检：把草稿里的文本轨升级成剪映「字幕」并当场校验。

    <jyenv\\python.exe> check_draft_subtitle.py <草稿目录> <skill\\scripts 目录>

必须 ok=true，否则说明 scripts\\subtitle_module.py 与 pyJianYingDraft 版本不配套，
用户拿不到剪映的「字幕」面板（只能拿到「文本」面板）。
"""
import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    draft_dir, scripts = Path(sys.argv[1]), Path(sys.argv[2])
    sys.path.insert(0, str(scripts))
    out = {"draft_dir": str(draft_dir), "ok": False}
    try:
        from subtitle_module import promote_draft_to_subtitles, verify_subtitle_draft

        rep = promote_draft_to_subtitles(draft_dir)
        out["promoted"] = getattr(rep, "promoted", None)
        out["group_id"] = getattr(rep, "group_id", None)
        ver = verify_subtitle_draft(draft_dir)
        out["subtitle_materials"] = ver.get("subtitle_materials")
        out["failed_checks"] = [c for c in ver.get("checks", []) if not c.get("ok")]
        out["ok"] = bool(ver.get("ok"))
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
