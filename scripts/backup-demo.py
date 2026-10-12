"""Create local source and selected demo snapshots without credentials or dependency folders."""

from pathlib import Path
import hashlib
import json
from zipfile import ZipFile, ZIP_DEFLATED, ZIP_STORED

root = Path(__file__).resolve().parents[1]
docs = root / "docs"
ids = json.loads((docs / "REHEARSAL_CAMPAIGNS.json").read_text(encoding="utf-8"))
source = []
for name in (
    "backend/app",
    "backend/tests",
    "backend/evals",
    "backend/scaffold",
    "frontend/src",
    "frontend/public",
    "frontend/dist",
    "scripts",
):
    directory = root / name
    for path in directory.rglob("*"):
        if (
            path.is_file()
            and "__pycache__" not in path.parts
            and path.suffix != ".pyc"
            and not path.name.startswith(".env")
        ):
            source.append(path)
for name in (
    "README.md",
    "backend/requirements.txt",
    "backend/.env.example",
    "frontend/package.json",
    "frontend/package-lock.json",
    "frontend/index.html",
    "frontend/vite.config.ts",
    "frontend/tsconfig.json",
    "frontend/tsconfig.node.json",
    "frontend/tailwind.config.js",
    "frontend/postcss.config.js",
):
    if (root / name).is_file():
        source.append(root / name)
for pattern in (
    "*.md",
    "REHEARSAL_*.json",
    "REHEARSAL_*.jpg",
    "REHEARSAL_*.png",
    "STORY_ROOM_*.json",
    "EXTENSION_*.json",
):
    source.extend(docs.glob(pattern))
allowed = {
    "source.pdf",
    "source.docx",
    "extracted_text.json",
    "analysis.json",
    "master_content.json",
    "platforms.json",
    "assets.json",
    "brief.json",
    "workspace.json",
    "campaign.json",
    "output_language.json",
    "master_preferences.json",
    "platform_preferences.json",
    "verification.json",
    "combined.json",
    "story_room.json",
}
media_names = {
    "final.mp4",
    "final_en.mp4",
    "final_hu.mp4",
    "captions.srt",
    "captions_en.srt",
    "captions_hu.srt",
    "video_plan.json",
    "video_plan_en.json",
    "video_plan_hu.json",
    "status.json",
}
storage = root / "backend/storage"
demo = []
for run in set(ids.values()):
    folder = storage / run
    demo.extend(path for path in folder.iterdir() if path.is_file() and path.name in allowed)
    if (folder / "extensions").is_dir():
        demo.extend(path for path in (folder / "extensions").rglob("*.json") if path.is_file())
    if (folder / "assets").is_dir():
        demo.extend(
            path
            for path in (folder / "assets").rglob("*")
            if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}
        )
    if (folder / "video").is_dir():
        demo.extend(
            path
            for path in (folder / "video").iterdir()
            if path.is_file() and path.name in media_names
        )
if (storage / "news_inbox.json").is_file():
    demo.append(storage / "news_inbox.json")
for path in (storage / "jobs").glob("*.json"):
    job = json.loads(path.read_text(encoding="utf-8"))
    if job.get("run_id") in ids.values() and job.get("state") == "ready":
        demo.append(path)


def snapshot(paths, output):
    manifest = []
    with ZipFile(output, "w", ZIP_DEFLATED) as archive:
        for path in sorted(set(paths)):
            if not path.resolve().is_relative_to(root.resolve()):
                raise ValueError("A snapshot path escaped the project directory.")
            relative = path.relative_to(root).as_posix()
            if "/auth/" in relative or path.name == ".env":
                raise ValueError("Credentials cannot be included in demo snapshots.")
            payload = path.read_bytes()
            manifest.append(
                {
                    "path": relative,
                    "bytes": len(payload),
                    "sha256": hashlib.sha256(payload).hexdigest(),
                }
            )
            archive.writestr(
                relative,
                payload,
                compress_type=ZIP_STORED
                if path.suffix.lower() in {".mp4", ".png", ".jpg", ".webp"}
                else ZIP_DEFLATED,
            )
        archive.writestr(
            "SNAPSHOT_MANIFEST.json",
            json.dumps({"files": manifest, "credentials_included": False}, indent=2),
        )
    with ZipFile(output) as archive:
        assert archive.testzip() is None
    return {
        "file": output.name,
        "entries": len(manifest),
        "bytes": output.stat().st_size,
        "sha256": hashlib.sha256(output.read_bytes()).hexdigest(),
    }


report = {
    "source": snapshot(source, docs / "SPRINT_SOURCE_SNAPSHOT.zip"),
    "demo": snapshot(demo, docs / "SPRINT_DEMO_STORAGE.zip"),
    "credentials_included": False,
}
(docs / "SPRINT_BACKUP_MANIFEST.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
print(json.dumps(report, indent=2))
