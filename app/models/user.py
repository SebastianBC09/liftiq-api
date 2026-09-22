"""Public account/profile persistence; credentials live in a separate table."""

from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Enum, Numeric, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column, validates

from app.db.base import Base
from app.db.types import UTCDateTime, utc_now


class ExperienceLevel(StrEnum):
    BEGINNER = "beginner"
    INTERMEDIATE = "intermediate"
    ADVANCED = "advanced"


class TrainingGoal(StrEnum):
    STRENGTH = "strength"
    HYPERTROPHY = "hypertrophy"
    TECHNIQUE = "technique"
    GENERAL_FITNESS = "general_fitness"


class User(Base):
    """Account identity and required profile fields, without password material."""

    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint(
            "experience_level IN ('beginner', 'intermediate', 'advanced')", name="experience_level"
        ),
        CheckConstraint(
            "goal IN ('strength', 'hypertrophy', 'technique', 'general_fitness')",
            name="training_goal",
        ),
        CheckConstraint("email = lower(trim(email))", name="email_normalized"),
        CheckConstraint("length(email) BETWEEN 3 AND 254", name="email_length"),
        CheckConstraint(
            "length(first_name) BETWEEN 1 AND 100 AND length(trim(first_name)) > 0",
            name="first_name_length",
        ),
        CheckConstraint(
            "length(last_name) BETWEEN 1 AND 100 AND length(trim(last_name)) > 0",
            name="last_name_length",
        ),
        CheckConstraint(
            "height_cm > 0 AND height_cm < 10000 AND round(height_cm, 2) = height_cm",
            name="height_value",
        ),
        CheckConstraint(
            "weight_kg > 0 AND weight_kg < 10000 AND round(weight_kg, 2) = weight_kg",
            name="weight_value",
        ),
        CheckConstraint("updated_at >= created_at", name="timestamp_order"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(254), unique=True)
    first_name: Mapped[str] = mapped_column(String(100))
    last_name: Mapped[str] = mapped_column(String(100))
    height_cm: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    weight_kg: Mapped[Decimal] = mapped_column(Numeric(6, 2))
    experience_level: Mapped[ExperienceLevel] = mapped_column(
        Enum(
            ExperienceLevel,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            name="experience_level",
        )
    )
    goal: Mapped[TrainingGoal] = mapped_column(
        Enum(
            TrainingGoal,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            name="training_goal",
        )
    )
    created_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=text("(strftime('%Y-%m-%d %H:%M:%f', 'now'))")
    )
    updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(),
        server_default=text("(strftime('%Y-%m-%d %H:%M:%f', 'now'))"),
        onupdate=utc_now,
    )

    @validates("email")
    def normalize_email(self, key: str, value: str) -> str:
        """Use one canonical address for storage and uniqueness."""
        return value.strip().lower()
