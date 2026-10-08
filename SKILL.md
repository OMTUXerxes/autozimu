---
name: autozimu
description: 为小学四、五年级制作视频链接或本地视频的中英双语字幕成片、可编辑 ASS 和剪映三轨草稿。用户要求此类完整视频字幕制作时使用；普通文字翻译或仅改写字幕时不使用。
---

# Autozimu

先读同目录的 [AGENTS.md](AGENTS.md)。它定义交付、字幕样式、词汇判断和质检要求；用户当前要求优先。运行环境为 Windows 桌面版剪映专业版。

## 安装门槛

- 用户通过仓库的 `install.ps1` 一次安装 `autozimu` 和 [jianying-editor](https://github.com/luoluoluo22/jianying-editor-skill)。脚本也准备 Python 3.12、FFmpeg/FFprobe、Deno 和所需 Python 包。不要把只安装本 skill 说成完整安装。
- 首次使用或缺依赖时运行 `powershell -NoProfile -ExecutionPolicy Bypass -File <skill-root>\install.ps1`；随后运行 `<CODEX_HOME>\autozimu-venv\Scripts\python.exe <skill-root>\scripts\render.py --check`。若安装或检查失败，指出具体缺项，不继续生成虚假的成片。
- 剪映首次安装后要打开一次以初始化草稿目录。制作草稿前读取已安装的 `jianying-editor/SKILL.md` 中相关规则。本 skill 通过它的 `JyProject` 创建可编辑草稿；成片用同一份字幕数据生成 ASS 并由 FFmpeg 压制。

## 制作流程

1. **取素材与对白。** 视频链接用 `scripts/fetch.py <URL> --project-dir <项目目录>` 下载最高可用画质和英文字幕；本地视频直接使用。优先发布者英文字幕，其次自动字幕，最后运行 `scripts/transcribe.py <视频文件>` 做本地 ASR。逐句听读、核对时码，修正自动字幕和识别错误。拿不到可靠对白就说明原因并停下。
2. **确定片尾。** 抽看最后一段画面，结合对白和音乐识别片尾；仅在边界明确时剪去。边界不清就保留并说明。不要把单条视频的截点写成固定默认值。
3. **写双语与生词。** 从项目的 `词汇库.md` 读取人工确认；项目没有词库时从 `assets/词汇库模板.md` 复制空白模板。英文保留原意、按节奏分句；中文自然、适合四五年级。只选有教学价值且译文精确对应的词；中英文成对标黄、放大。不要公开或代入作者的个人词库。
4. **生成。** 在该视频的 `work/` 下保存审核后的 `subtitles.json`，格式见下文。调用 `scripts/render.py --source <视频文件> --subtitles <subtitles.json> --title <标题> --id <视频ID> --project-dir <项目目录> [--cut-end 秒数]`。脚本生成 `outputs/` 中的 MP4、ASS，剪映的 Video/English/Chinese 三轨草稿，以及桌面 MP4；没有明确片尾截点就省略 `--cut-end`。
5. **复核。** 脚本验证时长、分辨率、音视频、整片解码、三轨数量和桌面哈希。仍需抽看开头、中段、结尾及每个人工指定生词的实际画面，确认无截字、错位、漏高亮或多高亮；复核片尾没有剪掉正片。

`subtitles.json` 是按时间顺序排列的数组，每行写 `[开始秒, 结束秒, 英文, 中文, 英文高亮词, 对应中文高亮词, ...]`。没有高亮时只写前四项。例如：

```json
[[1.2, 3.4, "A penguin can swim.", "企鹅会游泳。"],
 [3.5, 5.8, "It catches krill.", "它会捕食磷虾。", "krill", "磷虾"]]
```

逐词反馈先遵从用户对本次交付的范围：要求修改成片时重建 MP4、ASS、剪映草稿和桌面副本；仅要求记录词库时只更新项目词库。用户确认写入“人工确认”，推断词放“扩展候选”，附语境和日期。
