"""create auth tables

Revision ID: 0001
Revises:
Create Date: 2026-09-21 19:59:02.026686

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Frozen schema: do not import application models or custom types.
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("first_name", sa.String(length=100), nullable=False),
        sa.Column("last_name", sa.String(length=100), nullable=False),
        sa.Column("height_cm", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column("weight_kg", sa.Numeric(precision=6, scale=2), nullable=False),
        sa.Column(
            "experience_level",
            sa.Enum(
                "beginner",
                "intermediate",
                "advanced",
                name="experience_level",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "goal",
            sa.Enum(
                "strength",
                "hypertrophy",
                "technique",
                "general_fitness",
                name="training_goal",
                native_enum=False,
            ),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f', 'now'))"),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f', 'now'))"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "experience_level IN ('beginner', 'intermediate', 'advanced')",
            name=op.f("ck_users_experience_level"),
        ),
        sa.CheckConstraint(
            "goal IN ('strength', 'hypertrophy', 'technique', 'general_fitness')",
            name=op.f("ck_users_training_goal"),
        ),
        sa.CheckConstraint(
            "email = lower(trim(email))", name=op.f("ck_users_email_normalized")
        ),
        sa.CheckConstraint(
            "height_cm > 0 AND height_cm < 10000 AND round(height_cm, 2) = height_cm",
            name=op.f("ck_users_height_value"),
        ),
        sa.CheckConstraint(
            "length(email) BETWEEN 3 AND 254", name=op.f("ck_users_email_length")
        ),
        sa.CheckConstraint(
            "length(first_name) BETWEEN 1 AND 100 AND length(trim(first_name)) > 0",
            name=op.f("ck_users_first_name_length"),
        ),
        sa.CheckConstraint(
            "length(last_name) BETWEEN 1 AND 100 AND length(trim(last_name)) > 0",
            name=op.f("ck_users_last_name_length"),
        ),
        sa.CheckConstraint(
            "updated_at >= created_at", name=op.f("ck_users_timestamp_order")
        ),
        sa.CheckConstraint(
            "weight_kg > 0 AND weight_kg < 10000 AND round(weight_kg, 2) = weight_kg",
            name=op.f("ck_users_weight_value"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_users")),
        sa.UniqueConstraint("email", name=op.f("uq_users_email")),
    )
    op.create_table(
        "credentials",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column(
            "password_updated_at",
            sa.DateTime(),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f', 'now'))"),
            nullable=False,
        ),
        sa.CheckConstraint(
            "length(password_hash) BETWEEN 1 AND 255",
            name=op.f("ck_credentials_hash_length"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_credentials_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("user_id", name=op.f("pk_credentials")),
    )
    op.create_table(
        "refresh_tokens",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("family_id", sa.Uuid(), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column(
            "issued_at",
            sa.DateTime(),
            server_default=sa.text("(strftime('%Y-%m-%d %H:%M:%f', 'now'))"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("revoked_at", sa.DateTime(), nullable=True),
        sa.Column(
            "revocation_reason",
            sa.Enum(
                "rotated",
                "logout",
                "reuse",
                name="revocation_reason",
                native_enum=False,
            ),
            nullable=True,
        ),
        sa.Column("device_info", sa.String(length=512), nullable=True),
        sa.CheckConstraint(
            "length(token_hash) = 64 AND token_hash NOT GLOB '*[^0-9a-f]*'",
            name=op.f("ck_refresh_tokens_sha256_hex"),
        ),
        sa.CheckConstraint(
            "revocation_reason IN ('rotated', 'logout', 'reuse')",
            name=op.f("ck_refresh_tokens_revocation_reason"),
        ),
        sa.CheckConstraint(
            "(revoked_at IS NULL AND revocation_reason IS NULL) OR (revoked_at IS NOT NULL AND revocation_reason IS NOT NULL)",
            name=op.f("ck_refresh_tokens_revocation_state"),
        ),
        sa.CheckConstraint(
            "device_info IS NULL OR length(device_info) <= 512",
            name=op.f("ck_refresh_tokens_device_info_length"),
        ),
        sa.CheckConstraint(
            "expires_at > issued_at", name=op.f("ck_refresh_tokens_expiry_order")
        ),
        sa.CheckConstraint(
            "revoked_at IS NULL OR revoked_at >= issued_at",
            name=op.f("ck_refresh_tokens_revocation_order"),
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_refresh_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_refresh_tokens")),
        sa.UniqueConstraint("token_hash", name=op.f("uq_refresh_tokens_token_hash")),
    )
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.create_index(
            "ix_refresh_tokens_user_id_family_id",
            ["user_id", "family_id"],
            unique=False,
        )


def downgrade() -> None:
    # Frozen schema: do not import application models or custom types.
    with op.batch_alter_table("refresh_tokens", schema=None) as batch_op:
        batch_op.drop_index("ix_refresh_tokens_user_id_family_id")

    op.drop_table("refresh_tokens")
    op.drop_table("credentials")
    op.drop_table("users")
