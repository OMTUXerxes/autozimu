"""Render one reviewed bilingual subtitle JSON to ASS, MP4, and a Jianying draft."""

import argparse
import hashlib
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from PIL import ImageFont


def skill_root():
    override = os.environ.get("JY_SKILL_ROOT")
    codex_home = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
    candidates = [Path(override)] if override else []
    candidates += [Path(__file__).resolve().parents[1].parent / "jianying-editor", codex_home / "skills" / "jianying-editor"]
    return next((p for p in candidates if (p / "scripts" / "jy_wrapper.py").is_file()), None)


def preflight():
    if os.name != "nt":
        raise RuntimeError("autozimu currently supports Windows only")
    required = ["ffmpeg", "ffprobe"]
    missing = [name for name in required if not shutil.which(name)]
    if not shutil.which("deno"):
        node = shutil.which("node")
        result = subprocess.run([node, "--version"], capture_output=True, text=True) if node else None
        version = re.search(r"v(\d+)", result.stdout) if result and result.returncode == 0 else None
        if version is None or int(version.group(1)) < 22:
            missing.append("Deno 2.3+ or Node 22+")
    if skill_root() is None:
        missing.append("jianying-editor skill")
    for package in ["yt_dlp", "PIL", "faster_whisper"]:
        if importlib.util.find_spec(package) is None:
            missing.append(package)
    if not Path(r"C:\Windows\Fonts\ariali.ttf").is_file():
        missing.append("Arial Italic font")
    if not Path(r"C:\Windows\Fonts\msyhbd.ttc").is_file():
        missing.append("Microsoft YaHei Bold font")
    if missing:
        raise RuntimeError("Missing dependencies: " + ", ".join(missing) + ". Run install.ps1.")
    print("Dependencies OK")


def run(command, *, cwd=None):
    subprocess.run(command, cwd=cwd, check=True)


def probe(path):
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration:stream=codec_type,width,height", "-of", "json", str(path)],
        capture_output=True, text=True, check=True,
    )
    info = json.loads(result.stdout)
    video = next((s for s in info["streams"] if s["codec_type"] == "video"), None)
    audio = next((s for s in info["streams"] if s["codec_type"] == "audio"), None)
    if video is None or audio is None:
        raise ValueError("Source or output must contain video and audio")
    return int(video["width"]), int(video["height"]), float(info["format"]["duration"])


def ass_time(seconds):
    cs = round(seconds * 100)
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return f"{h}:{m:02}:{s:02}.{cs:02}"


def matches(text, words, english):
    found = []
    for word in words:
        pattern = (r"(?<!\w)" + re.escape(word) + r"(?!\w)") if english else re.escape(word)
        spans = [(m.start(), m.end()) for m in re.finditer(pattern, text, re.I if english else 0)]
        if not spans:
            raise ValueError(f"Highlight '{word}' absent from '{text}'")
        found.extend(spans)
    found.sort()
    if any(a[0] < b[1] for b, a in zip(found, found[1:])):
        raise ValueError(f"Overlapping highlights in '{text}'")
    return found


def render_text(text, spans, style, size):
    parts = []
    prev = 0
    for start, end in spans:
        parts.append(text[prev:start])
        parts.append(r"{\c&H3AE1FF&\fs" + str(round(size * 1.17)) + "}" + text[start:end] + r"{\r" + style + "}")
        prev = end
    parts.append(text[prev:])
    return "".join(parts).replace("\n", " ")


def width_of(text, spans, font_path, size):
    normal = ImageFont.truetype(str(font_path), size)
    large = ImageFont.truetype(str(font_path), round(size * 1.17))
    width = 0
    prev = 0
    for start, end in spans:
        width += normal.getlength(text[prev:start]) + large.getlength(text[start:end])
        prev = end
    return width + normal.getlength(text[prev:])


def safe_name(title, video_id):
    raw = f"{title}_{video_id}" if video_id else title
    name = re.sub(r'''[<>:"/\\|?*\x00-\x1f,;'\[\]=]''', "_", raw).strip(" ._")
    return name[:90] or "bilingual_video"


def load_rows(path, cut, width, height):
    rows = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(rows, list) or not rows:
        raise ValueError("Subtitle JSON must be a nonempty list")
    scale = height / 1080
    en_size, zh_size = round(57 * scale), round(49 * scale)
    fonts = [Path(r"C:\Windows\Fonts\ariali.ttf"), Path(r"C:\Windows\Fonts\msyhbd.ttc")]
    previous_end = 0
    parsed = []
    for row in rows:
        if not isinstance(row, list) or len(row) < 4 or (len(row) - 4) % 2:
            raise ValueError(f"Invalid subtitle row: {row}")
        start, end, en, zh, *marked = row
        start, end = float(start), float(end)
        if start < previous_end or end <= start or end > cut + 0.01:
            raise ValueError(f"Invalid or overlapping time: {row}")
        if not all(isinstance(v, str) and v.strip() and "\n" not in v for v in [en, zh, *marked]):
            raise ValueError(f"Empty or multiline subtitle: {row}")
        en_spans, zh_spans = matches(en, marked[::2], True), matches(zh, marked[1::2], False)
        if width_of(en, en_spans, fonts[0], en_size) > width * 0.92:
            raise ValueError(f"English line too wide: {en}")
        if width_of(zh, zh_spans, fonts[1], zh_size) > width * 0.92:
            raise ValueError(f"Chinese line too wide: {zh}")
        parsed.append((start, end, en, zh, marked, en_spans, zh_spans))
        previous_end = end
    return parsed, en_size, zh_size


def make_ass(path, rows, width, height, en_size, zh_size):
    scale = height / 1080
    outline = round(2.2 * scale, 2)
    shadow = round(0.6 * scale, 2)
    header = f"""[Script Info]
ScriptType: v4.00+
PlayResX: {width}
PlayResY: {height}
ScaledBorderAndShadow: yes
WrapStyle: 2

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: English,Arial,{en_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,0,-1,0,0,100,100,0,0,1,{outline},{shadow},5,0,0,0,1
Style: Chinese,Microsoft YaHei,{zh_size},&H00FFFFFF,&H00FFFFFF,&H00000000,&H64000000,-1,0,0,0,100,100,0,0,1,{outline},{shadow},5,0,0,0,1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""
    lines = [header]
    for start, end, en, zh, _, en_spans, zh_spans in rows:
        for style, text, spans, size, y in [
            ("English", en, en_spans, en_size, round(height * 940 / 1080)),
            ("Chinese", zh, zh_spans, zh_size, round(height * 1010 / 1080)),
        ]:
            body = render_text(text, spans, style, size)
            lines.append(f"Dialogue: 0,{ass_time(start)},{ass_time(end)},{style},,0,0,0,,"
                         + rf"{{\an5\pos({width // 2},{y})}}" + body + "\n")
    path.write_text("".join(lines), encoding="utf-8-sig")


def make_draft(name, source, rows, cut, width, height, drafts_root):
    root = skill_root()
    sys.path.insert(0, str(root / "scripts"))
    from jy_wrapper import JyProject
    import pyJianYingDraft as draft

    project = JyProject(name, width=width, height=height, drafts_root=drafts_root, overwrite=True)
    project.add_media_safe(str(source), "0s", duration=f"{cut}s", track_name="Video")
    border = draft.TextBorder(width=11.0)
    scale = height / 1080
    yellow = (1.0, 225 / 255, 58 / 255)
    for start, end, en, zh, marked, _, _ in rows:
        for text, track, size, y, italic, bold, words in [
            (en, "English", 5.0 * scale, -0.74, True, False, marked[::2]),
            (zh, "Chinese", 4.3 * scale, -0.88, False, True, marked[1::2]),
        ]:
            highlights = [{"word": word, "color": yellow, "size": size * 1.17, "bold": True} for word in words]
            project.add_rich_text(
                text, highlights, start_time=f"{start}s", duration=f"{end - start}s", track_name=track,
                style=draft.TextStyle(size=size, italic=italic, bold=bold, align=1, auto_wrapping=False),
                clip_settings=draft.ClipSettings(transform_y=y), border=border,
            )
    result = project.save()
    draft_info = Path(result["draft_path"]) / "draft_info.json"
    data = json.loads(draft_info.read_text(encoding="utf-8"))
    tracks = {t["name"]: len(t["segments"]) for t in data["tracks"]}
    if tracks != {"Video": 1, "English": len(rows), "Chinese": len(rows)}:
        raise RuntimeError(f"Draft track check failed: {tracks}")
    return draft_info


def desktop_path(filename):
    try:
        import winreg
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Explorer\User Shell Folders") as key:
            folder, _ = winreg.QueryValueEx(key, "Desktop")
        return Path(os.path.expandvars(folder)) / filename
    except (OSError, ImportError):
        return Path.home() / "Desktop" / filename


def sha256(path):
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.digest()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true", help="Check dependencies without editing files")
    parser.add_argument("--source", type=Path)
    parser.add_argument("--subtitles", type=Path)
    parser.add_argument("--title")
    parser.add_argument("--id", default="")
    parser.add_argument("--cut-end", type=float)
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    parser.add_argument("--drafts-root", type=Path, help=argparse.SUPPRESS)
    parser.add_argument("--no-desktop", action="store_true", help=argparse.SUPPRESS)
    args = parser.parse_args()
    preflight()
    if args.check:
        return
    if not args.source or not args.subtitles:
        parser.error("--source and --subtitles are required")
    source = args.source.resolve(strict=True)
    subtitles = args.subtitles.resolve(strict=True)
    width, height, duration = probe(source)
    cut = args.cut_end if args.cut_end is not None else duration
    if cut <= 0 or cut > duration + 0.01:
        raise ValueError("--cut-end must be within the source duration")
    rows, en_size, zh_size = load_rows(subtitles, cut, width, height)
    name = safe_name(args.title or source.stem, args.id)
    project_dir = args.project_dir.resolve()
    output_dir = project_dir / "outputs"
    work_dir = project_dir / "work" / name
    output_dir.mkdir(parents=True, exist_ok=True)
    work_dir.mkdir(parents=True, exist_ok=True)
    work_ass = work_dir / f"{name}.ass"
    make_ass(work_ass, rows, width, height, en_size, zh_size)
    output_ass = output_dir / work_ass.name
    shutil.copy2(work_ass, output_ass)
    draft_info = make_draft(name, source, rows, cut, width, height, str(args.drafts_root) if args.drafts_root else None)
    output_mp4 = output_dir / f"{name}.mp4"
    run(["ffmpeg", "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
         "-t", str(cut), "-vf", f"ass={work_ass.name}", "-c:v", "libx264", "-preset", "fast",
         "-crf", "18", "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(output_mp4)], cwd=work_dir)
    out_width, out_height, out_duration = probe(output_mp4)
    if (out_width, out_height) != (width, height) or abs(out_duration - cut) > 0.1:
        raise RuntimeError("Output dimensions or duration do not match")
    run(["ffmpeg", "-v", "error", "-i", str(output_mp4), "-f", "null", "NUL"])
    desktop = None
    if not args.no_desktop:
        desktop = desktop_path(output_mp4.name)
        desktop.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(output_mp4, desktop)
        if sha256(output_mp4) != sha256(desktop):
            raise RuntimeError("Desktop copy differs from output")
    print(json.dumps({"mp4": str(output_mp4), "ass": str(output_ass), "draft": str(draft_info),
                      "desktop": str(desktop) if desktop else None, "resolution": [width, height], "duration": out_duration,
                      "subtitle_count": len(rows)}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
