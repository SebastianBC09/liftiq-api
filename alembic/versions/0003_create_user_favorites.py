"""create user favorites

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-25 20:43:13.720634

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Frozen schema; no application-model imports.
    op.create_table(
        "user_favorites",
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("exercise_id", sa.Uuid(), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.CheckConstraint(
            "sort_order >= 0", name=op.f("ck_user_favorites_sort_order_nonnegative")
        ),
        sa.ForeignKeyConstraint(
            ["exercise_id"],
            ["exercises.id"],
            name=op.f("fk_user_favorites_exercise_id_exercises"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=op.f("fk_user_favorites_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint(
            "user_id", "exercise_id", name=op.f("pk_user_favorites")
        ),
        sa.UniqueConstraint(
            "user_id", "sort_order", name=op.f("uq_user_favorites_user_id")
        ),
    )
    with op.batch_alter_table("user_favorites", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_user_favorites_exercise_id"), ["exercise_id"], unique=False
        )


def downgrade() -> None:
    # Frozen schema; no application-model imports.
    with op.batch_alter_table("user_favorites", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_user_favorites_exercise_id"))

    op.drop_table("user_favorites")
