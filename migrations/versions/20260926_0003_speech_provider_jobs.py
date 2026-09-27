"""Persist cloud speech provider execution state for idempotent recovery.

Revision ID: 20260926_0003
Revises: 20260926_0002
"""
import sqlalchemy as sa
from alembic import op


revision = "20260926_0003"
down_revision = "20260926_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("analysis_jobs_v1")}
    additions = (
        ("requested_backend", sa.String(20), True, None),
        ("provider", sa.String(30), True, None),
        ("provider_model", sa.String(100), True, None),
        ("provider_task_id", sa.String(160), True, None),
        ("fallback_used", sa.Boolean(), False, sa.false()),
        ("fallback_reason", sa.String(160), True, None),
    )
    for name, type_, nullable, default in additions:
        if name not in columns:
            op.add_column(
                "analysis_jobs_v1",
                sa.Column(name, type_, nullable=nullable, server_default=default),
            )
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("analysis_jobs_v1")}
    if "ix_analysis_jobs_v1_provider_task_id" not in indexes:
        op.create_index("ix_analysis_jobs_v1_provider_task_id", "analysis_jobs_v1", ["provider_task_id"])


def downgrade() -> None:
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("analysis_jobs_v1")}
    if "ix_analysis_jobs_v1_provider_task_id" in indexes:
        op.drop_index("ix_analysis_jobs_v1_provider_task_id", table_name="analysis_jobs_v1")
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("analysis_jobs_v1")}
    for name in ("fallback_reason", "fallback_used", "provider_task_id", "provider_model", "provider", "requested_backend"):
        if name in columns:
            op.drop_column("analysis_jobs_v1", name)
