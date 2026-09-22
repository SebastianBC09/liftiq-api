"""One password credential per user; never used as a public response model."""

from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, ForeignKey, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime


class Credential(Base):
    __tablename__ = "credentials"
    __table_args__ = (
        CheckConstraint("length(password_hash) BETWEEN 1 AND 255", name="hash_length"),
    )

    user_id: Mapped[UUID] = mapped_column(
        Uuid, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    password_hash: Mapped[str] = mapped_column(String(255))
    password_updated_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=text("(strftime('%Y-%m-%d %H:%M:%f', 'now'))")
    )
