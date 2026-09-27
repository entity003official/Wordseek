"""Persist scene practice conversations and link them to practice statistics."""

from alembic import op
import sqlalchemy as sa

revision = "20260927_0014"
down_revision = "20260927_0013"
branch_labels = None
depends_on = None


def upgrade():
    if "practice_conversations" in sa.inspect(op.get_bind()).get_table_names():
        return
    op.create_table(
        "practice_conversations",
        sa.Column("id", sa.String(36), primary_key=True),
        sa.Column("owner_id", sa.String(36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("practice_id", sa.String(36), sa.ForeignKey("practices_v1.id", ondelete="CASCADE"), nullable=False),
        sa.Column("scene_id", sa.String(160), nullable=False),
        sa.Column("target_language", sa.String(8), nullable=False),
        sa.Column("messages", sa.JSON(), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.UniqueConstraint("owner_id", "scene_id", "target_language", name="uq_practice_conversation_scene"),
    )
    op.create_index("ix_practice_conversations_owner_id", "practice_conversations", ["owner_id"])
    op.create_index("ix_practice_conversations_practice_id", "practice_conversations", ["practice_id"])
    op.create_index("ix_practice_conversations_scene_id", "practice_conversations", ["scene_id"])


def downgrade():
    op.drop_table("practice_conversations")
