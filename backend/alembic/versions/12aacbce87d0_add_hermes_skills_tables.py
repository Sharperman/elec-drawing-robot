"""add_hermes_skills_tables

Revision ID: 12aacbce87d0
Revises: fede628e0a19
Create Date: 2026-06-09 17:58:11.511936

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '12aacbce87d0'
down_revision: Union[str, Sequence[str], None] = 'fede628e0a19'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # ---- hermes_skills ----
    op.create_table(
        "hermes_skills",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("skill_id", sa.String(length=128), nullable=False),
        sa.Column("name", sa.String(length=256), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("category", sa.String(length=32), nullable=False,
                  server_default="external"),
        sa.Column("status", sa.String(length=16), nullable=False,
                  server_default="active"),
        sa.Column("source_path", sa.String(length=512), nullable=True),
        sa.Column("triggers_json", sa.Text(), nullable=True),
        sa.Column("inputs_json", sa.Text(), nullable=True),
        sa.Column("execution_json", sa.Text(), nullable=True),
        sa.Column("metadata_json", sa.Text(), nullable=True),
        sa.Column("use_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("success_count", sa.Integer(), nullable=False,
                  server_default=sa.text("0")),
        sa.Column("last_used_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.func.current_timestamp()),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("skill_id"),
    )
    op.create_index("idx_skills_category", "hermes_skills", ["category"])
    op.create_index("idx_skills_status", "hermes_skills", ["status"])
    op.create_index("idx_skills_skill_id", "hermes_skills", ["skill_id"])

    # ---- hermes_skill_executions ----
    op.create_table(
        "hermes_skill_executions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("execution_id", sa.String(length=64), nullable=False),
        sa.Column("skill_id", sa.String(length=128), nullable=False),
        sa.Column("session_id", sa.String(length=128), nullable=True),
        sa.Column("inputs_json", sa.Text(), nullable=True),
        sa.Column("outputs_json", sa.Text(), nullable=True),
        sa.Column("steps_json", sa.Text(), nullable=True),
        sa.Column("logs_json", sa.Text(), nullable=True),
        sa.Column("success", sa.Boolean(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("execution_time_ms", sa.Integer(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("finished_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("execution_id"),
    )
    op.create_index("idx_exec_skill_id", "hermes_skill_executions", ["skill_id"])
    op.create_index("idx_exec_session_id", "hermes_skill_executions", ["session_id"])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table("hermes_skill_executions")
    op.drop_table("hermes_skills")
