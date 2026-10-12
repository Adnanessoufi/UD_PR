from contextlib import asynccontextmanager
from uuid import UUID

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.assets import router as assets_router
from app.api.campaigns import router as campaigns_router
from app.api.content import router as content_router
from app.api.meta import router as meta_router
from app.api.news import router as news_router
from app.api.platforms import router as platforms_router
from app.api.quick_announcement import router as quick_announcement_router
from app.api.tasks import router as tasks_router
from app.api.tiktok import router as tiktok_router
from app.api.university_site import router as university_site_router
from app.api.upload import router as upload_router
from app.api.verification import router as verification_router
from app.api.video import router as video_router
from app.api.youtube import router as youtube_router
from app.extensions import extension_routers
from app.services import job_service
from app.services.verification_service import run_lock


@asynccontextmanager
async def lifespan(app):
    job_service.manager.prepare()
    try:
        yield
    finally:
        await job_service.manager.stop()


app = FastAPI(title="UD PR Studio API", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["*"],
)

for router in (
    upload_router,
    content_router,
    platforms_router,
    assets_router,
    video_router,
    youtube_router,
    tiktok_router,
    meta_router,
    university_site_router,
    quick_announcement_router,
    verification_router,
    campaigns_router,
    news_router,
    tasks_router,
    *extension_routers(),
):
    app.include_router(router)


@app.middleware("http")
async def serialize_run_mutations(request, call_next):
    # Keep edits, approval and publishing on the same campaign from racing.
    if request.method in {"POST", "PUT", "DELETE"}:
        for segment in request.url.path.split("/"):
            try:
                run_id = str(UUID(segment))
            except ValueError:
                continue
            async with run_lock(run_id):
                return await call_next(request)
    return await call_next(request)
