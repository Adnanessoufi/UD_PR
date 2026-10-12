"""One-request analysis and master generation for normal-sized documents."""

from pathlib import Path
from time import perf_counter

from app.models.content import CombinedResult
from app.services.analysis_service import analyze_source, load_source, verified_facts
from app.services.content_service import (
    generate_content,
    load_analysis,
    save_content,
    validate_content,
)
from app.services.platform_service import load_master
from app.services.openai_service import AIServiceError, structured_response
import json
from app.services.campaign_service import brief_instruction, preferences_match
from app.services.output_language import load_output_language

PROMPT_FILE = Path(__file__).resolve().parents[1] / "prompts" / "combined.txt"


async def process_source(run_dir: Path) -> CombinedResult:
    started = perf_counter()
    analysis = load_analysis(run_dir)
    if analysis is not None:
        if (run_dir / "master_content.json").is_file() and preferences_match(run_dir, "master"):
            content = load_master(run_dir)
            validate_content(analysis, content)
            return CombinedResult(
                analysis=analysis, content=content, output_language=load_output_language(run_dir)
            )
        language = load_output_language(run_dir)
        content = await generate_content(run_dir, analysis, language)
        return CombinedResult(analysis=analysis, content=content, output_language=language)
    chunks, sources = load_source(run_dir)

    if len(chunks) == 1:
        ai_started = perf_counter()
        result = await structured_response(
            PROMPT_FILE.read_text(encoding="utf-8") + brief_instruction(run_dir),
            chunks[0],
            CombinedResult,
        )
        print(
            f"[{run_dir.name}] OpenAI combined generation: {perf_counter() - ai_started:.1f}s",
            flush=True,
        )

        facts = verified_facts([result.analysis], sources, preserve_ids=True)
        if not facts:
            raise AIServiceError("No source-grounded facts could be extracted. Please retry.", 422)
        analysis = result.analysis.model_copy(update={"key_facts": facts})
        source_meta = json.loads((run_dir / "extracted_text.json").read_text(encoding="utf-8"))
        if source_meta.get("source_url"):
            analysis = analysis.model_copy(
                update={
                    "document_type": "news_article",
                    "source_links": [source_meta["source_url"]],
                }
            )
        validate_content(analysis, result.content)

        saving_started = perf_counter()
        (run_dir / "analysis.json").write_text(analysis.model_dump_json(indent=2), encoding="utf-8")
        save_content(run_dir, result.content)
        print(
            f"[{run_dir.name}] Saving results: {perf_counter() - saving_started:.1f}s", flush=True
        )
        output = CombinedResult(analysis=analysis, content=result.content)
    else:
        print(
            f"[{run_dir.name}] Large document: {len(chunks)} parallel analysis chunks", flush=True
        )
        ai_started = perf_counter()
        analysis = await analyze_source(run_dir)
        content = await generate_content(run_dir, analysis)
        print(
            f"[{run_dir.name}] OpenAI large-document processing: {perf_counter() - ai_started:.1f}s",
            flush=True,
        )
        output = CombinedResult(analysis=analysis, content=content)

    print(f"[{run_dir.name}] TOTAL processing: {perf_counter() - started:.1f}s", flush=True)
    return output
