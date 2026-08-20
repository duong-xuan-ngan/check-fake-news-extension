"""Create daily usage table for per-account check quota."""
from alembic import op
import sqlalchemy as sa

revision = "0003_daily_quota"
down_revision = "0002_users"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "usage",
        sa.Column("user_id", sa.String(), nullable=False),
        sa.Column("check_date", sa.Date(), nullable=False),
        sa.Column("checks_used", sa.Integer(), nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("user_id", "check_date"),
    )


def downgrade() -> None:
    op.drop_table("usage")
