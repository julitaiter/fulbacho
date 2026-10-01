"""Global superusers, independent of group membership roles."""
from alembic import op
import sqlalchemy as sa

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column("users", sa.Column("is_superuser", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.alter_column("users", "is_active", server_default=sa.true())


def downgrade():
    op.alter_column("users", "is_active", server_default=None)
    op.drop_column("users", "is_superuser")
