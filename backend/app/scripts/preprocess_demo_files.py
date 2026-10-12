"""Prepare the six official demo documents without touching video outputs."""

import argparse
import asyncio
import json
import shutil
from pathlib import Path
from uuid import uuid4

import pymupdf

from app.services.asset_service import create_assets, family_for
from app.services.cache_service import (
    DEMO_PLATFORMS,
    STORAGE_DIR,
    availability,
    find_run,
    register,
    sha256_file,
)
from app.services.content_service import load_analysis
from app.services.document_service import extract_document
from app.services.platform_service import create_platforms, load_platforms
from app.services.process_service import process_source
from app.models.platform import PlatformRequest

DEFAULT_FOLDER = Path(__file__).resolve().parents[3] / "sample_files_for_PR (1)"
SUMMARY_PATH = STORAGE_DIR / "demo_preparation_summary.json"


def save_summary(records: list[dict]) -> None:
    SUMMARY_PATH.write_text(
        json.dumps(
            {
                "documents": records,
                "files_discovered": len(records),
                "successfully_prepared": sum(item["ready_for_demo"] for item in records),
                "failed": sum(not item["ready_for_demo"] for item in records),
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def source_family(path: Path) -> str:
    """Use the document itself for a fallback label if AI analysis failed."""
    if path.suffix.lower() == ".pdf":
        with pymupdf.open(path) as document:
            beginning = document[0].get_text().lower()[:2500]
    else:
        from docx import Document

        beginning = " ".join(paragraph.text for paragraph in Document(path).paragraphs[:20]).lower()
    curriculum_words = ("tanterv", "curriculum", "degree programme", "study programme")
    return "curriculum" if any(word in beginning for word in curriculum_words) else "research"


async def prepare(path: Path, number: int, total: int) -> dict:
    print(f"[{number}/{total}] {path.name}", flush=True)
    record = {
        "filename": path.name,
        "sha256": "",
        "run_id": "",
        "document_family": source_family(path),
        "extraction": "failed",
        "analysis": "failed",
        "master_content": "failed",
        "platforms": "failed",
        "platform_details": {},
        "assets": "failed",
        "asset_count": 0,
        "video": "skipped",
        "ready_for_demo": False,
        "error": None,
    }
    run_dir = None
    try:
        digest = sha256_file(path)
        record["sha256"] = digest
        file_type = path.suffix.lower().lstrip(".")
        run_dir = find_run(digest, file_type)
        if run_dir is None:
            run_dir = STORAGE_DIR / str(uuid4())
            run_dir.mkdir(parents=True, exist_ok=False)
            shutil.copyfile(path, run_dir / f"source.{file_type}")
        record["run_id"] = run_dir.name
        extracted = run_dir / "extracted_text.json"
        if extracted.is_file():
            record["extraction"] = "reused"
        else:
            result = extract_document(run_dir / f"source.{file_type}", path.name, file_type)
            extracted.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
            record["extraction"] = "generated"
        print(f"  extraction: {record['extraction']}", flush=True)

        had_analysis = (run_dir / "analysis.json").is_file()
        had_master = (run_dir / "master_content.json").is_file()
        combined = await process_source(run_dir)
        record["analysis"] = "reused" if had_analysis else "generated"
        record["master_content"] = "reused" if had_master else "generated"
        record["document_family"] = family_for(combined.analysis)
        print(
            f"  analysis: {record['analysis']}; master content: {record['master_content']}",
            flush=True,
        )

        prior = load_platforms(run_dir)
        before = (
            {item.platform for item in prior.items if item.body.strip() and item.source_fact_ids}
            if prior
            else set()
        )
        await create_platforms(
            run_dir,
            PlatformRequest(content_types=["text", "image"], platforms=list(DEMO_PLATFORMS)),
        )
        record["platform_details"] = {
            name: "reused" if name in before else "generated" for name in DEMO_PLATFORMS
        }
        record["platforms"] = (
            "reused" if all(name in before for name in DEMO_PLATFORMS) else "generated"
        )
        for name, status in record["platform_details"].items():
            print(f"  {name}: {status}", flush=True)

        asset_before = availability(run_dir)["assets"]
        pack = await create_assets(run_dir, list(DEMO_PLATFORMS))
        record["assets"] = "reused" if asset_before else "generated"
        record["asset_count"] = len(pack.assets)
        current = availability(run_dir)
        if not all(current.values()):
            if not current["assets"]:
                record["assets"] = "failed"
            raise RuntimeError(
                f"Saved stages remain incomplete: {[key for key, ready in current.items() if not ready]}; image error: {pack.image_error}"
            )
        record["ready_for_demo"] = True
        print(
            f"  assets: {record['assets']} ({record['asset_count']}); video: SKIPPED; READY",
            flush=True,
        )
    except Exception as exc:
        record["error"] = f"{type(exc).__name__}: {exc}"
        if run_dir is not None and run_dir.is_dir():
            try:
                analysis = load_analysis(run_dir)
                if analysis is not None:
                    record["document_family"] = family_for(analysis)
            except Exception:
                pass
        print(f"  video: SKIPPED; FAILED: {record['error']}", flush=True)
    finally:
        if (
            run_dir is not None
            and (run_dir / f"source.{path.suffix.lower().lstrip('.')}").is_file()
            and record["sha256"]
        ):
            register(record["sha256"], run_dir, path.name)
    return record


async def main(folder: Path) -> None:
    if not folder.is_dir():
        raise SystemExit(f"Sample folder not found: {folder}")
    files = sorted(
        path
        for path in folder.iterdir()
        if path.is_file() and path.suffix.lower() in {".pdf", ".docx"}
    )
    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Preparing {len(files)} supported documents from {folder}", flush=True)
    records = []
    for number, path in enumerate(files, 1):
        records.append(await prepare(path, number, len(files)))
        save_summary(records)
    print(
        f"Complete: {sum(item['ready_for_demo'] for item in records)}/{len(records)} ready. Summary: {SUMMARY_PATH}",
        flush=True,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--folder", type=Path, default=DEFAULT_FOLDER)
    asyncio.run(main(parser.parse_args().folder))
