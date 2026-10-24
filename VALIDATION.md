# 本机验证记录

日期：2026-10-24（Asia/Shanghai）。

环境：macOS / Apple Silicon arm64，Python 3.12.13，ffmpeg 9.0.1；pyJianYingDraft 0.3.0、pymediainfo 7.0.1、faster-whisper 1.2.1、CTranslate2 4.8.3。实际解析的依赖快照在 deploy/*-macos-arm64.lock.txt，可用于复现本次环境；Intel 应根据其架构重新解析依赖。

已验证：

- 12 项回归测试：安全备份失败、替换回滚、原子写入、标题保护、唯一草稿 ID、Mac 活动时间线、视频旋转、区间越界、字幕跨切点与重叠等。
- 真实 ffmpeg 生成 1080×1920 五秒素材，生成三秒视频/字幕两轨草稿，并校验字幕起点 200000 微秒、时长 2300000 微秒。
- Mac profile：draft_info.json 与 draft_content.json 同内容，os=mac、new_version=103.0.0；草稿元数据名称、唯一 ID、时长一致。
- 本地 1.6 GB turbo 模型成功加载和 CPU int8 推理；VAD 和两套环境 pip check 通过。
- macOS 中文语音合成测试视频转写产生有效中文片段；自带商品视频前八秒未识别出人声时，程序返回失败并保存空结果，没有误报通过。
- 命令行 probe 已读取工作目录中的实际 1080×1920 商品视频。

## 应用内验收补充（2026-10-24）

已从剪映官网页面提供的默认 Mac 链接安装剪映专业版 5.5.0（VideoFusion-macOS.app），通过 macOS Developer ID 公证检查，签名主体为 Shenzhen Lianmeng Technology Co.Ltd.。

- 测试草稿已显示在首页，可打开和播放；时间轴只有视频轨与字幕轨。
- 字幕面板显示 5 条字幕；将“粗简”改为“粗剪”后，SRT 导出保留了修改。
- 已通过剪映自身导出 H.264/AAC MP4：1080×1920、30fps、9.5 秒、11357501 字节。音轨有效，平均音量 -21.4 dB，峰值 -6.9 dB。
- 首次测试发现官方 Mac 应用启用了沙盒，无法访问 Documents 下未授权的外部素材。已修复为默认复制素材到工程 media 目录，再次打开不再提示素材丢失。
- 本机默认输出位置已更新为剪映实际草稿库，安装位置和能力自检会检测到该应用。

本机验收项目：~/Movies/JianyingPro/User Data/Projects/com.lveditor.draft/Mac兼容性验收_打包素材。

限制：其他剪映版本、Intel Mac 与 Windows 未做实机验收。草稿基础样式不代表全部视觉规范完成。默认草稿会包含素材副本；选择 --link-media 时，移动、删除或未授权的原素材可能导致丢失。

完整机器报告位于用户运行配置旁的 verify-report.json。自动结构自检的 app_open_verified=false 仅表示该脚本不操作应用。独立 app-acceptance-report.json 保存本次实际界面、字幕编辑与导出验收，app_open_verified=true。
