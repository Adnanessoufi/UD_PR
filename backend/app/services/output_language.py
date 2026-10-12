"""Persist the output language independently of the source document language."""

import json
from pathlib import Path
from typing import Literal

OutputLanguage = Literal["en", "hu"]


def load_output_language(run_dir: Path) -> OutputLanguage:
    path = run_dir / "output_language.json"
    if path.is_file():
        try:
            value = json.loads(path.read_text(encoding="utf-8")).get("language")
            if value in ("en", "hu"):
                return value
        except (OSError, ValueError, TypeError, AttributeError):
            pass
    return "en"


def save_output_language(run_dir: Path, language: OutputLanguage) -> None:
    (run_dir / "output_language.json").write_text(
        json.dumps({"language": language}), encoding="utf-8"
    )


def language_instruction(language: OutputLanguage) -> str:
    if language == "hu":
        return (
            "Output language: Hungarian (Magyar). Write every publishable field in natural, "
            "professional Hungarian, not a literal translation. Keep proper names, technical "
            "terms, exact numbers, and factual qualifiers accurate. The source may be in English "
            "or Hungarian. Source excerpts and fact IDs remain unchanged."
        )
    return (
        "Output language: English. Write every publishable field in natural, "
        "professional English. The source may be in English or Hungarian. "
        "Keep proper names, technical terms, exact numbers, and factual qualifiers accurate."
    )
