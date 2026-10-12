"""Task definitions and input validation."""

from dataclasses import dataclass
from pathlib import Path
import re
from typing import Awaitable, Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from app.services.extension_support import CampaignInputs, ExtensionStore
from pydantic import BaseModel, ConfigDict
from app.services.openai_service import AIServiceError


class EmptyArgs(BaseModel):
    model_config = ConfigDict(extra="forbid")


@dataclass
class TaskContext:
    run_id: str
    run_dir: Path
    report: Callable[[int, str], Awaitable[None]]

    def campaign(self) -> "CampaignInputs":
        from app.services.extension_support import CampaignInputs

        return CampaignInputs.load(self.run_dir)

    def store(self, feature_id: str) -> "ExtensionStore":
        from app.services.extension_support import ExtensionStore

        return ExtensionStore(self.run_dir, feature_id)


@dataclass(frozen=True)
class TaskSpec:
    id: str
    label: str
    arguments: type[BaseModel]
    result: type[BaseModel]
    handler: Callable[[TaskContext, BaseModel], Awaitable[BaseModel]]
    required_files: tuple[str, ...] = ()


class TaskRegistry:
    def __init__(self):
        self.tasks: dict[str, TaskSpec] = {}

    def register(self, spec: TaskSpec) -> None:
        if not re.fullmatch(r"[a-z][a-z0-9_.-]{1,60}", spec.id) or spec.id in self.tasks:
            raise ValueError("Task ID is invalid or already registered.")
        if (
            spec.arguments.model_json_schema().get("type") != "object"
            or spec.result.model_json_schema().get("type") != "object"
        ):
            raise ValueError("Task arguments and results must be JSON object schemas.")
        for name in spec.required_files:
            path = Path(name)
            if path.is_absolute() or ".." in path.parts:
                raise ValueError("Required files must be relative to the campaign.")
        self.tasks[spec.id] = spec

    def get(self, task_id: str) -> TaskSpec:
        if task_id not in self.tasks:
            raise AIServiceError("Task is not registered.", 404)
        return self.tasks[task_id]

    def validate(self, task_id: str, arguments: dict, folder: Path) -> BaseModel:
        spec = self.get(task_id)
        for name in spec.required_files:
            if not (folder / name).is_file():
                raise AIServiceError(
                    f"This task requires {name}. Collect or process the source first.", 409
                )
        return spec.arguments.model_validate(arguments)

    def descriptors(self) -> list[dict]:
        return [
            {
                "id": spec.id,
                "label": spec.label,
                "arguments_schema": spec.arguments.model_json_schema(),
                "result_schema": spec.result.model_json_schema(),
                "required_files": list(spec.required_files),
            }
            for spec in self.tasks.values()
        ]


registry = TaskRegistry()
