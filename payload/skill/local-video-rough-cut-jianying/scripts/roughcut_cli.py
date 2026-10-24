"""Executable helpers. A reviewed plan decides ordering/cuts; never infer deletion from text."""
from __future__ import annotations
import argparse
import json
import math
import os
import shutil
from pathlib import Path
import subprocess
import sys
import tempfile
import uuid
import wave


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix='.' + path.name, dir=path.parent)
    try:
        with os.fdopen(fd, 'w', encoding='utf-8') as f:
            json.dump(value, f, ensure_ascii=False, indent=2)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)


def probe(path):
    path = Path(path).expanduser().resolve(strict=True)
    r = subprocess.run([os.environ.get('CUT_FFPROBE', 'ffprobe'), '-v', 'error',
                        '-show_format', '-show_streams', '-of', 'json', str(path)],
                       check=True, capture_output=True, text=True)
    d = json.loads(r.stdout)
    v = next((s for s in d['streams'] if s['codec_type'] == 'video'), None)
    if v is None:
        raise ValueError(f'没有视频流：{path}')
    rotation = next((s['rotation'] for s in v.get('side_data_list', []) if 'rotation' in s),
                    v.get('tags', {}).get('rotate', 0))
    w, h = int(v['width']), int(v['height'])
    if round(float(rotation)) % 180 == 90:
        w, h = h, w
    return {'path': str(path), 'duration': float(v.get('duration') or d['format']['duration']),
            'container_duration': float(d['format']['duration']),
            'width': w, 'height': h, 'rotation': rotation,
            'has_audio': any(s['codec_type'] == 'audio' for s in d['streams'])}


def transcribe(args):
    import numpy as np
    from faster_whisper import WhisperModel
    src = Path(args.video).expanduser().resolve(strict=True)
    model = args.model or os.environ.get('CUT_MODEL')
    if not model or not Path(model).is_dir():
        raise ValueError('请用 --model 指定已下载的本地 CTranslate2 模型')
    with tempfile.TemporaryDirectory(prefix='roughcut-asr-') as tmp:
        wav = Path(tmp) / 'audio.wav'
        subprocess.run([os.environ.get('CUT_FFMPEG', 'ffmpeg'), '-nostdin', '-y', '-v', 'error',
                        '-i', str(src), '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(wav)], check=True)
        with wave.open(str(wav), 'rb') as f:
            audio = np.frombuffer(f.readframes(f.getnframes()), dtype=np.int16).astype(np.float32) / 32768
        m = WhisperModel(str(Path(model).resolve()), device='cpu', compute_type='int8',
                         cpu_threads=args.threads, local_files_only=True)
        segments, info = m.transcribe(audio, language=args.language, vad_filter=True,
                                      word_timestamps=True, condition_on_previous_text=False,
                                      initial_prompt='以下是普通话的句子。' if args.language == 'zh' else None)
        rows = [{'start': s.start, 'end': s.end, 'text': s.text.strip(),
                 'words': [{'start': w.start, 'end': w.end, 'word': w.word} for w in (s.words or [])]}
                for s in segments]
    write_json(args.output, {'source': str(src), 'language': info.language, 'segments': rows})
    if not rows:
        raise ValueError(f'没有识别到人声，空结果已保存到 {args.output}')
    print(f'已转写 {len(rows)} 条：{args.output}')


def validate_plan(plan, base):
    """All times are seconds. Reject invalid plans before creating a draft."""
    if not isinstance(plan.get('clips'), list) or not plan['clips']:
        raise ValueError('计划需要非空 clips 数组')
    out = []
    for clip in plan['clips']:
        src = Path(clip['source']).expanduser()
        if not src.is_absolute():
            src = base / src
        media = probe(src)
        start, end = float(clip.get('start', 0)), float(clip.get('end', media['duration']))
        if not all(map(math.isfinite, (start, end))) or not 0 <= start < end <= media['duration'] + 0.001:
            raise ValueError(f'片段时间范围非法：{src} {start}..{end}')
        subs = []
        for sub in clip.get('subtitles', []):
            a, b = float(sub['start']), float(sub['end'])
            if not all(map(math.isfinite, (a, b))) or not start <= a < b <= end:
                raise ValueError('字幕必须处于保留区间内；跨切点字幕需要先按真实词时间拆分')
            if not str(sub['text']).strip():
                raise ValueError('字幕不能为空')
            subs.append({'start': a, 'end': b, 'text': str(sub['text'])})
        if round(end * 1e6) <= round(start * 1e6):
            raise ValueError('片段长度必须至少为一微秒')
        out.append({'source': media['path'], 'start': start, 'end': end, 'subtitles': subs})
    previous = -1
    offset = 0
    for c in out:
        for sub in c['subtitles']:
            a, b = offset + sub['start'] - c['start'], offset + sub['end'] - c['start']
            if round(a * 1e6) < previous:
                raise ValueError('字幕未按顺序排列或存在重叠，无法写入单条字幕轨')
            previous = round(b * 1e6)
        offset += c['end'] - c['start']
    return out


def build(args):
    import pyJianYingDraft as draft
    from subtitle_module import SUBTITLE_TRACK, promote_draft_to_subtitles, subtitle_style, verify_subtitle_draft
    path = Path(args.plan).expanduser().resolve(strict=True)
    plan = json.loads(path.read_text(encoding='utf-8'))
    clips = validate_plan(plan, path.parent)
    root = Path(args.draft_root or os.environ.get('CUT_DRAFT_ROOT', '')).expanduser()
    if not args.draft_root and not os.environ.get('CUT_DRAFT_ROOT'):
        raise ValueError('需要 --draft-root 或 CUT_DRAFT_ROOT')
    root.mkdir(parents=True, exist_ok=True)
    name = args.name or '粗剪_' + uuid.uuid4().hex[:10]
    if Path(name).name != name or name in {'.', '..'}:
        raise ValueError('草稿名不能包含路径')
    if (root / name).exists():
        raise FileExistsError(f'拒绝覆盖已有草稿：{root / name}')
    # Derive display orientation from source unless the plan explicitly chooses dimensions.
    media = probe(clips[0]['source'])
    width, height = int(plan.get('width', media['width'])), int(plan.get('height', media['height']))
    fps = int(plan.get('fps', 30))
    if not (0 < width <= 16384 and 0 < height <= 16384 and 0 < fps <= 120):
        raise ValueError('画布或帧率超出允许范围')
    materials = [draft.VideoMaterial(c['source']) for c in clips]
    for clip, material in zip(clips, materials):
        if round(clip['end'] * 1e6) > material.duration:
            raise ValueError(f"剪辑终点超出草稿库读取的有效视频时长：{clip['source']}（{material.duration / 1e6} 秒）")
    s = draft.DraftFolder(str(root)).create_draft(name, width, height, fps=fps, allow_replace=False)
    # The notarized Mac app is sandboxed. Store media inside its Movies draft library.
    if not args.link_media:
        media_dir = root / name / 'media'
        media_dir.mkdir()
        copied = {}
        for material in materials:
            original = material.path
            if original not in copied:
                destination = media_dir / f'{len(copied):03d}_{Path(original).name}'
                shutil.copy2(original, destination)
                copied[original] = str(destination.resolve())
            material.path = copied[original]
    s.append_tracks([draft.TrackSpec(draft.TrackType.video, '视频'), draft.TrackSpec(draft.TrackType.text, SUBTITLE_TRACK)])
    offset = 0
    count = 0
    mapping = []
    for clip, material in zip(clips, materials):
        start = round(clip['start'] * 1e6)
        dur = round(clip['end'] * 1e6) - start
        s.add_segment(draft.VideoSegment(material, draft.trange(offset, dur),
                      source_timerange=draft.trange(start, dur)), '视频')
        for sub in clip['subtitles']:
            a = offset + round(sub['start'] * 1e6) - start
            b = offset + round(sub['end'] * 1e6) - start
            s.add_segment(draft.TextSegment(sub['text'], draft.trange(a, b-a),
                          style=subtitle_style(size=11, align=1),
                          clip_settings=draft.ClipSettings(transform_y=-0.34)), SUBTITLE_TRACK)
            count += 1
        mapping.append({**clip, 'target_start_us': offset, 'duration_us': dur})
        offset += dur
    s.save()
    target = root / name
    if count:
        promote_draft_to_subtitles(target)
        if not verify_subtitle_draft(target)['ok']:
            raise ValueError('生成后字幕结构检查失败')
    from mac_draft import finalize_draft
    finalize_draft(target, root, args.profile)
    write_json(target / 'edit_plan.json', {'clips': mapping, 'duration_us': offset})
    print(json.dumps({'draft': str(target), 'duration_us': offset, 'subtitle_count': count,
                      'status': 'generated_pending_app_review',
                      'note': '基础草稿已生成；请在剪映内核对素材、声音、字幕和样式。'}, ensure_ascii=False))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    subs = ap.add_subparsers(dest='command', required=True)
    p = subs.add_parser('probe', help='读取视频显示尺寸、时长和音轨')
    p.add_argument('video')
    p = subs.add_parser('transcribe', help='本地 CPU 语音转写，不上传素材')
    p.add_argument('video'); p.add_argument('-o', '--output', required=True)
    p.add_argument('--model'); p.add_argument('--language', default='zh'); p.add_argument('--threads', type=int, default=4)
    p = subs.add_parser('build', help='按审核后的 JSON 计划生成基础草稿')
    p.add_argument('plan'); p.add_argument('--draft-root'); p.add_argument('--name')
    p.add_argument('--link-media', action='store_true', help='引用原素材而不复制；Mac 沙盒可能无法访问外部路径')
    p.add_argument('--profile', choices=['mac-5.5', 'windows'],
                   default='mac-5.5' if sys.platform == 'darwin' else 'windows')
    args = ap.parse_args(argv)
    if args.command == 'probe':
        print(json.dumps(probe(args.video), ensure_ascii=False, indent=2))
    elif args.command == 'transcribe':
        transcribe(args)
    else:
        build(args)
    return 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, subprocess.CalledProcessError) as e:
        print(f'失败：{e}', file=sys.stderr)
        sys.exit(1)
