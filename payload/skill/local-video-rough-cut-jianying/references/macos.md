# macOS 执行指南

本项目提供本地粗剪的环境和可执行工具。剪辑顺序和切点来自人工或 agent 审核的 edit_plan；程序不擅自按台本删掉素材。

## 配置与环境

先读 `setup/detected.json`。它是当前机器路径的权威来源，覆盖其他参考文档中的旧 Windows 路径示例。

- `jyenv`：草稿工具的 Python；`asrenv`：ASR Python（仅草稿安装时为 null）。
- `ffmpeg`、`ffprobe`：原生可执行文件，不带 `.exe`。
- `draft_root`：输出目录。使用剪映设置里的实际草稿目录；默认暂存目录不能保证出现在首页。
- macOS 关闭剪映请使用 ⌘Q。禁止使用 Windows PowerShell、盘符和 `Scripts/python.exe`。
- Apple Silicon 的 faster-whisper 使用 CPU int8；不支持 CUDA / Metal，本项目不会声称使用 MPS。

## 可执行命令

在项目根目录运行：

```bash
./run.sh probe '/绝对路径/素材.mov'
./run.sh transcribe '/绝对路径/素材.mov' -o '/绝对路径/asr.json'
./run.sh build '/绝对路径/edit_plan.json' --name '示例粗剪'
./verify.command
```

如配置不在默认位置，在子命令前加 `./run.sh --config '/路径/config.json' probe ...`。

所有时间单位在计划文件中是**秒**；写入草稿时统一转换为微秒。字幕时间是原素材时间，生成时按保留区间映射到目标时间轴。字幕跨越切点时先根据实际逐词 ASR 拆分，禁止把整句话复制到切点两边。

```json
{
  "width": 1080,
  "height": 1920,
  "fps": 30,
  "clips": [
    {
      "source": "/绝对路径/素材.mov",
      "start": 1,
      "end": 4,
      "subtitles": [{"start": 1.2, "end": 3.5, "text": "实际口播内容"}]
    }
  ]
}
```

`clips` 的顺序就是输出顺序；source 相对路径相对于计划文件目录。片段必须在视频时长内，字幕必须在对应保留区间内且不能重叠。程序拒绝覆盖同名草稿，默认创建唯一名称。

## 验收边界

build 生成包含原声视频轨和可编辑字幕轨的**基础草稿**。基础样式不等于已完成参考规范中的全部强调、语义对比与渐显动画；这些属于后续剪辑与视觉 QC。没有字幕的计划允许生成空字幕轨，并明确返回 subtitle_count=0。

自检会验证环境、原生二进制、真实五秒测试视频、三秒草稿、两轨结构、字幕时间映射和字幕素材字段。启用 ASR 时还验证模型推理和 VAD。测试使用独立临时目录，退出后删除，不触碰已有草稿。

这些检查不代表已在剪映内打开验证。不同剪映版本可能调整草稿格式；必须在安装的 macOS 剪映中人工打开，核对画面、原声、字幕面板、字体、动画和首页可见性，再宣告完成。

## 草稿格式基线

默认 `mac-5.5` profile 写入 macOS 活动时间线 `draft_info.json`，协议 `103.0.0`、平台 `mac`，同步生成有唯一 ID、名称、路径和时长的 `draft_meta_info.json`。保留同内容的 `draft_content.json` 便于结构审查。格式依据为 [jianying-tool 作者的 macOS 说明](https://pypi.org/project/jianying-tool/)；当前机器未安装剪映，不能据此推断所有 Mac 版本兼容。新版剪映需要实机验收，CapCut 不在本项目验收范围。不要改剪映全局索引或现有工程。

## 沙盒素材访问

官方 Mac 应用启用 App Sandbox。build 默认把视频复制到新草稿 media 目录（草稿应在剪映可访问的 Movies 目录或用户选择的目录），避免 Documents 等外部素材被提示丢失。--link-media 可关闭复制；此时需在剪映内手动导入或重新链接以获得授权。程序不会关闭沙盒或扩大系统权限。
