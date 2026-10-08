"""Create a review-only English VTT when no usable source captions exist."""

import argparse
from pathlib import Path

from faster_whisper import WhisperModel


def stamp(seconds):
    millis = round(seconds * 1000)
    h, millis = divmod(millis, 3600000)
    m, millis = divmod(millis, 60000)
    s, millis = divmod(millis, 1000)
    return f"{h:02}:{m:02}:{s:02}.{millis:03}"


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("source", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--model", default="small.en")
    args = parser.parse_args()
    source = args.source.resolve(strict=True)
    output = args.output or source.with_suffix(".asr.en.vtt")
    model = WhisperModel(args.model, device="cpu", compute_type="int8")
    segments, _ = model.transcribe(str(source), language="en", vad_filter=True, beam_size=5)
    lines = ["WEBVTT\n\n"]
    for segment in segments:
        text = segment.text.strip().replace("\n", " ")
        if text:
            lines.append(f"{stamp(segment.start)} --> {stamp(segment.end)}\n{text}\n\n")
    output.write_text("".join(lines), encoding="utf-8")
    print(output)


if __name__ == "__main__":
    main()
