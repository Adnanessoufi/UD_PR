"""Local source-document upload endpoint."""

import json
import hashlib
import shutil
from pathlib import Path
from time import perf_counter
from uuid import uuid4
from zipfile import BadZipFile

import pymupdf
from docx.opc.exceptions import PackageNotFoundError
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

from app.services.document_service import EmptyDocxError, EmptyPdfError, extract_document
from app.services.cache_service import availability, find_run, register

router = APIRouter(prefix="/api")
STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage"


class UploadResponse(BaseModel):
    run_id: str
    filename: str
    file_type: str
    page_count: int | None
    status: str
    cached: bool = False


@router.post("/upload", response_model=UploadResponse)
async def upload_document(file: UploadFile = File(...)) -> UploadResponse:
    started = perf_counter()
    filename = Path(file.filename or "").name
    file_type = Path(filename).suffix.lower().lstrip(".")
    if file_type not in {"pdf", "docx"}:
        raise HTTPException(status_code=415, detail="Please upload a PDF or DOCX file.")

    STORAGE_DIR.mkdir(parents=True, exist_ok=True)
    temporary = STORAGE_DIR / f".upload-{uuid4().hex}.tmp"
    run_dir: Path | None = None
    created = False

    try:
        digest = hashlib.sha256()
        with temporary.open("wb") as destination:
            while chunk := await file.read(1024 * 1024):
                destination.write(chunk)
                digest.update(chunk)
        if temporary.stat().st_size == 0:
            raise HTTPException(status_code=400, detail="The uploaded file is empty.")

        fingerprint = digest.hexdigest()
        run_dir = find_run(fingerprint, file_type)
        cached = run_dir is not None and all(availability(run_dir).values())
        if run_dir is None:
            run_dir = STORAGE_DIR / str(uuid4())
            run_dir.mkdir(parents=True, exist_ok=False)
            created = True
            source_path = run_dir / f"source.{file_type}"
            temporary.replace(source_path)
        else:
            source_path = run_dir / f"source.{file_type}"
        run_id = run_dir.name

        extracted_path = run_dir / "extracted_text.json"
        try:
            extracted = json.loads(extracted_path.read_text(encoding="utf-8"))
            if file_type == "docx" and not extracted.get("text", "").strip():
                raise ValueError("Empty legacy extraction")
        except (OSError, ValueError):
            extraction_started = perf_counter()
            extracted = extract_document(source_path, filename, file_type)
            print(
                f"[{run_id}] {file_type.upper()} extraction: {perf_counter() - extraction_started:.1f}s",
                flush=True,
            )
            extracted_path.write_text(
                json.dumps(extracted, ensure_ascii=False, indent=2), encoding="utf-8"
            )
        register(fingerprint, run_dir, filename)
        print(f"[{run_id}] TOTAL upload: {perf_counter() - started:.1f}s", flush=True)
        return UploadResponse(
            run_id=run_id,
            filename=filename,
            file_type=file_type,
            page_count=extracted["page_count"],
            status="ready",
            cached=cached,
        )
    except EmptyDocxError as exc:
        if created and run_dir is not None:
            shutil.rmtree(run_dir, ignore_errors=True)
        raise HTTPException(
            422, "This DOCX has no readable text. Include text in the document body or tables."
        ) from exc
    except EmptyPdfError as exc:
        if created and run_dir is not None:
            shutil.rmtree(run_dir, ignore_errors=True)
        raise HTTPException(
            status_code=422,
            detail="This PDF has no extractable text. Please upload a text-based PDF.",
        ) from exc
    except (pymupdf.FileDataError, PackageNotFoundError, BadZipFile, ValueError, KeyError) as exc:
        if created and run_dir is not None:
            shutil.rmtree(run_dir, ignore_errors=True)
        raise HTTPException(
            status_code=422,
            detail="The document could not be read. Please check the file and try again.",
        ) from exc
    except HTTPException:
        if created and run_dir is not None:
            shutil.rmtree(run_dir, ignore_errors=True)
        raise
    except Exception as exc:
        if created and run_dir is not None:
            shutil.rmtree(run_dir, ignore_errors=True)
        raise HTTPException(
            status_code=500, detail="Document extraction failed. Please try again."
        ) from exc
    finally:
        temporary.unlink(missing_ok=True)
        await file.close()
