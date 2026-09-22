"""Refresh-token digests and rotation families; never persist raw tokens."""

from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Enum, ForeignKey, Index, String, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.db.types import UTCDateTime


class RevocationReason(StrEnum):
    ROTATED = "rotated"
    LOGOUT = "logout"
    REUSE = "reuse"


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"
    __table_args__ = (
        CheckConstraint(
            "revocation_reason IN ('rotated', 'logout', 'reuse')", name="revocation_reason"
        ),
        CheckConstraint(
            "length(token_hash) = 64 AND token_hash NOT GLOB '*[^0-9a-f]*'", name="sha256_hex"
        ),
        CheckConstraint("expires_at > issued_at", name="expiry_order"),
        CheckConstraint("revoked_at IS NULL OR revoked_at >= issued_at", name="revocation_order"),
        CheckConstraint(
            "(revoked_at IS NULL AND revocation_reason IS NULL) OR "
            "(revoked_at IS NOT NULL AND revocation_reason IS NOT NULL)",
            name="revocation_state",
        ),
        CheckConstraint(
            "device_info IS NULL OR length(device_info) <= 512", name="device_info_length"
        ),
        Index("ix_refresh_tokens_user_id_family_id", "user_id", "family_id"),
    )

    id: Mapped[UUID] = mapped_column(Uuid, primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(Uuid, ForeignKey("users.id", ondelete="CASCADE"))
    family_id: Mapped[UUID] = mapped_column(Uuid)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True)
    issued_at: Mapped[datetime] = mapped_column(
        UTCDateTime(), server_default=text("(strftime('%Y-%m-%d %H:%M:%f', 'now'))")
    )
    expires_at: Mapped[datetime] = mapped_column(UTCDateTime())
    revoked_at: Mapped[datetime | None] = mapped_column(UTCDateTime())
    revocation_reason: Mapped[RevocationReason | None] = mapped_column(
        Enum(
            RevocationReason,
            values_callable=lambda cls: [item.value for item in cls],
            native_enum=False,
            create_constraint=False,
            validate_strings=True,
            name="revocation_reason",
        )
    )
    device_info: Mapped[str | None] = mapped_column(String(512))
