"""add user profiles
Revision ID: 0002_user_profiles
Revises: 0001_initial_users
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0002_user_profiles"
down_revision = "0001_initial_users"
branch_labels = None
depends_on = None

def upgrade():
    op.create_table(
        "user_profiles",
        sa.Column("id", sa.Integer(), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.UniqueConstraint("user_id"),
    )
    op.create_index("ix_user_profiles_user_id", "user_profiles", ["user_id"])

def downgrade():
    op.drop_index("ix_user_profiles_user_id", table_name="user_profiles")
    op.drop_table("user_profiles")
