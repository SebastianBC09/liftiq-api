"""Per-user catalog bookmarks with a unique, nonnegative position."""

from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class UserFavorite(Base):
    __tablename__ = "user_favorites"
    __table_args__ = (
        UniqueConstraint("user_id", "sort_order"),
        CheckConstraint("sort_order >= 0", name="sort_order_nonnegative"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    exercise_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("exercises.id", ondelete="CASCADE"), primary_key=True, index=True
    )
    sort_order: Mapped[int]
