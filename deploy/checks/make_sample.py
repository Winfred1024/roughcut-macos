# -*- coding: utf-8 -*-
"""造一条 5 秒竖屏测试素材（无版权问题、不依赖用户文件）。

    python make_sample.py <ffmpeg.exe> <输出.mp4>

产出：1080x1920 / 30fps / H.264 + 44.1k AAC，用于跑 probe / draft 两个 smoke。
"""
import subprocess
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print(__doc__)
        return 2
    ffmpeg, out = sys.argv[1], Path(sys.argv[2])
    out.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        ffmpeg, "-y", "-loglevel", "error",
        "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=5",
        "-f", "lavfi", "-i", "sine=frequency=440:duration=5",
        "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "96k", "-shortest", str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print("FAIL  ffmpeg 造样片失败：", (r.stderr or "")[-600:])
        return 1
    if not out.exists() or out.stat().st_size < 10_000:
        print("FAIL  样片没生成或太小")
        return 1
    print(f"OK  样片 {out}  {out.stat().st_size / 1024:.0f} KB")
    return 0


if __name__ == "__main__":
    sys.exit(main())
