"""Task schemas and background job endpoints."""

from uuid import UUID
from fastapi import APIRouter, HTTPException
from pydantic import ValidationError
from app.models.job import JobRecord, JobRequest
from app.services import builtin_tasks  # register the existing adapters
from app.extensions import load_extensions

load_extensions()
from app.services import job_service
from app.services.model_gateway import describe
from app.services.openai_service import AIServiceError
from app.services.task_registry import registry

router = APIRouter(prefix="/api", tags=["tasks"])


@router.get("/tasks")
def tasks():
    return registry.descriptors()


@router.get("/system/capabilities")
def capabilities():
    try:
        return {
            "provider": describe(),
            "tasks": [{"id": x["id"], "label": x["label"]} for x in registry.descriptors()],
            "job_states": ["queued", "running", "ready", "failed", "cancelled", "interrupted"],
        }
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.post("/jobs/runs/{run_id}", status_code=202, response_model=JobRecord)
async def start(run_id: UUID, request: JobRequest):
    try:
        return await job_service.manager.start(run_id, request.task_id, request.arguments)
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(422, "Task arguments do not match the registered schema.") from exc


@router.get("/jobs/runs/{run_id}", response_model=list[JobRecord])
def history(run_id: UUID):
    return job_service.manager.list(run_id)


@router.get("/jobs/{job_id}", response_model=JobRecord)
def status(job_id: UUID):
    try:
        return job_service.manager.get(job_id)
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.post("/jobs/{job_id}/cancel", response_model=JobRecord)
async def cancel(job_id: UUID):
    try:
        return await job_service.manager.cancel(job_id)
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.post("/jobs/{job_id}/retry", status_code=202, response_model=JobRecord)
async def retry(job_id: UUID):
    try:
        return await job_service.manager.retry(job_id)
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
    except ValidationError as exc:
        raise HTTPException(422, "The saved arguments no longer match the task schema.") from exc
