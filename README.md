# autozimu

把英文科普视频制作成适合小学四、五年级的中英双语字幕视频。默认按朗读给英文逐词加红色下划线，输出带字幕 MP4、可编辑 ASS 和剪映草稿；字幕样式与流程见 [AGENTS.md](AGENTS.md)。

## 一次安装两个 skill（Windows）

1. 从本仓库下载 ZIP 并解压；电脑需要联网，支持 `winget`（Windows App Installer）。
2. 在解压目录运行：

   ```powershell
   powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1
   ```

安装器会把 `autozimu` 和 `jianying-editor` 一起装入 Codex skills 目录，并安装或检查剪映专业版、Python 3.12、FFmpeg/FFprobe、Deno 和 Python 依赖。首次运行剪映后，重新打开 Codex，即可说“用 autozimu 给这个视频做四五年级双语字幕：<链接>”。不需要 API 密钥；首次本地语音识别会下载模型。

可先只检查环境：

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\install.ps1 -CheckOnly
```

安装脚本会从 [jianying-editor 原仓库](https://github.com/luoluoluo22/jianying-editor-skill)下载固定提交的源码，不把上游源码打包进本仓库。若上游已安装且结构完整，脚本沿用现有安装。它不会上传用户视频、字幕或词汇库。

## 产物

- `项目目录/outputs/`：成片 MP4、可编辑 ASS。
- `项目目录/work/`：原视频、原始字幕、人工校订字幕和中间文件。
- 剪映草稿目录：一条视频轨、英文和中文各一条可编辑文本轨，以及独立的逐词红线轨。
- 桌面：与 `outputs/` 哈希一致的成片副本。

词汇库从空白模板开始，不含作者的个人词汇记录。视频素材和成片不属于 skill 仓库。

## 运行条件

仅支持 Windows 桌面版剪映专业版；不支持手机剪映和国际版 CapCut。下载受视频站点可用性影响；无可靠对白时停止，不编造字幕。`jianying-editor` 用于草稿，MP4 使用 FFmpeg 按同一字幕数据压制。
