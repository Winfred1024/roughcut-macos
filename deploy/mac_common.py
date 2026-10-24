"""Shared macOS configuration. Standard library only; safe to import before setup."""
from __future__ import annotations
import json
import hashlib
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile

BUNDLE = Path(__file__).resolve().parent.parent
SKILL_NAME = 'local-video-rough-cut-jianying'
MODEL_NAME = 'faster-whisper-large-v3-turbo'
DEFAULT_ROOT = Path.home() / 'Library' / 'Application Support' / 'RoughCut'
CONFIG_PATH = Path(os.environ.get('CUT_CONFIG', DEFAULT_ROOT / 'config.json')).expanduser()


def run(cmd, **kwargs):
    return subprocess.run([str(x) for x in cmd], check=True, **kwargs)


def atomic_json(path, data):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def load_config(path=None):
    p = Path(path or CONFIG_PATH).expanduser()
    if not p.is_file():
        raise RuntimeError(f'尚未安装，请运行 ./install.command（找不到配置 {p}）')
    return json.loads(p.read_text(encoding='utf-8'))


def draft_root(explicit=None):
    if explicit or os.environ.get('CUT_DRAFT_ROOT'):
        return Path(explicit or os.environ['CUT_DRAFT_ROOT']).expanduser().resolve(), True
    candidates = [
        Path.home() / 'Movies/JianyingPro/User Data/Projects/com.lveditor.draft',
        Path.home() / 'Movies/JianyingPro Drafts',
        Path.home() / 'Library/Containers/com.lemon.lvpro/Data/Movies/JianyingPro/User Data/Projects/com.lveditor.draft',
    ]
    hits = [p for p in candidates if p.is_dir()]
    if len(hits) == 1:
        return hits[0], False
    # A staging directory avoids claiming an arbitrary path is the app's active library.
    return DEFAULT_ROOT / 'drafts', False


def find_binary(name):
    for p in [shutil.which(name), f'/opt/homebrew/bin/{name}', f'/usr/local/bin/{name}']:
        if p and Path(p).is_file() and os.access(p, os.X_OK):
            return str(Path(p).resolve())
    return None


def app_path():
    for base in [Path('/Applications'), Path.home() / 'Applications']:
        for name in ['剪映专业版.app', 'JianyingPro.app', 'VideoFusion-macOS.app']:
            if (base / name).is_dir():
                return str(base / name)
    return None


def python_exe(root, name):
    return Path(root) / name / 'bin/python'


def env_for(config):
    env = dict(os.environ, PYTHONIOENCODING='utf-8', CUT_TOOLS=config['tool_root'],
               CUT_DRAFT_ROOT=config['draft_root'], CUT_MODEL=config['model'],
               CUT_FFMPEG=config['ffmpeg'], CUT_FFPROBE=config['ffprobe'])
    # pymediainfo's native library must be explicit on Apple Silicon.
    if config.get('mediainfo_library'):
        env['CUT_MEDIAINFO_LIBRARY'] = config['mediainfo_library']
    return env


def verify_manifest():
    manifest = BUNDLE / 'manifest.json'
    if not manifest.is_file():
        raise RuntimeError('缺少 manifest.json；发布者请先运行 deploy/make_manifest.py')
    data = json.loads(manifest.read_text(encoding='utf-8'))
    for item in data['files']:
        path = (BUNDLE / item['path']).resolve()
        if not path.is_relative_to(BUNDLE.resolve()) or not path.is_file():
            raise RuntimeError(f"发布文件缺失或路径非法：{item['path']}")
        if path.stat().st_size != item['size'] or hashlib.sha256(path.read_bytes()).hexdigest() != item['sha256']:
            raise RuntimeError(f"发布文件校验失败：{item['path']}")
