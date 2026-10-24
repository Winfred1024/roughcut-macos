# 本机环境与技术约定（env & pitfalls）

本机 2026-10-19 装机实测，所有路径已跑通 smoke。**执行前先读这一页**——下面四条坑每条都能让整条片子返工。

> **换到另一台机器**：见 `setup\README.md`；先跑 `python setup\check_env.py` 自检，再按第 1 节把下面这张表改成新机器的路径。本文其余内容（四个坑、切点规则）与机器无关。

## 一、绝对路径（不要依赖 PATH）

| 组件 | 路径 | 版本 |
|---|---|---|
| ffmpeg | `E:\auto_cut\tools\ffmpeg\ffmpeg.exe` | 7.1-essentials_build |
| ffprobe | `E:\auto_cut\tools\ffmpeg\ffprobe.exe` | 7.1-essentials_build |
| 环境 A（写草稿） | `E:\auto_cut\tools\jyenv\Scripts\python.exe` | Python 3.12.10 + pyjianyingdraft 0.3.0 |
| 环境 B（ASR） | `E:\auto_cut\tools\asrenv\Scripts\python.exe` | Python 3.12.10 + faster-whisper 1.2.1 / ctranslate2 4.8.2 / numpy 2.5.4 / av 19.0.1 |
| 模型 turbo | `E:\auto_cut\tools\models\faster-whisper-large-v3-turbo` | model.bin 1542.9 MB |
| 模型 small | `E:\auto_cut\tools\models\faster-whisper-small` | model.bin 461.1 MB |
| 草稿根目录 | `E:\草稿\JianyingPro Drafts` | 剪映专业版 11.6.0.14552 |
| smoke 脚本 | `E:\auto_cut\tools\smoke\smoke_{probe,draft,asr}.py` | 已跑通 |

- 系统 PATH 里另有 winget 装的 ffmpeg 9.0.2，**流程不用它**，一律走上面的绝对路径。
- 两个 Python 环境**不能合并**（torch/av/numpy 会打架）。不要往 `asrenv` 装 torch/torchaudio/whisperx。

## 二、四个必踩的坑

### 坑 1：`trange` 单位是微秒，不是秒

`pyJianYingDraft` 的 `Timerange` 永远是微秒。传秒进去**不报错**，但每段变成几微秒，剪映里全部塌成 0 帧。

```python
from pyJianYingDraft import SEC          # SEC == 1_000_000
def us(sec: float) -> int:
    return int(round(sec * SEC))
```

自查：`draft_content.json` 的 `duration` 应该是 8 位数（如 `23580000`），**不是** `23`。

### 坑 2：竖拍素材被当成横屏

iPhone/安卓竖拍常见：编码 `1920x1080` + 旋转元数据 `rotation=-90`，实际显示是 1080×1920。只读 coded 宽高会判错。

```python
v = next(s for s in info["streams"] if s["codec_type"] == "video")
rot = next((sd["rotation"] for sd in v.get("side_data_list", []) if "rotation" in sd), None)
portrait = rot in (-90, 270) or v["height"] > v["width"]
W, H = (1080, 1920) if portrait else (1920, 1080)
```

判错后果：竖屏塞进横屏画布 → 两侧黑边，字幕按横屏宽度排版直接溢出。

### 坑 3：`av>=16` 让 ASR 直接崩

`faster_whisper` 默认用 PyAV 打开文件，报
`TypeError: open() got an unexpected keyword argument 'metadata_errors'`。
**不要为此降级 av**，把 PCM 数组直接喂给模型：

```python
import wave, numpy as np
def read_wav(path):                      # 16 kHz 单声道 s16le
    with wave.open(str(path), "rb") as w:
        raw = w.readframes(w.getnframes())
    return np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0

segments, info = model.transcribe(read_wav(wav), language="zh",
                                  vad_filter=True, word_timestamps=True,
                                  condition_on_previous_text=False,
                                  initial_prompt="以下是普通话的句子。")
```

`initial_prompt` 必加：不加时 Whisper 常输出**繁体**（实测「還有一天我們三千平方的倉儲店」），会污染字幕。

### 坑 4：剪映打开过的草稿不能再改

打开后生成 `draft_cover.jpg`、`.locked` 等，`draft_content.json` 变密文。所以：

- 脚本只在**生成阶段**写草稿；
- 要改就**换新草稿名重新生成**，绝不覆盖；
- 生成前先 `assert not (draft_dir / ".locked").exists()`；
- 生成前确认剪映已**托盘右键退出**（`Get-Process JianyingPro` 无输出；只关窗口进程还在）。

## 三、其它容易漏的点

| 现象 | 原因 | 处理 |
|---|---|---|
| 草稿列表不刷新 | 外部生成的草稿不自动出现 | 首页点刷新；还不行托盘退出重启剪映 |
| `force_apply_line_max_width` 恒 false | 库导出写死 | 生成后改 JSON：置 true、`line_max_width=0.82`、`line_feed=1`（见 SKILL.md 第 8 步） |
| `drawtext` 字体/文本路径报错 | 中文路径 + `C:` 冒号被滤镜吃掉 | 字体和文本复制到工作目录，`cwd` 切进去，用相对路径 |
| 剪映换版本后打不开 | 草稿格式随版本变 | 先跑 `smoke_draft.py`，能打开再跑真素材 |
| 出现 `trange_seconds` | 装到了另一个发行版 | 0.3.0 只有 `trange(start, duration)`，重装 |

## 四、一条命令自检

```powershell
$env:PYTHONIOENCODING='utf-8'
& "E:\auto_cut\tools\jyenv\Scripts\python.exe"   "E:\auto_cut\tools\smoke\smoke_probe.py"
& "E:\auto_cut\tools\jyenv\Scripts\python.exe"   "E:\auto_cut\tools\smoke\smoke_draft.py"
& "E:\auto_cut\tools\asrenv\Scripts\python.exe"  "E:\auto_cut\tools\smoke\smoke_asr.py"
```

期望依次：`coded 1728x3072 … 1080 1920` / `canvas … dur_us 3000000` / 带时间码中文 + `language zh`。
