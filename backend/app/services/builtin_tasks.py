"""Task handlers for the main content workflow."""

from app.models.content import CombinedResult, MasterContent, SourceAnalysis
from app.models.platform import PlatformRequest, PlatformResult
from app.models.verification import ReviewContext, ReviewStatus
from app.services.task_registry import EmptyArgs, TaskContext, TaskSpec, registry


async def process(context: TaskContext, args: EmptyArgs) -> CombinedResult:
    from app.services.process_service import process_source

    await context.report(5, "Understanding the source and preparing the master story")
    return await process_source(context.run_dir)


async def analyze(context: TaskContext, args: EmptyArgs) -> SourceAnalysis:
    from app.services.analysis_service import analyze_source

    await context.report(5, "Analyzing original source passages")
    return await analyze_source(context.run_dir)


async def master(context: TaskContext, args: EmptyArgs) -> MasterContent:
    from app.services.content_service import load_analysis, generate_content
    from app.services.output_language import load_output_language
    from app.services.openai_service import AIServiceError

    analysis = load_analysis(context.run_dir)
    if analysis is None:
        raise AIServiceError("Analyze the source before generating master content.", 409)
    await context.report(5, "Preparing the master story")
    return await generate_content(context.run_dir, analysis, load_output_language(context.run_dir))


async def platforms(context: TaskContext, args: PlatformRequest) -> PlatformResult:
    from app.services.platform_service import create_platforms

    await context.report(5, "Adapting content for the selected channels")
    return await create_platforms(context.run_dir, args)


async def verification(context: TaskContext, args: ReviewContext) -> ReviewStatus:
    from app.services.verification_service import verify

    await context.report(5, "Checking factual claims and linked evidence")
    return await verify(context.run_dir, args)


for spec in (
    TaskSpec(
        "document.process",
        "Prepare source and story",
        EmptyArgs,
        CombinedResult,
        process,
        ("extracted_text.json",),
    ),
    TaskSpec(
        "source.analyze",
        "Analyze source",
        EmptyArgs,
        SourceAnalysis,
        analyze,
        ("extracted_text.json",),
    ),
    TaskSpec(
        "master.generate",
        "Generate master story",
        EmptyArgs,
        MasterContent,
        master,
        ("analysis.json",),
    ),
    TaskSpec(
        "platforms.generate",
        "Generate channel drafts",
        PlatformRequest,
        PlatformResult,
        platforms,
        ("analysis.json", "master_content.json"),
    ),
    TaskSpec(
        "verification.check",
        "Check factual claims",
        ReviewContext,
        ReviewStatus,
        verification,
        ("platforms.json",),
    ),
):
    registry.register(spec)
