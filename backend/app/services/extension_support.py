"""Campaign inputs and cached feature results."""

from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
from uuid import uuid4
from typing import TypeVar
from pydantic import BaseModel
from app.models.content import SourceAnalysis, MasterContent
from app.models.platform import PlatformResult
from app.models.campaign import CampaignBrief
from app.services.openai_service import AIServiceError
from app.services.output_language import OutputLanguage, load_output_language

T = TypeVar("T", bound=BaseModel)


def digest(value) -> str:
    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False).encode("utf-8")
    ).hexdigest()


def read_input(folder: Path, filename: str):
    path = folder / filename
    if not path.is_file():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as exc:
        raise AIServiceError(f"Saved {filename} could not be read.", 422) from exc


@dataclass(frozen=True)
class CampaignInputs:
    source: dict | None
    analysis: SourceAnalysis | None
    master: MasterContent | None
    platforms: PlatformResult | None
    brief: CampaignBrief
    language: OutputLanguage

    @classmethod
    def load(cls, folder: Path) -> "CampaignInputs":
        def model(filename, schema):
            raw = read_input(folder, filename)
            return schema.model_validate(raw) if raw is not None else None

        return cls(
            source=read_input(folder, "extracted_text.json"),
            analysis=model("analysis.json", SourceAnalysis),
            master=model("master_content.json", MasterContent),
            platforms=model("platforms.json", PlatformResult),
            brief=model("brief.json", CampaignBrief) or CampaignBrief(),
            language=load_output_language(folder),
        )

    def source_passages(self) -> list[dict]:
        from app.services.verification_service import passages

        return passages(
            {"source": self.source, "analysis": self.analysis.model_dump() if self.analysis else {}}
        )

    def fingerprint(self, *fields: str) -> str:
        """Choose the inputs your output actually depends on; default to all."""
        values = {
            "source": self.source,
            "analysis": self.analysis,
            "master": self.master,
            "platforms": self.platforms,
            "brief": self.brief,
            "language": self.language,
        }
        selected = fields or tuple(values)
        if not set(selected).issubset(values):
            raise ValueError("Unknown campaign input field.")
        return digest(
            {
                key: values[key].model_dump(mode="json")
                if isinstance(values[key], BaseModel)
                else values[key]
                for key in selected
            }
        )


class ExtensionStore:
    """Feature-owned JSON outputs; input/revision changes cause a cache miss."""

    def __init__(self, folder: Path, feature_id: str):
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{0,60}", feature_id) or ".." in feature_id:
            raise ValueError("Invalid feature storage ID.")
        self.folder = folder.resolve()
        self.root = folder / "extensions" / feature_id

    def _path(self, key: str) -> Path:
        if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", key):
            raise ValueError("Invalid artifact key.")
        path = self.root / f"{key}.json"
        if not path.resolve().is_relative_to(self.folder):
            raise ValueError("Artifact path escapes the campaign.")
        return path

    def read(self, key: str, schema: type[T], *, inputs: dict, version: int = 1) -> T | None:
        path = self._path(key)
        if not path.is_file():
            return None
        try:
            record = json.loads(path.read_text(encoding="utf-8"))
            if record.get("schema_version") != version or record.get("input_fingerprint") != digest(
                inputs
            ):
                return None
            return schema.model_validate(record["value"])
        except (ValueError, KeyError, OSError) as exc:
            raise AIServiceError("Saved extension output could not be read.", 422) from exc

    def write(self, key: str, value: BaseModel, *, inputs: dict, version: int = 1) -> None:
        if version < 1:
            raise ValueError("Artifact schema version must be positive.")
        path = self._path(key)
        path.parent.mkdir(parents=True, exist_ok=True)
        temporary = path.with_name(f".{path.name}.{uuid4().hex}.tmp")
        record = {
            "schema_version": version,
            "input_fingerprint": digest(inputs),
            "created_at": datetime.now(timezone.utc).isoformat(),
            "value": value.model_dump(mode="json"),
        }
        try:
            temporary.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(path)
        finally:
            temporary.unlink(missing_ok=True)
