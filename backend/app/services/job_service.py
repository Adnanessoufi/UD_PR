"""Persistent, bounded jobs for registered non-publishing tasks."""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone
import json
from pathlib import Path
from uuid import UUID, uuid4
from pydantic import ValidationError
from app.models.job import JobRecord
from app.services import campaign_service
from app.services.openai_service import AIServiceError
from app.services.task_registry import TaskContext, TaskRegistry, registry
from app.services.verification_service import run_lock


class JobManager:
    def __init__(
        self, tasks: TaskRegistry = registry, root: Path | None = None, concurrency: int = 2
    ):
        self.registry = tasks
        self.storage_root = root
        self.concurrency = concurrency
        self.workers: dict[str, asyncio.Task] = {}
        self.slots = asyncio.Semaphore(concurrency)

    @property
    def root(self) -> Path:
        return (
            self.storage_root
            if self.storage_root is not None
            else campaign_service.STORAGE / "jobs"
        )

    def _path(self, job_id: UUID | str) -> Path:
        return self.root / f"{UUID(str(job_id))}.json"

    def _save(self, record: JobRecord) -> None:
        self.root.mkdir(parents=True, exist_ok=True)
        path = self._path(record.id)
        temp = self.root / f".{record.id}.{uuid4().hex}.tmp"
        try:
            temp.write_text(record.model_dump_json(indent=2), encoding="utf-8")
            temp.replace(path)
        finally:
            temp.unlink(missing_ok=True)

    def _read(self, job_id: UUID | str) -> JobRecord:
        try:
            return JobRecord.model_validate_json(self._path(job_id).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise AIServiceError("Job was not found.", 404) from exc
        except (ValueError, OSError) as exc:
            raise AIServiceError("Job record could not be read.", 422) from exc

    def get(self, job_id: UUID | str) -> JobRecord:
        record = self._read(job_id)
        if record.state in {"queued", "running"} and (
            str(record.id) not in self.workers or self.workers[str(record.id)].done()
        ):
            # A new process cannot resume an unknown partially completed action safely.
            record.state = "interrupted"
            record.message = "Worker stopped. Retry this job explicitly."
            record.error = "The previous worker is no longer active."
        return record

    def list(self, run_id: UUID) -> list[JobRecord]:
        result = []
        if self.root.is_dir():
            for path in self.root.glob("*.json"):
                try:
                    item = self.get(path.stem)
                except (AIServiceError, ValueError):
                    continue
                if item.run_id == run_id:
                    result.append(item)
        return sorted(result, key=lambda item: item.created_at, reverse=True)[:50]

    async def start(
        self,
        run_id: UUID,
        task_id: str,
        arguments: dict,
        *,
        retry_of: UUID | None = None,
        attempt: int = 1,
    ) -> JobRecord:
        folder = campaign_service.run_folder(run_id)
        normalized = self.registry.validate(task_id, arguments, folder).model_dump(mode="json")
        for active_id in tuple(self.workers):
            record = self._read(active_id)
            if (
                record.run_id == run_id
                and record.task_id == task_id
                and record.arguments == normalized
            ):
                return record
        now = datetime.now(timezone.utc)
        record = JobRecord(
            id=uuid4(),
            run_id=run_id,
            task_id=task_id,
            label=self.registry.get(task_id).label,
            arguments=normalized,
            created_at=now,
            updated_at=now,
            retry_of=retry_of,
            attempt=attempt,
        )
        self._save(record)
        self.workers[str(record.id)] = asyncio.create_task(self._run(record, folder))
        return record

    async def _run(self, record: JobRecord, folder: Path) -> None:
        async def progress(value: int, message: str):
            record.progress = max(record.progress, min(99, max(0, value)))
            record.message = message[:300]
            record.updated_at = datetime.now(timezone.utc)
            self._save(record)

        try:
            async with self.slots:
                async with run_lock(str(record.run_id)):
                    record.state = "running"
                    await progress(1, "Starting")
                    spec = self.registry.get(record.task_id)
                    args = spec.arguments.model_validate(record.arguments)
                    result = await spec.handler(
                        TaskContext(str(record.run_id), folder, progress), args
                    )
                    validated = (
                        result
                        if isinstance(result, spec.result)
                        else spec.result.model_validate(result)
                    )
                    record.result = validated.model_dump(mode="json")
                    record.state = "ready"
                    record.progress = 100
                    record.message = "Complete"
        except asyncio.CancelledError:
            record.state = "cancelled"
            record.message = "Cancelled. Any already saved draft remains available."
        except AIServiceError as exc:
            record.state = "failed"
            record.error = str(exc)
            record.message = "Task failed"
        except Exception as exc:
            record.state = "failed"
            record.error = f"Task failed ({type(exc).__name__}). Check the implementation or input."
            record.message = "Task failed"
        finally:
            record.updated_at = datetime.now(timezone.utc)
            self._save(record)
            self.workers.pop(str(record.id), None)

    async def cancel(self, job_id: UUID) -> JobRecord:
        worker = self.workers.get(str(job_id))
        if worker:
            worker.cancel()
            await asyncio.gather(worker, return_exceptions=True)
            record = self._read(job_id)
            if record.state in {"queued", "running"}:
                record.state = "cancelled"
                record.message = "Cancelled before the worker started."
                record.updated_at = datetime.now(timezone.utc)
                self._save(record)
            self.workers.pop(str(job_id), None)
        return self.get(job_id)

    async def retry(self, job_id: UUID) -> JobRecord:
        old = self.get(job_id)
        if old.state not in {"failed", "interrupted", "cancelled"}:
            raise AIServiceError("Only failed, interrupted or cancelled jobs can be retried.", 409)
        return await self.start(
            old.run_id, old.task_id, old.arguments, retry_of=old.id, attempt=old.attempt + 1
        )

    async def stop(self):
        for job_id in tuple(self.workers):
            await self.cancel(UUID(job_id))
        self.workers.clear()

    def prepare(self):
        # Lifespan/test loops get their own semaphore; saved status remains on disk.
        self.slots = asyncio.Semaphore(self.concurrency)


manager = JobManager()
