"""Keep completed videos for each output language without losing legacy final.mp4."""

import json
from pathlib import Path
import shutil

from app.services.output_language import load_output_language


def _usable(path: Path) -> bool:
    try:
        return path.is_file() and path.stat().st_size > 0
    except OSError:
        return False


def _legacy_language(video_dir: Path, final: Path) -> str:
    plan = video_dir / "video_plan.json"
    try:
        # A newer plan belongs to a job that has not replaced this final video.
        if plan.is_file() and plan.stat().st_mtime <= final.stat().st_mtime + 2:
            language = json.loads(plan.read_text(encoding="utf-8")).get("language")
            if language in ("en", "hu"):
                return language
    except (OSError, ValueError, TypeError, AttributeError):
        pass
    # Videos created before language selection were English. In particular,
    # an in-progress Hungarian job can overwrite the shared plan and status
    # while final.mp4 is still the older English video.
    return "en"


def preserve_legacy_video(run_dir: Path) -> None:
    video_dir = run_dir / "video"
    final = video_dir / "final.mp4"
    if not _usable(final):
        return
    language = _legacy_language(video_dir, final)
    cached = video_dir / f"final_{language}.mp4"
    if not _usable(cached):
        shutil.copy2(final, cached)
    # Keep review text and subtitles together with the video they describe.
    for source_name, target_name in (
        ("video_plan.json", f"video_plan_{language}.json"),
        ("captions.srt", f"captions_{language}.srt"),
    ):
        source, target = video_dir / source_name, video_dir / target_name
        if (
            _usable(source)
            and not _usable(target)
            and source.stat().st_mtime <= final.stat().st_mtime + 2
        ):
            if source_name == "video_plan.json":
                try:
                    if (
                        json.loads(source.read_text(encoding="utf-8")).get("language", "en")
                        != language
                    ):
                        continue
                except (ValueError, OSError):
                    continue
            shutil.copy2(source, target)


def cached_video_file(run_dir: Path) -> Path | None:
    preserve_legacy_video(run_dir)
    path = run_dir / "video" / f"final_{load_output_language(run_dir)}.mp4"
    return path if _usable(path) else None


def cached_video_plan(run_dir: Path) -> dict | None:
    preserve_legacy_video(run_dir)
    language = load_output_language(run_dir)
    video = run_dir / "video"
    for path in (video / f"video_plan_{language}.json", video / "video_plan.json"):
        try:
            plan = json.loads(path.read_text(encoding="utf-8"))
            if plan.get("language", "en") == language:
                return plan
        except (OSError, ValueError, AttributeError):
            continue
    return None


def cached_video_captions(run_dir: Path) -> Path | None:
    preserve_legacy_video(run_dir)
    language = load_output_language(run_dir)
    video = run_dir / "video"
    dedicated = video / f"captions_{language}.srt"
    if _usable(dedicated):
        return dedicated
    # Never attach the other language's shared subtitles to a cached video.
    shared = video / "captions.srt"
    try:
        plan = json.loads((video / "video_plan.json").read_text(encoding="utf-8"))
        if plan.get("language", "en") == language and _usable(shared):
            return shared
    except (OSError, ValueError, AttributeError):
        pass
    return None
