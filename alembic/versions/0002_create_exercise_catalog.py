"""create exercise catalog

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-25 20:35:11.596682

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Frozen catalog schema; data is managed separately by the seed command.
    op.create_table(
        "exercises",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("slug", sa.String(length=100), nullable=False),
        sa.Column("name", sa.String(length=1000), nullable=False),
        sa.Column("muscle_group", sa.String(length=20), nullable=False),
        sa.Column("difficulty", sa.String(length=10), nullable=False),
        sa.Column("description", sa.String(length=1000), nullable=False),
        sa.Column("instructions", sa.JSON(), nullable=False),
        sa.Column("common_mistakes", sa.JSON(), nullable=False),
        sa.Column("primary_muscles", sa.JSON(), nullable=False),
        sa.Column("secondary_muscles", sa.JSON(), nullable=False),
        sa.Column("joint_angles", sa.JSON(), nullable=False),
        sa.Column("required_keypoints", sa.JSON(), nullable=False),
        sa.Column("analysis_supported", sa.Boolean(), nullable=False),
        sa.Column("analysis_version", sa.Integer(), nullable=True),
        sa.Column("camera_view", sa.String(length=10), nullable=True),
        sa.Column("animation_url", sa.String(length=2048), nullable=True),
        sa.Column("thumbnail_url", sa.String(length=2048), nullable=True),
        sa.CheckConstraint(
            "camera_view IS NULL OR camera_view IN ('front','side')",
            name=op.f("ck_exercises_camera_view"),
        ),
        sa.CheckConstraint(
            "difficulty IN ('easy','medium','hard')",
            name=op.f("ck_exercises_difficulty"),
        ),
        sa.CheckConstraint(
            "json_valid(joint_angles) AND json_type(joint_angles) = 'object'",
            name=op.f("ck_exercises_joint_angles_object"),
        ),
        sa.CheckConstraint(
            "muscle_group IN ('chest','back','legs','shoulders','biceps','triceps','core')",
            name=op.f("ck_exercises_muscle_group"),
        ),
        sa.CheckConstraint(
            "analysis_supported IN (0, 1)", name=op.f("ck_exercises_analysis_supported")
        ),
        sa.CheckConstraint(
            "analysis_version IS NULL OR analysis_version > 0",
            name=op.f("ck_exercises_analysis_version"),
        ),
        sa.CheckConstraint(
            "length(slug) BETWEEN 1 AND 100", name=op.f("ck_exercises_slug_length")
        ),
        sa.CheckConstraint(
            "length(trim(name)) > 0", name=op.f("ck_exercises_name_not_empty")
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_exercises")),
        sa.UniqueConstraint("slug", name=op.f("uq_exercises_slug")),
    )
    with op.batch_alter_table("exercises", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_exercises_muscle_group"), ["muscle_group"], unique=False
        )



def downgrade() -> None:
    # Frozen catalog schema; data is managed separately by the seed command.
    with op.batch_alter_table("exercises", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_exercises_muscle_group"))

    op.drop_table("exercises")
