"""Analysis, generation, and edited master-content persistence."""

from pathlib import Path
from time import perf_counter
from uuid import UUID

from fastapi import APIRouter, HTTPException

from app.models.content import CombinedResult, MasterContent, SourceAnalysis
from app.services.analysis_service import analyze_source
from app.services.content_service import (
    generate_content,
    load_analysis,
    save_content,
    validate_content,
)
from app.services.platform_service import load_master
from app.services.openai_service import AIServiceError
from app.services.output_language import load_output_language
from app.services.process_service import process_source

router = APIRouter(prefix="/api")
STORAGE_DIR = Path(__file__).resolve().parents[2] / "storage"


def run_folder(run_id: UUID) -> Path:
    path = STORAGE_DIR / str(run_id)
    if not path.is_dir():
        raise HTTPException(
            status_code=404, detail="Document run was not found. Please upload again."
        )
    return path


@router.post("/analyze/{run_id}", response_model=SourceAnalysis)
async def analyze(run_id: UUID) -> SourceAnalysis:
    try:
        return await analyze_source(run_folder(run_id))
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/process/{run_id}", response_model=CombinedResult)
async def process(run_id: UUID) -> CombinedResult:
    try:
        return await process_source(run_folder(run_id))
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.get("/saved/{run_id}", response_model=CombinedResult)
async def saved(run_id: UUID) -> CombinedResult:
    folder = run_folder(run_id)
    try:
        analysis = load_analysis(folder)
        if analysis is None:
            raise AIServiceError("Saved analysis is missing.", 404)
        return CombinedResult(
            analysis=analysis,
            content=load_master(folder),
            output_language=load_output_language(folder),
        )
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.post("/generate/{run_id}", response_model=MasterContent)
async def generate(run_id: UUID) -> MasterContent:
    folder = run_folder(run_id)
    try:
        analysis = load_analysis(folder)
        if analysis is None:
            raise AIServiceError(
                "Source analysis is missing. Please process the document first.", 404
            )
        started = perf_counter()
        content = await generate_content(folder, analysis, load_output_language(folder))
        print(f"[{folder.name}] OpenAI regeneration: {perf_counter() - started:.1f}s", flush=True)
        return content
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


@router.put("/master/{run_id}", response_model=MasterContent)
async def save_master(run_id: UUID, content: MasterContent) -> MasterContent:
    folder = run_folder(run_id)
    try:
        analysis = load_analysis(folder)
        if analysis is None:
            raise AIServiceError(
                "Source analysis is missing. Please analyze the document again.", 404
            )
        valid_ids = {fact.id for fact in analysis.key_facts}
        if not content.source_fact_ids or any(
            fact_id not in valid_ids for fact_id in content.source_fact_ids
        ):
            raise AIServiceError("Content has invalid source references.", 422)
        validate_content(analysis, content)
        save_content(folder, content)
        return content
    except AIServiceError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc
