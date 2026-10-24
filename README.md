# RoughCut for macOS

将 Windows 粗剪技能部署包改为可在 macOS 执行的本地工具项目，支持 Apple Silicon 与 Intel（Intel 尚未实机验证）。保留原 Windows 入口；macOS 使用本页流程。

## 1. 准备

需要 macOS、Python 3.12/3.13 和 ffmpeg。推荐使用 Homebrew：

```bash
brew install python@3.12 ffmpeg
```

已装 uv 也可使用 `uv python install 3.12`；安装器会自动寻找该解释器。Finder 双击 `.command` 时 PATH 可能不同，安装器也会查找 `/opt/homebrew` 和 `/usr/local`。

## 2. 安装

```bash
cd '/项目所在目录/roughcut-macos'
./install.command --verify
```

默认联网安装两个隔离环境、从 Hugging Face 下载约 1.6 GB ASR 模型，并安装技能到 `~/.agents/skills/local-video-rough-cut-jianying`。原技能会先备份到技能扫描目录之外的 skill-backups，备份失败则停止。

```bash
# 已有原部署包的模型可复用，避免重新下载
./install.command --model-from '/原包/models/faster-whisper-large-v3-turbo' --verify

# 指定剪映设置显示的实际草稿目录
./install.command --draft-root '/实际/草稿目录' --verify

# 只安装草稿生成链路，省略 ASR 和模型
./install.command --no-model --verify

# 官方 PyPI 慢时选择镜像（仍校验 HTTPS）
./install.command --index https://pypi.tuna.tsinghua.edu.cn/simple --verify
```

配置默认保存在 `~/Library/Application Support/RoughCut/config.json`，工具环境在同目录的 `tools`。草稿位置无法唯一探测时使用同目录 `drafts` 暂存，并提示核对剪映设置。没有剪映也能生成草稿，但不能完成应用内验收。

其他参数见 `./install.command --help`。离线安装需要 `--offline --wheelhouse '/本地wheel目录' --model-from '/完整模型'`，wheel 必须匹配 Python 版本和 Mac 架构。安装器不会自动安装 Homebrew 或执行 Windows 安装程序。

## 3. 使用

```bash
./run.sh probe '/素材/视频.mov'
./run.sh transcribe '/素材/视频.mov' -o '/工作目录/asr.json'
./run.sh build examples/edit_plan.json --name '我的粗剪'
./verify.command
```

先将示例计划中的视频路径、保留区间及字幕改为实际内容。计划内时间单位为秒，字幕使用原素材时间；程序自动映射到剪后时间轴。ASR JSON 的 segments 可供 agent 整理为计划中的 subtitles。程序不负责自动理解台本或决定应删除哪些口播。

详细格式与限制见 [macOS 指南](payload/skill/local-video-rough-cut-jianying/references/macos.md)。仅草稿模式自检会明确跳过 ASR，不会把未测试的能力报告为可用。

build 默认输出 macOS 剪映 5.5 格式（`draft_info.json` / `103.0.0`），同时保留 `draft_content.json`。基础两轨草稿保留原声，默认把素材复制到工程 media 目录以兼容 Mac 沙盒，不覆盖已有草稿。可用 --link-media 只引用源文件，但需自行保证剪映有访问权限。字幕样式、动画和不同剪映版本兼容性仍需在剪映里验收。当前不包含成片 MP4 渲染器，导出视频请在剪映中完成。

## 4. 测试

```bash
python3 -m unittest discover -s tests -v
```

此轻量项目包不再携带 Windows Python 安装器和 1.6 GB 模型；模型可联网下载或从原 ZIP 解压后通过 `--model-from` 复用。

macOS 自检使用真实 ffmpeg 和草稿库生成测试工程，检查完成后删除临时素材与工程。报告保存在配置文件旁的 `verify-report.json`。本机已在剪映专业版 5.5.0 完成打开、字幕编辑和 MP4 导出验收，详见 `VALIDATION.md`。

## 5. Windows 兼容

原 `deploy/install.cmd` 和 `deploy/verify.cmd` 保留用于 Windows。其修复已覆盖安全备份、默认路径误报和子进程路径传递；本次未进行 Windows 实机回归。`START_HERE_WINDOWS.md` 为原始 Windows 说明。
