"""Persist conversation tutor history."""
from alembic import op
import sqlalchemy as sa
revision = "20260927_0010"
down_revision = "20260927_0009"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table("tutor_conversations", sa.Column("session_id", sa.String(36), sa.ForeignKey("conversation_sessions.id", ondelete="CASCADE"), primary_key=True), sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False), sa.Column("messages", sa.JSON(), nullable=False), sa.Column("version", sa.Integer(), nullable=False))
    op.create_index("ix_tutor_conversations_owner_id", "tutor_conversations", ["owner_id"])

def downgrade():
    op.drop_table("tutor_conversations")
