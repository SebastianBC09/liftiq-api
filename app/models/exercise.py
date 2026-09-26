"""Catalog persistence. Repositories validate structured content at both boundaries."""

from typing import Any
from uuid import UUID

from sqlalchemy import JSON, Boolean, CheckConstraint, Integer, String, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Exercise(Base):
    __tablename__ = "exercises"
    __table_args__ = (
        CheckConstraint("analysis_supported IN (0, 1)", name="analysis_supported"),
        CheckConstraint("length(slug) BETWEEN 1 AND 100", name="slug_length"),
        CheckConstraint("length(trim(name)) > 0", name="name_not_empty"),
        CheckConstraint(
            "muscle_group IN ('chest','back','legs','shoulders','biceps','triceps','core')",
            name="muscle_group",
        ),
        CheckConstraint("difficulty IN ('easy','medium','hard')", name="difficulty"),
        CheckConstraint(
            "json_valid(joint_angles) AND json_type(joint_angles) = 'object'",
            name="joint_angles_object",
        ),
        CheckConstraint(
            "analysis_version IS NULL OR analysis_version > 0", name="analysis_version"
        ),
        CheckConstraint(
            "camera_view IS NULL OR camera_view IN ('front','side')", name="camera_view"
        ),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True)
    slug: Mapped[str] = mapped_column(String(100), unique=True)
    name: Mapped[str] = mapped_column(String(1000))
    muscle_group: Mapped[str] = mapped_column(String(20), index=True)
    difficulty: Mapped[str] = mapped_column(String(10))
    description: Mapped[str] = mapped_column(String(1000))
    instructions: Mapped[list[str]] = mapped_column(JSON)
    common_mistakes: Mapped[list[str]] = mapped_column(JSON)
    primary_muscles: Mapped[list[str]] = mapped_column(JSON)
    secondary_muscles: Mapped[list[str]] = mapped_column(JSON)
    joint_angles: Mapped[dict[str, Any]] = mapped_column(JSON)
    required_keypoints: Mapped[list[str]] = mapped_column(JSON)
    analysis_supported: Mapped[bool] = mapped_column(Boolean())
    analysis_version: Mapped[int | None] = mapped_column(Integer)
    camera_view: Mapped[str | None] = mapped_column(String(10))
    animation_url: Mapped[str | None] = mapped_column(String(2048))
    thumbnail_url: Mapped[str | None] = mapped_column(String(2048))
