"""Page-preserved document input and grounded analysis for oversized sources."""

import asyncio
import json
import re
import unicodedata
from pathlib import Path

from app.models.content import ConsolidatedOverview, SourceAnalysis, SourceFact
from app.services.openai_service import AIServiceError, structured_response

PROMPT_DIR = Path(__file__).resolve().parents[1] / "prompts"
CHUNK_SIZE = 75000


def _normalized(value: str) -> str:
    return " ".join(value.split()).casefold()


def _exact_excerpt(excerpt: str, source: str) -> str | None:
    """Find a quote despite PDF punctuation/spacing changes and return source bytes verbatim."""
    target = "".join(
        char for char in unicodedata.normalize("NFKC", excerpt).casefold() if char.isalnum()
    )
    if len(target) < 6:
        return None
    compact = []
    positions = []
    for index, original in enumerate(source):
        for char in unicodedata.normalize("NFKC", original).casefold():
            if char.isalnum():
                compact.append(char)
                positions.append(index)
    start = "".join(compact).find(target)
    if start < 0:
        return None
    match = source[positions[start] : positions[start + len(target) - 1] + 1].strip()
    return match if len(match) <= 300 else None


def _split_text(text: str) -> list[str]:
    parts = []
    while text:
        if len(text) <= CHUNK_SIZE:
            parts.append(text)
            break
        cut = text.rfind("\n", CHUNK_SIZE // 2, CHUNK_SIZE)
        if cut < 0:
            cut = text.rfind(" ", CHUNK_SIZE // 2, CHUNK_SIZE)
        if cut < 0:
            cut = CHUNK_SIZE
        parts.append(text[:cut])
        text = text[cut:].lstrip()
    return parts


def _chunks(document: dict) -> tuple[list[str], dict[int | None, str]]:
    if document.get("file_type") == "pdf":
        sources = {int(page["page"]): page["text"] for page in document["pages"]}
    else:
        sources = {None: document["text"]}

    segments = []
    for page, text in sources.items():
        label = (
            f"--- PAGE {page} ---" if page is not None else "--- SOURCE TEXT; PAGE UNAVAILABLE ---"
        )
        segments.extend(f"{label}\n{part}" for part in _split_text(text) if part.strip())

    chunks: list[str] = []
    current = ""
    for segment in segments:
        if current and len(current) + len(segment) + 2 > CHUNK_SIZE:
            chunks.append(current)
            current = ""
        current += ("\n\n" if current else "") + segment
    if current:
        chunks.append(current)
    return chunks, sources


def verified_facts(
    analyses: list[SourceAnalysis], sources: dict[int | None, str], preserve_ids: bool = False
) -> list[SourceFact]:
    facts = []
    seen = set()
    seen_ids = set()
    for analysis in analyses:
        for fact in analysis.key_facts:
            statement = _normalized(fact.statement)
            if not statement:
                continue
            excerpt = _exact_excerpt(fact.source_excerpt, sources.get(fact.page, ""))
            page = fact.page
            if excerpt is None and fact.page is not None:
                matches = [
                    (candidate_page, found)
                    for candidate_page, text in sources.items()
                    if (found := _exact_excerpt(fact.source_excerpt, text)) is not None
                ]
                if len(matches) == 1:
                    page, excerpt = matches[0]
            if excerpt is None:
                continue
            if statement in seen:
                continue
            if preserve_ids and (not re.fullmatch(r"F\d+", fact.id) or fact.id in seen_ids):
                continue
            seen.add(statement)
            seen_ids.add(fact.id)
            facts.append(
                fact.model_copy(
                    update={
                        "id": fact.id if preserve_ids else f"F{len(facts) + 1}",
                        "page": page,
                        "source_excerpt": excerpt,
                    }
                )
            )
    return facts


def load_source(run_dir: Path) -> tuple[list[str], dict[int | None, str]]:
    source_file = run_dir / "extracted_text.json"
    if not source_file.is_file():
        raise AIServiceError(
            "Extracted document text is missing. Please upload the document again.", 404
        )
    try:
        document = json.loads(source_file.read_text(encoding="utf-8"))
        chunks, sources = _chunks(document)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        raise AIServiceError(
            "Extracted document text could not be read. Please upload it again.", 422
        ) from exc
    if not chunks:
        raise AIServiceError("The document has no text to analyze.", 422)
    return chunks, sources


async def analyze_source(run_dir: Path) -> SourceAnalysis:
    chunks, sources = load_source(run_dir)
    analyze_prompt = (PROMPT_DIR / "analyze.txt").read_text(encoding="utf-8")
    partials = await asyncio.gather(
        *(structured_response(analyze_prompt, chunk, SourceAnalysis) for chunk in chunks)
    )
    facts = verified_facts(partials, sources)
    if not facts:
        raise AIServiceError(
            "No source-grounded facts could be extracted. Please try another document.", 422
        )

    if len(partials) == 1:
        analysis = partials[0].model_copy(update={"key_facts": facts})
    else:
        consolidation_input = {
            "partial_overviews": [
                {
                    "document_type": p.document_type,
                    "source_language": p.source_language,
                    "title": p.title,
                    "organization": p.organization,
                    "people": p.people,
                    "summary": p.summary,
                    "communication_focus": p.communication_focus,
                }
                for p in partials
            ],
            "verified_facts": [
                {
                    "id": f.id,
                    "statement": f.statement,
                    "category": f.category,
                    "page": f.page,
                    "importance": f.importance,
                }
                for f in facts
            ],
        }
        overview = await structured_response(
            (PROMPT_DIR / "consolidate.txt").read_text(encoding="utf-8"),
            json.dumps(consolidation_input, ensure_ascii=False),
            ConsolidatedOverview,
        )
        selected = set(overview.selected_fact_ids)
        chosen = [fact for fact in facts if fact.id in selected]
        if not chosen:
            raise AIServiceError("The AI returned an empty analysis. Please retry.")
        analysis = SourceAnalysis(
            document_type=overview.document_type,
            source_language=overview.source_language,
            title=overview.title,
            organization=overview.organization,
            people=overview.people,
            summary=overview.summary,
            key_facts=chosen,
            important_numbers=overview.important_numbers,
            important_dates=overview.important_dates,
            conditions_and_limitations=overview.conditions_and_limitations,
            communication_focus=overview.communication_focus,
        )

    source_meta = json.loads((run_dir / "extracted_text.json").read_text(encoding="utf-8"))
    if source_meta.get("source_url"):
        analysis = analysis.model_copy(
            update={"document_type": "news_article", "source_links": [source_meta["source_url"]]}
        )

    (run_dir / "analysis.json").write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
    return analysis
