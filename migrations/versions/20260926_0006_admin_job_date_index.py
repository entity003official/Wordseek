"""Add a direct creation-time index for admin job date filtering.

Revision ID: 20260926_0006
Revises: 20260926_0005
"""

from alembic import op


revision = "20260926_0006"
down_revision = "20260926_0005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_jobs_created_at", "analysis_jobs_v1", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_jobs_created_at", table_name="analysis_jobs_v1")
