"""Grounded video planning and asynchronous ElevenLabs production."""

from __future__ import annotations

import asyncio
import base64
from io import BytesIO
import json
import os
from pathlib import Path
import re
import shutil
from time import monotonic
from uuid import uuid4

import httpx
from dotenv import load_dotenv
from PIL import Image
from pydantic import ValidationError

from app.models.assets import AssetPack
from app.models.content import MasterContent, SourceAnalysis
from app.services.content_service import load_analysis
from app.services.platform_service import load_master
from app.services.output_language import load_output_language
from app.services.video_cache import preserve_legacy_video
from app.services.video_compose import compose_video

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
API = "https://api.elevenlabs.io/v1"


class VideoError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def config() -> tuple[str, str, str]:
    # Read the current voice choice for each explicitly requested new video.
    load_dotenv(Path(__file__).resolve().parents[2] / ".env", override=True)
    values = tuple(
        os.getenv(name, "").strip()
        for name in ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "ELEVENLABS_VIDEO_MODEL")
    )
    missing = [
        name
        for name, value in zip(
            ("ELEVENLABS_API_KEY", "ELEVENLABS_VOICE_ID", "ELEVENLABS_VIDEO_MODEL"), values
        )
        if not value
    ]
    if missing:
        raise VideoError(f"Set {', '.join(missing)} in backend/.env before generating video.", 503)
    return values


def _sentence(value: str) -> str:
    value = " ".join(value.strip().split())
    return value if not value or value[-1] in ".!?" else f"{value}."


def _words(value: str) -> int:
    return len(value.split())


def _script(
    analysis: SourceAnalysis, master: MasterContent, language: str = "en"
) -> tuple[str, list[str]]:
    approved_ids = set(master.source_fact_ids)
    facts = [
        fact for fact in analysis.key_facts if fact.id in approved_ids and fact.statement.strip()
    ]
    if not facts:
        raise VideoError("The saved master story has no matching source facts for video.", 422)
    # The approved short summary already condenses the story and its caveat.
    script = _sentence(master.short_summary)
    if language == "hu" and _words(script) < 45:
        for message in master.key_messages:
            if _words(script) >= 65 or _words(script) + _words(message) > 90:
                break
            if message.strip() and message.strip().casefold() not in script.casefold():
                script += " " + _sentence(message)
    elif _words(script) < 45:
        method = next(
            (
                fact
                for fact in facts
                if "method" in fact.category.lower()
                and _words(script) + _words(fact.statement) <= 60
            ),
            None,
        )
        if method:
            first, separator, rest = script.partition(". ")
            addition = _sentence(method.statement)
            script = f"{first}. {addition} {rest}" if separator else f"{script} {addition}"
    return script, list(master.source_fact_ids)


def _asset_file(
    run_dir: Path, pack: AssetPack | None, kinds: tuple[str, ...]
) -> tuple[Path | None, str | None]:
    if pack is None:
        return None, None
    for kind in kinds:
        for asset in pack.assets:
            if asset.type == kind and asset.source != "user":
                path = run_dir / "assets" / f"{kind}.png"
                if path.is_file():
                    return path, asset.id
    return None, None


def plan_video(run_dir: Path, uploads: list[dict]) -> dict:
    analysis = load_analysis(run_dir)
    master = load_master(run_dir)
    if analysis is None or master is None:
        raise VideoError("Saved analysis.json and master_content.json are required for video.", 404)
    pack_path = run_dir / "assets.json"
    pack = None
    if pack_path.is_file():
        try:
            pack = AssetPack.model_validate_json(pack_path.read_text(encoding="utf-8"))
        except ValidationError as exc:
            raise VideoError("Saved assets.json is malformed.", 422) from exc
    family = (
        "curriculum"
        if any(
            word in analysis.document_type.lower()
            for word in ("curriculum", "programme", "program", "degree", "educational")
        )
        else "research"
    )
    language = load_output_language(run_dir)
    script, fact_ids = _script(analysis, master, language)
    reference, reference_id = _asset_file(
        run_dir,
        pack,
        ("generated_explainer", "source_visual")
        if family == "research"
        else ("generated_education_visual", "programme_card"),
    )
    prepared_reference = run_dir / "video" / "reference.jpg"
    if reference and prepared_reference.is_file():
        reference = prepared_reference
    source, source_id = _asset_file(
        run_dir,
        pack,
        ("source_visual", "publication_preview")
        if family == "research"
        else ("programme_card", "source_visual"),
    )
    scenes: list[dict] = []
    scenes.append(
        {
            "id": "scene_1",
            "type": "fact_card",
            "duration": 2,
            "purpose": "institutional opening",
            "overlay": "UAV obstacle avoidance"
            if re.search(r"\b(UAV|drone)\b", analysis.title, re.I)
            else analysis.title,
            "detail": analysis.organization
            or (
                "Source-based news"
                if analysis.document_type == "news_article"
                else "Source-based communication"
            ),
        }
    )
    selected_uploads = uploads[:2]
    for item in selected_uploads:
        scenes.append(
            {
                "id": f"scene_{len(scenes) + 1}",
                "type": "uploaded_video",
                "duration": 5,
                "purpose": "user-supplied institutional or topic footage",
                "path": str(run_dir / "video" / "uploads" / item["filename"]),
                "overlay": "",
            }
        )
    motion_count = 3 if not selected_uploads else 2
    focus = analysis.communication_focus.strip() or analysis.title
    is_uav = bool(re.search(r"\b(UAV|drone)\b", analysis.title, re.I))
    for index in range(motion_count):
        if family == "research":
            purpose = (
                "research context",
                "method or process",
                "research environment",
                "conceptual closing",
            )[index]
            caution = "Clearly depict a computer simulation, never real-world deployment or validated operational safety. No fake university footage or branding."
            visual = (
                (
                    "A clearly computer-generated autonomous drone flies forward through a virtual obstacle course; camera follows its motion.",
                    "In a 3D flight simulation, a moving drone changes direction to avoid a virtual obstacle; tracking camera and depth motion.",
                    "A virtual drone navigates as an abstract LiDAR sensing field updates around it; drone and camera both move, no numeric readouts.",
                    "Dynamic simulated aerial navigation among virtual obstacles, with continuous drone and camera movement; no real location or people.",
                )[index]
                if is_uav
                else f"Conceptual animated research visualization with continuous subject and camera motion. Scene purpose: {purpose}."
            )
        else:
            purpose = (
                "learning environment",
                "students and coursework",
                "data and computing practice",
                "academic closing",
            )[index]
            caution = "Education communication only. Do not imply unreported partnerships, outcomes, or programme requirements."
            visual = f"Moving academic learning environment. Scene purpose: {purpose}."
        prompt = (
            f"Professional 16:9 editorial motion clip, 6 seconds. Topic: {analysis.title}. "
            f"Visual focus: {focus}. {visual} Calm institutional tone. {caution} "
            "No legible text, labels, numbers, charts, voice, or music."
        )
        scenes.append(
            {
                "id": f"scene_{len(scenes) + 1}",
                "type": "generated_motion",
                "duration": 6,
                "purpose": purpose,
                "prompt": prompt,
                "reference_asset_id": reference_id if index == 0 else None,
                "reference_path": str(reference) if index == 0 and reference else None,
                "overlay": "",
            }
        )
    high_fact = next(
        (
            fact.statement
            for fact in analysis.key_facts
            if fact.id in fact_ids and any(char.isdigit() for char in fact.statement)
        ),
        "",
    )
    if not high_fact:
        high_fact = next((fact.statement for fact in analysis.key_facts if fact.id in fact_ids), "")
    percentage = re.search(r"\b\d+(?:\.\d+)?%\s+success rate\b", high_fact, re.I)
    if (
        percentage
        and "zero collisions" in high_fact.lower()
        and "simulation" in " ".join(analysis.conditions_and_limitations).lower()
    ):
        card_title, card_detail = (
            percentage.group(0),
            "Zero collisions in main tested configurations · simulation",
        )
    else:
        card_title, card_detail = high_fact, "Source: uploaded document"
    scenes.append(
        {
            "id": f"scene_{len(scenes) + 1}",
            "type": "fact_card",
            "duration": 2,
            "purpose": "grounded fact",
            "overlay": card_title,
            "detail": card_detail,
        }
    )
    if source:
        scenes.append(
            {
                "id": f"scene_{len(scenes) + 1}",
                "type": "source_visual",
                "duration": 2,
                "purpose": "source material",
                "path": str(source),
                "asset_id": source_id,
                "overlay": "",
            }
        )
    publication, publication_id = _asset_file(run_dir, pack, ("publication_preview",))
    if publication and publication != source and not source:
        scenes.append(
            {
                "id": f"scene_{len(scenes) + 1}",
                "type": "publication_preview",
                "duration": 2,
                "purpose": "original publication",
                "path": str(publication),
                "asset_id": publication_id,
                "overlay": "",
            }
        )
    return {
        "duration_target": 25,
        "aspect_ratio": "16:9",
        "language": language,
        "narration": script,
        "source_fact_ids": fact_ids,
        "document_family": family,
        "scenes": scenes,
    }


def video_dir(run_dir: Path) -> Path:
    path = run_dir / "video"
    path.mkdir(exist_ok=True)
    return path


def save_status(run_dir: Path, stage: str, **extra: object) -> dict:
    path = video_dir(run_dir) / "status.json"
    previous = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    value = {**previous, "stage": stage, **extra}
    path.write_text(json.dumps(value, indent=2), encoding="utf-8")
    return value


def load_status(run_dir: Path) -> dict:
    path = run_dir / "video" / "status.json"
    if not path.is_file():
        return {"stage": "idle", "url": None, "error": None}
    return json.loads(path.read_text(encoding="utf-8"))


def load_uploads(run_dir: Path) -> list[dict]:
    path = run_dir / "video" / "uploads.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else []


def save_uploads(run_dir: Path, uploads: list[dict]) -> None:
    video_dir(run_dir)
    (run_dir / "video" / "uploads.json").write_text(json.dumps(uploads, indent=2), encoding="utf-8")


def _api_error(response: httpx.Response) -> VideoError:
    try:
        detail = (
            response.json().get("detail") or response.json().get("message") or response.text[:250]
        )
    except ValueError:
        detail = response.text[:250]
    return VideoError(f"ElevenLabs HTTP {response.status_code}: {detail}", response.status_code)


def _reference_payload(path: Path, model: str) -> dict:
    # Only existing non-user images may be sent. ElevenLabs reference fields differ by model family.
    with Image.open(path) as source:
        source.thumbnail((1280, 720))
        memory = BytesIO()
        source.convert("RGB").save(memory, format="JPEG", quality=84)
    reference = {
        "type": "inline_base64",
        "content_base64": base64.b64encode(memory.getvalue()).decode("ascii"),
        "mime_type": "image/jpeg",
    }
    if model.startswith("veo-"):
        return {"start_frame": reference}
    if "seedance" in model.lower():
        return {"images": [reference]}
    return {}


async def _narrate(
    client: httpx.AsyncClient, voice: str, script: str, path: Path
) -> tuple[dict | None, int]:
    response = await client.post(
        f"{API}/text-to-speech/{voice}/with-timestamps",
        json={
            "text": script,
            "model_id": "eleven_multilingual_v2",
            "voice_settings": {"stability": 0.65, "similarity_boost": 0.75},
        },
    )
    if response.is_error:
        raise _api_error(response)
    data = response.json()
    if not data.get("audio_base64"):
        raise VideoError("ElevenLabs TTS returned an empty audio file.")
    path.write_bytes(base64.b64decode(data["audio_base64"], validate=True))
    return data.get("alignment"), response.status_code


async def _generate_motion(client: httpx.AsyncClient, model: str, scene: dict, path: Path) -> int:
    payload = {
        "model_id": model,
        "prompt": scene["prompt"],
        "duration_secs": 6,
        "aspect_ratio": "16:9",
        "resolution": "720p",
        "generate_audio": False,
    }
    reference = scene.get("reference_path")
    if reference and Path(reference).is_file():
        payload.update(_reference_payload(Path(reference), model))
    response = await client.post(f"{API}/flows/video", json=payload)
    if response.is_error:
        raise _api_error(response)
    generation_id = response.json().get("id")
    if not generation_id:
        raise VideoError("ElevenLabs did not return a video generation ID.")
    deadline = monotonic() + 900
    interval = 10
    while monotonic() < deadline:
        await asyncio.sleep(interval)
        result = await client.get(f"{API}/flows/video/{generation_id}")
        if result.is_error:
            raise _api_error(result)
        data = result.json()
        state = data.get("status")
        if state == "completed":
            url = data.get("content_url")
            if not url:
                raise VideoError("Completed ElevenLabs generation had no content_url.")
            async with httpx.AsyncClient(timeout=120, follow_redirects=True) as download_client:
                async with download_client.stream("GET", url) as stream:
                    if stream.is_error:
                        raise VideoError(
                            f"Could not download ElevenLabs video: HTTP {stream.status_code}."
                        )
                    with path.open("wb") as output:
                        async for chunk in stream.aiter_bytes():
                            output.write(chunk)
            if path.stat().st_size < 1024:
                raise VideoError("ElevenLabs returned an empty video clip.")
            return response.status_code
        if state in {"failed", "error", "cancelled"}:
            raise VideoError(
                f"ElevenLabs video generation {state}: {data.get('error_message') or data.get('error') or data.get('failure_reason') or generation_id}"
            )
        interval = min(60, interval * 2)
    raise VideoError(f"ElevenLabs video generation {generation_id} timed out after 15 minutes.")


async def run_video_job(run_dir: Path, uploads: list[dict], fail_fast: bool = False) -> None:
    folder = video_dir(run_dir)
    stage = "planning"
    narration_seconds = None
    ai_video_seconds = None
    composition_seconds = None
    clips_requested = 0
    clips_succeeded = 0
    video_http_statuses: list[int] = []
    try:
        key, voice, model = config()
        preserve_legacy_video(run_dir)
        save_status(
            run_dir,
            "planning",
            error=None,
            url=None,
            model=model,
            language=load_output_language(run_dir),
        )
        plan = plan_video(run_dir, uploads)
        (folder / "video_plan.json").write_text(
            json.dumps(plan, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        headers = {"xi-api-key": key}
        async with httpx.AsyncClient(headers=headers, timeout=120) as client:
            stage = "narration"
            save_status(run_dir, "narration")
            started = monotonic()
            alignment, tts_http_status = await _narrate(
                client, voice, plan["narration"], folder / "narration.mp3"
            )
            if alignment:
                (folder / "narration_alignment.json").write_text(
                    json.dumps(alignment), encoding="utf-8"
                )
            narration_seconds = round(monotonic() - started, 2)
            generated = [scene for scene in plan["scenes"] if scene["type"] == "generated_motion"]
            errors = []
            stage = "generating_clips"
            save_status(run_dir, "generating_clips", clips_done=0, clips_total=len(generated))
            started = monotonic()
            for index, scene in enumerate(generated):
                path = folder / f"{scene['id']}_{uuid4().hex[:8]}.mp4"
                clips_requested += 1
                try:
                    video_http_statuses.append(await _generate_motion(client, model, scene, path))
                    scene["path"] = str(path)
                    clips_succeeded += 1
                except (VideoError, httpx.HTTPError, OSError, ValueError) as exc:
                    errors.append(f"{scene['id']}: {exc}")
                    if fail_fast or (
                        isinstance(exc, VideoError)
                        and exc.status_code in {400, 401, 402, 403, 404, 422}
                    ):
                        raise
                save_status(
                    run_dir,
                    "generating_clips",
                    clips_done=index + 1,
                    clips_total=len(generated),
                    clip_errors=errors,
                )
            ai_video_seconds = round(monotonic() - started, 2)
        successful = [scene for scene in generated if scene.get("path")]
        failed = [scene for scene in generated if not scene.get("path")]
        for index, scene in enumerate(failed):
            if successful:
                replacement = successful[index % len(successful)]
                scene["path"] = replacement["path"]
                scene["reused_from"] = replacement["id"]
        stage = "composing"
        save_status(run_dir, "composing")
        candidate = folder / "final.pending.mp4"
        started = monotonic()
        result = await asyncio.to_thread(
            compose_video,
            plan["scenes"],
            folder / "narration.mp3",
            plan["narration"],
            candidate,
            folder / "captions.srt",
            alignment=alignment,
        )
        composition_seconds = round(monotonic() - started, 2)
        candidate.replace(folder / "final.mp4")
        shutil.copy2(folder / "final.mp4", folder / f"final_{plan['language']}.mp4")
        (folder / "video_plan.json").write_text(
            json.dumps(
                {**plan, "composition": result, "clip_errors": errors}, indent=2, ensure_ascii=False
            ),
            encoding="utf-8",
        )
        shutil.copy2(folder / "video_plan.json", folder / f"video_plan_{plan['language']}.json")
        shutil.copy2(folder / "captions.srt", folder / f"captions_{plan['language']}.srt")
        save_status(
            run_dir,
            "ready",
            url=f"/api/video/{run_dir.name}/file?v={uuid4().hex}",
            error=None,
            tts_http_status=tts_http_status,
            video_http_statuses=video_http_statuses,
            narration_seconds=narration_seconds,
            ai_video_seconds=ai_video_seconds,
            composition_seconds=composition_seconds,
            clips_requested=clips_requested,
            clips_succeeded=clips_succeeded,
            **result,
        )
    except Exception as exc:
        if stage == "generating_clips" and ai_video_seconds is None and "started" in locals():
            ai_video_seconds = round(monotonic() - started, 2)
        save_status(
            run_dir,
            "failed",
            error=f"{type(exc).__name__}: {exc}",
            failed_stage=stage,
            url=None,
            narration_seconds=narration_seconds,
            ai_video_seconds=ai_video_seconds,
            composition_seconds=composition_seconds,
            clips_requested=clips_requested,
            clips_succeeded=clips_succeeded,
            video_http_statuses=video_http_statuses,
            api_http_status=exc.status_code if isinstance(exc, VideoError) else None,
        )
