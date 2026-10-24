"""macOS installer. Never executes the Windows payload or overwrites an old skill."""
from __future__ import annotations
import argparse
import datetime
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import tempfile
from mac_common import (BUNDLE, CONFIG_PATH, DEFAULT_ROOT, MODEL_NAME, SKILL_NAME,
                        app_path, atomic_json, draft_root, find_binary, python_exe, run, verify_manifest)


def choose_python(explicit=None):
    candidates = [explicit] if explicit else [sys.executable, find_binary('python3.12'),
                  find_binary('python3.13'), '/opt/homebrew/opt/python@3.12/bin/python3.12',
                  '/usr/local/opt/python@3.12/bin/python3.12', str(Path.home() / '.local/bin/python3.12')]
    uv = find_binary('uv')
    if not explicit and uv:
        r = subprocess.run([uv, 'python', 'find', '3.12'], capture_output=True, text=True)
        if r.returncode == 0:
            candidates.append(r.stdout.strip())
    for p in candidates:
        if not p or not Path(p).is_file():
            continue
        r = subprocess.run([str(p), '-c', 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")'],
                           capture_output=True, text=True)
        if r.returncode == 0 and r.stdout.strip() in {'3.12', '3.13'}:
            return str(Path(p).absolute())
    raise RuntimeError('需要 Python 3.12 或 3.13。运行 brew install python@3.12，或 uv python install 3.12；再用 --python 指定。')


def venv(root, name, python, requirements, args):
    target = root / name
    exe = python_exe(root, name)
    if target.exists() and not exe.exists():
        raise RuntimeError(f'环境不完整：{target}。请移走这个目录后重试。')
    if not exe.exists():
        run([python, '-m', 'venv', target])
    cmd = [exe, '-m', 'pip', 'install', '--disable-pip-version-check', '-r', requirements]
    if args.offline:
        if not args.wheelhouse:
            raise RuntimeError('--offline 需要 --wheelhouse（包含 macOS 对应架构的所有依赖）')
        cmd += ['--no-index', '--find-links', str(Path(args.wheelhouse).expanduser().resolve())]
    elif args.index:
        cmd += ['--index-url', args.index]
    run(cmd)
    return exe


def install_skill(source, target, config):
    target.parent.mkdir(parents=True, exist_ok=True)
    stage = Path(tempfile.mkdtemp(prefix='.roughcut-stage-', dir=target.parent)) / SKILL_NAME
    backup = None
    try:
        shutil.copytree(source, stage)
        atomic_json(stage / 'setup/detected.json', config)
        text = (stage / 'SKILL.md').read_text(encoding='utf-8')
        note = ('\n## 当前机器（macOS）\n\n'
                f'运行配置：`{config["config_path"]}`。项目入口：`{BUNDLE / "run.sh"}`。\n'
                f'草稿输出：`{config["draft_root"]}`。文档中的 Windows 命令仅供 Windows 使用，'
                'macOS 按 `references/macos.md` 执行。先读取 detected.json，禁止猜测本机路径。\n\n')
        pos = text.index('\n', text.index('# 本地视频粗剪并生成剪映草稿'))
        (stage / 'SKILL.md').write_text(text[:pos] + note + text[pos:], encoding='utf-8')
        if target.exists():
            stamp = datetime.datetime.now().strftime('%Y%m%d-%H%M%S-%f')
            backup_dir = (target.parent.parent if target.parent.name == 'skills' else target.parent) / 'skill-backups'
            backup_dir.mkdir(parents=True, exist_ok=True)
            backup = backup_dir / (target.name + '.bak-' + stamp)
            target.rename(backup)  # Failure aborts; never delete a user's skill.
        try:
            stage.rename(target)
        except Exception:
            if backup is not None:
                backup.rename(target)
            raise
    finally:
        shutil.rmtree(stage.parent, ignore_errors=True)
    return str(backup) if backup else None


def main(argv=None):
    ap = argparse.ArgumentParser(description='macOS 粗剪环境安装（Apple Silicon / Intel）')
    ap.add_argument('--python', help='Python 3.12/3.13 可执行文件')
    ap.add_argument('--tool-root', default=os.environ.get('CUT_TOOLS', str(DEFAULT_ROOT / 'tools')))
    ap.add_argument('--draft-root', help='从剪映设置复制的真实草稿目录；省略时仅探测或使用暂存目录')
    ap.add_argument('--skill-dir', default=str(Path.home() / '.agents/skills' / SKILL_NAME))
    ap.add_argument('--config', default=str(CONFIG_PATH))
    ap.add_argument('--index', help='pip HTTPS 索引地址')
    ap.add_argument('--offline', action='store_true', help='禁止 pip 和模型联网下载')
    ap.add_argument('--wheelhouse')
    ap.add_argument('--model-from', help='已有的 CTranslate2 模型目录')
    ap.add_argument('--no-model', action='store_true', help='只安装草稿链路')
    ap.add_argument('--verify', action='store_true')
    args = ap.parse_args(argv)
    if sys.platform != 'darwin':
        ap.error('本入口仅用于 macOS；Windows 使用 deploy/install.cmd')
    verify_manifest()
    python = choose_python(args.python)
    ff, fp = find_binary('ffmpeg'), find_binary('ffprobe')
    if not ff or not fp:
        raise RuntimeError('缺少 ffmpeg/ffprobe，请先运行 brew install ffmpeg')
    root = Path(args.tool_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    jy = venv(root, 'jyenv', python, BUNDLE / 'deploy/requirements-jy-macos.txt', args)
    # Validate native library availability before modifying the user's installed skill.
    run([jy, '-c', 'import pyJianYingDraft; from pymediainfo import MediaInfo; assert MediaInfo.can_parse(), "MediaInfo native library unavailable"'])
    asr = None
    model = root / 'models' / MODEL_NAME
    if not args.no_model:
        asr = venv(root, 'asrenv', python, BUNDLE / 'deploy/requirements-asr-macos.txt', args)
        source = Path(args.model_from).expanduser().resolve() if args.model_from else BUNDLE / 'models' / MODEL_NAME
        if args.model_from and not (source / 'model.bin').is_file():
            raise RuntimeError(f'本地模型缺少 model.bin：{source}')
        if source.is_dir() and source != model and (source / 'model.bin').is_file():
            shutil.copytree(source, model, dirs_exist_ok=True)
        elif not (model / 'model.bin').is_file():
            if args.offline:
                raise RuntimeError('离线模式缺少模型，请用 --model-from 指定完整模型目录')
            code = ('from huggingface_hub import snapshot_download; '
                    f'snapshot_download(repo_id="mobiuslabsgmbh/faster-whisper-large-v3-turbo", local_dir={str(model)!r})')
            run([asr, '-c', code])
        run([asr, BUNDLE / 'deploy/checks/check_asr.py', model])
    dr, confirmed = draft_root(args.draft_root)
    dr.mkdir(parents=True, exist_ok=True)
    skill = Path(args.skill_dir).expanduser().resolve()
    config = {'platform': 'macos', 'architecture': platform.machine(), 'tool_root': str(root),
              'draft_root': str(dr), 'draft_root_confirmed': confirmed, 'skill_dir': str(skill),
              'jyenv': str(jy), 'asrenv': str(asr) if asr else None, 'model': str(model),
              'model_turbo': str(model), 'ffmpeg': ff, 'ffprobe': fp, 'jianying': app_path(),
              'asr_enabled': not args.no_model, 'config_path': str(Path(args.config).expanduser().resolve())}
    backup = install_skill(BUNDLE / 'payload/skill' / SKILL_NAME, skill, config)
    atomic_json(args.config, config)
    atomic_json(root.parent / 'install-report.json', {'ok': True, 'config': config, 'backup': backup})
    print(f'安装完成。配置：{config["config_path"]}\n草稿目录：{dr}')
    if not confirmed:
        print('请在剪映设置中核对草稿位置；当前路径未经应用内确认。可重跑 --draft-root "实际目录"。')
    if args.verify:
        return subprocess.call([python, str(BUNDLE / 'deploy/verify_macos.py'), '--config', config['config_path']])
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, subprocess.CalledProcessError, OSError) as e:
        print(f'安装失败：{e}', file=sys.stderr)
        sys.exit(1)
