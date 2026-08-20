"""Add Google profile picture to users."""
from alembic import op
import sqlalchemy as sa

revision = "0004_user_picture"
down_revision = "0003_daily_quota"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("users", sa.Column("picture", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("users", "picture")
