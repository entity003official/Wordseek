"""Add retry lineage and monitoring indexes to analysis jobs.

Revision ID: 20260926_0005
Revises: 20260926_0004
"""
import sqlalchemy as sa
from alembic import op


revision = "20260926_0005"
down_revision = "20260926_0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    inspector = sa.inspect(op.get_bind())
    columns = {column["name"] for column in inspector.get_columns("analysis_jobs_v1")}
    if "retry_of_job_id" not in columns:
        op.add_column("analysis_jobs_v1", sa.Column("retry_of_job_id", sa.String(36), nullable=True))

    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("analysis_jobs_v1")}
    additions = (
        ("ix_analysis_jobs_v1_retry_of_job_id", ["retry_of_job_id"]),
        ("ix_jobs_status_created", ["status", "created_at"]),
        ("ix_jobs_kind_created", ["kind", "created_at"]),
        ("ix_jobs_provider_created", ["provider", "created_at"]),
    )
    for name, columns_ in additions:
        if name not in indexes:
            op.create_index(name, "analysis_jobs_v1", columns_)


def downgrade() -> None:
    indexes = {index["name"] for index in sa.inspect(op.get_bind()).get_indexes("analysis_jobs_v1")}
    for name in (
        "ix_jobs_provider_created",
        "ix_jobs_kind_created",
        "ix_jobs_status_created",
        "ix_analysis_jobs_v1_retry_of_job_id",
    ):
        if name in indexes:
            op.drop_index(name, table_name="analysis_jobs_v1")
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("analysis_jobs_v1")}
    if "retry_of_job_id" in columns:
        op.drop_column("analysis_jobs_v1", "retry_of_job_id")
