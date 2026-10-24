# START HERE —— 给目标电脑上的 coding agent

你拿到的这个目录是一个**可自安装的部署包**：视频粗剪 skill（`local-video-rough-cut-jianying`）+ 它的工具链安装器 + 运行环境配方 + ASR 模型。
你的任务只有一件：**在这台机器上把它装上，并让自检全部通过**。装完之后用户就能让任意 agent 用它粗剪视频、生成剪映草稿。

> 读这一份就够了。包里其他文件是它的细节来源，按需查，不必先全读。

---

## 0. 三十秒判断：这台机器能不能装

| 条件 | 要求 | 不满足怎么办 |
|---|---|---|
| 操作系统 | Windows 10 / 11 x64 | 本包只支持 Windows（剪映专业版是 Windows/macOS，这里的脚本与路径都按 Windows 写） |
| 网络 | 能访问 python.org 和 PyPI | pip 失败时安装器会自动切清华镜像；完全断网时用 `--ffmpeg-zip` + `--model-from` 走本地文件（见 §5） |
| 磁盘 | ≥ 5 GB 空闲（venv 约 0.4 GB + 模型 1.6 GB + 缓存） | 换一个足够大的盘并加 `--tool-root` |
| 剪映专业版 | 建议已装（11.x） | 可以先装 skill，剪映后装；自检里剪映只是「可选」项，但**最终用户必须在剪映里打开草稿** |

包内**已经带了**：Python 3.12.10 安装器（`vendor\`）、`faster-whisper-large-v3-turbo` 模型（`models\`，1.6 GB）。
包内**没有带**：ffmpeg 二进制（安装器联网下载官方 7.x essentials 构建）、剪映本体。

> 拿到的是**精简版**（没有 `models\`，包只有几十 MB）？第 7 步会自动从 HuggingFace 拉模型（约 1.6 GB）；
> 也可以把单独的模型包解压到 `<包根>\models\` 再跑，就不会联网下模型。

---

## 1. 装（一条命令）

```bat
deploy\install.cmd
```

这条 `.cmd` 会先找 Python 3.12，找不到就静默安装 `vendor\python-3.12.10-amd64.exe`，然后调 `deploy\install.py`。
如果你确认这台机器已有 Python 3.12，也可以直接：

```bat
python deploy\install.py
```

安装器是**幂等**的：中断了、报错了，修好原因再跑一次即可，不会重复下载/重复建 venv。

它按顺序做 9 件事（每步都会打印 `[n/9]` 和结果）：

| 步骤 | 做什么 | 默认落点 |
|---|---|---|
| 1 | 对照 `manifest.json` 校验包完整性（sha256） | — |
| 2 | 确保 Python 3.12（必要时静默装包内安装器） | `%LOCALAPPDATA%\Programs\Python\Python312` |
| 3 | 定工具链根目录 | `E:\auto_cut\tools`；无 E 盘则 `%LOCALAPPDATA%\auto_cut\tools` |
| 4 | 装 ffmpeg / ffprobe | `<tool_root>\ffmpeg` |
| 5 | 建 jyenv + 装 `requirements-jy.txt`（写草稿） | `<tool_root>\jyenv` |
| 6 | 建 asrenv + 装 `requirements-asr.txt`（ASR） | `<tool_root>\asrenv` |
| 7 | 放 turbo 模型 | `<tool_root>\models\faster-whisper-large-v3-turbo` |
| 8 | 装 skill + **把文档里的旧机器路径改写成本机路径** | `%USERPROFILE%\.agents\skills\local-video-rough-cut-jianying` |
| 9 | 生成 `setup\detected.json` + `deploy\install-report.json` 快照 | skill 目录内 |

耗时参考：有网、机器普通 ≈ 6–12 分钟（模型不下载的话），主要花在 pip。

### 可选参数（只有需要时才用）

```bat
python deploy\install.py --tool-root "D:\cut\tools"      :: 工具链放别处
python deploy\install.py --skill-dir "D:\skills\local-video-rough-cut-jianying"
python deploy\install.py --draft-root "D:\剪映草稿"        :: 剪映设置里的实际草稿位置
python deploy\install.py --index https://mirrors.aliyun.com/pypi/simple
python deploy\install.py --use-ffmpeg "C:\ffmpeg\bin"     :: 机器上已有 ffmpeg，直接复制
python deploy\install.py --ffmpeg-zip "D:\ffmpeg-7.1-essentials_build.zip"
python deploy\install.py --model-from "D:\models\faster-whisper-large-v3-turbo"
python deploy\install.py --no-model                       :: 只装草稿链路，不要 ASR
python deploy\install.py --all-harnesses                  :: 同时装到 ~/.codex/skills 和 ~/.claude/skills
python deploy\install.py --verify                         :: 装完自动跑自检
```

---

## 2. 验（必须做，别跳过）

```bat
deploy\verify.cmd
```

或 `python deploy\verify.py`。它会造一条 5 秒竖屏样片（1080×1920，含音轨），不需要用户素材，逐项检查：

| 项 | 通过标准 |
|---|---|
| A 环境快照 | `setup\check_env.py` 退出码 0，必需项无 FAIL |
| B 文档路径 | `SKILL.md` / `references\env-and-pitfalls.md` / `setup\README.md` 里**不再出现** `E:\auto_cut\tools`、`E:\草稿\JianyingPro Drafts`、`C:\Users\lr286`、`E:\字幕规范提取` |
| C ffmpeg | `ffmpeg -version` 有输出，`ffprobe.exe` 同一目录 |
| D 样片 + 探针 | 造片成功；`smoke_probe.py` 打印 `canvas 1080 1920` |
| E 草稿 | `smoke_draft.py` 打印 `dur_us 3000000`（8 位数 = 微秒没搞错），轨道是 `['video', 'text']` |
| F 字幕链路 | `check_draft_subtitle.py` 返回 `ok: true`（`type=subtitle`、`group_id`、`words`、自动换行都在） |
| G ASR | 模型能加载、ctranslate2 能推理（喂 2 秒静音，只验链路） |
| H 剪映 | 可选：找到 `JianyingPro.exe` 就打勾 |
| I 草稿目录 | 可写 |

**全部必需项通过**才会打印「这台机器可以干活了」并返回 0。报告落在 `deploy\verify-report.json`。

想再验一次真人声 ASR（推荐，尤其交付给客户时）：

```bat
python deploy\verify.py --sample "D:\test\任意一条有人声的素材.MOV"
```

---

## 3. 装完还要做两件事（否则用户用不上）

1. **刷新技能列表**：agent 的技能是按目录扫描的，不热更新。新开一轮会话/重启客户端，确认技能目录里能看到 `local-video-rough-cut-jianying`（本会话里就能直接调用）。
2. **告诉用户在剪映里核对草稿位置**：剪映「设置 → 草稿位置」必须等于 `install-report.json` 里的 `draft_root`。不一致就用 `--draft-root` 重跑第 9 步那一段（或直接改 `references\env-and-pitfalls.md` 第 1 节那一行）。

---

## 4. 验收：真实任务跑一遍

给 skill 一条 10 秒左右、有人声的素材 + 一句台本，让它粗剪一次。看三件事：

1. 草稿出现在剪映草稿列表里（不出现 → 剪映从**托盘退出**再启动，或首页刷新）；
2. 轨道**只有 2 条**：视频 + 字幕；
3. 字幕**不是全片一字号一颜色**，每条有「渐显」，且能在剪映里看到「字幕」面板（不是「文本」面板）。

3 条都过，才算真装机成功。任何一条不过，看 §6。

---

## 5. 完全断网怎么装

按这个顺序准备，然后加 `--no-download`：

```bat
:: 1) ffmpeg 官方构建 zip（gyan.dev 或 BtbN 的 Windows 构建）
::    解压出 ffmpeg.exe / ffprobe.exe，或用 --ffmpeg-zip 直接给 zip
python deploy\install.py --no-download --use-ffmpeg "D:\ffmpeg\bin"

:: 2) 模型：包里 models\ 已有；如果被裁掉了，给一个本地模型目录
python deploy\install.py --no-download --model-from "D:\models\faster-whisper-large-v3-turbo"
```

`--no-download` 仍需要 PyPI 可达（pip 装依赖）；真要全离线，先在一台同架构机器上 `pip download -r deploy\requirements-*.txt -d wheelhouse`，再用 `--index file:///D:/wheelhouse`（或先 `pip install --no-index --find-links`）预装到两个 venv，最后 `--no-download` 跳过网络步骤。

---

## 6. 失败对照表

| 现象 | 原因 | 处理 |
|---|---|---|
| `[x] 部署包不完整` | 拷贝/解压不全、被网盘截断 | 重新完整传输，别只拷子目录；模型 1.6 GB 容易断 |
| Python 安装器跑完仍找不到 3.12 | 装了但没在当前 PATH | 用绝对路径 `%LOCALAPPDATA%\Programs\Python\Python312\python.exe deploy\install.py` |
| pip 卡住/超时 | 官方 PyPI 慢 | 加 `--index https://pypi.tuna.tsinghua.edu.cn/simple` |
| ffmpeg 下载失败 | gyan.dev 被墙/限速 | 手动下 zip，`--ffmpeg-zip <zip>`；或 `--use-ffmpeg <已有目录>` |
| `pymediainfo` 报找不到库 | MediaInfo.dll 缺失 | 装 MediaInfo 官方版；或重装 `pymediainfo==7.0.1` wheel |
| ASR 报 `metadata_errors` | `av>=16` 与 faster-whisper 不兼容 | **不要降 av**：把 PCM 数组直接喂模型（skill 里已是这么写的） |
| ASR 输出繁体 | 缺 `initial_prompt` | 必须 `initial_prompt="以下是普通话的句子。"` |
| 草稿里全是 0 帧 | `trange` 传了秒 | 单位是**微秒**，`SEC = 1_000_000`；`duration` 应是 8 位数 |
| 竖拍素材在剪映里横着/黑边 | 只读编码宽高，漏了 `side_data_list.rotation` | 按 display 尺寸算画布（self-check D 就是在查这个） |
| 草稿改不动、像乱码 | 剪映打开过的 `draft_content.json` 是密文 | 只能换新草稿名重生成；写之前确认剪映已从托盘退出、目录无 `.locked` |
| 剪映里看不到新草稿 | 外部生成的草稿不自动刷新 | 首页刷新；不行托盘退出重启剪映 |
| `.ps1` 无法运行 | 执行策略限制 | 本包**没有 .ps1**，一律用 `.py` / `.cmd` |
| 字幕面板没有、只有「文本」 | 文本素材是 `type="text"` | 必须跑 `scripts\subtitle_module.py`（self-check F 在查这个） |

---

## 7. 卸载 / 回滚

```bat
:: skill
rd /s /q "%USERPROFILE%\.agents\skills\local-video-rough-cut-jianying"
:: 工具链（含两个 venv 和模型）
rd /s /q "E:\auto_cut\tools"
:: 若是重装覆盖，旧 skill 在 .agents\skills\local-video-rough-cut-jianying.bak-<时间戳>
```

安装器**从不动**用户的草稿目录（只往 `<draft_root>\smoke_01` 写一条自检草稿）。已有 skill 目录会被重命名备份，不删除。

---

## 8. 目录里都是什么

```
粗剪skill部署包_v1\
├─ START_HERE.md                 ← 你正在读的这份（唯一入口）
├─ manifest.json                 ← 全部文件的 sha256 / 大小（安装器第 1 步用它校验）
├─ deploy\
│   ├─ install.cmd / install.py  ← 安装器（9 步，幂等）
│   ├─ verify.cmd / verify.py    ← 自检（A–I 九项）
│   ├─ requirements-jy.txt       ← jyenv 依赖（pyjianyingdraft 0.3.0 等）
│   ├─ requirements-asr.txt      ← asrenv 依赖（faster-whisper 1.2.1 等）
│   ├─ make_manifest.py          ← 打包期用（生成 manifest.json），用户不用跑
│   └─ checks\                   ← 自检用的三个小脚本（造样片 / 查字幕链路 / 查 ASR）
├─ payload\skill\local-video-rough-cut-jianying\   ← skill 本体（31 个文件，装到 .agents\skills）
│   ├─ SKILL.md                  ← 技能主文档（YAML frontmatter 必须保留）
│   ├─ references\               ← 字幕规范 v2/v3、切点规则、环境坑位、字幕模块说明
│   ├─ scripts\subtitle_module.py← 字幕升级/校验
│   └─ setup\                    ← check_env.py + 三个 smoke
├─ vendor\python-3.12.10-amd64.exe  ← 没有 Python 时用它静默装
└─ models\faster-whisper-large-v3-turbo\  ← ASR 模型（1.6 GB，可整目录挪走）
```

`deploy\install-report.json` 和 `deploy\verify-report.json` 是**安装后**生成的，不要随包分发。

---

## 9. 交付时向用户回报什么

- 安装路径三件套：`skill_dir` / `tool_root` / `draft_root`（都在 `install-report.json`）
- `verify.py` 的结论：全部必需项通过 / 哪几项没过 + 原因
- 剪映是否已装、版本；若没装，提醒「先装剪映再精剪」
- 是否已刷新技能列表（用户要新开一轮会话才能看到 skill）
- 一句真实任务验收的结果（§4 的三条）

不要只说「装好了」——`verify-report.json` 的 `ok` 才是证据。
