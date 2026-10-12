"""Shared interface for structured model responses."""

from __future__ import annotations
import os
import re
from typing import Literal, Protocol, TypeVar
from pydantic import BaseModel, ValidationError
from app.services.openai_service import AIServiceError

Role = Literal["writer", "checker"]
T = TypeVar("T", bound=BaseModel)


class StructuredProvider(Protocol):
    def describe(self) -> dict: ...
    async def generate(self, prompt: str, source: str, schema: type[T], role: Role) -> T: ...


class OpenAIProvider:
    def describe(self) -> dict:
        writer = os.getenv("OPENAI_MODEL", "").strip()
        checker = os.getenv("OPENAI_CHECKER_MODEL", "").strip()
        configured = bool(os.getenv("OPENAI_API_KEY", "").strip())
        return {
            "name": "openai",
            "writer_model": writer,
            "checker_model": checker,
            "writer_ready": configured and bool(writer),
            "checker_ready": configured and bool(checker) and bool(writer) and writer != checker,
        }

    async def generate(self, prompt: str, source: str, schema: type[T], role: Role) -> T:
        from app.services.openai_service import _openai_structured_response

        return await _openai_structured_response(prompt, source, schema, checker=role == "checker")


PROVIDERS: dict[str, StructuredProvider] = {"openai": OpenAIProvider()}


def register_provider(name: str, provider: StructuredProvider) -> None:
    if not re.fullmatch(r"[a-z][a-z0-9_-]{1,40}", name):
        raise ValueError(
            "Provider names must use lowercase letters, digits, underscores or hyphens."
        )
    if not callable(getattr(provider, "describe", None)) or not callable(
        getattr(provider, "generate", None)
    ):
        raise ValueError("Provider must implement describe and generate.")
    if name in PROVIDERS:
        raise ValueError(f"Provider {name} is already registered.")
    PROVIDERS[name] = provider


def selected_provider() -> StructuredProvider:
    name = os.getenv("AI_PROVIDER", "openai").strip() or "openai"
    if name not in PROVIDERS:
        raise AIServiceError(
            "The selected AI provider is not registered. Add its adapter or select openai.", 503
        )
    return PROVIDERS[name]


def describe() -> dict:
    raw = selected_provider().describe()
    description = {
        key: raw.get(key)
        for key in ("name", "writer_model", "checker_model", "writer_ready", "checker_ready")
    }
    return {**description, "available_providers": sorted(PROVIDERS)}


def checker_readiness() -> tuple[bool, str | None]:
    try:
        info = describe()
    except AIServiceError as exc:
        return False, str(exc)
    if (
        not info.get("checker_ready")
        or not info.get("writer_model")
        or not info.get("checker_model")
        or info["writer_model"] == info["checker_model"]
    ):
        return (
            False,
            "Configure credentials and distinct writer/checker models for the selected AI provider.",
        )
    return True, None


async def generate(prompt: str, source: str, schema: type[T], *, checker: bool = False) -> T:
    provider = selected_provider()
    info = provider.describe()
    role: Role = "checker" if checker else "writer"
    if not info.get(f"{role}_ready"):
        raise AIServiceError(
            f"The selected AI provider is not configured for the {role} role.", 503
        )
    if checker and info.get("writer_model") == info.get("checker_model"):
        raise AIServiceError("The checker must use a different model from the writer.", 503)
    try:
        result = await provider.generate(prompt, source, schema, role)
    except AIServiceError:
        raise
    except Exception as exc:
        raise AIServiceError(
            f"The AI adapter failed ({type(exc).__name__}). Check its configuration.", 502
        ) from exc
    try:
        return (
            result
            if isinstance(result, schema)
            else schema.model_validate(
                result.model_dump() if isinstance(result, BaseModel) else result
            )
        )
    except ValidationError as exc:
        raise AIServiceError(
            "The AI adapter returned output that does not match the task schema.", 502
        ) from exc
