"""macOS capability verification. Checks real commands; app opening is a separate acceptance step."""
from __future__ import annotations
import argparse
import json
from pathlib import Path
import subprocess
import sys
import tempfile
from mac_common import BUNDLE, CONFIG_PATH, atomic_json, env_for, load_config


def check_process(cmd, env, timeout=180):
    r = subprocess.run([str(x) for x in cmd], env=env, capture_output=True,
                       text=True, encoding='utf-8', errors='replace', timeout=timeout)
    if r.returncode:
        raise RuntimeError(f'exit {r.returncode}: {(r.stderr or r.stdout)[-1800:]}')
    return r.stdout


def verify(config):
    env = env_for(config)
    rows = []
    def check(name, fn, required=True):
        try:
            detail = fn()
            rows.append({'name': name, 'ok': True, 'required': required, 'detail': detail or ''})
        except Exception as e:
            rows.append({'name': name, 'ok': False, 'required': required, 'detail': str(e)})
        print(('OK   ' if rows[-1]['ok'] else 'FAIL ' if required else 'WARN ') + name, flush=True)
        if not rows[-1]['ok']:
            print('     ' + rows[-1]['detail'], flush=True)
    jy = config['jyenv']
    cli = Path(config['skill_dir']) / 'scripts/roughcut_cli.py'
    check('草稿运行环境', lambda: check_process([jy, '-c',
          'import pyJianYingDraft; from pymediainfo import MediaInfo; assert MediaInfo.can_parse(); print("native MediaInfo OK")'], env))
    check('ffmpeg 可执行', lambda: check_process([config['ffmpeg'], '-version'], env).splitlines()[0])
    check('ffprobe 可执行', lambda: check_process([config['ffprobe'], '-version'], env).splitlines()[0])
    check('技能文件齐全', lambda: require_files(Path(config['skill_dir']), [
        'SKILL.md', 'scripts/subtitle_module.py', 'scripts/roughcut_cli.py', 'scripts/mac_draft.py', 'setup/smoke/_paths.py', 'references/macos.md']))
    with tempfile.TemporaryDirectory(prefix='roughcut-verify-') as t:
        tmp = Path(t)
        sample = tmp / 'sample.mp4'
        check('生成 5 秒测试素材', lambda: check_process([sys.executable,
              BUNDLE / 'deploy/checks/make_sample.py', config['ffmpeg'], sample], env))
        def probe():
            data = json.loads(check_process([jy, cli, 'probe', sample], env))
            if (data['width'], data['height']) != (1080, 1920) or not data['has_audio']:
                raise ValueError(f'显示尺寸或音轨错误：{data}')
            return data
        check('视频探针与显示尺寸', probe)
        def build():
            plan = {'clips': [{'source': str(sample), 'start': 1, 'end': 4,
                               'subtitles': [{'start': 1.2, 'end': 3.5, 'text': '测试字幕 第二行'}]}]}
            atomic_json(tmp / 'plan.json', plan)
            out = check_process([jy, cli, 'build', tmp / 'plan.json', '--draft-root', tmp / 'drafts',
                                 '--name', 'verify'], env)
            d = json.loads((tmp / 'drafts/verify/draft_content.json').read_text(encoding='utf-8'))
            if d['duration'] != 3_000_000 or [t['type'] for t in d['tracks']] != ['video', 'text']:
                raise ValueError('草稿时长或两轨结构错误')
            active = json.loads((tmp / 'drafts/verify/draft_info.json').read_text(encoding='utf-8'))
            meta = json.loads((tmp / 'drafts/verify/draft_meta_info.json').read_text(encoding='utf-8'))
            if active != d or active['platform']['os'] != 'mac' or active['new_version'] != '103.0.0':
                raise ValueError('macOS 活动时间线或协议标记错误')
            if meta['draft_name'] != 'verify' or meta['draft_id'] != d['id'] or meta['tm_duration'] != d['duration']:
                raise ValueError('草稿身份或首页元数据不一致')
            for material in d['materials']['videos']:
                media_path = Path(material['path'])
                if not media_path.is_file() or not media_path.resolve().is_relative_to((tmp / 'drafts/verify/media').resolve()):
                    raise ValueError('素材未打包到草稿 media 目录')
            seg = d['tracks'][1]['segments'][0]['target_timerange']
            if seg['start'] != 200_000 or seg['duration'] != 2_300_000:
                raise ValueError(f'字幕重映射错误：{seg}')
            return out
        check('三秒草稿与字幕时间轴映射', build)
        check('字幕素材结构', lambda: check_process([jy,
              Path(config['skill_dir']) / 'scripts/subtitle_module.py', tmp / 'drafts/verify', '--verify'], env))
    if config.get('asr_enabled'):
        check('ASR 模型加载与推理', lambda: check_process([config['asrenv'],
              BUNDLE / 'deploy/checks/check_asr.py', config['model']], env, timeout=1800))
        check('ASR VAD 依赖', lambda: check_process([config['asrenv'], '-c',
              'import numpy as np; from faster_whisper.vad import get_speech_timestamps; '
              'get_speech_timestamps(np.zeros(32000, dtype=np.float32)); print("VAD OK")'], env))
        check('ASR 依赖一致性', lambda: check_process([config['asrenv'], '-m', 'pip', 'check'], env))
    else:
        rows.append({'name': 'ASR', 'ok': None, 'required': False, 'detail': '安装时指定 --no-model，未启用 ASR'})
        print('SKIP ASR（仅草稿模式）')
    def writable():
        root = Path(config['draft_root'])
        root.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(prefix='.roughcut-probe-', dir=root):
            pass
        return str(root)
    check('草稿目录可写', writable)
    check('剪映应用安装', lambda: require_app(config.get('jianying')), required=False)
    check('依赖一致性', lambda: check_process([jy, '-m', 'pip', 'check'], env))
    report = {'ok': all(r['ok'] for r in rows if r['required']), 'platform': 'macos',
              'capabilities': {'draft': True, 'asr_requested': config.get('asr_enabled', False)},
              'app_open_verified': False, 'draft_root_confirmed': config.get('draft_root_confirmed', False),
              'results': rows}
    report['capabilities']['draft'] = all(r['ok'] for r in rows if r['required'] and not r['name'].startswith('ASR'))
    return report


def require_files(root, paths):
    missing = [p for p in paths if not (root / p).is_file()]
    if missing:
        raise FileNotFoundError(', '.join(missing))
    return '文件齐全'


def require_app(app):
    if not app or not Path(app).is_dir():
        raise FileNotFoundError('未找到剪映；可生成基础草稿，尚未完成应用内验收')
    return app


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--config', default=str(CONFIG_PATH))
    args = ap.parse_args(argv)
    c = load_config(args.config)
    report = verify(c)
    output = Path(args.config).expanduser().resolve().parent / 'verify-report.json'
    atomic_json(output, report)
    print(f'报告：{output}')
    print('已启用能力检查通过；剪映内打开仍需验收。' if report['ok'] else '有必需检查失败，见上方详情。')
    return 0 if report['ok'] else 1


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (RuntimeError, OSError, ValueError) as e:
        print(f'自检失败：{e}', file=sys.stderr)
        sys.exit(1)
