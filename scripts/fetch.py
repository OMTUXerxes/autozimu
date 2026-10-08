"""Download the best available video and English captions into work/<video-id>."""

import argparse
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path


def runtime():
    if shutil.which("deno"):
        return "deno"
    if shutil.which("node"):
        result = subprocess.run(["node", "--version"], capture_output=True, text=True, check=True)
        match = re.search(r"v(\d+)", result.stdout)
        if match and int(match.group(1)) >= 22:
            return "node"
    raise RuntimeError("Install Deno 2.3+ or Node 22+ for YouTube extraction")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("url")
    parser.add_argument("--project-dir", type=Path, default=Path.cwd())
    args = parser.parse_args()
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        raise RuntimeError("Install FFmpeg and FFprobe first")
    client = ["--extractor-args", "youtube:player_client=web_safari,android_vr"] if "youtu" in args.url.lower() else []
    base = [sys.executable, "-m", "yt_dlp", "--no-config", "--no-playlist", "--js-runtimes", runtime(), *client]
    info_result = subprocess.run(base + ["--dump-single-json", "--skip-download", args.url], capture_output=True, text=True, check=True)
    info = json.loads(info_result.stdout)
    video_id = str(info["id"])
    if not re.fullmatch(r"[A-Za-z0-9_-]+", video_id):
        raise ValueError("Unexpected video ID")
    work = args.project_dir.resolve() / "work" / video_id
    work.mkdir(parents=True, exist_ok=True)
    languages = ["en", "en-orig", "en-US", "en-GB"]
    manual_language = next((lang for lang in languages if lang in info.get("subtitles", {})), None)
    auto_language = next((lang for lang in languages if lang in info.get("automatic_captions", {})), None)
    language = manual_language or auto_language
    subtitle_args = (["--write-subs"] if manual_language else ["--write-auto-subs"] if auto_language else [])
    if language:
        subtitle_args += ["--sub-langs", language, "--sub-format", "vtt"]
    command = base + [
        *subtitle_args, "-f", "bv*+ba/b", "-S", "res,vcodec:h264,acodec:aac", "--merge-output-format", "mp4",
        "-o", str(work / "source.%(ext)s"), args.url,
    ]
    subprocess.run(command, check=True)
    media = [p for p in work.glob("source.*") if p.suffix.lower() in {".mp4", ".mkv", ".webm", ".mov"}]
    if len(media) != 1:
        raise RuntimeError(f"Expected one downloaded video, found {len(media)}")
    captions = sorted(work.glob("source.en*.vtt"))
    source = "publisher" if manual_language and captions else "automatic" if captions else "none"
    result = {
        "id": video_id, "title": info.get("title", video_id), "url": args.url,
        "video": str(media[0]), "english_captions": [str(p) for p in captions],
        "caption_source": source, "duration": info.get("duration"),
    }
    (work / "fetch.json").write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    main()
