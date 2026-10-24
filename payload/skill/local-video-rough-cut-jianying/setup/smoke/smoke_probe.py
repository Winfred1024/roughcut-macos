# -*- coding: utf-8 -*-
"""smoke 1/3：读一条真实素材，确认 ffprobe 可用 + 竖拍 rotation 判定正确。

    python setup/smoke/smoke_probe.py <video>
期望：打印 coded 宽高 / rotation / 时长，并给出 canvas 与 display 尺寸。
"""
import json
import subprocess

from _paths import ffprobe, sample_video

F = sample_video()
info = json.loads(subprocess.run([ffprobe(), '-v', 'error', '-print_format', 'json',
                                  '-show_format', '-show_streams', F],
                                 capture_output=True, text=True, encoding='utf-8',
                                 errors='replace', check=True).stdout)
v = next(s for s in info['streams'] if s['codec_type'] == 'video')
rot = next((sd['rotation'] for sd in v.get('side_data_list', []) if 'rotation' in sd), None)
print('coded', f"{v['width']}x{v['height']}", 'rotation', rot, 'dur', info['format']['duration'])

rot = float(rot or v.get('tags', {}).get('rotate', 0))
display = (v['height'], v['width']) if round(rot) % 180 == 90 else (v['width'], v['height'])
portrait = display[1] > display[0]
W, H = (1080, 1920) if portrait else (1920, 1080)
print('canvas', W, H)
print('display', display)
print('OK  ffprobe 可用' + ('，且识别为竖拍' if portrait else '，且识别为横拍'))
