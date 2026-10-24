# -*- coding: utf-8 -*-
"""粗剪 skill 跨机部署安装器（Windows / 联网）。

一条命令把「skill + 工具链 + 运行环境」装到本机：

    python deploy\\install.py                 # 全自动（推荐先跑 deploy\\install.cmd）
    python deploy\\install.py --verify        # 装完顺手跑自检

它做 9 件事，全部幂等（可重复执行）：
  1. 校验包完整性（对照 manifest.json 的 sha256）
  2. 确保有 Python 3.12（没有就用 vendor\\python-3.12.10-amd64.exe 静默装）
  3. 定工具链根目录（默认 E:\\auto_cut\\tools，没有 E 盘则 %LOCALAPPDATA%\\auto_cut\\tools）
  4. 装 ffmpeg / ffprobe（没有就下载 gyan.dev 官方 release essentials）
  5. 建 jyenv（写草稿）并装 requirements-jy.txt
  6. 建 asrenv（ASR）并装 requirements-asr.txt
  7. 放 faster-whisper-large-v3-turbo 模型（包内 models\\ 有就拷，没有就从 HF 下）
  8. 把 skill 装到 %USERPROFILE%\\.agents\\skills\\ 并改写其中的本机路径表
  9. 生成 setup\\detected.json + deploy\\install-report.json

退出码：0 成功；1 失败（会打印「怎么修」）。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
import zipfile
from pathlib import Path

try:  # Windows 控制台默认 GBK，中文输出会炸
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

BUNDLE = Path(__file__).resolve().parent.parent          # 部署包根目录
DEPLOY = BUNDLE / "deploy"
PAYLOAD_SKILL = BUNDLE / "payload" / "skill" / "local-video-rough-cut-jianying"
VENDOR_PY = BUNDLE / "vendor" / "python-3.12.10-amd64.exe"
BUNDLE_MODEL = BUNDLE / "models" / "faster-whisper-large-v3-turbo"
SKILL_NAME = "local-video-rough-cut-jianying"
MODEL_NAME = "faster-whisper-large-v3-turbo"
HF_REPO = "mobiuslabsgmbh/faster-whisper-large-v3-turbo"
FFMPEG_URLS = [
    "https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip",
    "https://github.com/BtbN/FFmpeg-Builds/releases/latest/download/ffmpeg-master-latest-win64-gpl.zip",
]
MIRROR = "https://pypi.tuna.tsinghua.edu.cn/simple"
IS_WIN = os.name == "nt"

STALE_PATTERNS = [
    r"E:\auto_cut\tools",
    r"E:\草稿\JianyingPro Drafts",
    r"C:\Users\lr286",
    r"E:\字幕规范提取",
]


class Fail(Exception):
    """可预期的安装失败：打印 hint 后退出 1。"""

    def __init__(self, msg: str, hint: str = ""):
        super().__init__(msg)
        self.msg = msg
        self.hint = hint


def log(msg: str = "") -> None:
    print(msg, flush=True)


def head(n: int, total: int, title: str) -> None:
    log("")
    log(f"[{n}/{total}] {title}")


def run(cmd, *, cwd=None, timeout=None, check=True, quiet=False):
    cmd = [str(c) for c in cmd]
    if not quiet:
        log("    $ " + " ".join(cmd))
    r = subprocess.run(cmd, cwd=cwd, timeout=timeout, capture_output=True,
                       text=True, encoding="utf-8", errors="replace")
    if check and r.returncode != 0:
        tail = ((r.stdout or "") + "\n" + (r.stderr or "")).strip().splitlines()[-12:]
        raise Fail(f"命令失败（exit {r.returncode}）：{' '.join(cmd)}",
                   "\n".join(tail))
    return r


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# --------------------------------------------------------------------------------------
# 1. 包完整性
# --------------------------------------------------------------------------------------
def check_manifest(deep: bool = False) -> list[str]:
    mf = BUNDLE / "manifest.json"
    if not mf.exists():
        log("    ! 没有 manifest.json，跳过完整性校验（不影响安装）")
        return []
    data = json.loads(mf.read_text(encoding="utf-8"))
    problems = []
    optional_missing = []
    for item in data.get("files", []):
        rel = item["path"]
        p = BUNDLE / rel
        if not p.exists():
            # 模型可以被裁掉（精简版包）：缺了就从 HF 下，不算损坏
            if rel.startswith("models/"):
                optional_missing.append(rel)
                continue
            problems.append(f"缺文件：{rel}")
            continue
        if p.stat().st_size != item["size"]:
            problems.append(f"大小不符：{rel}（期望 {item['size']}，实际 {p.stat().st_size}）")
            continue
        # 大文件（模型/安装包）默认只比大小，省 30 秒
        if deep or item["size"] < 200 * 1024 * 1024:
            if sha256(p) != item["sha256"]:
                problems.append(f"sha256 不符：{rel}")
    if optional_missing:
        log(f"    ! 包内没有模型（{len(optional_missing)} 个文件）：第 7 步会从 HuggingFace 下载")
    if problems:
        for p in problems[:10]:
            log("    ! " + p)
        raise Fail(
            f"部署包不完整或有文件损坏（{len(problems)} 项）",
            "重新完整拷贝/解压部署包后再跑；不要只拷一部分。",
        )
    log(f"    OK  {len(data.get('files', []))} 个文件与 manifest 一致")
    return problems


# --------------------------------------------------------------------------------------
# 2. Python 3.12
# --------------------------------------------------------------------------------------
def _py312_ok(argv: list) -> bool:
    try:
        r = subprocess.run(argv + ["-c", "import sys;print('%d.%d' % sys.version_info[:2])"],
                           capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=120)
        return r.returncode == 0 and r.stdout.strip() == "3.12"
    except Exception:
        return False


def find_python312() -> list | None:
    cands: list[list] = []
    py = shutil.which("py")
    if py:
        cands.append([py, "-3.12"])
        cands.append([py, "-3"])
    for name in ("python3.12", "python"):
        w = shutil.which(name)
        if w:
            cands.append([w])
    local = Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "Python" / "Python312" / "python.exe"
    for p in (local, Path("C:/Python312/python.exe"), Path("C:/Program Files/Python312/python.exe")):
        if p.exists():
            cands.append([str(p)])
    for c in cands:
        if _py312_ok(c):
            return c
    return None


def ensure_python(args) -> list:
    argv = find_python312()
    if argv:
        log(f"    OK  Python 3.12：{argv[-1] if argv[-1] != '-3.12' else argv[0] + ' -3.12'}")
        return argv
    if args.no_download:
        raise Fail("没有 Python 3.12，且指定了 --no-download",
                   "手动安装 Python 3.12（勾 Add to PATH）后重跑。")
    if not VENDOR_PY.exists():
        raise Fail("没有 Python 3.12，且包里没有 vendor\\python-3.12.10-amd64.exe",
                   "从 python.org 下载 Python 3.12.x 安装（勾 Add python.exe to PATH）后重跑。")
    log(f"    未找到 3.12，静默安装 {VENDOR_PY.name}（约 1-2 分钟，无界面）…")
    run([str(VENDOR_PY), "/quiet", "InstallAllUsers=0", "PrependPath=0",
         "Include_test=0", "Include_pip=1", "Include_launcher=1"], timeout=1800)
    for _ in range(20):
        argv = find_python312()
        if argv:
            return argv
        time.sleep(3)
    raise Fail("Python 安装器跑完了但找不到 3.12",
               "手动运行 vendor\\python-3.12.10-amd64.exe（勾 Add to PATH），再重跑。")


# --------------------------------------------------------------------------------------
# 3. 工具链根目录 / 草稿目录 / 剪映
# --------------------------------------------------------------------------------------
def pick_tool_root(explicit: str | None) -> Path:
    if explicit:
        return Path(explicit).expanduser().resolve()
    env = os.environ.get("CUT_TOOLS")
    if env:
        return Path(env)
    prefs = [Path("E:/auto_cut/tools"), Path("D:/auto_cut/tools")]
    for p in prefs:
        try:
            if p.drive and Path(p.drive + "/").exists():
                return p
        except Exception:
            continue
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "auto_cut" / "tools"


def find_jianying() -> Path | None:
    cands: list[Path] = []
    apps = Path(os.environ.get("LOCALAPPDATA", "")) / "JianyingPro" / "Apps"
    if apps.exists():
        cands += list(apps.glob("*/JianyingPro.exe"))
    for base in (r"C:\Program Files\JianyingPro", r"C:\Program Files (x86)\JianyingPro"):
        p = Path(base) / "JianyingPro.exe"
        if p.exists():
            cands.append(p)

    def key(p: Path):
        nums = re.findall(r"\d+", p.parent.name)
        return (tuple(int(x) for x in nums[:4]) if nums else (0,))

    return max(cands, key=key) if cands else None


def pick_draft_root(explicit: str | None) -> tuple[Path, bool]:
    if explicit:  # 用户指定就照办，不存在则建
        p = Path(explicit).expanduser().resolve()
        created = not p.exists()
        p.mkdir(parents=True, exist_ok=True)
        return p, created
    cands = [os.environ.get("CUT_DRAFT_ROOT"),
             str(Path.home() / "JianyingPro Drafts"),
             str(Path.home() / "Videos" / "JianyingPro Drafts")]
    for drv in "CDEFGH":
        cands += [f"{drv}:/JianyingPro Drafts", f"{drv}:/草稿/JianyingPro Drafts",
                  f"{drv}:/剪映草稿/JianyingPro Drafts", f"{drv}:/视频/JianyingPro Drafts"]
    for c in cands:
        if c and Path(c).exists():
            return Path(c), False
    p = Path.home() / "JianyingPro Drafts"
    p.mkdir(parents=True, exist_ok=True)
    return p, True


# --------------------------------------------------------------------------------------
# 4. ffmpeg
# --------------------------------------------------------------------------------------
def _ffmpeg_ok(ffdir: Path) -> bool:
    ff = ffdir / "ffmpeg.exe"
    fp = ffdir / "ffprobe.exe"
    if not (ff.exists() and fp.exists()):
        return False
    try:
        r = subprocess.run([str(ff), "-version"], capture_output=True, text=True, timeout=60)
        return r.returncode == 0
    except Exception:
        return False


def _extract_ffmpeg(zip_path: Path, ffdir: Path) -> None:
    ffdir.mkdir(parents=True, exist_ok=True)
    wanted = {"ffmpeg.exe": ffdir / "ffmpeg.exe", "ffprobe.exe": ffdir / "ffprobe.exe"}
    got = set()
    with zipfile.ZipFile(zip_path) as zf:
        for name in zf.namelist():
            base = name.rsplit("/", 1)[-1].lower()
            if base in wanted and base not in got:
                with zf.open(name) as src, wanted[base].open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                got.add(base)
    if got != set(wanted):
        raise Fail(f"压缩包里没找到 ffmpeg.exe / ffprobe.exe（只找到 {sorted(got)}）",
                   "确认给的是 gyan.dev / BtbN 的 Windows 构建 zip。")


def _download(url: str, dst: Path) -> None:
    log(f"    下载 {url}")
    t0 = time.time()
    with urllib.request.urlopen(url, timeout=30) as r, dst.open("wb") as f:
        total = int(r.headers.get("Content-Length") or 0)
        done = 0
        last = 0
        while True:
            buf = r.read(1 << 20)
            if not buf:
                break
            f.write(buf)
            done += len(buf)
            if done - last > 40 << 20:
                last = done
                log(f"      {done / 1e6:.0f} / {total / 1e6:.0f} MB")
            # 卡住/太慢的源早点放弃，换下一个
            if total and time.time() - t0 > 90 and done < total * 0.25:
                raise TimeoutError(f"下载过慢（90 秒只下了 {done / 1e6:.0f}/{total / 1e6:.0f} MB）")


def ensure_ffmpeg(tool_root: Path, args) -> Path:
    ffdir = tool_root / "ffmpeg"
    if _ffmpeg_ok(ffdir):
        log(f"    OK  已存在 {ffdir}")
        return ffdir

    if args.use_ffmpeg:
        src = Path(args.use_ffmpeg)
        srcdir = src if src.is_dir() else src.parent
        ffdir.mkdir(parents=True, exist_ok=True)
        for name in ("ffmpeg.exe", "ffprobe.exe"):
            s = srcdir / name
            if not s.exists():
                raise Fail(f"--use-ffmpeg 指向的目录缺少 {name}：{srcdir}")
            shutil.copy2(s, ffdir / name)
    elif args.ffmpeg_zip:
        log(f"    从本地压缩包解出：{args.ffmpeg_zip}")
        _extract_ffmpeg(Path(args.ffmpeg_zip), ffdir)
    elif args.no_download:
        raise Fail("没有 ffmpeg，且指定了 --no-download",
                   "用 --ffmpeg-zip <本地zip> 或 --use-ffmpeg <目录> 指定现成的二进制。")
    else:
        tmp = Path(tempfile.gettempdir()) / "ffmpeg-build.zip"
        last_err = None
        for url in ([args.ffmpeg_url] if args.ffmpeg_url else FFMPEG_URLS):
            try:
                _download(url, tmp)
                _extract_ffmpeg(tmp, ffdir)
                last_err = None
                break
            except Exception as e:  # noqa: BLE001
                last_err = f"{url} -> {type(e).__name__}: {e}"
                log(f"    ! 这个源不行：{last_err}")
            finally:
                tmp.unlink(missing_ok=True)
        if last_err:
            raise Fail("ffmpeg 下载失败（所有源都试过了）",
                       f"{last_err}\n可以手动下载 ffmpeg Windows 构建 zip，然后 "
                       "python deploy\\install.py --ffmpeg-zip <zip路径>。")

    if not _ffmpeg_ok(ffdir):
        raise Fail(f"ffmpeg 落地后仍无法运行：{ffdir}")
    log(f"    OK  {ffdir}")
    return ffdir


# --------------------------------------------------------------------------------------
# 5/6. 两个 Python venv
# --------------------------------------------------------------------------------------
def _install_reqs(pyexe: Path, req: Path, args) -> None:
    base = [str(pyexe), "-m", "pip", "install", "--disable-pip-version-check",
            "--no-input", "-r", str(req)]
    if args.index:  # 用户显式给了源，直接用
        host = args.index.split("//")[-1].split("/")[0]
        r0 = run(base + ["-i", args.index, "--trusted-host", host], check=False, quiet=True)
        if r0.returncode != 0:
            tail = ((r0.stdout or "") + "\n" + (r0.stderr or "")).strip().splitlines()[-15:]
            raise Fail(f"pip 安装失败（指定源 {args.index}）", "\n".join(tail))
        return
    r = run(base, check=False, quiet=True)
    if r.returncode == 0:
        return
    log("    ! 官方 PyPI 失败，改走清华镜像重试…")
    host = MIRROR.split("//")[1].split("/")[0]
    r2 = run(base + ["-i", MIRROR, "--trusted-host", host], check=False, quiet=True)
    if r2.returncode != 0:
        tail = ((r2.stdout or "") + "\n" + (r2.stderr or "")).strip().splitlines()[-15:]
        raise Fail("pip 安装失败（官方源和镜像都失败）", "\n".join(tail))


def ensure_venv(tool_root: Path, name: str, req_name: str, py312: list, args) -> Path:
    venv = tool_root / name
    pyexe = venv / "Scripts" / "python.exe"
    if not pyexe.exists():
        log(f"    创建 {venv}")
        run(py312 + ["-m", "venv", str(venv)], timeout=900)
        pyexe = venv / "Scripts" / "python.exe"
    run([str(pyexe), "-m", "pip", "install", "-q", "-U", "pip",
         "--disable-pip-version-check"], check=False, timeout=900, quiet=True)
    log(f"    安装 {req_name}")
    _install_reqs(pyexe, DEPLOY / req_name, args)
    log(f"    OK  {pyexe}")
    return pyexe


def verify_jyenv(pyexe: Path) -> None:
    code = ("import pyJianYingDraft, pymediainfo, PIL;"
            "from pymediainfo import MediaInfo;"
            "print('pyJianYingDraft', getattr(pyJianYingDraft, '__version__', 'ok'));"
            "print('pymediainfo', pymediainfo.__version__, 'dll', MediaInfo.can_parse())")
    r = run([str(pyexe), "-c", code], quiet=True)
    log("    " + " | ".join(r.stdout.strip().splitlines()))
    if "False" in r.stdout.split("dll")[-1]:
        raise Fail("pymediainfo 找不到 MediaInfo.dll",
                   "装 MediaInfo 官方版（或重装 pymediainfo wheel），确认 dll 在 PATH。")


def verify_asrenv(pyexe: Path) -> None:
    code = ("import faster_whisper, ctranslate2, numpy, av;"
            "print('faster-whisper', faster_whisper.__version__, "
            "'ct2', ctranslate2.__version__, 'np', numpy.__version__, 'av', av.__version__)")
    r = run([str(pyexe), "-c", code], quiet=True)
    log("    " + r.stdout.strip())


# --------------------------------------------------------------------------------------
# 7. 模型
# --------------------------------------------------------------------------------------
def _model_ok(p: Path) -> bool:
    m = p / "model.bin"
    return m.exists() and m.stat().st_size > 1_000_000_000 and (p / "config.json").exists()


def ensure_model(tool_root: Path, asr_py: Path, args) -> Path:
    dst = tool_root / "models" / MODEL_NAME
    if _model_ok(dst):
        log(f"    OK  已存在 {dst}")
        return dst

    src = Path(args.model_from) if args.model_from else (BUNDLE_MODEL if _model_ok(BUNDLE_MODEL) else None)
    if src is None and (BUNDLE / "models").exists():
        for cand in (BUNDLE / "models").glob("*"):
            if cand.is_dir() and _model_ok(cand) and (cand / "model.bin").stat().st_size > 1_400_000_000:
                src = cand
                break
    if src is not None:
        if not _model_ok(src):
            raise Fail(f"--model-from 目录不像 faster-whisper 模型：{src}",
                       "需要 model.bin + config.json + tokenizer.json。")
        log(f"    从本地拷贝模型（约 1.6 GB，几十秒）…")
        dst.parent.mkdir(parents=True, exist_ok=True)
        if IS_WIN and shutil.which("robocopy"):
            r = subprocess.run(["robocopy", str(src), str(dst), "/E", "/NFL", "/NDL",
                                "/NJH", "/NJS", "/NP"], capture_output=True, text=True)
            if r.returncode > 7:
                raise Fail(f"robocopy 拷贝模型失败（exit {r.returncode}）", r.stdout[-800:])
        else:
            shutil.copytree(src, dst, dirs_exist_ok=True)
    elif args.no_download:
        raise Fail("没有 ASR 模型，且指定了 --no-download",
                   "把模型解压到 <包根>\\models\\，或用 --model-from <模型目录>。")
    else:
        log("    包内没有模型，从 HuggingFace 拉取（约 1.6 GB，视网速 5-40 分钟）…")
        code = ("from huggingface_hub import snapshot_download;"
                f"snapshot_download(repo_id={HF_REPO!r}, local_dir={str(dst)!r})")
        run([str(asr_py), "-c", code], timeout=None)

    if not _model_ok(dst):
        raise Fail(f"模型目录不完整：{dst}", "确认 model.bin 存在且 >1 GB。")
    log(f"    OK  {dst}  ({dst.joinpath('model.bin').stat().st_size / 1e9:.2f} GB)")
    return dst


# --------------------------------------------------------------------------------------
# 8. skill + 路径表改写
# --------------------------------------------------------------------------------------
def install_skill(skill_dir: Path) -> Path:
    if not (PAYLOAD_SKILL / "SKILL.md").exists():
        raise Fail(f"包内 skill 不完整：{PAYLOAD_SKILL}",
                   "重新完整解压部署包（payload\\skill\\ 不能缺）。")
    if skill_dir.exists():
        bak = skill_dir.with_name(skill_dir.name + ".bak-" + time.strftime("%Y%m%d-%H%M%S"))
        log(f"    目标已存在，先备份到 {bak.name}")
        if bak.exists():
            shutil.rmtree(bak, ignore_errors=True)
        try:
            skill_dir.rename(bak)
        except Exception as e:
            raise Fail(f"无法备份原 skill，已停止安装：{e}") from e
    skill_dir.parent.mkdir(parents=True, exist_ok=True)
    shutil.copytree(PAYLOAD_SKILL, skill_dir)
    log(f"    OK  {skill_dir}")
    return skill_dir


def rewrite_paths(skill_dir: Path, tool_root: Path, draft_root: Path,
                  python_version: str = "", model_mb: float | None = None,
                  jianying_version: str | None = None) -> dict:
    """把 skill 文档里的旧机器绝对路径换成本机路径。返回 {文件: 替换次数}。"""
    tool = str(tool_root).replace("/", "\\")
    draft = str(draft_root).replace("/", "\\")
    skill = str(skill_dir).replace("/", "\\")
    pyver = python_version or "3.12"

    def path_map(text: str) -> tuple[str, int]:
        n = 0
        # 先处理更具体的（顺序有意义）
        pairs = [
            # 分类台本库：未随包部署（源目录在本机也已不存在）
            ("（分类库在 `E:\\字幕规范提取\\全部草稿台本\\分类台本\\`）",
             "（分类库未随包部署，按 SKILL.md 第 7 步的 6 类自行归类）"),
            ("`E:\\字幕规范提取\\全部草稿台本\\分类台本\\`",
             "（未随包部署，按 SKILL.md 第 7 步的 6 类自行归类）"),
            # v2 规范源文件：旧机器上还有一份源目录，本包内副本即权威
            ("（源文件在 `E:\\字幕规范提取\\字幕呈现规范\\字幕呈现规范_v2_文本+动画.md`，"
             "改规则改源文件后覆盖副本；该源目录在本机已不存在，此副本即权威）",
             "（本副本即权威；改规则直接改这个文件，然后重新出片）"),
            ("E:\\字幕规范提取\\全部草稿台本\\分类台本\\",
             "（未随包部署，按 SKILL.md 第 7 步的 6 类自行归类）"),
            ("E:\\字幕规范提取\\全部草稿台本\\分类台本",
             "（未随包部署，按 SKILL.md 第 7 步的 6 类自行归类）"),
            ("E:\\字幕规范提取", "（未随包部署）"),
            # smoke 脚本：旧机器在 tools\smoke，本包里在 skill\setup\smoke
            (r"| smoke 脚本 | `E:\auto_cut\tools\smoke\smoke_{probe,draft,asr}.py` | 已跑通 |",
             f"| smoke 脚本 | `{skill}\\setup\\smoke\\smoke_{{probe,draft,asr}}.py` | 随 skill 一起部署 |"),
            # 低配备选模型：本包只带 turbo
            (r"| 模型 small | `E:\auto_cut\tools\models\faster-whisper-small` | model.bin 461.1 MB |",
             "| 模型 small | 未随包部署（可选，低配可自行下载） | — |"),
            # 版本信息：写实测值，别照抄旧机器
            ("Python 3.12.10 +", f"Python {pyver} +"),
            ("ctranslate2 4.8.2", "ctranslate2 4.8.3"),
            ("7.1-essentials_build", "7.x（安装器下载的官方构建）"),
            # 工具链与草稿目录
            (r"E:\auto_cut\tools", tool),
            (r"E:\草稿\JianyingPro Drafts", draft),
            # skill 自身位置
            (r"C:\Users\lr286\.agents\skills\local-video-rough-cut-jianying", skill),
            (r"$env:USERPROFILE\.agents\skills\local-video-rough-cut-jianying", skill),
        ]
        if model_mb:
            pairs.append(("model.bin 1542.9 MB", f"model.bin {model_mb:.0f} MB"))
        if jianying_version:
            pairs.append(("剪映专业版 11.6.0.14552", f"剪映专业版 {jianying_version}"))
        for old, new in pairs:
            if old in text:
                n += text.count(old)
                text = text.replace(old, new)
        return text, n

    targets = [skill_dir / "SKILL.md",
               skill_dir / "references" / "env-and-pitfalls.md",
               skill_dir / "setup" / "README.md"]
    report = {}
    for t in targets:
        if not t.exists():
            continue
        raw = t.read_text(encoding="utf-8")
        new, n = path_map(raw)
        if n:
            t.write_text(new, encoding="utf-8")
        report[str(t.relative_to(skill_dir))] = n
    return report


def check_stale(skill_dir: Path, allowed_roots=()) -> list[str]:
    """改写后还能不能在文档里找到旧机器路径。"""
    leftovers = []
    for t in (skill_dir / "SKILL.md",
              skill_dir / "references" / "env-and-pitfalls.md",
              skill_dir / "setup" / "README.md"):
        if not t.exists():
            continue
        text = t.read_text(encoding="utf-8")
        for pat in STALE_PATTERNS:
            if pat in text and pat not in {str(p) for p in allowed_roots}:
                leftovers.append(f"{t.relative_to(skill_dir)}: {pat}")
    return leftovers


# --------------------------------------------------------------------------------------
# 9. detected.json / 报告
# --------------------------------------------------------------------------------------
def write_detected(py312: list, skill_dir: Path, tool_root: Path, draft_root: Path) -> Path:
    env = dict(os.environ, PYTHONIOENCODING="utf-8",
               CUT_TOOLS=str(tool_root), CUT_DRAFT_ROOT=str(draft_root))
    r = subprocess.run(py312 + [str(skill_dir / "setup" / "check_env.py"), "--json"],
                       capture_output=True, text=True, encoding="utf-8",
                       errors="replace", env=env)
    log(r.stdout.rstrip())
    if r.returncode != 0:
        log("    ! check_env 报了缺项（见上），装完剪映/补依赖后重跑 verify")
    return skill_dir / "setup" / "detected.json"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="粗剪 skill 跨机部署安装器")
    ap.add_argument("--tool-root", help="工具链根目录（默认 E:\\auto_cut\\tools 或 %%LOCALAPPDATA%%\\auto_cut\\tools）")
    ap.add_argument("--skill-dir", help="skill 安装目录（默认 %%USERPROFILE%%\\.agents\\skills\\<name>）")
    ap.add_argument("--draft-root", help="剪映草稿根目录（默认自动探测）")
    ap.add_argument("--index", help="pip 镜像源（默认官方，失败自动切清华）")
    ap.add_argument("--ffmpeg-zip", help="本地 ffmpeg Windows 构建 zip，不联网下载")
    ap.add_argument("--ffmpeg-url", help="自定义 ffmpeg 构建 zip 下载地址（默认依次试 gyan.dev / BtbN）")
    ap.add_argument("--use-ffmpeg", help="已有 ffmpeg.exe 所在目录（或 exe 路径），直接复制")
    ap.add_argument("--model-from", help="本地 faster-whisper 模型目录")
    ap.add_argument("--no-download", action="store_true", help="禁止联网下载 ffmpeg / 模型")
    ap.add_argument("--no-model", action="store_true", help="跳过模型（只装草稿链路）")
    ap.add_argument("--all-harnesses", action="store_true",
                    help="同时装到 ~/.codex/skills 和 ~/.claude/skills（默认只装 ~/.agents/skills）")
    ap.add_argument("--verify", action="store_true", help="装完自动跑 deploy/verify.py")
    args = ap.parse_args(argv)

    t0 = time.time()
    log("=" * 78)
    log(f"粗剪 skill 部署安装器   包：{BUNDLE}")
    log("=" * 78)
    if not IS_WIN:
        log("[x] 本包只支持 Windows（剪映专业版 + 桌面路径假设）")
        return 1

    total = 9
    report: dict = {"bundle": str(BUNDLE), "started_at": time.strftime("%Y-%m-%d %H:%M:%S"),
                    "steps": []}

    try:
        head(1, total, "校验部署包完整性")
        check_manifest()

        head(2, total, "准备 Python 3.12")
        py312 = ensure_python(args)
        report["python312"] = " ".join(py312)

        head(3, total, "确定路径")
        tool_root = pick_tool_root(args.tool_root)
        tool_root.mkdir(parents=True, exist_ok=True)
        skill_dir = (Path(args.skill_dir).expanduser().resolve() if args.skill_dir
                     else Path.home() / ".agents" / "skills" / SKILL_NAME)
        draft_root, created = pick_draft_root(args.draft_root)
        jy = find_jianying()
        log(f"    工具链：{tool_root}")
        log(f"    skill ：{skill_dir}")
        log(f"    草稿  ：{draft_root}" + ("（新建，装好剪映后在设置里核对）" if created else ""))
        log(f"    剪映  ：{jy if jy else '未安装（草稿能生成，但没法在剪映里打开）'}")
        report.update(tool_root=str(tool_root), skill_dir=str(skill_dir),
                      draft_root=str(draft_root), jianying=str(jy) if jy else None)

        head(4, total, "安装 ffmpeg / ffprobe")
        ensure_ffmpeg(tool_root, args)
        report["ffmpeg"] = str(tool_root / "ffmpeg")

        head(5, total, "安装 jyenv（写剪映草稿）")
        jy_py = ensure_venv(tool_root, "jyenv", "requirements-jy.txt", py312, args)
        verify_jyenv(jy_py)
        report["jyenv"] = str(jy_py)

        head(6, total, "安装 asrenv（本地 ASR）")
        asr_py = ensure_venv(tool_root, "asrenv", "requirements-asr.txt", py312, args)
        verify_asrenv(asr_py)
        report["asrenv"] = str(asr_py)

        head(7, total, "准备 faster-whisper 模型")
        if args.no_model:
            log("    跳过（--no-model）")
            report["model"] = None
        else:
            model = ensure_model(tool_root, asr_py, args)
            report["model"] = str(model)

        head(8, total, "安装 skill 并改写本机路径")
        pyver = run(py312 + ["-c", "import sys;print('%d.%d.%d' % sys.version_info[:3])"],
                    quiet=True).stdout.strip() or "3.12"
        model_mb = None
        if report.get("model"):
            mp = Path(report["model"]) / "model.bin"
            if mp.exists():
                model_mb = mp.stat().st_size / 1e6
        jy_ver = jy.parent.name if (jy and re.fullmatch(r"\d+(\.\d+)+", jy.parent.name)) else None
        install_skill(skill_dir)
        repl = rewrite_paths(skill_dir, tool_root, draft_root, pyver, model_mb, jy_ver)
        for f, n in repl.items():
            log(f"    {f}: 替换 {n} 处路径")
        stale = check_stale(skill_dir, (tool_root, draft_root))
        if stale:
            log("    ! 仍有旧路径残留：" + "; ".join(stale))
        else:
            log("    OK  文档里已无旧机器路径")
        report["path_rewrite"] = repl
        report["stale_left"] = stale

        if args.all_harnesses:
            extra = []
            for rel in (".codex/skills", ".claude/skills"):
                d = Path.home() / rel / SKILL_NAME
                try:
                    install_skill(d)
                    rewrite_paths(d, tool_root, draft_root, pyver, model_mb, jy_ver)
                    extra.append(str(d))
                    log(f"    额外装到：{d}")
                except Exception as e:  # noqa: BLE001
                    log(f"    ! 额外装到 {d} 失败：{e}")
            report["extra_harnesses"] = extra

        head(9, total, "生成环境快照 detected.json")
        det = write_detected(py312, skill_dir, tool_root, draft_root)
        report["detected"] = str(det)

        report["ok"] = True
        report["duration_sec"] = round(time.time() - t0, 1)
        rep_path = DEPLOY / "install-report.json"
        rep_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")

        log("")
        log("=" * 78)
        log(f"安装完成（{report['duration_sec']} 秒）。下一步：")
        log(f"  python \"{DEPLOY / 'verify.py'}\"        # 或 deploy\\verify.cmd")
        log(f"报告：{rep_path}")
        log("=" * 78)

    except Fail as e:
        report["ok"] = False
        report["error"] = e.msg
        (DEPLOY / "install-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        log("")
        log("[x] 安装失败：" + e.msg)
        if e.hint:
            log("    细节 / 怎么修：")
            for line in e.hint.splitlines():
                log("      " + line)
        return 1
    except KeyboardInterrupt:
        log("")
        log("[x] 已中断。这是幂等的：修好/重跑同一个命令即可，已完成的步骤不会重做。")
        return 1
    except Exception as e:  # noqa: BLE001
        import traceback
        traceback.print_exc()
        report["ok"] = False
        report["error"] = f"{type(e).__name__}: {e}"
        (DEPLOY / "install-report.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        log("")
        log(f"[x] 安装异常终止：{type(e).__name__}: {e}")
        log("    把上面的 traceback + deploy\\install-report.json 一起反馈；修好原因后重跑即可。")
        return 1

    if args.verify:
        log("")
        log("— 自动跑自检 —")
        r = subprocess.run(py312 + [str(DEPLOY / "verify.py")], text=True,
                           encoding="utf-8", errors="replace")
        return r.returncode
    return 0


if __name__ == "__main__":
    sys.exit(main())
