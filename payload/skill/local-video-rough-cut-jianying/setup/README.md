# 换机器安装指南（把这个 skill 搬到另一台 Windows）

> **本机已由部署包安装过？** 那 §1–§3（复制目录、装工具链、改路径表）已经由 `deploy\install.py` 自动做完，
> 你只需要看 §4 的自检和 §6 的坑表。这份文件保留原文，用于「手工搬家」或排查安装到底改了什么。

一句话：**整个目录拷过去 + 改一张路径表 + 跑三个 smoke**，就这一步。

本 skill 是「文档 + 脚本」型的技能，**不含模型/编解码器/剪映本体**，依赖是外部工具链。
所以换机器的成本，主要花在把工具链搬过去，而不是改 skill 本身。

---

## 1. 复制到哪

放到目标机器当前用户的技能目录，**目录名与来源保持一致**：

```
C:\Users\<用户名>\.agents\skills\local-video-rough-cut-jianying\
├─ SKILL.md                      ← 必须保留顶部的 YAML frontmatter（name / description），技能索引读它
├─ agents\openai.yaml            ← 部分 harness 用来显示名称/默认提示词，可留可删
├─ references\
│   ├─ env-and-pitfalls.md       ← 本机路径表（换机器唯一必改的文件）
│   ├─ cut-boundary-padding.md
│   ├─ subtitle-presentation-spec.md
│   └─ subtitle-style-details.xlsx
└─ setup\                        ← 本次新增：换机器自检 + smoke + 本说明
    ├─ check_env.py
    ├─ detected.json             ← 本机生成物（`--json` 写出），**换机器别拷这个文件**
    └─ smoke\{_paths.py, smoke_probe.py, smoke_draft.py, smoke_asr.py}
```

拷完**让 agent 重新加载技能列表**（重启会话/客户端，或新开一轮对话）——技能是按目录扫描的，不会热更新。
验证是否被发现：新会话里让它「列一下可用技能」，应能看到 `local-video-rough-cut-jianying`。

> 不要只拷 `SKILL.md`。`references\` 里是唯一依据，缺了它 agent 只能临场编样式。

---

## 2. 工具链怎么来（三选一）

目标机器需要这些**外部依赖**：

| 组件 | 本机实测版本 | 用途 |
|---|---|---|
| ffmpeg / ffprobe | 7.1 essentials | 抽帧、转 wav、拼预览 |
| 环境 A `jyenv` | Python 3.12.10 + `pyjianyingdraft==0.3.0`、`pymediainfo==7.0.1`、`pillow==13.0.0` | 写剪映草稿 |
| 环境 B `asrenv` | Python 3.12.10 + `faster-whisper==1.2.1`、`ctranslate2==4.8.2`、`numpy==2.5.4`、`av==19.0.1`、`onnxruntime==1.31.0`、`tokenizers==0.23.3` | 本地语音识别 |
| 模型 | `faster-whisper-large-v3-turbo`（1.5 GB）、可选 `faster-whisper-small`（464 MB） | ASR |
| 剪映专业版 | 11.6.0.14552 | 打开草稿继续精剪 |

**方案 A（最省事，推荐）**：把整台机器上的 `E:\auto_cut\tools` 目录原样拷到新机器**同一盘符同一路径**，路径表一个字都不用改。

**方案 B（新装）**：按本机结构重建，两个 venv **不能合并**（`av`/`numpy` 版本会打架）：

```powershell
# 目录骨架
$T = 'E:\auto_cut\tools'
New-Item -ItemType Directory -Force "$T\ffmpeg","$T\models" | Out-Null

# ffmpeg 7.1 essentials：解压到 $T\ffmpeg（含 ffmpeg.exe / ffprobe.exe）

# 环境 A：写草稿
py -3.12 -m venv "$T\jyenv"
& "$T\jyenv\Scripts\python.exe" -m pip install -U pip
& "$T\jyenv\Scripts\python.exe" -m pip install pyjianyingdraft==0.3.0 pymediainfo==7.0.1 pillow==13.0.0

# 环境 B：ASR
py -3.12 -m venv "$T\asrenv"
& "$T\asrenv\Scripts\python.exe" -m pip install -U pip
& "$T\asrenv\Scripts\python.exe" -m pip install faster-whisper==1.2.1 ctranslate2==4.8.2 numpy==2.5.4 av==19.0.1
```

**模型**：最快是直接从旧机器拷 `E:\auto_cut\tools\models\faster-whisper-large-v3-turbo`（含 `model.bin`）。
要用下载的话，faster-whisper 会在首次调用时自动拉取到 `%USERPROFILE%\.cache\huggingface`，此时把 `references\env-and-pitfalls.md` 里的模型路径改成缓存目录即可。

**方案 C**：工具链放网络盘/共享目录，只改路径表（只读共享注意不要多人同时写草稿）。

---

## 3. 改路径表（唯一必改的地方）

打开 `references\env-and-pitfalls.md` 第 1 节「绝对路径」那张表，把 7 行改成新机器的实际路径：

| 行 | 改成 |
|---|---|
| ffmpeg / ffprobe | 新机器的 `ffmpeg.exe` / `ffprobe.exe` |
| 环境 A / 环境 B | 两个 venv 的 `python.exe` |
| 模型 turbo / small | `model.bin` 所在目录 |
| 草稿根目录 | 剪映「设置 → 草稿位置」里的实际目录 |
| smoke 脚本 | 这行可以删掉（现在用 `setup\smoke\`） |

另外两处 `E:\字幕规范提取\...` 是**可选**的，只在「以后要改规范 / 查分类台本」时才用到，新机器没有就把对应半句删掉：
- `SKILL.md` 第 7 步「分类卡只影响两件事」里的分类库路径；
- `SKILL.md` 文末参考表里 `subtitle-presentation-spec.md` 的源文件路径。

草稿根目录在 `SKILL.md` 第 9 步已改成引用这张表，不用再单独改。

---

## 4. 自检 + 三个 smoke

```powershell
$SK = "$env:USERPROFILE\.agents\skills\local-video-rough-cut-jianying"

# ① 环境自检（纯标准库，任意 python 都能跑）
python "$SK\setup\check_env.py"
python "$SK\setup\check_env.py" --json     # 顺便写出 setup\detected.json，smoke 脚本会优先读它

# ② 三个 smoke：随便给一条真实素材
$video = 'D:\test\任意一条素材.MOV'
& 'E:\auto_cut\tools\jyenv\Scripts\python.exe'   "$SK\setup\smoke\smoke_probe.py" $video
& 'E:\auto_cut\tools\jyenv\Scripts\python.exe'   "$SK\setup\smoke\smoke_draft.py" $video
& 'E:\auto_cut\tools\asrenv\Scripts\python.exe'  "$SK\setup\smoke\smoke_asr.py"   $video
```

> `detected.json` 是**本机**探测结果。把 skill 目录拷到新机器时别带上它（指向旧路径）；在新机器上重新 `--json` 生成一次即可。
> 不生成也能跑：smoke 会退回环境变量/默认路径，`check_env.py` 本身不依赖它。

期望输出：

| smoke | 期望 |
|---|---|
| ① probe | `coded 1920x1080 rotation -90` → `canvas 1080 1920`（竖拍判定正确） |
| ② draft | `canvas {...} tracks ['video','text'] dur_us 3000000`（8 位数，微秒没搞错） |
| ③ asr | 带时间码的中文 + `language zh` |

② 会覆盖草稿目录里的 `smoke_01`，不影响已有草稿；跑前把剪映从**托盘**退出。

---

## 5. 真实任务验收

拿一条 10 秒左右、有口播的素材 + 一句话台本，完整走一遍，检查三件事：

1. 草稿出现在剪映草稿列表里（不出现就托盘退出重启剪映）；
2. 轨道**只有 2 条**（视频 + 字幕）；
3. 字幕**不是全片一字号一颜色**，且每条有渐显。

上面 3 条过了，才说明这台机器真的能干活。

---

## 6. 本机踩过的坑（换机器大概率还会踩）

| 现象 | 原因 | 处理 |
|---|---|---|
| `trange` 传了秒，草稿全是 0 帧 | 库的单位是**微秒** | `us = int(round(sec*1_000_000))`；自查 `duration` 应为 8 位数 |
| 竖拍素材在剪映里横着/两侧黑边 | 只读了编码宽高，漏了 `side_data_list.rotation` | 按 display 尺寸算画布（smoke ① 就是在查这个） |
| ASR 报 `metadata_errors` | `av>=16` 与 faster-whisper 不兼容 | 不要降级 av，把 PCM 数组直接喂模型（`read_wav` + `model.transcribe(array)`） |
| ASR 输出繁体 | 缺 `initial_prompt` | 必加 `initial_prompt="以下是普通话的句子。"` |
| 草稿被剪映打开后变密文，改不动 | 剪映会加密打开过的 `draft_content.json` | 只能换新草稿名重生成；写前确认剪映已从托盘退出、目标目录无 `.locked` |
| `.ps1` 脚本报「未数字签名」 | 执行策略 | 用 `.py` 脚本，别用 `.ps1` |
| 剪映里找不到刚生成的草稿 | 外部生成的草稿不自动刷新 | 首页刷新；不行就托盘退出重启剪映 |
| `pymediainfo` 报找不到库 | MediaInfo 动态库缺失 | 用官方 wheel（自带）；仍报错就装 MediaInfo 并把 dll 放 PATH |

---

## 7. 一页速查

```powershell
# 搬家 = 3 步
# 1) 拷目录：...\.agents\skills\local-video-rough-cut-jianying\  （连同 references\ 和 setup\）
# 2) 拷/装工具链：E:\auto_cut\tools\{ffmpeg, jyenv, asrenv, models}
# 3) 改 references\env-and-pitfalls.md 第 1 节路径表
# 验收：
python "$env:USERPROFILE\.agents\skills\local-video-rough-cut-jianying\setup\check_env.py"
```
