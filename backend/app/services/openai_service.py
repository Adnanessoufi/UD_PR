"""Shared OpenAI configuration and structured-response error handling."""

import os
from pathlib import Path
from typing import TypeVar

from dotenv import load_dotenv
from openai import APIError, AsyncOpenAI, AuthenticationError, BadRequestError, NotFoundError
from pydantic import BaseModel, ValidationError

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
T = TypeVar("T", bound=BaseModel)


class AIServiceError(Exception):
    def __init__(self, message: str, status_code: int = 502):
        super().__init__(message)
        self.status_code = status_code


def config(*, checker: bool = False) -> tuple[AsyncOpenAI, str, str]:
    key = os.getenv("OPENAI_API_KEY", "").strip()
    model = os.getenv("OPENAI_MODEL", "").strip()
    effort = os.getenv("OPENAI_REASONING_EFFORT", "low").strip().lower()
    if not key:
        raise AIServiceError("OPENAI_API_KEY is missing. Add it to backend/.env.", 503)
    if not model:
        raise AIServiceError("OPENAI_MODEL is missing. Add a supported model to backend/.env.", 503)
    if checker:
        checker_model = os.getenv("OPENAI_CHECKER_MODEL", "").strip()
        if not checker_model or checker_model == model:
            raise AIServiceError(
                "Set OPENAI_CHECKER_MODEL to a model different from OPENAI_MODEL before verification.",
                503,
            )
        model = checker_model
        effort = os.getenv("OPENAI_CHECKER_REASONING_EFFORT", "low").strip().lower()
    if effort not in {"low", "medium", "high", "xhigh", "max"}:
        raise AIServiceError(
            "Choose a supported reasoning effort: low, medium, high, xhigh or max.", 503
        )
    # The recovery workflow owns its one allowed connection retry per stage.
    return AsyncOpenAI(api_key=key, timeout=120.0, max_retries=0), model, effort


async def _openai_structured_response(
    prompt: str, source: str, schema: type[T], *, checker: bool = False
) -> T:
    client, model, effort = config(checker=checker)
    try:
        response = await client.responses.parse(
            model=model,
            input=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": source},
            ],
            text_format=schema,
            reasoning={"effort": effort},
        )
        if response.output_parsed is None:
            raise AIServiceError("The AI returned no valid structured content. Please retry.")
        return response.output_parsed
    except AuthenticationError as exc:
        raise AIServiceError("The OpenAI API key was rejected. Check backend/.env.", 503) from exc
    except (BadRequestError, NotFoundError) as exc:
        raise AIServiceError(
            "The selected OpenAI model could not produce structured output. Check the writer/checker model configuration in backend/.env.",
            503,
        ) from exc
    except ValidationError as exc:
        raise AIServiceError("The AI returned malformed structured content. Please retry.") from exc
    except APIError as exc:
        raise AIServiceError(
            "The OpenAI service could not complete the request. Please retry."
        ) from exc


async def structured_response(
    prompt: str, source: str, schema: type[T], *, checker: bool = False
) -> T:
    """Shared entry point for structured model responses."""
    from app.services.model_gateway import generate

    return await generate(prompt, source, schema, checker=checker)
