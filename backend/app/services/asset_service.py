"""Fast local PDF assets and at most one optional image request per pack."""

import base64
import binascii
import json
from io import BytesIO
import os
import re
from pathlib import Path
from time import perf_counter
from uuid import uuid4

import pymupdf
from openai import APIError, AsyncOpenAI
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from fastapi import UploadFile
from pydantic import ValidationError

from app.models.assets import AssetPack, VisualAsset
from app.models.content import MasterContent, SourceAnalysis
from app.models.platform import PlatformName
from app.services.content_service import load_analysis
from app.services.cache_service import asset_exists
from app.services.openai_service import AIServiceError
from app.services.platform_service import load_master

SOCIAL = {"linkedin", "facebook", "instagram"}
GENERATED = {"research": "generated_explainer", "curriculum": "generated_education_visual"}
LABELS = {
    "publication_preview": "Original publication",
    "source_visual": "Source visual",
    "generated_explainer": "AI explainer",
    "programme_card": "Programme card",
    "generated_education_visual": "Education visual",
    "user_upload": "Uploaded image",
}


def family_for(analysis: SourceAnalysis) -> str:
    kind = analysis.document_type.lower()
    if kind == "quick_announcement":
        return "research"
    if any(
        word in kind for word in ("curriculum", "programme", "program", "degree", "educational")
    ):
        return "curriculum"
    if any(
        word in kind for word in ("research", "scientific", "journal", "study", "paper", "article")
    ):
        return "research"
    raise AIServiceError(
        "This image workflow supports research papers and curriculum documents only.", 422
    )


def _asset(run_dir: Path, kind: str, source: str) -> VisualAsset:
    return VisualAsset(
        id=kind,
        type=kind,
        label=LABELS[kind],
        source=source,
        path=f"/api/assets/{run_dir.name}/files/{kind}.png",
    )


def _quick_web_assets(run_dir: Path) -> list[VisualAsset]:
    path = run_dir / "quick_announcement.json"
    if not path.is_file():
        return []
    try:
        quick = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        raise AIServiceError("Saved announcement media could not be read.", 422) from exc
    assets: list[VisualAsset] = []
    for item in quick.get("images", [])[:3]:
        filename = item.get("filename", "") if isinstance(item, dict) else ""
        if (
            not re.fullmatch(r"[0-9a-f]{32}\.jpg", filename)
            or not (run_dir / "assets" / "uploads" / filename).is_file()
        ):
            continue
        label = (
            "Official profile photo"
            if item.get("kind") == "profile"
            else (
                "Faculty of Informatics" if item.get("kind") == "faculty" else "Sourced web visual"
            )
        )
        assets.append(
            VisualAsset(
                id=f"upload_{filename.removesuffix('.jpg')}",
                type="user_upload",
                label=label,
                source="web",
                path=f"/api/assets/{run_dir.name}/files/uploads/{filename}",
            )
        )
    return assets


def _save(run_dir: Path, pack: AssetPack) -> AssetPack:
    (run_dir / "assets.json").write_text(pack.model_dump_json(indent=2), encoding="utf-8")
    return pack


def _load(run_dir: Path) -> AssetPack | None:
    path = run_dir / "assets.json"
    if not path.is_file():
        return None
    try:
        return AssetPack.model_validate_json(path.read_text(encoding="utf-8"))
    except ValidationError as exc:
        raise AIServiceError("Saved asset metadata could not be read.", 422) from exc


def _recommend(pack: AssetPack, preserve_main: bool = False, prefer_sourced: bool = False) -> None:
    ids = {asset.id for asset in pack.assets}
    order = (
        ("generated_explainer", "source_visual", "publication_preview")
        if pack.document_family == "research"
        else ("generated_education_visual", "programme_card", "source_visual")
    )
    sourced = (
        (
            next(
                (
                    asset.id
                    for asset in pack.assets
                    if asset.source == "web" and asset.label == "Official profile photo"
                ),
                None,
            )
            or next((asset.id for asset in pack.assets if asset.source == "web"), None)
        )
        if prefer_sourced
        else None
    )
    selected = sourced or next((kind for kind in order if kind in ids), None)
    fallback = selected or (pack.assets[0].id if pack.assets else None)
    previous = pack.main_asset_id if preserve_main and pack.main_asset_id in ids else None
    pack.recommended_asset_id = selected
    pack.main_asset_id = previous or fallback
    for asset in pack.assets:
        asset.recommended = asset.id == selected


def _render(page: pymupdf.Page, clip: pymupdf.Rect, path: Path, scale: float = 2.0) -> None:
    page.get_pixmap(matrix=pymupdf.Matrix(scale, scale), clip=clip, alpha=False).save(path)


def _publication_preview(document: pymupdf.Document, path: Path, title: str) -> None:
    page = document[0]
    height = page.rect.height
    title_hits = page.search_for(title[:75]) if title else []
    title_bottom = min((r.y1 for r in title_hits if r.y0 < height * 0.55), default=height * 0.22)
    abstract_hits = page.search_for("abstract")
    abstract_bottom = min(
        (r.y1 for r in abstract_hits if r.y0 < height * 0.7), default=height * 0.43
    )
    bottom = max(height * 0.52, title_bottom + height * 0.27, abstract_bottom + height * 0.18)
    graphical = page.search_for("graphical abstract")
    if graphical and graphical[0].y0 < height * 0.72:
        bottom = max(bottom, graphical[0].y1 + height * 0.20)
    else:
        introduction = [r.y0 for r in page.search_for("Introduction") if r.y0 > abstract_bottom]
        if introduction:
            bottom = min(bottom, min(introduction) - 8)
    cap = 0.82 if graphical else 0.68
    clip = pymupdf.Rect(page.rect.x0, page.rect.y0, page.rect.x1, min(height * cap, bottom))
    _render(page, clip, path)


def _graphic_bounds(page: pymupdf.Page, region: pymupdf.Rect) -> pymupdf.Rect | None:
    """Tight bounds for a vector or multi-object figure, excluding page text."""
    parts = [pymupdf.Rect(info["bbox"]) & region for info in page.get_image_info()]
    drawings = []
    for item in page.get_drawings():
        rect = pymupdf.Rect(item["rect"]) & region
        if rect.is_empty or rect.width < 4 or rect.height < 4:
            continue
        if rect.width > page.rect.width * 0.75 and rect.height < 3:
            continue
        drawings.append(rect)
    parts = [rect for rect in parts if not rect.is_empty and rect.width > 40 and rect.height > 30]
    if not parts and len(drawings) < 8:
        return None
    parts.extend(drawings)
    bounds = pymupdf.Rect(
        min(rect.x0 for rect in parts),
        min(rect.y0 for rect in parts),
        max(rect.x1 for rect in parts),
        max(rect.y1 for rect in parts),
    )
    if bounds.width < 140 or bounds.height < 90:
        return None
    return pymupdf.Rect(
        max(region.x0, bounds.x0 - 6),
        max(region.y0, bounds.y0 - 6),
        min(region.x1, bounds.x1 + 6),
        min(region.y1, bounds.y1 + 6),
    )


def _visual_candidate(document: pymupdf.Document) -> tuple[int, pymupdf.Rect, int | None] | None:
    best: tuple[float, int, pymupdf.Rect, int | None] | None = None
    for index in range(min(len(document), 6)):
        page = document[index]
        bounds = page.rect
        page_area = bounds.width * bounds.height
        text = page.get_text().lower()
        if "references" in text[:500] or "bibliography" in text[:500]:
            continue
        # A graphical abstract may be vector art, so crop the rendered region.
        for heading in page.search_for("graphical abstract"):
            if heading.y0 > bounds.height * 0.82:
                continue
            below = pymupdf.Rect(
                bounds.x0 + 24,
                heading.y1 + 3,
                bounds.x1 - 24,
                min(bounds.y1 - 24, heading.y1 + bounds.height * 0.34),
            )
            tight = _graphic_bounds(page, below)
            if tight:
                score = 2.0 - index * 0.08
                if best is None or score > best[0]:
                    best = (score, index, tight, None)
        # Large embedded images are likely figures. Reject page headers and tiny branding.
        for info in page.get_image_info(xrefs=True):
            rect = pymupdf.Rect(info["bbox"]) & bounds
            if rect.is_empty or rect.width < 150 or rect.height < 110:
                continue
            ratio = rect.width / rect.height
            area = rect.width * rect.height / page_area
            if not 0.35 < ratio < 6 or not 0.055 < area < 0.65:
                continue
            if index == 0 and rect.y1 < bounds.height * 0.25:
                continue
            if re.search(r"\b(table|tab\.)\s*\d", page.get_textbox(rect).lower()):
                continue
            score = area + (0.18 if "figure" in text or "fig." in text else 0) - index * 0.03
            crop = pymupdf.Rect(
                max(bounds.x0, rect.x0 - 6),
                max(bounds.y0, rect.y0 - 6),
                min(bounds.x1, rect.x1 + 6),
                min(bounds.y1, rect.y1 + 6),
            )
            if best is None or score > best[0]:
                best = (score, index, crop, info.get("xref") or None)
        # Vector figures: look for a caption and sufficient drawing content above it.
        captions = [
            line
            for line in page.get_text("blocks")
            if re.search(r"^\s*(fig(?:ure)?\.?\s*\d+)", line[4], re.I)
        ]
        drawings = page.get_drawings()
        for caption in captions:
            y = caption[1]
            region = pymupdf.Rect(
                bounds.x0 + 24,
                max(bounds.y0 + 40, y - bounds.height * 0.33),
                bounds.x1 - 24,
                max(bounds.y0 + 40, y - 8),
            )
            if region.height < 110:
                continue
            relevant = sum(
                1 for drawing in drawings if pymupdf.Rect(drawing["rect"]).intersects(region)
            )
            tight = _graphic_bounds(page, region) if relevant >= 8 else None
            if tight:
                score = 0.6 + min(relevant, 80) / 200 - index * 0.03
                if best is None or score > best[0]:
                    best = (score, index, tight, None)
    return (best[1], best[2], best[3]) if best else None


def _source_visual(
    document: pymupdf.Document, candidate: tuple[int, pymupdf.Rect, int | None], path: Path
) -> None:
    page_index, clip, xref = candidate
    if xref:
        try:
            original = document.extract_image(xref)["image"]
            with Image.open(BytesIO(original)) as image:
                if image.mode == "CMYK":
                    image = image.convert("RGB")
                image.save(path, format="PNG")
            return
        except (KeyError, OSError, UnidentifiedImageError):
            pass
    _render(document[page_index], clip, path)


def _font(size: int, bold: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    names = [
        "C:/Windows/Fonts/arialbd.ttf" if bold else "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeuib.ttf" if bold else "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"
        if bold
        else "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ]
    for name in names:
        if Path(name).is_file():
            return ImageFont.truetype(name, size)
    return ImageFont.load_default()


def _wrap(draw: ImageDraw.ImageDraw, text: str, font: ImageFont.ImageFont, width: int) -> list[str]:
    lines: list[str] = []
    current = ""
    for word in text.split():
        proposal = f"{current} {word}".strip()
        if current and draw.textlength(proposal, font=font) > width:
            lines.append(current)
            current = word
        else:
            current = proposal
    if current:
        lines.append(current)
    return lines


def _programme_card(analysis: SourceAnalysis, path: Path) -> None:
    image = Image.new("RGB", (1400, 900), "#ffffff")
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, 0, 26, 900), fill="#174a91")
    draw.rectangle((80, 82, 1320, 88), fill="#174a91")
    draw.text((80, 119), "PROGRAMME OVERVIEW", font=_font(25, True), fill="#174a91")
    y = 177
    title_font = _font(62, True)
    for line in _wrap(draw, analysis.title, title_font, 1180)[:3]:
        draw.text((80, y), line, font=title_font, fill="#142e52")
        y += 76
    if analysis.organization.strip():
        org_font = _font(29)
        for line in _wrap(draw, analysis.organization, org_font, 1180)[:2]:
            draw.text((80, y + 8), line, font=org_font, fill="#52667d")
            y += 38
    y = max(y + 43, 430)
    draw.line((80, y - 20, 1320, y - 20), fill="#dce6f2", width=2)
    fact_font = _font(27)
    facts = [fact.statement.strip() for fact in analysis.key_facts if fact.importance == "high"]
    if len(facts) < 3:
        facts += [
            fact.statement.strip() for fact in analysis.key_facts if fact.importance != "high"
        ]
    seen: set[str] = set()
    for fact in facts:
        if not fact or fact in seen:
            continue
        seen.add(fact)
        lines = _wrap(draw, fact, fact_font, 1120)
        if len(lines) > 2 or y + 42 * len(lines) > 815:
            continue
        draw.ellipse((84, y + 12, 98, y + 26), fill="#2676c8")
        for line in lines:
            draw.text((116, y), line, font=fact_font, fill="#263c58")
            y += 38
        y += 20
        if len(seen) >= 5:
            break
    image.save(path)


def _prompt(analysis: SourceAnalysis, master: MasterContent, family: str) -> str:
    if analysis.document_type == "quick_announcement":
        return (
            "Create one clean, horizontal editorial visual for an internal University of Debrecen announcement. "
            f"Announcement: {analysis.summary}. Topic: {analysis.communication_focus}. "
            "Use restrained university green and gold with a realistic, simple subject appropriate to the announcement. "
            "Do not depict a named real person unless a verified reference image is supplied. "
            "No text, logos, watermarks, infographic elements, invented award certificates, or unsupported specifics. "
            "Professional university press-office style, not futuristic or promotional."
        )
    facts = [fact.statement for fact in analysis.key_facts if fact.id in master.source_fact_ids][:5]
    basis = "\n".join(f"- {fact}" for fact in facts)
    limits = "\n".join(f"- {item}" for item in analysis.conditions_and_limitations[:4])
    subject = "research explainer" if family == "research" else "education visual"
    extra = (
        "Show a conceptual research setting, not a deployed product or proven clinical application."
        if family == "research"
        else "Show a natural, diverse academic learning environment if people appear."
    )
    return (
        f"Create one polished, professional horizontal editorial {subject} for University of Debrecen communication. "
        f"Topic: {analysis.title}. Context: {analysis.summary}. Visual focus: {analysis.communication_focus}. "
        f"Grounded facts for conceptual guidance only:\n{basis}\nLimitations to respect:\n{limits}\n"
        f"{extra} No text, numbers, scientific labels, fake university branding, logos, watermarks, or exaggerated claims. "
        "No data charts with invented values. Suitable for a university website and social post."
    )


async def _generate_image(
    run_dir: Path, pack: AssetPack, analysis: SourceAnalysis, master: MasterContent
) -> None:
    started = perf_counter()
    pack.image_attempted = True
    model = os.getenv("OPENAI_IMAGE_MODEL", "").strip()
    key = os.getenv("OPENAI_API_KEY", "").strip()
    if not model:
        pack.image_error = (
            "AI visual could not be generated: set OPENAI_IMAGE_MODEL in backend/.env."
        )
    elif not key:
        pack.image_error = "AI visual could not be generated: OPENAI_API_KEY is missing."
    else:
        try:
            client = AsyncOpenAI(api_key=key, timeout=180.0, max_retries=0)
            response = await client.images.generate(
                model=model,
                prompt=_prompt(analysis, master, pack.document_family),
                size="1536x1024",
                output_format="png",
                n=1,
            )
            encoded = response.data[0].b64_json if response.data else None
            if not encoded:
                raise ValueError("The image API returned no image data.")
            kind = GENERATED[pack.document_family]
            path = run_dir / "assets" / f"{kind}.png"
            path.write_bytes(base64.b64decode(encoded, validate=True))
            if not any(asset.type == kind for asset in pack.assets):
                pack.assets.append(_asset(run_dir, kind, "generated"))
            generated_asset = next(asset for asset in pack.assets if asset.type == kind)
            generated_asset.path = f"/api/assets/{run_dir.name}/files/{kind}.png?v={uuid4().hex}"
            pack.image_error = None
        except (APIError, ValueError, OSError, binascii.Error) as exc:
            pack.image_error = f"AI visual could not be generated: {str(exc)[:240]}"
    print(f"[{run_dir.name}] AI visual generation: {perf_counter() - started:.1f}s", flush=True)


async def create_assets(run_dir: Path, platforms: list[PlatformName]) -> AssetPack:
    started = perf_counter()
    analysis = load_analysis(run_dir)
    if analysis is None:
        raise AIServiceError("Source analysis is still finishing. Please try again shortly.", 409)
    master = load_master(run_dir)
    family = family_for(analysis)
    existing = _load(run_dir)
    if existing and existing.document_family != family:
        raise AIServiceError("Saved asset family does not match this document.", 422)
    if existing:
        pack = existing
        added_quick_assets = False
        missing = [asset for asset in pack.assets if not asset_exists(run_dir, asset.path)]
        if missing:
            pack.assets = [asset for asset in pack.assets if asset not in missing]
            assets_dir = run_dir / "assets"
            assets_dir.mkdir(exist_ok=True)
            pdf = run_dir / "source.pdf"
            local_missing = {asset.type for asset in missing}
            if "programme_card" in local_missing:
                _programme_card(analysis, assets_dir / "programme_card.png")
                pack.assets.append(_asset(run_dir, "programme_card", "local"))
            if pdf.is_file() and local_missing.intersection(
                {"publication_preview", "source_visual"}
            ):
                with pymupdf.open(pdf) as document:
                    if "publication_preview" in local_missing:
                        _publication_preview(
                            document, assets_dir / "publication_preview.png", analysis.title
                        )
                        pack.assets.append(_asset(run_dir, "publication_preview", "document"))
                    if "source_visual" in local_missing:
                        candidate = _visual_candidate(document)
                        if candidate:
                            _source_visual(document, candidate, assets_dir / "source_visual.png")
                            pack.assets.append(_asset(run_dir, "source_visual", "document"))
            _save(run_dir, pack)
        if analysis.document_type == "quick_announcement":
            known = {asset.id for asset in pack.assets}
            pack.assets.extend(
                asset for asset in _quick_web_assets(run_dir) if asset.id not in known
            )
            added_quick_assets = len(pack.assets) > len(known)
        old_main, old_recommendation = pack.main_asset_id, pack.recommended_asset_id
        _recommend(
            pack,
            preserve_main=pack.main_is_manual,
            prefer_sourced=analysis.document_type == "quick_announcement",
        )
        if added_quick_assets or (pack.main_asset_id, pack.recommended_asset_id) != (
            old_main,
            old_recommendation,
        ):
            _save(run_dir, pack)
    else:
        assets_dir = run_dir / "assets"
        assets_dir.mkdir(exist_ok=True)
        assets: list[VisualAsset] = []
        pdf = run_dir / "source.pdf"
        if (run_dir / "quick_announcement.json").is_file():
            assets.extend(_quick_web_assets(run_dir))
        elif family == "research":
            if not pdf.is_file():
                raise AIServiceError("Research publication preview requires the original PDF.", 422)
            with pymupdf.open(pdf) as document:
                tick = perf_counter()
                _publication_preview(
                    document, assets_dir / "publication_preview.png", analysis.title
                )
                print(
                    f"[{run_dir.name}] Publication preview: {perf_counter() - tick:.1f}s",
                    flush=True,
                )
                assets.append(_asset(run_dir, "publication_preview", "document"))
                tick = perf_counter()
                candidate = _visual_candidate(document)
                if candidate:
                    _source_visual(document, candidate, assets_dir / "source_visual.png")
                    assets.append(_asset(run_dir, "source_visual", "document"))
                print(
                    f"[{run_dir.name}] Source visual extraction: {perf_counter() - tick:.1f}s",
                    flush=True,
                )
        else:
            tick = perf_counter()
            _programme_card(analysis, assets_dir / "programme_card.png")
            assets.append(_asset(run_dir, "programme_card", "local"))
            print(f"[{run_dir.name}] Programme card: {perf_counter() - tick:.1f}s", flush=True)
            if pdf.is_file():
                tick = perf_counter()
                with pymupdf.open(pdf) as document:
                    candidate = _visual_candidate(document)
                    if candidate:
                        # Curriculum figures are uncommon; require an explicit visual heading.
                        page = document[candidate[0]]
                        text = page.get_textbox(candidate[1]).lower()
                        if "figure" in text or "diagram" in text or "graphical abstract" in text:
                            _source_visual(document, candidate, assets_dir / "source_visual.png")
                            assets.append(_asset(run_dir, "source_visual", "document"))
                print(
                    f"[{run_dir.name}] Source visual extraction: {perf_counter() - tick:.1f}s",
                    flush=True,
                )
        pack = AssetPack(
            document_family=family,
            assets=assets,
            recommended_asset_id=assets[0].id if assets else None,
            main_asset_id=assets[0].id if assets else None,
        )
        _recommend(pack, prefer_sourced=analysis.document_type == "quick_announcement")
        _save(run_dir, pack)
    has_source = any(asset.type == "source_visual" for asset in pack.assets)
    useful = not has_source or bool(SOCIAL.intersection(platforms))
    if analysis.document_type == "quick_announcement":
        useful = True
    generated_kind = GENERATED[family]
    has_generated = any(
        asset.type == generated_kind and asset_exists(run_dir, asset.path) for asset in pack.assets
    )
    if useful and not has_generated:
        await _generate_image(run_dir, pack, analysis, master)
        _recommend(
            pack,
            preserve_main=pack.main_is_manual,
            prefer_sourced=analysis.document_type == "quick_announcement",
        )
        _save(run_dir, pack)
    print(f"[{run_dir.name}] Asset pack total: {perf_counter() - started:.1f}s", flush=True)
    return pack


async def regenerate_image(run_dir: Path) -> AssetPack:
    pack = _load(run_dir)
    if pack is None:
        raise AIServiceError("Create the asset pack first.", 404)
    analysis = load_analysis(run_dir)
    if analysis is None:
        raise AIServiceError("Source analysis is missing.", 404)
    await _generate_image(run_dir, pack, analysis, load_master(run_dir))
    _recommend(
        pack,
        preserve_main=pack.main_is_manual,
        prefer_sourced=analysis.document_type == "quick_announcement",
    )
    return _save(run_dir, pack)


def select_main(run_dir: Path, asset_id: str) -> AssetPack:
    pack = _load(run_dir)
    if pack is None:
        raise AIServiceError("Create the asset pack first.", 404)
    if asset_id not in {asset.id for asset in pack.assets}:
        raise AIServiceError("Selected asset does not exist.", 422)
    pack.main_asset_id = asset_id
    pack.main_is_manual = True
    return _save(run_dir, pack)


async def upload_image(run_dir: Path, upload: UploadFile) -> AssetPack:
    pack = _load(run_dir)
    if pack is None:
        raise AIServiceError("Create the asset pack before adding an image.", 404)
    extension = Path(upload.filename or "").suffix.lower()
    expected = {".png": "PNG", ".jpg": "JPEG", ".jpeg": "JPEG", ".webp": "WEBP"}
    if extension not in expected:
        raise AIServiceError("Choose a PNG, JPG, JPEG, or WEBP image.", 422)
    uploads_dir = run_dir / "assets" / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    identifier = uuid4().hex
    temporary = uploads_dir / f"{identifier}.pending"
    try:
        total = 0
        with temporary.open("wb") as output:
            while chunk := await upload.read(1024 * 1024):
                total += len(chunk)
                if total > 25 * 1024 * 1024:
                    raise AIServiceError("Image is too large. Choose a file under 25 MB.", 413)
                output.write(chunk)
        try:
            with Image.open(temporary) as image:
                actual = image.format
                image.verify()
        except (OSError, UnidentifiedImageError) as exc:
            raise AIServiceError("The selected file is not a valid image.", 422) from exc
        if actual != expected[extension]:
            raise AIServiceError("The image content does not match its file extension.", 422)
        suffix = ".jpg" if actual == "JPEG" else extension
        filename = f"{identifier}{suffix}"
        temporary.replace(uploads_dir / filename)
        pack.assets.append(
            VisualAsset(
                id=f"upload_{identifier}",
                type="user_upload",
                label="Uploaded image",
                source="user",
                path=f"/api/assets/{run_dir.name}/files/uploads/{filename}",
            )
        )
        _recommend(
            pack,
            preserve_main=pack.main_is_manual,
            prefer_sourced=(run_dir / "quick_announcement.json").is_file(),
        )
        return _save(run_dir, pack)
    finally:
        temporary.unlink(missing_ok=True)
        await upload.close()


def delete_asset(run_dir: Path, asset_id: str) -> AssetPack:
    pack = _load(run_dir)
    if pack is None:
        raise AIServiceError("Create the asset pack first.", 404)
    asset = next((item for item in pack.assets if item.id == asset_id), None)
    if asset is None:
        raise AIServiceError("Selected asset does not exist.", 404)
    if asset.type == "user_upload":
        filename = asset.path.rsplit("/", 1)[-1].split("?", 1)[0]
        if not re.fullmatch(r"[0-9a-f]{32}\.(png|jpg|webp)", filename):
            raise AIServiceError("Saved upload filename is invalid.", 422)
        path = run_dir / "assets" / "uploads" / filename
    else:
        path = run_dir / "assets" / f"{asset.type}.png"
    path.unlink(missing_ok=True)
    pack.assets = [item for item in pack.assets if item.id != asset_id]
    if pack.main_asset_id == asset_id:
        pack.main_is_manual = False
    _recommend(
        pack,
        preserve_main=pack.main_is_manual,
        prefer_sourced=(run_dir / "quick_announcement.json").is_file(),
    )
    return _save(run_dir, pack)
