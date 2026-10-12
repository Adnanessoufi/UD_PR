"""Contract, isolation, retry and persistence tests for the Sprint foundation."""

import asyncio
from datetime import datetime, timezone
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
from pydantic import BaseModel, Field, ValidationError
from fastapi.testclient import TestClient

from app.models.job import JobRecord
from app.services import campaign_service, job_service, model_gateway
from app.services.job_service import JobManager
from app.services.openai_service import AIServiceError, structured_response
from app.services.task_registry import EmptyArgs, TaskContext, TaskRegistry, TaskSpec
from app.scripts.evaluate_factuality import load_cases, score, evaluate
from app.models.verification import CheckerResult, CheckedUnit, EvidenceReference


class Input(BaseModel):
    count: int = Field(ge=1, le=10)


class Output(BaseModel):
    value: int


class FixtureProvider:
    def describe(self):
        return {
            "name": "fixture",
            "writer_model": "fixture-writer",
            "checker_model": "fixture-checker",
            "writer_ready": True,
            "checker_ready": True,
            "credential": "must-never-be-exposed",
        }

    async def generate(self, prompt, source, schema, role):
        return {"value": 7}


class GatewayTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_facade_preserves_openai_checker_role(self):
        with (
            patch.dict(
                os.environ,
                {
                    "AI_PROVIDER": "openai",
                    "OPENAI_MODEL": "writer",
                    "OPENAI_CHECKER_MODEL": "checker",
                    "OPENAI_API_KEY": "test-only",
                },
            ),
            patch(
                "app.services.openai_service._openai_structured_response",
                new_callable=AsyncMock,
                return_value=Output(value=4),
            ) as low,
        ):
            result = await structured_response("prompt", "source", Output, checker=True)
            self.assertEqual(result.value, 4)
            self.assertTrue(low.call_args.kwargs["checker"])

    async def test_registered_provider_and_public_descriptor(self):
        with (
            patch.dict(model_gateway.PROVIDERS, {"fixture": FixtureProvider()}),
            patch.dict(os.environ, {"AI_PROVIDER": "fixture"}),
        ):
            self.assertEqual((await structured_response("p", "s", Output)).value, 7)
            self.assertNotIn("credential", model_gateway.describe())
            self.assertTrue(model_gateway.checker_readiness()[0])

    async def test_invalid_adapter_output_is_rejected(self):
        provider = FixtureProvider()
        provider.generate = AsyncMock(return_value={"wrong": "schema"})
        with (
            patch.dict(model_gateway.PROVIDERS, {"fixture": provider}),
            patch.dict(os.environ, {"AI_PROVIDER": "fixture"}),
        ):
            with self.assertRaises(AIServiceError):
                await structured_response("p", "s", Output)

    async def test_unknown_provider_fails_without_fallback(self):
        with patch.dict(os.environ, {"AI_PROVIDER": "not-registered"}):
            with self.assertRaises(AIServiceError):
                await structured_response("p", "s", Output)

    async def test_adapter_exception_does_not_expose_vendor_secret(self):
        provider = FixtureProvider()
        provider.generate = AsyncMock(side_effect=RuntimeError("vendor secret"))
        with (
            patch.dict(model_gateway.PROVIDERS, {"fixture": provider}),
            patch.dict(os.environ, {"AI_PROVIDER": "fixture"}),
        ):
            with self.assertRaises(AIServiceError) as failure:
                await structured_response("p", "s", Output)
            self.assertNotIn("vendor secret", str(failure.exception))

    def test_reasoning_effort_is_configurable_without_changing_default_models(self):
        from app.services.openai_service import config

        with (
            patch.dict(
                os.environ,
                {
                    "OPENAI_API_KEY": "test-only",
                    "OPENAI_MODEL": "writer",
                    "OPENAI_REASONING_EFFORT": "medium",
                },
            ),
            patch("app.services.openai_service.AsyncOpenAI"),
        ):
            _, model, effort = config()
            self.assertEqual(model, "writer")
            self.assertEqual(effort, "medium")
        with patch.dict(
            os.environ,
            {
                "OPENAI_API_KEY": "test-only",
                "OPENAI_MODEL": "writer",
                "OPENAI_REASONING_EFFORT": "invalid",
            },
        ):
            with self.assertRaises(AIServiceError):
                config()

    def test_provider_registration_requires_contract_and_unique_name(self):
        with self.assertRaises(ValueError):
            model_gateway.register_provider("openai", FixtureProvider())
        with self.assertRaises(ValueError):
            model_gateway.register_provider("incomplete", object())


class JobTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.storage = Path(__file__).resolve().parents[1] / "storage"
        self.temp = tempfile.TemporaryDirectory(prefix=".foundation-test-", dir=self.storage)
        self.root = Path(self.temp.name)
        self.run_id = uuid4()
        self.folder = self.root / str(self.run_id)
        self.folder.mkdir()
        self.storage_patch = patch.object(campaign_service, "STORAGE", self.root)
        self.storage_patch.start()
        self.registry = TaskRegistry()
        self.manager = JobManager(self.registry, self.root / "jobs", concurrency=2)

    async def asyncTearDown(self):
        await self.manager.stop()
        self.storage_patch.stop()
        assert self.root.resolve().is_relative_to(self.storage.resolve())
        self.temp.cleanup()

    async def settle(self, job_id):
        worker = self.manager.workers.get(str(job_id))
        if worker:
            await worker
        return self.manager.get(job_id)

    def register(self, handler, required_files=()):
        self.registry.register(
            TaskSpec("fixture.run", "Fixture task", Input, Output, handler, required_files)
        )

    async def test_new_typed_task_progress_result_and_disk_recovery(self):
        async def handler(context, args):
            self.assertEqual(context.run_dir, self.folder)
            await context.report(55, "Halfway")
            return Output(value=args.count * 2)

        self.register(handler)
        job = await self.manager.start(self.run_id, "fixture.run", {"count": 3})
        result = await self.settle(job.id)
        self.assertEqual(result.state, "ready")
        self.assertEqual(result.progress, 100)
        self.assertEqual(result.result, {"value": 6})
        recovered = JobManager(self.registry, self.root / "jobs").get(job.id)
        self.assertEqual(recovered.result, {"value": 6})

    async def test_preconditions_and_argument_schema_fail_before_execution(self):
        handler = AsyncMock(return_value=Output(value=2))
        self.register(handler, ("needed.json",))
        with self.assertRaises(AIServiceError):
            await self.manager.start(self.run_id, "fixture.run", {"count": 1})
        (self.folder / "needed.json").write_text("{}")
        with self.assertRaises(ValidationError):
            await self.manager.start(self.run_id, "fixture.run", {"count": 50})
        with self.assertRaises(AIServiceError):
            await self.manager.start(self.run_id, "missing", {})
        handler.assert_not_called()

    async def test_active_request_deduplication_and_cancel_before_start(self):
        gate = asyncio.Event()

        async def handler(context, args):
            await gate.wait()
            return Output(value=1)

        self.register(handler)
        first = await self.manager.start(self.run_id, "fixture.run", {"count": 1})
        second = await self.manager.start(self.run_id, "fixture.run", {"count": 1})
        self.assertEqual(first.id, second.id)
        cancelled = await self.manager.cancel(first.id)
        self.assertEqual(cancelled.state, "cancelled")
        self.assertFalse(self.manager.workers)

    async def test_failure_can_be_retried_as_a_new_attempt(self):
        calls = 0

        async def handler(context, args):
            nonlocal calls
            calls += 1
            if calls == 1:
                raise AIServiceError("Transient failure", 502)
            return Output(value=9)

        self.register(handler)
        first = await self.manager.start(self.run_id, "fixture.run", {"count": 1})
        failed = await self.settle(first.id)
        self.assertEqual(failed.state, "failed")
        retry = await self.manager.retry(first.id)
        result = await self.settle(retry.id)
        self.assertEqual(result.state, "ready")
        self.assertEqual(result.attempt, 2)
        self.assertEqual(result.retry_of, first.id)
        with self.assertRaises(AIServiceError):
            await self.manager.retry(result.id)

    async def test_restart_reports_interruption_without_automatic_execution(self):
        now = datetime.now(timezone.utc)
        record = JobRecord(
            id=uuid4(),
            run_id=self.run_id,
            task_id="fixture.run",
            label="Fixture task",
            arguments={"count": 1},
            state="running",
            created_at=now,
            updated_at=now,
        )
        self.manager._save(record)
        self.assertEqual(self.manager.get(record.id).state, "interrupted")
        self.assertFalse(self.manager.workers)

    async def test_different_tasks_on_same_campaign_do_not_overlap(self):
        active = 0
        maximum = 0

        async def handler(context, args):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            await asyncio.sleep(0.01)
            active -= 1
            return Output(value=args.count)

        self.register(handler)
        a = await self.manager.start(self.run_id, "fixture.run", {"count": 1})
        b = await self.manager.start(self.run_id, "fixture.run", {"count": 2})
        await self.settle(a.id)
        await self.settle(b.id)
        self.assertEqual(maximum, 1)

    def test_registry_descriptors_and_path_contract(self):
        async def handler(context, args):
            return Output(value=1)

        self.register(handler)
        spec = self.registry.descriptors()[0]
        self.assertIn("count", spec["arguments_schema"]["properties"])
        self.assertIn("value", spec["result_schema"]["properties"])
        with self.assertRaises(ValueError):
            self.registry.register(
                TaskSpec("unsafe", "Unsafe", Input, Output, handler, ("../secret",))
            )
        with self.assertRaises(ValueError):
            self.registry.register(TaskSpec("fixture.run", "Duplicate", Input, Output, handler))

    async def test_api_can_run_registered_fixture_without_ai_or_publication(self):
        from app.main import app

        async def handler(context, args):
            return Output(value=args.count)

        self.register(handler)
        with patch.object(job_service, "manager", self.manager), TestClient(app) as client:
            response = client.post(
                f"/api/jobs/runs/{self.run_id}",
                json={"task_id": "fixture.run", "arguments": {"count": 3}},
            )
            self.assertEqual(response.status_code, 202)
            job_id = response.json()["id"]
            # Ready may be committed during the response; get uses the persisted record.
            current = client.get(f"/api/jobs/{job_id}")
            self.assertEqual(current.status_code, 200)
            self.assertIn(current.json()["state"], {"queued", "running", "ready"})
            self.assertEqual(client.get(f"/api/jobs/runs/{self.run_id}").status_code, 200)
            invalid = client.post(
                f"/api/jobs/runs/{self.run_id}",
                json={"task_id": "fixture.run", "arguments": {"count": 99}},
            )
            self.assertEqual(invalid.status_code, 422)


class EvaluationTests(unittest.IsolatedAsyncioTestCase):
    def test_metrics_distinguish_missed_flags_and_false_alarms(self):
        metrics = score([True, True, False, False], [True, False, True, False])
        self.assertEqual(metrics["accuracy"], 0.5)
        self.assertEqual(metrics["flag_precision"], 0.5)
        self.assertEqual(metrics["flag_recall"], 0.5)
        self.assertEqual(metrics["false_negatives"], 1)

    def test_sample_dataset_is_valid_without_api_calls(self):
        cases = load_cases(Path(__file__).resolve().parents[1] / "evals/factuality.json")
        self.assertEqual(len(cases), 5)
        self.assertTrue(any("hu" in c.id for c in cases))

    async def test_runner_records_evidence_checks_and_metrics(self):
        cases = load_cases(Path(__file__).resolve().parents[1] / "evals/factuality.json")[:1]
        case = cases[0]
        reply = CheckerResult(
            items=[
                CheckedUnit(
                    id=case.id,
                    verdict="supported",
                    explanation="Supported.",
                    suggested_revision="",
                    evidence=[
                        EvidenceReference(
                            passage_id="P1", excerpt=case.source[: case.source.index(".") + 1]
                        )
                    ],
                )
            ]
        )
        # Decimal point is not a sentence boundary; use the full first sentence instead.
        reply.items[0].evidence[
            0
        ].excerpt = "In a computer simulation of 339 samples, the system achieved 88.8% accuracy."
        with patch(
            "app.scripts.evaluate_factuality.structured_response",
            new_callable=AsyncMock,
            return_value=reply,
        ):
            report = await evaluate(cases)
        self.assertEqual(report["metrics"]["false_negatives"], 0)
        self.assertFalse(report["results"][0]["predicted_flag"])
        self.assertIn("limitation", report)


if __name__ == "__main__":
    unittest.main()
