# -*- coding: utf-8 -*-
"""smoke 2/3：用 pyJianYingDraft 造一个 3 秒草稿，确认库能用、微秒单位正确。

    python setup/smoke/smoke_draft.py <video>
期望：canvas 1080x1920 / tracks ['video','text'] / dur_us 3000000（8 位数）。
"""
import json
import pathlib

from pyJianYingDraft import SEC, trange, DraftFolder, TrackSpec, TrackType, VideoSegment, TextSegment, TextStyle, ClipSettings

from _paths import draft_root, sample_video

SRC = sample_video()
OUT = draft_root()
name = 'smoke_01'
assert not (pathlib.Path(OUT) / name / '.locked').exists(), 'smoke_01 被剪映占用，先从托盘退出剪映'
s = DraftFolder(str(OUT)).create_draft(name, 1080, 1920, fps=30, allow_replace=True)
s.append_tracks([TrackSpec(TrackType.video, '视频'), TrackSpec(TrackType.text, '字幕')])
s.add_segment(VideoSegment(SRC, trange(0, 3 * SEC), source_timerange=trange(1 * SEC, 3 * SEC)), '视频')
s.add_segment(TextSegment('测试字幕\n第二行', trange(0, 3 * SEC),
                          style=TextStyle(size=8.5, align=1),
                          clip_settings=ClipSettings(transform_y=-0.28)), '字幕')
s.save()
dc = json.loads((pathlib.Path(OUT) / name / 'draft_content.json').read_text(encoding='utf-8'))
print('canvas', dc['canvas_config'], 'tracks', [t['type'] for t in dc['tracks']], 'dur_us', dc['duration'])
seg = dc['tracks'][0]['segments'][0]
print('target', seg['target_timerange'], 'source', seg['source_timerange'])
assert dc['duration'] == 3 * SEC, f'时长必须是微秒（期望 {3 * SEC}），实际 {dc["duration"]}'
print('OK  草稿已生成，时长单位正确 ->', pathlib.Path(OUT) / name)
