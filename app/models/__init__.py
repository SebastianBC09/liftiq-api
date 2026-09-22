"""Register every ORM model with the shared metadata for Alembic."""

from app.core.enums import ExperienceLevel, RevocationReason, TrainingGoal
from app.models.credential import Credential
from app.models.refresh_token import RefreshToken
from app.models.user import User

__all__ = [
    "Credential",
    "ExperienceLevel",
    "RefreshToken",
    "RevocationReason",
    "TrainingGoal",
    "User",
]
