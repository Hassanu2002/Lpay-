"""add authentication rate limit events

Revision ID: 0004_auth_rate_limit
Revises: 0003_authentication
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0004_auth_rate_limit"
down_revision = "0003_authentication"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "auth_rate_limit_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("bucket_key", sa.String(length=255), nullable=False),
        sa.Column("action", sa.String(length=40), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index(
        "ix_auth_rate_limit_bucket_created",
        "auth_rate_limit_events",
        ["bucket_key", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_auth_rate_limit_bucket_created", table_name="auth_rate_limit_events")
    op.drop_table("auth_rate_limit_events")
