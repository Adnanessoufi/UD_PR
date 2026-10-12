"""Byte-exact local run lookup for demo documents."""

import hashlib
import json
from pathlib import Path

from app.models.assets import AssetPack
from app.models.platform import PlatformResult

STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage"
INDEX_PATH = STORAGE_DIR / "cache_index.json"
DEMO_PLATFORMS = ("website", "linkedin", "facebook", "instagram")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for block in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def asset_exists(run_dir: Path, url: str) -> bool:
    route = url.split("?", 1)[0]
    prefix = f"/api/assets/{run_dir.name}/files/"
    if not route.startswith(prefix):
        return False
    relative = Path(route[len(prefix) :])
    if relative.is_absolute() or ".." in relative.parts:
        return False
    return (run_dir / "assets" / relative).is_file()


def availability(run_dir: Path) -> dict[str, bool]:
    stages = {
        "extraction": (run_dir / "extracted_text.json").is_file(),
        "analysis": (run_dir / "analysis.json").is_file(),
        "master_content": (run_dir / "master_content.json").is_file(),
        "platforms": False,
        "assets": False,
    }
    try:
        result = PlatformResult.model_validate_json(
            (run_dir / "platforms.json").read_text(encoding="utf-8")
        )
        stages["platforms"] = all(
            any(
                item.platform == name and item.body.strip() and item.source_fact_ids
                for item in result.items
            )
            for name in DEMO_PLATFORMS
        )
    except (OSError, ValueError):
        pass
    try:
        pack = AssetPack.model_validate_json((run_dir / "assets.json").read_text(encoding="utf-8"))
        generated = (
            "generated_explainer"
            if pack.document_family == "research"
            else "generated_education_visual"
        )
        stages["assets"] = (
            bool(pack.assets)
            and all(asset_exists(run_dir, item.path) for item in pack.assets)
            and any(item.type == generated for item in pack.assets)
        )
    except (OSError, ValueError):
        pass
    return stages


def _index() -> dict:
    try:
        value = json.loads(INDEX_PATH.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def register(digest: str, run_dir: Path, filename: str) -> None:
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    index = _index()
    index[digest] = {
        "run_id": run_dir.name,
        "filename": filename,
        "available": availability(run_dir),
    }
    temporary = INDEX_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(index, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(INDEX_PATH)


def find_run(digest: str, file_type: str) -> Path | None:
    indexed = _index().get(digest, {})
    preferred = indexed.get("run_id") if isinstance(indexed, dict) else None
    candidates = []
    if preferred:
        candidates.append(STORAGE_DIR / preferred)
    if STORAGE_DIR.is_dir():
        candidates.extend(
            path for path in STORAGE_DIR.iterdir() if path.is_dir() and path.name != preferred
        )
    matches = []
    for run_dir in candidates:
        source = run_dir / f"source.{file_type}"
        if source.is_file() and sha256_file(source) == digest:
            stages = availability(run_dir)
            score = sum(stages.values()) + (3 if stages["assets"] else 0)
            matches.append((score, run_dir))
    return max(matches, key=lambda pair: pair[0])[1] if matches else None
