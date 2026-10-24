# -*- coding: utf-8 -*-
"""打包期工具：为部署包生成 manifest.json（安装器第 1 步用它校验完整性）。

    python deploy\\make_manifest.py

不要把它当成用户步骤——它只在**制作这个包的那台机器**上跑一次。
"""
from __future__ import annotations

import hashlib
import json
import sys
import time
from pathlib import Path

BUNDLE = Path(__file__).resolve().parent.parent
SKIP_DIRS = {"__pycache__", ".git", ".venv", "venv", ".cache", ".pytest_cache", "models", "vendor"}
SKIP_NAMES = {"manifest.json", "install-report.json", "verify-report.json", "detected.json"}


def sha256(p: Path) -> str:
    h = hashlib.sha256()
    with p.open("rb") as f:
        for chunk in iter(lambda: f.read(4 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def main() -> int:
    files = []
    for p in sorted(BUNDLE.rglob("*")):
        if not p.is_file():
            continue
        if any(part in SKIP_DIRS or part.startswith(".bak-") for part in p.parts):
            continue
        if p.name in SKIP_NAMES or ".bak-" in p.name:
            continue
        files.append({
            "path": p.relative_to(BUNDLE).as_posix(),
            "size": p.stat().st_size,
            "sha256": sha256(p),
        })
        print(f"  {files[-1]['size']/1e6:9.3f} MB  {files[-1]['path']}")
    total = sum(f["size"] for f in files)
    data = {
        "bundle": "粗剪skill部署包_v1",
        "created_at": time.strftime("%Y-%m-%d %H:%M:%S"),
        "file_count": len(files),
        "total_bytes": total,
        "total_human": f"{total/1e9:.2f} GB",
        "files": files,
    }
    out = BUNDLE / "manifest.json"
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"\nOK  {len(files)} 个文件，共 {total/1e9:.2f} GB -> {out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
