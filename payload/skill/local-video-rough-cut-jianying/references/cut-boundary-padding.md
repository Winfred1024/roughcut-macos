# 切点保护带规则（cut-boundary-padding）

粗剪切的是"气口"，不是"波形"。单看电平判断"哪里是字尾"一定出错。

## 真案例（别重犯）

字尾后有一段 −33 dBFS、0.24 s 的尾音（"友"的韵尾），被当成场外杂音切掉，转写从"老朋友"变成"老伴"。波形上一眼看不出区别，听感与转写才看得出来。

## 保护带

```
切点 = 字首 onset − 0.20 s  …  字尾 offset + 0.20 s
```

- 两侧各留 **0.20 s**，再吸附到最近的静音窗内沿。
- 宁长勿短：多留 100 ms 气口听不出来，少留 50 ms 尾音就没了。

## 静音窗判定（20 ms RMS 包络）

```python
import wave, numpy as np
FRAME, DB = 0.02, -45.0
with wave.open(wav, "rb") as w:
    sr, raw = w.getframerate(), w.readframes(w.getnframes())
x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
n = int(sr * FRAME)
db = np.array([20*np.log10(np.sqrt(np.mean(x[i*n:(i+1)*n]**2) + 1e-12) + 1e-12)
               for i in range(len(x)//n)])
quiet = db < DB      # 连续 >= 2 帧（40 ms）才算静音窗
```

- 帧长 20 ms，阈值 −45 dBFS。
- **连续 ≥ 2 帧（40 ms）** 才算静音窗；单帧静音是采样抖动，不作数。
- 切点吸附到静音窗**内沿**（靠近语音那一侧），不要吸到窗中心——吸到中心等于把气口吃掉一半。

## 回读校验（唯一可靠判据）

```python
def transcribe_range(src, a, b):
    extract_wav(src, a, b, tmp)                     # ffmpeg -ss a -t (b-a)
    segs, _ = model.transcribe(read_wav(tmp), language="zh", vad_filter=False)
    return "".join(s.text for s in segs).strip()

cut = transcribe_range(src, head, tail)
ext = transcribe_range(src, head, tail + 0.5)
assert cut[-4:] == ext[-4:], f"尾部被切：{cut[-6:]!r} vs {ext[-6:]!r} → tail 后移重切"
```

规则：

1. 对每个切点做两次转写：**as-cut**（head..tail）和 **尾部 +0.5 s**（head..tail+0.5）。
2. **末 4 个字必须一致**，不一致就是尾巴被切了 → `tail` 后移 0.1 s 重切，直到一致。
3. 用 `vad_filter=False`，VAD 会自己吞掉短尾音，掩盖问题。
4. 这一步不能省、不能靠波形"看起来对"跳过。

## 拼接后整体复检

所有片段拼完后，对成片再整体转写一遍：

- 句子完整、无截断（尤其是每段衔接处）
- 无"嗯/啊/这个/那个"等口令残留
- 与台本对照，缺句或多句都要查原因

## 常见误判

| 现象 | 原因 | 处理 |
|---|---|---|
| 末字变另一个字 | 尾音被切 | tail 后移重切（本文核心） |
| 段首吞字 | 保护带太窄 | head 前移 0.1 s |
| 段间有明显"咔" | 切在语音中间 | 吸附到静音窗，别用固定偏移 |
| 整段听不清 | VAD 切掉了低音量音节 | 转写时 `vad_filter=False`，VAD 只用于定位气口 |
