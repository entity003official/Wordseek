"""Widen generated practice titles for validated DeepSeek output.

Revision ID: 20260926_0004
Revises: 20260926_0003
"""
import sqlalchemy as sa
from alembic import op


revision = "20260926_0004"
down_revision = "20260926_0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("practices_v1") as batch:
        batch.alter_column(
            "title",
            existing_type=sa.String(120),
            type_=sa.String(800),
            existing_nullable=False,
        )

def downgrade() -> None:
    op.execute(sa.text("UPDATE practices_v1 SET title = substr(title, 1, 120) WHERE length(title) > 120"))
    with op.batch_alter_table("practices_v1") as batch:
        batch.alter_column(
            "title",
            existing_type=sa.String(800),
            type_=sa.String(120),
            existing_nullable=False,
        )
