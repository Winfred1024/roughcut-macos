# -*- coding: utf-8 -*-
"""换机器自检：探测这个 skill 依赖的本机路径与版本，缺什么直接说。

只用标准库，可以用任意 Python 3.8+ 运行：
    python setup/check_env.py
    python setup/check_env.py --json          # 顺手写出 setup/detected.json

退出码 0 = 必需项齐全；1 = 有必需项缺失。
"""
import json
import os
import subprocess
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
IS_WIN = os.name == 'nt'

# --- 候选根目录：先看环境变量，再看本机常见位置 ---
TOOL_ROOTS = [os.environ.get('CUT_TOOLS')] + (
    [r'E:\auto_cut\tools', r'D:\auto_cut\tools', r'C:\auto_cut\tools'] if IS_WIN else ['/opt/auto_cut/tools'])
DRAFT_ROOTS = [os.environ.get('CUT_DRAFT_ROOT')] + (
    [r'E:\草稿\JianyingPro Drafts', str(Path.home() / 'JianyingPro Drafts'), str(Path.home() / 'Videos' / 'JianyingPro Drafts')]
    if IS_WIN else [str(Path.home() / 'JianyingPro Drafts')])
SPEC_ROOTS = [os.environ.get('CUT_SPEC_ROOT')] + ([r'E:\字幕规范提取'] if IS_WIN else [])

results = []   # (level, name, ok, detail)


def add(level, name, ok, detail=''):
    results.append((level, name, bool(ok), detail))


def first_exist(cands, rel):
    for c in cands:
        if not c:
            continue
        p = Path(c) / rel if rel else Path(c)
        if p.exists():
            return p
    return None


def run_py(exe, code):
    """跑一段 python，返回 (ok, 输出)。"""
    try:
        r = subprocess.run([str(exe), '-c', code], capture_output=True, text=True, timeout=120,
                           encoding='utf-8', errors='replace')
        return r.returncode == 0, (r.stdout or r.stderr).strip().splitlines()[-1] if (r.stdout or r.stderr) else ''
    except Exception as e:
        return False, str(e)


def find_jianying():
    cands = []
    if IS_WIN:
        local = Path(os.environ.get('LOCALAPPDATA', ''))
        apps = local / 'JianyingPro' / 'Apps'
        if apps.exists():
            cands += list(apps.glob('*/JianyingPro.exe'))
        for base in (r'C:\Program Files\JianyingPro', r'C:\Program Files (x86)\JianyingPro'):
            p = Path(base) / 'JianyingPro.exe'
            if p.exists():
                cands.append(p)

    def ver_key(p):
        # 按版本号数值排序：11.6 > 8.3（字符串排序会排反）
        import re
        nums = re.findall(r'\d+', p.parent.name)
        return (tuple(int(x) for x in nums[:4]), p.parent.stat().st_mtime)

    return max(cands, key=ver_key) if cands else None


def mac_main() -> int:
    snapshot = SKILL / 'setup/detected.json'
    if not snapshot.exists():
        print('缺少 macOS 运行配置，请先运行项目 install.command')
        return 1
    detected = json.loads(snapshot.read_text(encoding='utf-8'))
    missing = []
    for name in ('jyenv', 'ffmpeg', 'ffprobe'):
        value = detected.get(name)
        ok = bool(value and Path(value).is_file())
        print(('OK ' if ok else 'FAIL ') + name + ': ' + str(value))
        if not ok:
            missing.append(name)
    if detected.get('asr_enabled'):
        for name in ('asrenv', 'model'):
            value = detected.get(name)
            ok = bool(value and Path(value).exists())
            print(('OK ' if ok else 'FAIL ') + name + ': ' + str(value))
            if not ok:
                missing.append(name)
    else:
        print('SKIP ASR（仅草稿模式）')
    print('完整执行链路请运行项目 verify.command；本步骤仅检查配置路径。')
    return 1 if missing else 0


def main() -> int:
    if sys.platform == 'darwin':
        return mac_main()
    as_json = '--json' in sys.argv
    detected = {}

    # 0) 工具链根目录（smoke 脚本靠它定位 ffmpeg / 模型）
    troot = first_exist(TOOL_ROOTS, None)
    detected['tool_root'] = str(troot) if troot else None
    add('必需', '工具链根目录', troot, str(troot or '未找到（可用环境变量 CUT_TOOLS 指定）'))

    # 1) ffmpeg / ffprobe
    ff = first_exist(TOOL_ROOTS, r'ffmpeg\ffmpeg.exe' if IS_WIN else 'ffmpeg/ffmpeg')
    fp = first_exist(TOOL_ROOTS, r'ffmpeg\ffprobe.exe' if IS_WIN else 'ffmpeg/ffprobe')
    add('必需', 'ffmpeg', ff, str(ff or '未找到，见 README 第 3 步'))
    add('必需', 'ffprobe', fp, str(fp or '未找到'))
    if ff:
        try:
            v = subprocess.run([str(ff), '-version'], capture_output=True, text=True, timeout=30).stdout.splitlines()[0]
            add('信息', 'ffmpeg 版本', True, v.strip())
        except Exception as e:
            add('信息', 'ffmpeg 版本', False, str(e))

    # 2) 写草稿的 Python 环境
    jy = first_exist(TOOL_ROOTS, r'jyenv\Scripts\python.exe' if IS_WIN else 'jyenv/bin/python')
    ok, out = (False, '未找到')
    if jy:
        ok, out = run_py(jy, "import pyJianYingDraft as m;print('pyJianYingDraft OK')")
        if ok:
            ok2, v2 = run_py(jy, "import pymediainfo;from pymediainfo import MediaInfo;print('MediaInfo', MediaInfo.can_parse())")
            add('必需', 'pymediainfo / MediaInfo.dll', ok2 and 'True' in (v2 or ''), v2 or '')
    add('必需', 'jyenv（pyJianYingDraft）', ok, out)
    detected['jyenv'] = str(jy) if jy else None

    # 3) ASR 的 Python 环境
    asr = first_exist(TOOL_ROOTS, r'asrenv\Scripts\python.exe' if IS_WIN else 'asrenv/bin/python')
    ok, out = (False, '未找到')
    if asr:
        ok, out = run_py(asr, "from faster_whisper import WhisperModel;import ctranslate2,numpy;"
                              "print('faster-whisper OK ct2',ctranslate2.__version__,'np',numpy.__version__)")
    add('必需', 'asrenv（faster-whisper）', ok, out)
    detected['asrenv'] = str(asr) if asr else None

    # 坑 3：av>=16 会让 faster_whisper 直接崩，必须确认 av 版本并在流程里绕开
    if asr:
        ok_av, out_av = run_py(asr, "import av;print('av',av.__version__)")
        add('信息', 'av 版本（≥16 需绕过，见坑 3）', ok_av, out_av)

    # 4) 模型
    turbo = first_exist(TOOL_ROOTS, r'models\faster-whisper-large-v3-turbo' if IS_WIN else 'models/faster-whisper-large-v3-turbo')
    has_bin = turbo and (turbo / 'model.bin').exists()
    add('必需', 'whisper turbo 模型', has_bin, f'{turbo} (model.bin {round((turbo / "model.bin").stat().st_size / 1e6) if has_bin else 0} MB)' if turbo else '未找到')
    small = first_exist(TOOL_ROOTS, r'models\faster-whisper-small' if IS_WIN else 'models/faster-whisper-small')
    add('可选', 'whisper small 模型（低配备选）', small and (small / 'model.bin').exists(), str(small or '无'))
    detected['model_turbo'] = str(turbo) if turbo else None

    # 5) 剪映 + 草稿根目录
    jy_app = find_jianying()
    ver = ''
    if jy_app:
        try:
            ver = subprocess.run(['powershell', '-NoProfile', '-Command',
                                  f"(Get-Item '{jy_app}').VersionInfo.FileVersion"],
                                 capture_output=True, text=True, timeout=30).stdout.strip()
        except Exception:
            pass
    add('必需', '剪映专业版', jy_app, f'{jy_app} 版本 {ver}'.strip())
    draft = first_exist(DRAFT_ROOTS, None)
    add('必需', '草稿根目录', draft, str(draft or '未找到，剪映里确认实际路径后填进路径表'))
    detected['draft_root'] = str(draft) if draft else None

    # 6) 可选：规范源文件与分类台本库（只在“补充/修改规范”时才需要）
    spec = first_exist(SPEC_ROOTS, None)
    add('可选', '规范源文件根（E:\\字幕规范提取）', spec, str(spec or '无——不影响出片，只影响以后改规范'))
    add('可选', '分类台本库', (spec / r'全部草稿台本\分类台本') if spec else None,
        str((spec / '全部草稿台本' / '分类台本')) if spec else '无')

    # 7) skill 自身文件是否完整
    for rel in ('SKILL.md', r'references\subtitle-presentation-spec.md',
                r'references\cut-boundary-padding.md', r'references\env-and-pitfalls.md',
                r'references\subtitle-style-details.xlsx'):
        add('技能', rel, (SKILL / rel).exists(), '')

    # --- 输出 ---
    w = max(len(r[1]) for r in results) + 2
    print(f'\nskill: {SKILL}\n' + '-' * 78)
    for level, name, ok, detail in results:
        mark = 'OK  ' if ok else ('FAIL' if level == '必需' else '--  ')
        print(f'[{mark}] {name:<{w}} {detail}')
    print('-' * 78)
    missing = [r[1] for r in results if r[0] == '必需' and not r[2]]
    if missing:
        print('缺少必需项：' + '、'.join(missing))
        print('按 setup/README.md 补齐后重跑；路径不同时改 references/env-and-pitfalls.md 第 1 节的表。')
    else:
        print('必需项齐全。下一步：按 README 第 5 步跑 smoke 三步验证。')

    if as_json:
        out = SKILL / 'setup' / 'detected.json'
        out.write_text(json.dumps(detected, ensure_ascii=False, indent=2), encoding='utf-8')
        print(f'\n已写出 {out}')

    return 0 if not missing else 1


if __name__ == '__main__':
    sys.exit(main())
