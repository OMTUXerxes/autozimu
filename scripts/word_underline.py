"""Add instant red word underlines to an ASS subtitle file.

The input word events must already be checked against the audio and the
rendered English glyph positions. This tool only makes their rendering stable.
"""

import argparse
import json
import re
from pathlib import Path

from PIL import Image, ImageDraw


def ass_time(seconds):
    centis = round(seconds * 100)
    hours, centis = divmod(centis, 360000)
    minutes, centis = divmod(centis, 6000)
    secs, centis = divmod(centis, 100)
    return f"{hours}:{minutes:02}:{secs:02}.{centis:02}"


def resolution(ass):
    width = re.search(r"(?m)^PlayResX:\s*(\d+)\s*$", ass)
    height = re.search(r"(?m)^PlayResY:\s*(\d+)\s*$", ass)
    if not width or not height:
        raise ValueError("ASS must include PlayResX and PlayResY")
    return int(width.group(1)), int(height.group(1))


def load_events(path, width, height, thickness):
    events = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(events, list) or not events:
        raise ValueError("Word events must be a nonempty JSON array")
    checked = []
    for event in events:
        start, end = float(event["start"]), float(event["end"])
        x0, x1, y = (int(event[name]) for name in ("x0", "x1", "y"))
        if start < 0 or end <= start or not (0 <= x0 < x1 < width) or not (0 <= y <= height - thickness):
            raise ValueError(f"Invalid word event: {event}")
        if not str(event.get("word", "")).strip():
            raise ValueError(f"Word missing from event: {event}")
        checked.append((start, end, x0, x1, y))
    checked.sort()
    if any(left[1] > right[0] + 0.01 for left, right in zip(checked, checked[1:])):
        raise ValueError("Word events overlap; resolve the audio timing before rendering")
    return checked


def add_ass(base, events, thickness):
    if "Style: RedUnderline," in base:
        raise ValueError("ASS already has a RedUnderline style")
    if "[Events]" not in base or "[V4+ Styles]" not in base:
        raise ValueError("Expected ASS styles and events sections")
    style = (
        "Style: RedUnderline,Arial,20,&H000000FF,&H000000FF,&H00000000,&H00000000,"
        "0,0,0,0,100,100,0,0,1,0,0,7,0,0,0,1\n\n"
    )
    result = base.replace("[Events]", style + "[Events]", 1)
    if not result.endswith("\n"):
        result += "\n"
    for start, end, x0, x1, y in events:
        shape = (
            rf"{{\an7\pos({x0},{y})\p1}}m 0 0 l {x1-x0} 0 "
            rf"l {x1-x0} {thickness} l 0 {thickness}{{\p0}}"
        )
        result += f"Dialogue: 1,{ass_time(start)},{ass_time(end)},RedUnderline,,0,0,0,,{shape}\n"
    return result


def make_pngs(directory, events, width, height, thickness):
    directory.mkdir(parents=True, exist_ok=True)
    for x0, x1, y in sorted({(x0, x1, y) for _, _, x0, x1, y in events}):
        image = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        ImageDraw.Draw(image).rectangle((x0, y, x1, y + thickness - 1), fill=(255, 0, 0, 255))
        image.save(directory / f"{x0}_{x1}_{y}.png")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--base-ass", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--output-ass", type=Path, required=True)
    parser.add_argument("--png-dir", type=Path, help="Create full-canvas transparent red-line images for JianYing")
    args = parser.parse_args()
    base = args.base_ass.read_text(encoding="utf-8-sig")
    width, height = resolution(base)
    thickness = max(2, round(5 * width / 1920))
    events = load_events(args.events, width, height, thickness)
    if args.output_ass.resolve() == args.base_ass.resolve():
        raise ValueError("Keep the base ASS separate from the red-line ASS")
    args.output_ass.write_text(add_ass(base, events, thickness), encoding="utf-8-sig")
    if args.png_dir:
        make_pngs(args.png_dir, events, width, height, thickness)
    print(f"Red underlines: {len(events)} events, #FF0000, {thickness}px at {width}x{height}")


if __name__ == "__main__":
    main()
