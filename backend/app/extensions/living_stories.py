"""Living Stories task and API routes."""

from app.api.story_room import router
from app.models.story_room import StoryQuestion, StoryAnswer
from app.services.story_room_service import answer_question
from app.services.task_registry import TaskSpec, registry

registry.register(
    TaskSpec(
        "story.answer",
        "Answer an audience question",
        StoryQuestion,
        StoryAnswer,
        answer_question,
        ("analysis.json",),
    )
)
