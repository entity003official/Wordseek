"""Weekly vocabulary and sentences."""
from alembic import op
import sqlalchemy as sa
revision = "20260927_0013"
down_revision = "20260927_0012"
branch_labels = None
depends_on = None

def upgrade():
    if "weekly_entries" not in sa.inspect(op.get_bind()).get_table_names():
        op.create_table("weekly_entries", sa.Column("id", sa.String(36), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("week", sa.String(10), nullable=False), sa.Column("kind", sa.String(12), nullable=False), sa.Column("text", sa.String(1000), nullable=False), sa.Column("note", sa.String(500), nullable=False), sa.Column("created_at", sa.DateTime(timezone=True), nullable=False))
        op.create_index("ix_weekly_entries_owner_id", "weekly_entries", ["owner_id"])
        op.create_index("ix_weekly_entries_week", "weekly_entries", ["week"])

def downgrade():
    op.drop_table("weekly_entries")
