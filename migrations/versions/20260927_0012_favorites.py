"""Saved conversation favorites."""
from alembic import op
import sqlalchemy as sa
revision = "20260927_0012"
down_revision = "20260927_0011"
branch_labels = None
depends_on = None

def upgrade():
    if "is_favorite" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("conversation_sessions")}:
        op.add_column("conversation_sessions", sa.Column("is_favorite", sa.Boolean(), nullable=False, server_default=sa.false()))

def downgrade():
    op.drop_column("conversation_sessions", "is_favorite")
