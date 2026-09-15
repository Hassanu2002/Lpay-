"""add KYC verification records"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0005_kyc"
down_revision = "0004_auth_rate_limit"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "kyc_verifications",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("method", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_reference", sa.String(length=160), nullable=True, unique=True),
        sa.Column("identifier_hash", sa.String(length=64), nullable=False),
        sa.Column("failure_code", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_kyc_user_id", "kyc_verifications", ["user_id"])
    op.create_index("ix_kyc_user_status", "kyc_verifications", ["user_id", "status"])
    op.create_index("ix_kyc_user_identifier_hash", "kyc_verifications", ["user_id", "identifier_hash"])


def downgrade() -> None:
    op.drop_index("ix_kyc_user_identifier_hash", table_name="kyc_verifications")
    op.drop_index("ix_kyc_user_status", table_name="kyc_verifications")
    op.drop_index("ix_kyc_user_id", table_name="kyc_verifications")
    op.drop_table("kyc_verifications")
