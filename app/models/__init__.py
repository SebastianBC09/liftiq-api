"""Register every ORM model with the shared metadata for Alembic."""

from app.models.credential import Credential
from app.models.refresh_token import RefreshToken, RevocationReason
from app.models.user import ExperienceLevel, TrainingGoal, User

__all__ = [
    "Credential",
    "ExperienceLevel",
    "RefreshToken",
    "RevocationReason",
    "TrainingGoal",
    "User",
]
