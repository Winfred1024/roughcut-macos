# -*- coding: utf-8 -*-
"""ASR 链路自检：模型能否加载 + ctranslate2 能否推理（不需要人声素材）。

    <asrenv\\python.exe> check_asr.py <模型目录>

喂 2 秒静音 PCM 给模型：重点是「模型能加载、ct2 能跑、av 版本不拦路」，
不校验识别文字（静音本来就该没文字）。真素材验收用 skill 的 smoke_asr.py。
"""
import json
import sys


def main() -> int:
    if len(sys.argv) != 2:
        print(__doc__)
        return 2
    model_dir = sys.argv[1]
    out = {"model_dir": model_dir, "ok": False}
    try:
        import numpy as np
        import ctranslate2
        from faster_whisper import WhisperModel

        out["ct2"] = ctranslate2.__version__
        model = WhisperModel(model_dir, device="cpu", compute_type="int8", cpu_threads=2)
        out["loaded"] = True
        # 坑 3：av>=16 时不能让它自己开文件，直接喂 PCM 数组
        audio = np.zeros(16_000 * 2, dtype=np.float32)
        segments, info = model.transcribe(audio, language="zh", vad_filter=False)
        segs = list(segments)
        out["language"] = info.language
        out["segments"] = len(segs)
        out["ok"] = True
    except Exception as e:  # noqa: BLE001
        out["error"] = f"{type(e).__name__}: {e}"
    print(json.dumps(out, ensure_ascii=False))
    return 0 if out["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
