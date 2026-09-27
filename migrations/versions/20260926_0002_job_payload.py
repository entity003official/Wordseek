"""Add payload and result snapshots to durable analysis jobs.

Revision ID: 20260926_0002
Revises: 20260926_0001
"""
import sqlalchemy as sa
from alembic import op


revision = "20260926_0002"
down_revision = "20260926_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("analysis_jobs_v1")}
    if "payload_json" not in columns:
        op.add_column("analysis_jobs_v1", sa.Column("payload_json", sa.JSON(), nullable=False, server_default="{}"))
    if "result_json" not in columns:
        op.add_column("analysis_jobs_v1", sa.Column("result_json", sa.JSON(), nullable=True))


def downgrade() -> None:
    columns = {column["name"] for column in sa.inspect(op.get_bind()).get_columns("analysis_jobs_v1")}
    if "result_json" in columns:
        op.drop_column("analysis_jobs_v1", "result_json")
    if "payload_json" in columns:
        op.drop_column("analysis_jobs_v1", "payload_json")
