"""Add account avatar."""
from alembic import op
import sqlalchemy as sa
revision = "20260927_0008"
down_revision = "20260927_0007"
branch_labels = None
depends_on = None

def upgrade():
    if "avatar" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}:
        op.add_column("users", sa.Column("avatar", sa.Text(), nullable=True))

def downgrade():
    op.drop_column("users", "avatar")
