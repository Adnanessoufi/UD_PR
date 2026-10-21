"""Render the public demo's illustrated videos from local, synthetic narration.

Usage: backend/.venv/Scripts/python.exe scripts/render-demo-videos.py NARRATION_DIR
Expects research-0.wav through research-2.wav and announcement-0.wav through
announcement-2.wav. The committed MP4/VTT assets need no runtime renderer.
"""

import subprocess
import sys
import textwrap
import wave
from pathlib import Path

import imageio_ffmpeg
from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parents[1]
OUTPUT = ROOT / "frontend" / "public" / "demo"
FONTS = Path("C:/Windows/Fonts")
SCENES = {
    "research": [
        (
            "A quieter place to study.",
            "24 volunteers. Four weeks.",
            "This fictional study follows 24 volunteers in a quiet study room over four weeks.",
        ),
        (
            "18 out of 24.",
            "Self-reported concentration.",
            "18 said it helped them concentrate. That is self-reported feedback, not a measure of better grades.",
        ),
        (
            "Keep the limits in view.",
            "No control group. No grades measured.",
            "There was no control group. UD PR Studio keeps those limits in the draft, alongside the result.",
        ),
    ],
    "announcement": [
        (
            "An evening of student projects.",
            "Meet the teams. Try the demos.",
            "This fictional announcement introduces an evening of student project demos.",
        ),
        (
            "21 November 2026.",
            "17:00 to 19:00. Free entry.",
            "The sample brief says 21 November, from 5 to 7 p.m., with free entry and no registration.",
        ),
        (
            "Stick to the brief.",
            "No invented speakers or prizes.",
            "The draft keeps those details and adds no speakers or prizes. This is not a real event invitation.",
        ),
    ],
}


def clock(seconds):
    milliseconds = round(seconds * 1000)
    minutes, milliseconds = divmod(milliseconds, 60000)
    seconds, milliseconds = divmod(milliseconds, 1000)
    return f"00:{minutes:02}:{seconds:02}.{milliseconds:03}"


def render(narration_dir):
    ffmpeg = imageio_ffmpeg.get_ffmpeg_exe()
    for kind, scenes in SCENES.items():
        clips = []
        captions = ["WEBVTT\n"]
        elapsed = 0.0
        for index, (title, subtitle, spoken) in enumerate(scenes):
            audio = narration_dir / f"{kind}-{index}.wav"
            with wave.open(str(audio)) as recording:
                duration = recording.getnframes() / recording.getframerate() + 0.6
            image = Image.new("RGB", (1280, 720), "#173c34")
            draw = ImageDraw.Draw(image)
            sans = lambda size: ImageFont.truetype(str(FONTS / "segoeui.ttf"), size)
            serif = ImageFont.truetype(str(FONTS / "georgia.ttf"), 66)
            draw.text((70, 45), "UD PR STUDIO  /  PREPARED SAMPLE", font=sans(18), fill="#d7ec92")
            draw.line((70, 95, 1210, 95), fill="#496354", width=2)
            for line_no, line in enumerate(textwrap.wrap(title, 29)):
                draw.text((70, 185 + line_no * 85), line, font=serif, fill="#faf9ee")
            draw.text((75, 390), subtitle, font=sans(29), fill="#d7ec92")
            draw.text(
                (75, 447),
                "FICTIONAL EXAMPLE. No real study results or event.",
                font=sans(19),
                fill="#a7bdae",
            )
            draw.rectangle((0, 540, 1280, 720), fill="#102e28")
            for line_no, line in enumerate(textwrap.wrap(spoken, 92)):
                draw.text((70, 565 + line_no * 33), line, font=sans(24), fill="#f3f4e8")
            draw.text((1150, 662), f"0{index + 1} / 03", font=sans(16), fill="#a7bdae")
            frame = narration_dir / f"{kind}-{index}.png"
            clip = narration_dir / f"{kind}-{index}.mp4"
            image.save(frame)
            subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-loop",
                    "1",
                    "-framerate",
                    "24",
                    "-i",
                    str(frame),
                    "-i",
                    str(audio),
                    "-c:v",
                    "libx264",
                    "-preset",
                    "fast",
                    "-tune",
                    "stillimage",
                    "-crf",
                    "28",
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-b:a",
                    "96k",
                    "-af",
                    "apad=pad_dur=0.6",
                    "-t",
                    str(duration),
                    "-movflags",
                    "+faststart",
                    str(clip),
                ],
                check=True,
            )
            clips.append(clip)
            captions.append(f"{clock(elapsed)} --> {clock(elapsed + duration)}\n{spoken}\n")
            elapsed += duration
        concat = narration_dir / f"{kind}-concat.txt"
        concat.write_text(
            "\n".join(f"file '{clip.as_posix()}'" for clip in clips), encoding="utf-8"
        )
        name = "study-walkthrough.mp4" if kind == "research" else "event-walkthrough.mp4"
        subprocess.run(
            [
                ffmpeg,
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "concat",
                "-safe",
                "0",
                "-i",
                str(concat),
                "-c",
                "copy",
                "-movflags",
                "+faststart",
                str(OUTPUT / name),
            ],
            check=True,
        )
        (OUTPUT / f"{kind}.vtt").write_text("\n".join(captions), encoding="utf-8")
        print(f"{name}: {elapsed:.1f}s, {(OUTPUT / name).stat().st_size:,} bytes")


if __name__ == "__main__":
    render(Path(sys.argv[1]))
