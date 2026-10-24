# -*- coding: utf-8 -*-
"""部署后自检（不需要任何用户素材）。

    python deploy\\verify.py                 # 或 deploy\\verify.cmd
    python deploy\\verify.py --sample D:\\test\\某条素材.MOV    # 再补一个真人声的 ASR 校验

检查项：
  A 环境快照（setup\\check_env.py）
  B 文档里还有没有旧机器路径
  C ffmpeg / ffprobe
  D 合成样片（1080x1920）+ ffprobe 探针
  E 草稿生成（微秒单位 / 两轨）
  F 字幕升级链路（type=subtitle + group_id + words）
  G ASR 模型加载与推理
  H 剪映是否装了（只警告）
  I 草稿根目录可写

退出码 0 = 全部必需项通过；1 = 有失败项（看 [FAIL] 后面的「怎么修」）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile
from pathlib import Path

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BUNDLE = Path(__file__).resolve().parent.parent
DEPLOY = BUNDLE / "deploy"
CHECKS = DEPLOY / "checks"
STALE_PATTERNS = ["E:\\auto_cut\\tools", "E:\\草稿\\JianyingPro Drafts",
                  "C:\\Users\\lr286", "E:\\字幕规范提取"]

results: list[dict] = []

HINTS = {
    "check_env": "缺必需项：按上面列出的项补（多半是剪映没装 / 草稿目录没建）。",
    "stale": "skill 文档里还有旧机器路径：删掉这个 skill 目录，重跑 deploy\\install.py。",
    "ffmpeg": "重跑 install.py 第 4 步；或 --use-ffmpeg 指向现成 ffmpeg.exe 所在目录。",
    "sample": "ffmpeg 造样片失败：确认 tool_root\\ffmpeg\\ffmpeg.exe 能 `-version`。",
    "probe": "ffprobe 探针失败：确认 tool_root\\ffmpeg\\ffprobe.exe 存在且可执行。",
    "draft": "草稿生成失败：确认剪映已从托盘退出、草稿目录无 .locked，然后重跑第 5 步。",
    "subtitle": "字幕链路失败：jyenv 里 pyJianYingDraft 版本不对（要 0.3.0），重装 requirements-jy.txt。",
    "asr": "ASR 失败：确认 asrenv 装有 faster-whisper 1.2.1 / ctranslate2 4.8.x，模型目录有 model.bin。",
    "draft_rw": "草稿目录不可写：剪映设置里换一个可写目录，再 --draft-root 重跑 install.py。",
}


def add(name: str, ok: bool, detail: str = "", level: str = "必需", hint: str = "") -> None:
    results.append({"check": name, "level": level, "ok": bool(ok),
                    "detail": detail, "hint": hint})
    mark = "OK  " if ok else ("FAIL" if level == "必需" else "--  ")
    print(f"[{mark}] {name}" + (f"  {detail}" if detail else ""), flush=True)


def last_line(text: str, n: int = 300) -> str:
    lines = [ln for ln in (text or "").strip().splitlines() if ln.strip()]
    return lines[-1][:n] if lines else ""


def py_run(pyexe, script, *extra, env=None, timeout=1800):
    cmd = [str(pyexe), str(script)] + [str(x) for x in extra]
    return subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", env=env, timeout=timeout)


def load_report() -> dict:
    p = DEPLOY / "install-report.json"
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def find_tool_root(rep: dict) -> Path:
    for c in (rep.get("tool_root"), os.environ.get("CUT_TOOLS"),
              r"E:\auto_cut\tools", r"D:\auto_cut\tools",
              str(Path(os.environ.get("LOCALAPPDATA", "")) / "auto_cut" / "tools")):
        if c and Path(c).exists():
            return Path(c)
    return Path(rep.get("tool_root") or r"E:\auto_cut\tools")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="粗剪 skill 部署后自检")
    ap.add_argument("--sample", help="一条真人声素材，用于补跑真 ASR 校验")
    ap.add_argument("--skill-dir", help="skill 安装目录（默认从 install-report.json 取）")
    ap.add_argument("--draft-root", help="草稿根目录（默认从 install-report.json 取）")
    args = ap.parse_args(argv)

    rep = load_report()
    tool_root = find_tool_root(rep)
    skill_dir = Path(args.skill_dir) if args.skill_dir else Path(
        rep.get("skill_dir") or (Path.home() / ".agents" / "skills" / "local-video-rough-cut-jianying"))
    draft_root = Path(args.draft_root) if args.draft_root else Path(
        rep.get("draft_root") or (Path.home() / "JianyingPro Drafts"))
    jyenv = Path(rep.get("jyenv") or tool_root / "jyenv" / "Scripts" / "python.exe")
    asrenv = Path(rep.get("asrenv") or tool_root / "asrenv" / "Scripts" / "python.exe")
    model = Path(rep.get("model") or tool_root / "models" / "faster-whisper-large-v3-turbo")
    ffmpeg_dir = Path(rep.get("ffmpeg") or tool_root / "ffmpeg")

    print("=" * 78)
    print(f"粗剪 skill 自检    包：{BUNDLE}")
    print(f"  skill  : {skill_dir}")
    print(f"  工具链 : {tool_root}")
    print(f"  草稿   : {draft_root}")
    print("=" * 78)

    # A 环境快照
    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               CUT_TOOLS=str(tool_root), CUT_DRAFT_ROOT=str(draft_root))
    r = py_run(sys.executable, skill_dir / "setup" / "check_env.py", "--json", env=env)
    out_text = (r.stdout or "") + (r.stderr or "")
    ok_env = r.returncode == 0
    env_detail = "必需项齐全"
    if not ok_env:
        # 「剪映专业版」没装不该卡住整条草稿链路（H 项单独作为可选检查）
        missing_line = next((ln for ln in out_text.splitlines() if "缺少必需项" in ln), "")
        missing = [x.strip() for x in missing_line.split("：", 1)[-1].split("、") if x.strip()] if missing_line else []
        soft = {"剪映专业版", "草稿根目录"}
        if missing and set(missing) <= soft:
            ok_env = True
            env_detail = "剪映/草稿目录待用户补（不阻塞草稿生成）"
        else:
            env_detail = "见下方输出里的「缺少必需项」"
    add("A 环境快照 check_env", ok_env, env_detail, hint=HINTS["check_env"])
    if not ok_env:
        print("-" * 78)
        print(out_text.strip())
        print("-" * 78)

    # B 旧路径残留
    stale = []
    for f in ("SKILL.md", r"references\env-and-pitfalls.md", r"setup\README.md"):
        p = skill_dir / f
        if not p.exists():
            continue
        text = p.read_text(encoding="utf-8", errors="replace")
        stale += [f"{f}: {pat}" for pat in STALE_PATTERNS
                  if pat in text and pat not in {str(tool_root), str(draft_root)}]
    add("B 文档无旧机器路径", not stale, "; ".join(stale) if stale else "", hint=HINTS["stale"])

    # C ffmpeg
    ff = ffmpeg_dir / "ffmpeg.exe"
    fp = ffmpeg_dir / "ffprobe.exe"
    ok_ff = False
    ver = ""
    if ff.exists() and fp.exists():
        try:
            result = subprocess.run([str(ff), "-version"], capture_output=True, text=True, timeout=60)
            out = result.stdout.splitlines()
            ver = out[0].split("Copyright")[0].strip() if out else ""
            ok_ff = result.returncode == 0 and bool(out)
        except Exception as e:  # noqa: BLE001
            ver = str(e)
    add("C ffmpeg / ffprobe", ok_ff, ver or f"缺 {ff}", hint=HINTS["ffmpeg"])

    # D 合成样片 + 探针
    sample = Path(tempfile.gettempdir()) / "cut_smoke_sample.mp4"
    ok_sample = False
    if ok_ff:
        r = py_run(sys.executable, CHECKS / "make_sample.py", ff, sample, env=env)
        ok_sample = r.returncode == 0
        add("D1 合成测试样片", ok_sample, last_line((r.stdout or "") + (r.stderr or "")),
            hint=HINTS["sample"])
    ok_probe = False
    probe_out = ""
    if ok_sample and jyenv.exists():
        r = py_run(jyenv, skill_dir / "setup" / "smoke" / "smoke_probe.py", sample, env=env)
        probe_out = (r.stdout or "") + (r.stderr or "")
        ok_probe = r.returncode == 0 and "canvas 1080 1920" in probe_out
        add("D2 ffprobe 探针（竖拍 1080x1920）", ok_probe, last_line(probe_out), hint=HINTS["probe"])

    # E 草稿生成（微秒 / 两轨）
    ok_draft = False
    draft_dir = draft_root / "smoke_01"
    if ok_sample and jyenv.exists():
        r = py_run(jyenv, skill_dir / "setup" / "smoke" / "smoke_draft.py", sample, env=env)
        out = (r.stdout or "") + (r.stderr or "")
        ok_draft = r.returncode == 0 and "dur_us 3000000" in out
        add("E 草稿生成（微秒 + 视频/字幕两轨）", ok_draft, last_line(out, 400), hint=HINTS["draft"])

    # F 字幕链路
    ok_sub = False
    if ok_draft and jyenv.exists():
        r = py_run(jyenv, CHECKS / "check_draft_subtitle.py", draft_dir,
                   skill_dir / "scripts", env=env)
        ok_sub = r.returncode == 0
        add("F 字幕链路（type=subtitle / group_id / words）", ok_sub,
            last_line((r.stdout or "") + (r.stderr or "")), hint=HINTS["subtitle"])

    if not ok_sample:
        add("D2 视频探针", False, "前置样片生成失败，未执行", hint=HINTS["probe"])
    elif not jyenv.exists():
        add("D2 视频探针", False, "缺 jyenv", hint=HINTS["probe"])
    if not ok_sample or not jyenv.exists():
        add("E 草稿生成", False, "前置条件不满足，未执行", hint=HINTS["draft"])
    if not ok_draft or not jyenv.exists():
        add("F 字幕链路", False, "前置草稿生成失败，未执行", hint=HINTS["subtitle"])

    # G ASR
    ok_asr = False
    if asrenv.exists() and (model / "model.bin").exists():
        r = py_run(asrenv, CHECKS / "check_asr.py", model)
        ok_asr = r.returncode == 0
        add("G ASR 模型加载 + 推理", ok_asr, last_line((r.stdout or "") + (r.stderr or "")),
            hint=HINTS["asr"])
    else:
        add("G ASR 模型加载 + 推理", False,
            f"缺 {asrenv} 或 {model / 'model.bin'}", hint=HINTS["asr"])

    if args.sample and ok_asr:
        r = py_run(asrenv, skill_dir / "setup" / "smoke" / "smoke_asr.py", args.sample, env=env)
        ok_real = r.returncode == 0 and "language zh" in (r.stdout or "")
        add("G2 真素材 ASR（人声）", ok_real, last_line((r.stdout or "") + (r.stderr or "")),
            level="可选", hint="确认素材里确实有人声；没有就用 --sample 换一条。")

    # H 剪映
    jy = rep.get("jianying")
    if not jy:
        for base in (Path(os.environ.get("LOCALAPPDATA", "")) / "JianyingPro" / "Apps",
                     Path(r"C:\Program Files\JianyingPro"),
                     Path(r"C:\Program Files (x86)\JianyingPro")):
            if base.exists():
                hits = list(base.glob("**/JianyingPro.exe"))
                if hits:
                    jy = str(hits[-1])
                    break
    add("H 剪映专业版", bool(jy), str(jy or "未安装：草稿能生成，但没法在剪映里打开/精剪"), level="可选")

    # I 草稿目录可写
    ok_rw, rw_detail = False, ""
    try:
        draft_root.mkdir(parents=True, exist_ok=True)
        probe = draft_root / ".dsh_write_probe"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        ok_rw = True
    except Exception as e:  # noqa: BLE001
        rw_detail = str(e)
    add("I 草稿根目录可写", ok_rw, "" if ok_rw else f"不可写：{draft_root} {rw_detail}",
        hint=HINTS["draft_rw"])

    # 汇总
    required = [r for r in results if r["level"] == "必需"]
    failed = [r for r in required if not r["ok"]]
    print("-" * 78)
    if failed:
        print(f"结果：{len(failed)}/{len(required)} 个必需项未通过")
        for f in failed:
            print(f"  [FAIL] {f['check']}" + (f"  {f['detail']}" if f["detail"] else ""))
            hint = f.get("hint") or ""
            if hint:
                print(f"         怎么修：{hint}")
    else:
        print("结果：全部必需项通过 —— 这台机器可以干活了。")
        print("下一步：把技能列表刷新（新开一轮会话），对它说「用 local-video-rough-cut-jianying 帮我粗剪视频，"
              "素材和台本放在 <目录>」。")
    print("-" * 78)

    out = DEPLOY / "verify-report.json"
    out.write_text(json.dumps({
        "ok": not failed,
        "checked_at": __import__("time").strftime("%Y-%m-%d %H:%M:%S"),
        "paths": {"skill_dir": str(skill_dir), "tool_root": str(tool_root),
                  "draft_root": str(draft_root), "model": str(model)},
        "results": results,
    }, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告：{out}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(main())
