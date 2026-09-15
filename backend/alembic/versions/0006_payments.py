"""add payment customers, virtual accounts and webhook events"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0006_payments"
down_revision = "0005_kyc"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "payment_customer_profiles",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_customer_id", sa.String(length=160), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_payment_customer_profiles_user_id", "payment_customer_profiles", ["user_id"])

    op.create_table(
        "virtual_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("provider_account_id", sa.String(length=160), nullable=True),
        sa.Column("account_number", sa.String(length=32), nullable=False),
        sa.Column("bank_name", sa.String(length=120), nullable=False),
        sa.Column("bank_code", sa.String(length=32), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("account_type", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("reference", sa.String(length=160), nullable=False, unique=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
    )
    op.create_index("ix_virtual_accounts_user_id", "virtual_accounts", ["user_id"])
    op.create_index("ix_virtual_accounts_user_status", "virtual_accounts", ["user_id", "status"])

    op.create_table(
        "payment_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("transaction_type", sa.String(length=32), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("amount", sa.Numeric(18, 2), nullable=False),
        sa.Column("provider_reference", sa.String(length=160), nullable=True, unique=True),
        sa.Column("tx_ref", sa.String(length=160), nullable=False, unique=True),
        sa.Column("idempotency_key", sa.String(length=255), nullable=True, unique=True),
        sa.Column("raw_status", sa.String(length=64), nullable=True),
        sa.Column("failure_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_payment_user_status_created", "payment_transactions", ["user_id", "status", "created_at"])

    op.create_table(
        "webhook_events",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column("event_id", sa.String(length=160), nullable=True),
        sa.Column("event_type", sa.String(length=120), nullable=True),
        sa.Column("signature_valid", sa.Boolean(), nullable=False, server_default=sa.false()),
        sa.Column("payload_hash", sa.String(length=64), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("processing_error", sa.Text(), nullable=True),
        sa.Column("payload", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_webhook_provider_event", "webhook_events", ["provider", "event_id"])
    op.create_index("ix_webhook_payload_hash", "webhook_events", ["payload_hash"])


def downgrade() -> None:
    op.drop_index("ix_webhook_payload_hash", table_name="webhook_events")
    op.drop_index("ix_webhook_provider_event", table_name="webhook_events")
    op.drop_table("webhook_events")
    op.drop_index("ix_payment_user_status_created", table_name="payment_transactions")
    op.drop_table("payment_transactions")
    op.drop_index("ix_virtual_accounts_user_status", table_name="virtual_accounts")
    op.drop_index("ix_virtual_accounts_user_id", table_name="virtual_accounts")
    op.drop_table("virtual_accounts")
    op.drop_index("ix_payment_customer_profiles_user_id", table_name="payment_customer_profiles")
    op.drop_table("payment_customer_profiles")
