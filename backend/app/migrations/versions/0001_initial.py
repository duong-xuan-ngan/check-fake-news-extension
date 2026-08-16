"""Create credibility and pipeline log tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sources",
        sa.Column("domain", sa.String(), primary_key=True),
        sa.Column("credibility_score", sa.Float(), nullable=False),
        sa.Column("category", sa.String(), nullable=False),
        sa.Column("last_updated", sa.Date()),
    )
    op.create_table(
        "pipeline_logs",
        sa.Column("id", sa.String(), primary_key=True),
        sa.Column("input_hash", sa.String(), nullable=False),
        sa.Column("timestamp", sa.String(), nullable=False),
        sa.Column("steps_completed", sa.Text()),
        sa.Column("verdict", sa.String()),
        sa.Column("error_stage", sa.String()),
        sa.Column("error_message", sa.Text()),
        sa.Column("response_time_ms", sa.Integer()),
    )


def downgrade() -> None:
    op.drop_table("pipeline_logs")
    op.drop_table("sources")
