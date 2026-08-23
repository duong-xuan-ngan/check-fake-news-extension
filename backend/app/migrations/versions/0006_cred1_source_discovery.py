"""Add CRED-1 provenance and discovery queue for unrated domains."""
from alembic import op
import sqlalchemy as sa

revision = "0006_cred1_source_discovery"
down_revision = "0005_refresh_tokens"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("sources", sa.Column("rating_source", sa.String(), nullable=True))
    op.add_column("sources", sa.Column("source_count", sa.Integer(), nullable=True))
    op.add_column("sources", sa.Column("source_version", sa.String(), nullable=True))

    op.create_table(
        "source_candidates",
        sa.Column("domain", sa.String(), primary_key=True),
        sa.Column("sample_url", sa.Text(), nullable=True),
        sa.Column("discovery_source", sa.String(), nullable=False, server_default="serper_google"),
        sa.Column("review_status", sa.String(), nullable=False, server_default="pending"),
        sa.Column("discovery_count", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("first_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_source_candidates_review_priority",
        "source_candidates",
        ["review_status", "discovery_count", "last_seen_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_source_candidates_review_priority", table_name="source_candidates")
    op.drop_table("source_candidates")
    op.drop_column("sources", "source_version")
    op.drop_column("sources", "source_count")
    op.drop_column("sources", "rating_source")
