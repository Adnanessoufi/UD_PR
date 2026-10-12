"""Campaign library, brief, workspace recovery and draft exports."""

from uuid import UUID
from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from app.models.campaign import CampaignBrief, CampaignMetadata, WorkspaceState
from app.services import campaign_service as service
from app.services.openai_service import AIServiceError

router = APIRouter(prefix="/api/campaigns", tags=["campaigns"])


@router.get("")
def campaigns(query: str = "", archived: bool = False):
    return service.list_campaigns(query, archived)


@router.get("/{run_id}")
def reopen(run_id: UUID):
    try:
        return service.bundle(service.run_folder(run_id))
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.put("/{run_id}")
def update(run_id: UUID, metadata: CampaignMetadata):
    try:
        folder = service.run_folder(run_id)
        service.write_json(folder, "campaign.json", metadata.model_dump())
        return service.summary(folder)
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.put("/{run_id}/brief")
def brief(run_id: UUID, preferences: CampaignBrief):
    try:
        folder = service.run_folder(run_id)
        service.write_json(folder, "brief.json", preferences.model_dump())
        return preferences
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.put("/{run_id}/workspace")
def workspace(run_id: UUID, state: WorkspaceState):
    try:
        service.write_json(service.run_folder(run_id), "workspace.json", state.model_dump())
        return state
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc


@router.get("/{run_id}/export")
def export(run_id: UUID, include_media: bool = True):
    try:
        data, filename = service.export_campaign(service.run_folder(run_id), include_media)
        return Response(
            data,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    except AIServiceError as exc:
        raise HTTPException(exc.status_code, str(exc)) from exc
