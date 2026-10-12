"""Independent semantic checks plus deterministic evidence and version checks."""

from __future__ import annotations
import asyncio
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
import json
import os
from pathlib import Path
import re
from uuid import uuid4

from pydantic import ValidationError
from app.models.platform import PlatformResult
from app.models.content import MasterContent
from app.models.verification import (
    Approval,
    ApprovalRequest,
    CheckerResult,
    ClaimReview,
    Evidence,
    NumberCheck,
    ReviewContext,
    ReviewStatus,
    VerificationReport,
)
from app.services.openai_service import AIServiceError, structured_response
from app.models.campaign import CampaignBrief
from app.services.campaign_service import load_brief
from app.services.video_cache import cached_video_file, cached_video_plan

PROMPT = Path(__file__).resolve().parents[1] / "prompts" / "check_claims.txt"
LOCKS: dict[str, asyncio.Lock] = {}
BLOCKING = {"unsupported", "exaggerated", "needs_review"}
NUMBER = re.compile(r"(?<![\w])[-+]?\d+(?:[.,]\d+)*(?:[ \u00a0\u202f]\d{3})*(?![\w])")
SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-ZÁÉÍÓÖŐÚÜŰ0-9])|\n+")


def run_lock(run_id: str) -> asyncio.Lock:
    return LOCKS.setdefault(run_id, asyncio.Lock())


def _read(folder: Path, name: str, default=None):
    path = folder / name
    if not path.is_file():
        return default
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AIServiceError(f"Saved {name} could not be read.", 422) from exc


def _atomic(folder: Path, name: str, model) -> None:
    path = folder / name
    temporary = folder / f".{name}.{uuid4().hex}.tmp"
    try:
        temporary.write_text(model.model_dump_json(indent=2), encoding="utf-8")
        temporary.replace(path)
    finally:
        temporary.unlink(missing_ok=True)


def checker_configuration() -> tuple[bool, str | None]:
    from app.services.model_gateway import checker_readiness

    return checker_readiness()


def _digest(path: Path) -> str:
    if not path.is_file():
        raise AIServiceError("Selected media is missing. Review the package again.", 409)
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(chunk)
    return result.hexdigest()


def package(folder: Path, context: ReviewContext) -> dict:
    if len(set(context.platforms)) != len(context.platforms) or len(set(context.media_ids)) != len(
        context.media_ids
    ):
        raise AIServiceError("Review selections must be unique.", 422)
    if context.primary_media_id and context.primary_media_id not in context.media_ids:
        raise AIServiceError("Primary media must be included in the review.", 422)
    if context.media_ids and not context.primary_media_id:
        raise AIServiceError("Choose primary media before review.", 422)
    platforms = PlatformResult.model_validate(_read(folder, "platforms.json", {}))
    if not set(context.platforms).issubset(platforms.platforms):
        raise AIServiceError("Generate the selected platforms before review.", 409)
    language = (_read(folder, "output_language.json", {}) or {}).get("language", "en")
    if platforms.language != language:
        raise AIServiceError("Generate content in the current output language before review.", 409)
    master = MasterContent.model_validate(_read(folder, "master_content.json", {}))
    assets = _read(folder, "assets.json", {}) or {}
    available = {item["id"]: item for item in assets.get("assets", [])}
    uploads = {
        f"uploaded_video:{item['id']}": item
        for item in (_read(folder, "video/uploads.json", []) or [])
    }
    media = []
    plan = None
    for media_id in context.media_ids:
        if media_id == "generated_video":
            status = _read(folder, "video/status.json", {}) or {}
            plan = cached_video_plan(folder)
            if (
                not plan
                or (
                    status.get("stage") != "ready"
                    and not (folder / "video" / f"video_plan_{language}.json").is_file()
                )
                or plan.get("language", "en") != language
            ):
                raise AIServiceError(
                    "Finish generating the current language's video before review.", 409
                )
            path = cached_video_file(folder)
            if path is None:
                raise AIServiceError("Generated video is unavailable.", 409)
            record = {"id": media_id, "plan": plan}
        elif media_id in uploads:
            record = uploads[media_id]
            path = folder / "video" / "uploads" / record["filename"]
        elif media_id in available:
            record = available[media_id]
            prefix = f"/api/assets/{folder.name}/files/"
            route = record["path"].split("?", 1)[0]
            if not route.startswith(prefix):
                raise AIServiceError("Selected media path is invalid.", 422)
            path = folder / "assets" / route[len(prefix) :]
        else:
            raise AIServiceError("Selected media is unavailable.", 409)
        if not path.resolve().is_relative_to(folder.resolve()):
            raise AIServiceError("Selected media path is invalid.", 422)
        media.append({"record": record, "digest": _digest(path)})
    snapshot = {
        "context": context.model_dump(),
        "language": language,
        "master": master.model_dump(),
        "posts": [
            item.model_dump() for item in platforms.items if item.platform in context.platforms
        ],
        "source": _read(folder, "extracted_text.json"),
        "source_file_digest": {
            name: _digest(folder / name)
            for name in ("source.pdf", "source.docx")
            if (folder / name).is_file()
        },
        "analysis": _read(folder, "analysis.json", {}),
        "quick": _read(folder, "quick_announcement.json"),
        "video_plan": plan,
        "media": media,
        "writer_model": os.getenv("OPENAI_MODEL", "").strip(),
        "checker_model": os.getenv("OPENAI_CHECKER_MODEL", "").strip(),
        "checker_effort": os.getenv("OPENAI_CHECKER_REASONING_EFFORT", "low").strip(),
        "checker_prompt": PROMPT.read_text(encoding="utf-8"),
        "verification_rules": 1,
    }

    if os.getenv("AI_PROVIDER", "openai").strip() not in ("", "openai"):
        from app.services.model_gateway import describe

        info = describe()
        snapshot["ai_provider"] = info["name"]
        snapshot["writer_model"] = info["writer_model"]
        snapshot["checker_model"] = info["checker_model"]
    if load_brief(folder) != CampaignBrief():
        snapshot["campaign_brief"] = load_brief(folder).model_dump()
    return snapshot


def fingerprint(data: dict) -> str:
    return hashlib.sha256(
        json.dumps(data, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def units(data: dict) -> list[dict]:
    result = []

    def add(channel, field, value):
        for text in SENTENCE.split(value):
            if text.strip():
                result.append(
                    {
                        "id": f"C{len(result) + 1}",
                        "channel": channel,
                        "field": field,
                        "text": text.strip(),
                    }
                )

    for field in ("headline", "lead", "body", "short_summary", "press_release"):
        add("master", field, data["master"][field])
    for value in data["master"]["key_messages"]:
        add("master", "key_messages", value)
    for post in data["posts"]:
        add(post["platform"], "title", post["title"])
        add(post["platform"], "body", post["body"])
    if data["video_plan"]:
        add("video", "narration", data["video_plan"].get("narration", ""))
        for scene in data["video_plan"].get("scenes", []):
            add("video", "overlay", scene.get("overlay", ""))
            add("video", "detail", scene.get("detail", ""))
    if not result or len(result) > 300:
        raise AIServiceError(
            "Review supports 1–300 text units. Shorten the package before checking.", 422
        )
    return result


def passages(data: dict) -> list[dict]:
    result = []
    source = data.get("source")
    if source:
        pages = (
            source["pages"]
            if source.get("file_type") == "pdf"
            else [{"page": None, "text": source["text"]}]
        )
        for page in pages:
            # Overlap prevents passage boundaries from losing contextual qualifiers.
            for start in range(0, len(page["text"]), 1800):
                text = page["text"][start : start + 2400]
                if text.strip():
                    result.append(
                        {
                            "id": f"P{len(result) + 1}",
                            "page": page["page"],
                            "source_type": "web" if source.get("source_url") else "document",
                            "text": text,
                            "url": source.get("source_url"),
                        }
                    )
    else:
        for fact in data.get("analysis", {}).get("key_facts", []):
            value = fact["source_excerpt"]
            url = re.search(r"https://\S+", value)
            result.append(
                {
                    "id": fact["id"],
                    "page": None,
                    "source_type": "web" if fact.get("category") == "web_context" else "user",
                    "text": value,
                    "url": url.group(0) if url else None,
                }
            )
    if not result:
        raise AIServiceError("Original source evidence is missing.", 422)
    return result


def confirmed_excerpt(excerpt: str, source: str) -> str | None:
    # Preserve numeric punctuation/signs and percent symbols; only tolerate whitespace/case.
    excerpt = excerpt.strip()
    if not 6 <= len(excerpt) <= 300:
        return None
    pattern = r"\s+".join(re.escape(word) for word in excerpt.split())
    match = re.search(pattern, source, re.IGNORECASE)
    return match.group(0) if match else None


def number_tokens(text: str) -> list[tuple[str, str]]:
    tokens = []
    for match in NUMBER.finditer(text):
        raw = match.group()
        value = re.sub(r"[ \u00a0\u202f]", "", raw)
        # Treat a single separator as decimal; ambiguous grouped forms require review.
        if value.count(".") + value.count(",") == 1:
            value = value.replace(",", ".")
        elif "," in value and "." in value:
            decimal = max(value.rfind(","), value.rfind("."))
            value = value[:decimal].replace(",", "").replace(".", "") + "." + value[decimal + 1 :]
        try:
            value = str(Decimal(value).normalize())
        except InvalidOperation:
            value = raw
        suffix = text[match.end() : match.end() + 20].lstrip().casefold()
        kind = "%" if re.match(r"(%|percent\b|per cent\b|százalék)", suffix) else ""
        tokens.append((raw + kind, value + kind))
    return tokens


def number_checks(text: str, evidence: list[Evidence], original: list[dict]) -> list[NumberCheck]:
    source_values = {
        value
        for passage in original
        if passage["source_type"] != "user"
        for _, value in number_tokens(passage["text"])
    }
    evidence_values = {
        value
        for item in evidence
        if item.source_type != "user"
        for _, value in number_tokens(item.excerpt)
    }
    return [
        NumberCheck(
            token=raw,
            status="matched"
            if value in evidence_values
            else "missing_evidence"
            if value in source_values
            else "missing_source",
        )
        for raw, value in number_tokens(text)
    ]


def _candidates(batch: list[dict], original: list[dict], data: dict) -> list[dict]:
    terms = set(re.findall(r"\w{3,}", " ".join(unit["text"] for unit in batch).casefold()))
    cited_pages = {fact.get("page") for fact in data["analysis"].get("key_facts", [])}
    ranked = sorted(
        original,
        key=lambda p: (
            len(terms & set(re.findall(r"\w{3,}", p["text"].casefold())))
            + (2 if p["page"] in cited_pages else 0)
        ),
        reverse=True,
    )
    # A missing relevant passage leads to needs_review, never fabricated support.
    return ranked[:18]


async def verify(folder: Path, context: ReviewContext, *, force: bool = False) -> ReviewStatus:
    data = package(folder, context)
    version = fingerprint(data)
    current = review_status(folder, context)
    if current.report is not None and not force:
        return current
    if force:
        # A failed requested recheck must not leave an old approval usable.
        (folder / "approval.json").unlink(missing_ok=True)
        (folder / "verification.json").unlink(missing_ok=True)
    ready, message = checker_configuration()
    if not ready:
        raise AIServiceError(message or "Checker is unavailable.", 503)
    original = passages(data)
    pending = units(data)
    claims = []
    for start in range(0, len(pending), 12):
        batch = pending[start : start + 12]
        candidates = _candidates(batch, original, data)
        result = await structured_response(
            data["checker_prompt"],
            json.dumps(
                {
                    "units": batch,
                    "source_passages": candidates,
                    "limitations": data["analysis"].get("conditions_and_limitations", []),
                },
                ensure_ascii=False,
            ),
            CheckerResult,
            checker=True,
        )
        if len(result.items) != len(batch) or {item.id for item in result.items} != {
            unit["id"] for unit in batch
        }:
            raise AIServiceError(
                "Checker omitted or duplicated claims. No verification was saved.", 502
            )
        by_id = {item.id: item for item in result.items}
        by_passage = {passage["id"]: passage for passage in candidates}
        for unit in batch:
            item = by_id[unit["id"]]
            evidence = []
            invalid = False
            for reference in item.evidence:
                passage = by_passage.get(reference.passage_id)
                quote = confirmed_excerpt(reference.excerpt, passage["text"]) if passage else None
                if not quote:
                    invalid = True
                    continue
                evidence.append(
                    Evidence(
                        passage_id=passage["id"],
                        source_type=passage["source_type"],
                        page=passage["page"],
                        excerpt=quote,
                        url=passage["url"],
                    )
                )
            verdict = item.verdict
            explanation = item.explanation
            if invalid or (
                verdict == "supported" and not any(e.source_type != "user" for e in evidence)
            ):
                verdict = "needs_review"
                explanation += " Code could not confirm independent verbatim evidence."
            checks = number_checks(unit["text"], evidence, original)
            if any(check.status == "missing_source" for check in checks):
                verdict = "unsupported"
                explanation += " A numeric value is absent from the original evidence."
            elif (
                any(check.status == "missing_evidence" for check in checks)
                and verdict not in BLOCKING
            ):
                verdict = "needs_review"
                explanation += " A number occurs in the source but not in the linked evidence."
            claims.append(
                ClaimReview(
                    **unit,
                    verdict=verdict,
                    explanation=explanation.strip(),
                    suggested_revision=item.suggested_revision,
                    evidence=evidence,
                    number_checks=checks,
                )
            )
    # Never attach a report to content changed while the checker was working.
    if fingerprint(package(folder, context)) != version:
        raise AIServiceError("Package changed during verification. Run the checker again.", 409)
    report = VerificationReport(
        version=version,
        checked_at=datetime.now(timezone.utc).isoformat(),
        writer_model=data["writer_model"],
        checker_model=data["checker_model"],
        context=context,
        claims=claims,
    )
    _atomic(folder, "verification.json", report)
    # A fresh check requires a fresh human decision, including forced rechecks.
    (folder / "approval.json").unlink(missing_ok=True)
    return review_status(folder, context)


def review_status(folder: Path, context: ReviewContext) -> ReviewStatus:
    version = fingerprint(package(folder, context))
    ready, message = checker_configuration()
    report = None
    approval = None
    try:
        raw = _read(folder, "verification.json")
        candidate = VerificationReport.model_validate(raw) if raw else None
        if candidate and candidate.version == version and candidate.claims and ready:
            report = candidate
        raw = _read(folder, "approval.json")
        candidate_approval = Approval.model_validate(raw) if raw else None
        if report and candidate_approval and candidate_approval.version == version:
            approval = candidate_approval
    except ValidationError:
        pass  # Malformed or legacy review records never unlock publication.
    blocking = sum(claim.verdict in BLOCKING for claim in report.claims) if report else 0
    if blocking:
        approval = None
    state = (
        "unchecked"
        if report is None
        else "needs_review"
        if blocking
        else "approved"
        if approval
        else "verified"
    )
    return ReviewStatus(
        version=version,
        report=report,
        approval=approval,
        state=state,
        blocking_count=blocking,
        checker_ready=ready,
        configuration_message=message,
    )


def approve(folder: Path, context: ReviewContext, request: ApprovalRequest) -> ReviewStatus:
    current = review_status(folder, context)
    if request.version != current.version:
        raise AIServiceError("Content changed. Verify and review the latest version.", 409)
    if current.report is None or current.blocking_count:
        raise AIServiceError(
            "Every flagged claim must be corrected and rechecked before approval.", 409
        )
    reviewer = request.reviewer.strip()
    if len(reviewer) < 2 or not request.reviewed_claims or not request.reviewed_media:
        raise AIServiceError("Enter your name and confirm review of claims and media.", 422)
    _atomic(
        folder,
        "approval.json",
        Approval(
            version=current.version,
            reviewer=reviewer,
            approved_at=datetime.now(timezone.utc).isoformat(),
            reviewed_claims=True,
            reviewed_media=True,
        ),
    )
    return review_status(folder, context)


def require_approval(
    folder: Path,
    platform: str,
    *,
    primary_media_id: str | None = None,
    media_ids: list[str] | None = None,
) -> None:
    raw = _read(folder, "verification.json")
    if not raw:
        raise AIServiceError(
            "Verify this package and obtain human approval before publishing.", 409
        )
    try:
        report = VerificationReport.model_validate(raw)
        current = review_status(folder, report.context)
    except ValidationError as exc:
        raise AIServiceError("Review records are invalid. Verify and approve again.", 409) from exc
    if current.state != "approved" or not current.approval:
        raise AIServiceError(
            "Publication requires verification and human approval of the current version.", 409
        )
    if platform not in report.context.platforms:
        raise AIServiceError("This channel was not included in the approved package.", 409)
    if platform in {"youtube", "tiktok"}:
        if "generated_video" not in report.context.media_ids:
            raise AIServiceError(
                "Review and approve the generated video before publishing it.", 409
            )
    elif primary_media_id != report.context.primary_media_id:
        raise AIServiceError("Primary media changed. Review and approve it again.", 409)
    if media_ids is not None and media_ids != report.context.media_ids:
        raise AIServiceError("Selected media changed. Review and approve it again.", 409)
