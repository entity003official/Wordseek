"""Store consented local speaker embeddings."""
from alembic import op
import sqlalchemy as sa
revision = "20260927_0009"
down_revision = "20260927_0008"
branch_labels = None
depends_on = None

def upgrade():
    if "voiceprint_json" not in {c["name"] for c in sa.inspect(op.get_bind()).get_columns("users")}:
        op.add_column("users", sa.Column("voiceprint_json", sa.JSON(), nullable=True))

def downgrade():
    op.drop_column("users", "voiceprint_json")
