"""Persist learner languages, preserving existing Chinese/English defaults."""
from alembic import op
import sqlalchemy as sa

revision = "20260927_0007"
down_revision = "20260926_0006"
branch_labels = None
depends_on = None


def upgrade():
    for table, columns in {
        "user_preferences": [("native_language", "zh"), ("target_language", "en")],
        "practices_v1": [("target_language", "en")],
        "conversation_sessions": [("target_language", "en")],
    }.items():
        existing = {c["name"] for c in sa.inspect(op.get_bind()).get_columns(table)}
        for name, default in columns:
            if name not in existing:
                op.add_column(table, sa.Column(name, sa.String(8), nullable=False, server_default=default))


def downgrade():
    op.drop_column("conversation_sessions", "target_language")
    op.drop_column("practices_v1", "target_language")
    op.drop_column("user_preferences", "target_language")
    op.drop_column("user_preferences", "native_language")
