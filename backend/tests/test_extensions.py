"""Small contract checks for feature creation, shared inputs and persistent results."""

import importlib.util
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch, AsyncMock
from uuid import uuid4
from pydantic import BaseModel
from app.models.content import SourceAnalysis
from app.services.extension_support import CampaignInputs, ExtensionStore
from app.services.task_registry import TaskRegistry
from app.services.job_service import JobManager
from app.services import campaign_service

PROJECT = Path(__file__).resolve().parents[2]
STORAGE = PROJECT / "backend/storage"
spec = importlib.util.spec_from_file_location(
    "extension_scaffolder", PROJECT / "scripts/new-extension.py"
)
scaffolder = importlib.util.module_from_spec(spec)
spec.loader.exec_module(scaffolder)


class Output(BaseModel):
    message: str


class ExtensionTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix=".extension-check-", dir=STORAGE)
        self.root = Path(self.temp.name)

    def tearDown(self):
        assert self.root.resolve().is_relative_to(STORAGE.resolve())
        self.temp.cleanup()

    def test_campaign_inputs_preserve_original_page_and_web_url(self):
        source = {
            "file_type": "pdf",
            "source_url": "https://example.org/original",
            "pages": [{"page": 3, "text": "Original finding and its limitation."}],
        }
        (self.root / "extracted_text.json").write_text(json.dumps(source), encoding="utf-8")
        campaign = CampaignInputs.load(self.root)
        self.assertEqual(campaign.source_passages()[0]["page"], 3)
        self.assertEqual(campaign.source_passages()[0]["url"], source["source_url"])
        before = campaign.fingerprint("source")
        source["pages"][0]["text"] = "Revised original finding."
        (self.root / "extracted_text.json").write_text(json.dumps(source), encoding="utf-8")
        self.assertNotEqual(before, CampaignInputs.load(self.root).fingerprint("source"))

    def test_store_reuses_current_results_and_invalidates_changed_inputs(self):
        store = ExtensionStore(self.root, "fixture")
        inputs = {"source": "original", "language": "en"}
        store.write("result", Output(message="Saved output"), inputs=inputs)
        self.assertEqual(store.read("result", Output, inputs=inputs).message, "Saved output")
        self.assertIsNone(store.read("result", Output, inputs={**inputs, "language": "hu"}))
        self.assertIsNone(store.read("result", Output, inputs=inputs, version=2))
        self.assertIsNone(ExtensionStore(self.root, "other").read("result", Output, inputs=inputs))
        with self.assertRaises(ValueError):
            store.write("../result", Output(message="No"), inputs=inputs)

    def prepare_registries(self):
        for name in ("backend/app/extensions/__init__.py", "frontend/src/extensions/index.ts"):
            path = self.root / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text((PROJECT / name).read_text(encoding="utf-8"), encoding="utf-8")

    async def test_generated_feature_runs_as_a_durable_job_and_reuses_saved_output(self):
        self.prepare_registries()
        paths = scaffolder.create_extension(self.root, "future-demo", "Future demo", activate=True)
        backend = next(path for path in paths if path.suffix == ".py")
        text = backend.read_text(encoding="utf-8")
        compile(text, str(backend), "exec")
        text = text.replace(
            'raise AIServiceError("This feature starter needs its implementation before use.", 501)',
            "return Result(message=campaign.analysis.summary)",
        )
        tasks = TaskRegistry()
        namespace = {"__file__": str(backend)}
        with patch("app.services.task_registry.registry", tasks):
            exec(compile(text, str(backend), "exec"), namespace)
        root = self.root / "backend/storage"
        run = uuid4()
        folder = root / str(run)
        folder.mkdir(parents=True)
        analysis = SourceAnalysis(
            document_type="research",
            source_language="en",
            title="Fixture",
            organization="",
            people=[],
            summary="Fixture summary",
            key_facts=[],
            important_numbers=[],
            important_dates=[],
            conditions_and_limitations=[],
            communication_focus="",
        )
        (folder / "analysis.json").write_text(analysis.model_dump_json(), encoding="utf-8")
        manager = JobManager(tasks, root / "jobs")
        with patch.object(campaign_service, "STORAGE", root):
            job = await manager.start(
                run, "extension.future_demo", {"instruction": "Explain source", "language": "en"}
            )
            await manager.workers[str(job.id)]
            ready = manager.get(job.id)
            self.assertEqual(ready.state, "ready")
            self.assertEqual(ready.result["message"], "Fixture summary")
            restored = JobManager(tasks, root / "jobs")
            self.assertEqual(restored.get(job.id).result, ready.result)
            namespace["implement"] = AsyncMock(
                side_effect=AssertionError("Cached output must not run implementation again")
            )
            cached = await manager.start(
                run, "extension.future_demo", {"instruction": "Explain source", "language": "en"}
            )
            await manager.workers[str(cached.id)]
            self.assertEqual(manager.get(cached.id).state, "ready")
            namespace["implement"].assert_not_awaited()
        frontend = (self.root / "frontend/src/extensions/index.ts").read_text(encoding="utf-8")
        self.assertIn("feature as featureFutureDemo", frontend)
        self.assertIn("featureFutureDemo,", frontend)

    def test_generator_preserves_existing_files_and_stays_inactive_by_default(self):
        self.prepare_registries()
        before = (self.root / "frontend/src/extensions/index.ts").read_text(encoding="utf-8")
        paths = scaffolder.create_extension(self.root, "inactive-demo", "Inactive demo")
        self.assertEqual(
            (self.root / "frontend/src/extensions/index.ts").read_text(encoding="utf-8"), before
        )
        original = paths[0].read_text(encoding="utf-8")
        with self.assertRaises(FileExistsError):
            scaffolder.create_extension(self.root, "inactive-demo", "Other label")
        self.assertEqual(paths[0].read_text(encoding="utf-8"), original)
        with self.assertRaises(ValueError):
            scaffolder.create_extension(self.root, "../escape", "No")


if __name__ == "__main__":
    unittest.main()
