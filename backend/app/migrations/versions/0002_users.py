"""Create users table and link pipeline logs to users."""
from alembic import op
import sqlalchemy as sa

revision = "0002_users"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("google_sub", sa.String(), nullable=False, unique=True),
        sa.Column("email", sa.String()),
        sa.Column("name", sa.String()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now()),
    )
    op.add_column("pipeline_logs", sa.Column("user_id", sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column("pipeline_logs", "user_id")
    op.drop_table("users")
