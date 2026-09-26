"""Register every ORM model with the shared metadata for Alembic."""

from app.core.enums import ExperienceLevel, RevocationReason, TrainingGoal
from app.models.credential import Credential
from app.models.exercise import Exercise
from app.models.refresh_token import RefreshToken
from app.models.user import User

__all__ = [
    "Credential",
    "Exercise",
    "ExperienceLevel",
    "RefreshToken",
    "RevocationReason",
    "TrainingGoal",
    "User",
]
