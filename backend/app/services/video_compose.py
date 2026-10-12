"""Local 16:9 composition. No network access or AI calls occur here."""

from __future__ import annotations

from contextlib import ExitStack
from pathlib import Path
import re

import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageOps
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)

WIDTH, HEIGHT, FPS = 1280, 720, 24
PREFERRED_DURATION = 25.0
HARD_MAX_DURATION = 45.0


def planned_duration(audio_seconds: float, target_duration: float | None = None) -> float:
    target = (
        float(target_duration)
        if target_duration is not None
        else max(PREFERRED_DURATION, float(audio_seconds))
    )
    if target > HARD_MAX_DURATION:
        raise ValueError(
            f"Narration lasts {target:.1f}s; shorten the grounded script to fit the 45s hard maximum."
        )
    return target


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for candidate in candidates:
        if Path(candidate).is_file():
            return ImageFont.truetype(candidate, size)
    return ImageFont.load_default()


def _wrap(
    draw: ImageDraw.ImageDraw, value: str, font: ImageFont.ImageFont, max_width: int
) -> list[str]:
    lines: list[str] = []
    line = ""
    for word in value.split():
        next_line = f"{line} {word}".strip()
        if line and draw.textlength(next_line, font=font) > max_width:
            lines.append(line)
            line = word
        else:
            line = next_line
    if line:
        lines.append(line)
    return lines


def _cover_frame(image: Image.Image) -> Image.Image:
    background = Image.new("RGB", (WIDTH, HEIGHT), "#102944")
    fitted = ImageOps.contain(image.convert("RGB"), (WIDTH, HEIGHT))
    background.paste(fitted, ((WIDTH - fitted.width) // 2, (HEIGHT - fitted.height) // 2))
    return background


def _fact_frame(title: str, detail: str, at: float) -> np.ndarray:
    image = Image.new("RGB", (WIDTH, HEIGHT), "#102944")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 18, HEIGHT), fill="#3479c7")
    draw.text((92, 125), "UNIVERSITY OF DEBRECEN", font=_font(26, True), fill="#90c5fc")
    title_font = _font(62, True)
    detail_font = _font(34)
    slide = int(max(0, 1 - min(1, at * 2)) * 36)
    for index, line in enumerate(_wrap(draw, title, title_font, 1090)[:3]):
        draw.text((92, 225 + index * 78 + slide), line, font=title_font, fill="white")
    detail_y = 225 + min(3, len(_wrap(draw, title, title_font, 1090))) * 78 + 20
    for index, line in enumerate(_wrap(draw, detail, detail_font, 1090)[:2]):
        draw.text((94, detail_y + index * 50 + slide), line, font=detail_font, fill="#cbdcf1")
    return np.asarray(image)


def _caption_image(text: str) -> np.ndarray:
    image = Image.new("RGBA", (WIDTH, 135), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    font = _font(32, True)
    lines = _wrap(draw, text, font, 1120)[:2]
    if lines:
        top = max(4, (135 - len(lines) * 43) // 2)
        draw.rounded_rectangle(
            (50, top - 8, WIDTH - 50, top + len(lines) * 43 + 8), radius=18, fill=(5, 17, 32, 195)
        )
        for index, line in enumerate(lines):
            box = draw.textbbox((0, 0), line, font=font)
            draw.text(
                ((WIDTH - (box[2] - box[0])) // 2, top + index * 43), line, font=font, fill="white"
            )
    return np.asarray(image)


def _srt_time(seconds: float) -> str:
    milliseconds = int(round(seconds * 1000))
    hours, milliseconds = divmod(milliseconds, 3_600_000)
    minutes, milliseconds = divmod(milliseconds, 60_000)
    secs, milliseconds = divmod(milliseconds, 1000)
    return f"{hours:02}:{minutes:02}:{secs:02},{milliseconds:03}"


def caption_cues(
    script: str, duration: float, alignment: dict | None = None
) -> list[tuple[float, float, str]]:
    matches = list(re.finditer(r"\S+", script))
    groups = []
    current = []
    for match in matches:
        current.append(match)
        if len(current) >= 8 or match.group().endswith((".", "!", "?")):
            groups.append(current)
            current = []
    if current:
        groups.append(current)
    if alignment and len(alignment.get("characters", [])) == len(script):
        starts = alignment.get("character_start_times_seconds", [])
        ends = alignment.get("character_end_times_seconds", [])
        if len(starts) == len(script) and len(ends) == len(script):
            return [
                (
                    max(0, float(starts[group[0].start()])),
                    min(duration, float(ends[group[-1].end() - 1])),
                    script[group[0].start() : group[-1].end()],
                )
                for group in groups
            ]
    words = script.split()
    cues: list[tuple[float, float, str]] = []
    offset = 0
    for group in groups:
        chunk = script[group[0].start() : group[-1].end()]
        count = len(group)
        start = duration * offset / max(1, len(words))
        offset += count
        end = duration * offset / max(1, len(words))
        cues.append((start, end, chunk))
    return cues


def write_srt(path: Path, cues: list[tuple[float, float, str]]) -> None:
    path.write_text(
        "\n\n".join(
            f"{index}\n{_srt_time(start)} --> {_srt_time(end)}\n{text}"
            for index, (start, end, text) in enumerate(cues, 1)
        )
        + "\n",
        encoding="utf-8",
    )


def compose_video(
    scenes: list[dict],
    narration_path: Path,
    script: str,
    output_path: Path,
    srt_path: Path,
    *,
    min_motion_ratio: float = 0.6,
    target_duration: float | None = None,
    alignment: dict | None = None,
) -> dict:
    """Compose supplied clips; reject a video whose footage share is too small."""
    with ExitStack() as stack:
        audio = stack.enter_context(AudioFileClip(str(narration_path)))
        target = planned_duration(float(audio.duration), target_duration)
        prepared = []
        motion_seconds = 0.0
        static_weight = 0.0
        for scene in scenes:
            kind = scene["type"]
            if kind in {"uploaded_video", "generated_motion"}:
                if not scene.get("path") or not Path(scene["path"]).is_file():
                    continue
                clip = stack.enter_context(VideoFileClip(str(scene["path"]), audio=False))
                seconds = min(float(scene.get("duration", 6)), target - motion_seconds)
                if seconds < 0.5:
                    continue
                if seconds > clip.duration:
                    if seconds / clip.duration > 1.12:
                        raise ValueError(
                            "A motion clip would need more than 12% slow motion to meet the duration target."
                        )
                    frame = clip.with_effects([vfx.MultiplySpeed(final_duration=seconds)]).resized(
                        height=HEIGHT
                    )
                else:
                    frame = clip.subclipped(0, seconds).resized(height=HEIGHT)
                if frame.w > WIDTH:
                    frame = frame.cropped(x_center=frame.w / 2, width=WIDTH)
                frame = CompositeVideoClip(
                    [
                        ImageClip(
                            np.asarray(Image.new("RGB", (WIDTH, HEIGHT), "#102944"))
                        ).with_duration(seconds),
                        frame.with_position("center"),
                    ],
                    size=(WIDTH, HEIGHT),
                ).with_duration(seconds)
                prepared.append(("motion", frame, seconds))
                motion_seconds += seconds
            else:
                weight = max(0.5, float(scene.get("duration", 2)))
                prepared.append(("static", scene, weight))
                static_weight += weight
        if motion_seconds / target < min_motion_ratio:
            raise ValueError(
                f"Only {motion_seconds:.1f}s of usable moving footage for a {target:.1f}s video; at least 60% is required."
            )
        static_seconds = target - motion_seconds
        if static_seconds > 0.05 and not static_weight:
            prepared.append(
                (
                    "static",
                    {"type": "fact_card", "overlay": "University of Debrecen", "detail": ""},
                    1.0,
                )
            )
            static_weight = 1.0
        segments = []
        remaining = static_seconds
        for kind, scene, weight in prepared:
            if kind == "motion":
                segments.append(scene)
            elif remaining > 0.05:
                seconds = min(remaining, static_seconds * weight / static_weight)
                remaining -= seconds
                if scene.get("path") and Path(scene["path"]).is_file():
                    with Image.open(scene["path"]) as source:
                        still = np.asarray(_cover_frame(source))
                    frame = ImageClip(still).with_duration(seconds)
                else:
                    frame = VideoClip(
                        lambda t, item=scene: _fact_frame(
                            item.get("overlay", ""), item.get("detail", ""), t
                        ),
                        duration=seconds,
                    )
                segments.append(frame)
        if not segments:
            raise ValueError("No usable video scenes were available.")
        base = concatenate_videoclips(segments, method="compose")
        cues = caption_cues(script, min(target, float(audio.duration)), alignment)
        write_srt(srt_path, cues)
        captions = [
            ImageClip(_caption_image(line))
            .with_start(start)
            .with_duration(end - start)
            .with_position((0, HEIGHT - 155))
            for start, end, line in cues
        ]
        final = CompositeVideoClip([base, *captions], size=(WIDTH, HEIGHT)).with_audio(audio)
        final.write_videofile(
            str(output_path),
            fps=FPS,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=4,
            logger=None,
            ffmpeg_params=["-pix_fmt", "yuv420p", "-movflags", "+faststart"],
        )
        final.close()
        return {
            "duration_seconds": round(target, 2),
            "motion_seconds": round(motion_seconds, 2),
            "motion_ratio": round(motion_seconds / target, 3),
        }
