"""Behavioral validation tests; no paid AI requests or publication calls."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import AsyncMock, patch
from uuid import uuid4
import pymupdf
from fastapi.testclient import TestClient
from app.models.verification import (
    ApprovalRequest,
    CheckedUnit,
    CheckerResult,
    EvidenceReference,
    ReviewContext,
)
from app.services import verification_service as service
from app.services.openai_service import AIServiceError, config

QUOTE = "In simulation, the system achieved 88.8% accuracy on 339 samples."


class VerificationTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.test_root = Path(__file__).resolve().parents[1] / "storage"
        self.temp = tempfile.TemporaryDirectory(prefix=".verification-test-", dir=self.test_root)
        self.folder = Path(self.temp.name) / str(uuid4())
        self.folder.mkdir()
        self.env = patch.dict(
            os.environ,
            {
                "OPENAI_MODEL": "writer-test",
                "OPENAI_CHECKER_MODEL": "checker-test",
                "OPENAI_API_KEY": "test-only",
                "OPENAI_REASONING_EFFORT": "low",
            },
        )
        self.env.start()
        self.context = ReviewContext(platforms=["website"])
        self.write(
            "extracted_text.json",
            {
                "file_type": "pdf",
                "pages": [
                    {"page": 1, "text": QUOTE},
                    {"page": 2, "text": "An unrelated event happened in 2026."},
                ],
            },
        )
        self.write(
            "analysis.json",
            {
                "key_facts": [{"id": "F1", "page": 1}],
                "conditions_and_limitations": ["Simulation only."],
            },
        )
        self.write(
            "master_content.json",
            {
                "headline": "Simulation results",
                "lead": QUOTE,
                "body": QUOTE,
                "short_summary": QUOTE,
                "press_release": QUOTE,
                "key_messages": [QUOTE],
                "source_fact_ids": ["F1"],
            },
        )
        self.write(
            "platforms.json",
            {
                "platforms": ["website"],
                "content_types": ["text"],
                "language": "en",
                "items": [
                    {
                        "platform": "website",
                        "title": "Simulation results",
                        "body": QUOTE,
                        "source_fact_ids": ["F1"],
                    }
                ],
            },
        )

        async def checker(prompt, payload, schema, **kwargs):
            self.assertTrue(kwargs["checker"])
            data = json.loads(payload)
            source = next(p for p in data["source_passages"] if p["page"] == 1)
            return CheckerResult(
                items=[
                    CheckedUnit(
                        id=unit["id"],
                        verdict="supported",
                        explanation="Supported by the simulation result.",
                        suggested_revision="",
                        evidence=[EvidenceReference(passage_id=source["id"], excerpt=QUOTE)],
                    )
                    for unit in data["units"]
                ]
            )

        self.checker = patch.object(service, "structured_response", side_effect=checker)
        self.mock = self.checker.start()

    def tearDown(self):
        self.checker.stop()
        self.env.stop()
        assert Path(self.temp.name).resolve().is_relative_to(self.test_root.resolve())
        self.temp.cleanup()

    def write(self, name, value):
        path = self.folder / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value), encoding="utf-8")

    def edit_body(self, body):
        data = json.loads((self.folder / "platforms.json").read_text())
        data["items"][0]["body"] = body
        self.write("platforms.json", data)

    async def checked_and_approved(self):
        checked = await service.verify(self.folder, self.context)
        return service.approve(
            self.folder,
            self.context,
            ApprovalRequest(
                version=checked.version,
                reviewer="Demo reviewer",
                reviewed_claims=True,
                reviewed_media=True,
            ),
        )

    async def test_checks_all_outputs_with_distinct_checker_and_exact_pages(self):
        result = await service.verify(self.folder, self.context)
        self.assertEqual(result.state, "verified")
        self.assertEqual(result.blocking_count, 0)
        self.assertEqual(
            len(result.report.claims),
            len(service.units(service.package(self.folder, self.context))),
        )
        self.assertTrue(all(e.page == 1 for claim in result.report.claims for e in claim.evidence))
        self.assertTrue(
            all(
                n.status == "matched" for claim in result.report.claims for n in claim.number_checks
            )
        )
        self.assertNotEqual(result.report.writer_model, result.report.checker_model)

    async def test_invented_number_cannot_pass_valid_fact_ids_or_model_verdict(self):
        self.edit_body("The system achieved 99.9% accuracy.")
        result = await service.verify(self.folder, self.context)
        claim = next(
            c for c in result.report.claims if c.channel == "website" and c.field == "body"
        )
        self.assertEqual(claim.verdict, "unsupported")
        self.assertEqual(claim.number_checks[0].status, "missing_source")
        with self.assertRaises(AIServiceError):
            service.approve(
                self.folder,
                self.context,
                ApprovalRequest(
                    version=result.version,
                    reviewer="Reviewer",
                    reviewed_claims=True,
                    reviewed_media=True,
                ),
            )

    async def test_number_elsewhere_in_paper_is_not_linked_support(self):
        self.edit_body("The simulation took place in 2026.")
        result = await service.verify(self.folder, self.context)
        claim = next(
            c for c in result.report.claims if c.channel == "website" and c.field == "body"
        )
        self.assertEqual(claim.verdict, "needs_review")
        self.assertEqual(claim.number_checks[0].status, "missing_evidence")

    async def test_fabricated_quote_is_rejected(self):
        async def fake(prompt, payload, schema, **kwargs):
            return CheckerResult(
                items=[
                    CheckedUnit(
                        id=u["id"],
                        verdict="supported",
                        explanation="Claimed support.",
                        suggested_revision="",
                        evidence=[
                            EvidenceReference(
                                passage_id="P1",
                                excerpt="An invented passage that is not in the paper.",
                            )
                        ],
                    )
                    for u in json.loads(payload)["units"]
                ]
            )

        self.mock.side_effect = fake
        result = await service.verify(self.folder, self.context)
        self.assertTrue(all(c.verdict == "needs_review" for c in result.report.claims))

    async def test_missing_claim_output_fails_closed(self):
        self.mock.side_effect = None
        self.mock.return_value = CheckerResult(items=[])
        with self.assertRaises(AIServiceError):
            await service.verify(self.folder, self.context)
        self.assertFalse((self.folder / "verification.json").exists())

    async def test_same_or_missing_checker_model_does_not_fallback(self):
        for checker in ("", "writer-test"):
            with patch.dict(os.environ, {"OPENAI_CHECKER_MODEL": checker}):
                with self.assertRaises(AIServiceError):
                    await service.verify(self.folder, self.context)
                with self.assertRaises(AIServiceError):
                    config(checker=True)
        self.mock.assert_not_called()

    async def test_edit_invalidates_report_and_approval_and_publish_gate(self):
        approved = await self.checked_and_approved()
        self.assertEqual(approved.state, "approved")
        service.require_approval(self.folder, "website", media_ids=[])
        self.edit_body("The system is deployed worldwide.")
        self.assertEqual(service.review_status(self.folder, self.context).state, "unchecked")
        with self.assertRaises(AIServiceError):
            service.require_approval(self.folder, "website", media_ids=[])

    async def test_approval_requires_human_acknowledgements_and_current_version(self):
        checked = await service.verify(self.folder, self.context)
        for version, reviewed in (("old-version", True), (checked.version, False)):
            with self.assertRaises(AIServiceError):
                service.approve(
                    self.folder,
                    self.context,
                    ApprovalRequest(
                        version=version,
                        reviewer="Reviewer",
                        reviewed_claims=reviewed,
                        reviewed_media=True,
                    ),
                )

    async def test_force_recheck_revokes_approval(self):
        await self.checked_and_approved()
        checked = await service.verify(self.folder, self.context, force=True)
        self.assertEqual(checked.state, "verified")
        self.assertIsNone(checked.approval)

    async def test_failed_requested_recheck_revokes_old_report_and_approval(self):
        await self.checked_and_approved()
        self.mock.side_effect = AIServiceError("Provider unavailable.", 502)
        with self.assertRaises(AIServiceError):
            await service.verify(self.folder, self.context, force=True)
        self.assertEqual(service.review_status(self.folder, self.context).state, "unchecked")
        with self.assertRaises(AIServiceError):
            service.require_approval(self.folder, "website", media_ids=[])

    async def test_media_byte_change_invalidates_approval(self):
        path = self.folder / "assets" / "test.png"
        path.parent.mkdir()
        path.write_bytes(b"original")
        self.write(
            "assets.json",
            {"assets": [{"id": "image", "path": f"/api/assets/{self.folder.name}/files/test.png"}]},
        )
        self.context = ReviewContext(
            platforms=["website"], primary_media_id="image", media_ids=["image"]
        )
        await self.checked_and_approved()
        path.write_bytes(b"replaced")
        self.assertEqual(service.review_status(self.folder, self.context).state, "unchecked")

    async def test_changed_or_unapproved_publication_selection_is_rejected(self):
        await self.checked_and_approved()
        for platform, primary, media in (
            ("facebook", None, []),
            ("website", "another-image", []),
            ("website", None, ["other"]),
        ):
            with self.assertRaises(AIServiceError):
                service.require_approval(
                    self.folder, platform, primary_media_id=primary, media_ids=media
                )

    async def test_checker_exaggeration_verdict_remains_blocking(self):
        async def exaggerated(prompt, payload, schema, **kwargs):
            return CheckerResult(
                items=[
                    CheckedUnit(
                        id=u["id"],
                        verdict="exaggerated",
                        explanation="Simulation is not deployment.",
                        suggested_revision=QUOTE,
                        evidence=[EvidenceReference(passage_id="P1", excerpt=QUOTE)],
                    )
                    for u in json.loads(payload)["units"]
                ]
            )

        self.mock.side_effect = exaggerated
        result = await service.verify(self.folder, self.context)
        self.assertEqual(result.state, "needs_review")

    async def test_changes_during_check_are_not_saved(self):
        original_checker = self.mock.side_effect

        async def changing(*args, **kwargs):
            result = await original_checker(*args, **kwargs)
            self.edit_body("Changed while checking.")
            return result

        self.mock.side_effect = changing
        with self.assertRaises(AIServiceError):
            await service.verify(self.folder, self.context)
        self.assertFalse((self.folder / "verification.json").exists())

    async def test_source_file_change_invalidates_report(self):
        path = self.folder / "source.pdf"
        with pymupdf.open() as document:
            document.new_page().insert_text((40, 60), QUOTE)
            document.save(path)
        await self.checked_and_approved()
        path.write_bytes(b"changed source file")
        self.assertEqual(service.review_status(self.folder, self.context).state, "unchecked")

    async def test_evidence_page_is_rendered_with_highlight(self):
        from app.main import app
        from app.api import verification

        path = self.folder / "source.pdf"
        with pymupdf.open() as document:
            document.new_page().insert_text((40, 60), QUOTE)
            document.save(path)
        checked = await service.verify(self.folder, self.context)
        with patch.object(verification, "STORAGE", self.folder.parent), TestClient(app) as client:
            result = client.get(
                f"/api/verification/{self.folder.name}/evidence/{checked.report.claims[0].id}/0"
            )
            self.assertEqual(result.status_code, 200)
            self.assertEqual(result.headers["content-type"], "image/png")
            self.assertEqual(result.headers["x-evidence-highlighted"], "true")
            self.assertTrue(result.content.startswith(b"\x89PNG"))
        with pymupdf.open(path) as original:
            self.assertIsNone(original[0].first_annot)

    async def test_user_announcement_is_not_independent_evidence(self):
        (self.folder / "extracted_text.json").unlink()
        self.write(
            "analysis.json",
            {
                "key_facts": [
                    {
                        "id": "F1",
                        "category": "web_verified_announcement",
                        "source_excerpt": QUOTE + " https://example.org/announcement",
                    }
                ],
                "conditions_and_limitations": [],
            },
        )

        async def user_only(prompt, payload, schema, **kwargs):
            return CheckerResult(
                items=[
                    CheckedUnit(
                        id=u["id"],
                        verdict="supported",
                        explanation="Claimed support.",
                        suggested_revision="",
                        evidence=[EvidenceReference(passage_id="F1", excerpt=QUOTE)],
                    )
                    for u in json.loads(payload)["units"]
                ]
            )

        self.mock.side_effect = user_only
        checked = await service.verify(self.folder, self.context)
        self.assertEqual(checked.state, "needs_review")
        self.assertGreater(checked.blocking_count, 0)

    def test_quote_matching_preserves_numeric_punctuation(self):
        self.assertEqual(
            service.confirmed_excerpt("88.8% accuracy", "Reported 88.8% accuracy."),
            "88.8% accuracy",
        )
        self.assertIsNone(service.confirmed_excerpt("888% accuracy", "Reported 88.8% accuracy."))
        self.assertEqual(
            service.confirmed_excerpt("Result: -2.5%", "Result: -2.5%"), "Result: -2.5%"
        )

    def test_decimal_comma_percent_and_number_boundaries(self):
        self.assertEqual(
            service.number_tokens("88,8 percent")[0][1], service.number_tokens("88.8%")[0][1]
        )
        values = {value for _, value in service.number_tokens("1000 samples")}
        self.assertNotIn(service.number_tokens("100 samples")[0][1], values)
        self.assertNotEqual(
            service.number_tokens("88.8%")[0][1], service.number_tokens("88.8")[0][1]
        )


class PublicationRouteTests(unittest.TestCase):
    def test_every_publish_route_blocks_before_provider_call(self):
        from app.main import app
        from app.api import meta, youtube, tiktok, university_site

        run_id = uuid4()
        failure = AIServiceError("Approval is required.", 409)
        with (
            TestClient(app) as client,
            patch.object(meta, "require_approval", side_effect=failure),
            patch.object(youtube, "require_approval", side_effect=failure),
            patch.object(tiktok, "require_approval", side_effect=failure),
            patch.object(university_site, "require_approval", side_effect=failure),
            patch.object(meta, "publish_facebook", new_callable=AsyncMock) as facebook,
            patch.object(meta, "publish_instagram", new_callable=AsyncMock) as instagram,
            patch.object(youtube, "publish_video") as yt,
            patch.object(tiktok, "publish_video", new_callable=AsyncMock) as tt,
            patch.object(university_site, "publish_article") as site,
        ):
            routes = [
                (f"/api/meta/facebook/publish/{run_id}", {"primary_media_id": None}),
                (f"/api/meta/instagram/publish/{run_id}", {"primary_media_id": None}),
                (f"/api/youtube/publish/{run_id}", {}),
                (f"/api/tiktok/publish/{run_id}", {}),
                (f"/api/university-site/publish/{run_id}", {"media_ids": []}),
            ]
            for route, body in routes:
                self.assertEqual(client.post(route, json=body).status_code, 409, route)
            for provider in (facebook, instagram, yt, tt, site):
                provider.assert_not_called()


if __name__ == "__main__":
    unittest.main()
