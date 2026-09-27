"""User date display preference."""
from alembic import op
import sqlalchemy as sa
revision = "20260927_0011"
down_revision = "20260927_0010"
branch_labels = None
depends_on = None

def upgrade():
    if "date_format" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("user_preferences")}:
        op.add_column("user_preferences", sa.Column("date_format", sa.String(8), nullable=False, server_default="auto"))

def downgrade():
    op.drop_column("user_preferences", "date_format")
