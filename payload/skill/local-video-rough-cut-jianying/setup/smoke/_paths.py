# -*- coding: utf-8 -*-
"""smoke 脚本共用的路径解析：优先 setup/detected.json，其次环境变量，最后本机默认值。"""
import json
import os
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent.parent      # .../local-video-rough-cut-jianying
IS_WIN = os.name == 'nt'


def _detected() -> dict:
    p = SKILL / 'setup' / 'detected.json'
    if p.exists():
        try:
            return json.loads(p.read_text(encoding='utf-8'))
        except Exception:
            pass
    return {}


DET = _detected()


def tool_root() -> Path:
    for c in [os.environ.get('CUT_TOOLS'), DET.get('tool_root'),
              r'E:\auto_cut\tools' if IS_WIN else str(Path.home() / 'Library/Application Support/RoughCut/tools')]:
        if c and Path(c).exists():
            return Path(c)
    return Path(os.environ.get('CUT_TOOLS') or (r'E:\auto_cut\tools' if IS_WIN else str(Path.home() / 'Library/Application Support/RoughCut/tools')))


def ffmpeg() -> str:
    if os.environ.get('CUT_FFMPEG') or DET.get('ffmpeg'):
        return os.environ.get('CUT_FFMPEG') or DET['ffmpeg']
    p = tool_root() / ('ffmpeg/ffmpeg.exe' if IS_WIN else 'ffmpeg/ffmpeg')
    return str(p)


def ffprobe() -> str:
    if os.environ.get('CUT_FFPROBE') or DET.get('ffprobe'):
        return os.environ.get('CUT_FFPROBE') or DET['ffprobe']
    p = tool_root() / ('ffmpeg/ffprobe.exe' if IS_WIN else 'ffmpeg/ffprobe')
    return str(p)


def model_turbo() -> str:
    p = os.environ.get('CUT_MODEL') or DET.get('model_turbo')
    if p and Path(p).exists():
        return str(p)
    return str(tool_root() / 'models' / 'faster-whisper-large-v3-turbo')


def draft_root() -> Path:
    for c in [os.environ.get('CUT_DRAFT_ROOT'), DET.get('draft_root'),
              r'E:\草稿\JianyingPro Drafts' if IS_WIN else str(Path.home() / 'JianyingPro Drafts')]:
        if c and Path(c).exists():
            return Path(c)
    return Path(os.environ.get('CUT_DRAFT_ROOT') or (r'E:\草稿\JianyingPro Drafts' if IS_WIN
                                                     else str(Path.home() / 'JianyingPro Drafts')))


def sample_video() -> str:
    """取一个真实素材：命令行参数 > 环境变量 CUT_SAMPLE > 报错提示。"""
    import sys
    if len(sys.argv) > 1:
        return sys.argv[1]
    if os.environ.get('CUT_SAMPLE'):
        return os.environ['CUT_SAMPLE']
    raise SystemExit('用法：python <本脚本> <一条真实视频路径>\n'
                     '或设置环境变量 CUT_SAMPLE 指向任意一条 .mp4/.mov')
