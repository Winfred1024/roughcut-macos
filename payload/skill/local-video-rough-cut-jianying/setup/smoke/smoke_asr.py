# -*- coding: utf-8 -*-
"""smoke 3/3：截 5 秒音频喂给 faster-whisper，确认 ASR 与「av>=16 绕过」都正常。

    python setup/smoke/smoke_asr.py <video>
期望：带时间码的中文 + language zh。若这里报 metadata_errors，就是坑 3（见 SKILL.md 坑 3）。
"""
import subprocess
import tempfile
import wave
from pathlib import Path

import numpy as np
from faster_whisper import WhisperModel

from _paths import ffmpeg, model_turbo, sample_video

SRC = sample_video()
tmp = Path(tempfile.gettempdir()) / 'dsh_smoke_asr.wav'
subprocess.run([ffmpeg(), '-y', '-loglevel', 'error', '-ss', '1', '-t', '5',
                '-i', SRC, '-vn', '-ac', '1', '-ar', '16000', '-c:a', 'pcm_s16le', str(tmp)], check=True)
with wave.open(str(tmp), 'rb') as w:
    x = np.frombuffer(w.readframes(w.getnframes()), dtype=np.int16).astype(np.float32) / 32768.0
print('samples', len(x), 'sec', round(len(x) / 16000, 2))

m = WhisperModel(model_turbo(), device='cpu', compute_type='int8', cpu_threads=4)
segs, info = m.transcribe(x, language='zh', vad_filter=True, word_timestamps=True,
                          condition_on_previous_text=False, initial_prompt='以下是普通话的句子。')
n = 0
for s in segs:
    n += 1
    print(f'{s.start:6.2f}-{s.end:6.2f} {s.text.strip()}')
print('language', info.language)
print('OK  ASR 可用' if n else 'FAIL  没识别出任何句子，检查素材是否有口播')

raise SystemExit(0 if n else 1)
