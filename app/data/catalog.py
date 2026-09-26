"""Load and validate the bundled catalog before any database writes."""

import json
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

from app.schemas.exercise import ExerciseContent, ExerciseResponse


def load_catalog() -> list[ExerciseResponse]:
    payload = json.loads(Path(__file__).with_name("exercises.json").read_text())
    content = [ExerciseContent.model_validate(item) for item in payload]
    if len({item.slug for item in content}) != len(content):
        raise ValueError("Catalog slugs must be unique")
    return [ExerciseResponse(id=uuid5(NAMESPACE_URL, f"https://liftiq.app/exercises/{item.slug}"),
                             **item.model_dump()) for item in content]
