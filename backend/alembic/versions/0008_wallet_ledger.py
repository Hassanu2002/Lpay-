"""add immutable wallet ledger and funding limits"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "0008_wallet_ledger"
down_revision = "0007_profile_uuid"
branch_labels = None
depends_on = None

SYSTEM_ACCOUNTS = {
    "funding": "7e6d4f24-3f73-4d64-a0d3-7b9a2b4c6f01",
    "service": "7e6d4f24-3f73-4d64-a0d3-7b9a2b4c6f02",
}


def upgrade() -> None:
    # Phase 3 used non-unique webhook indexes. Make replay identity unique before
    # the ledger starts trusting a verified webhook. Existing duplicate rows are
    # intentionally not auto-deleted here; production operators must reconcile
    # them before applying this migration if any exist.
    op.drop_index("ix_webhook_provider_event", table_name="webhook_events")
    op.drop_index("ix_webhook_payload_hash", table_name="webhook_events")
    op.create_index("uq_webhook_provider_event", "webhook_events", ["provider", "event_id"], unique=True)
    op.create_index("uq_webhook_provider_payload_hash", "webhook_events", ["provider", "payload_hash"], unique=True)
    op.create_table(
        "ledger_accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("code", sa.String(80), nullable=False, unique=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("account_type", sa.String(16), nullable=False),
        sa.Column("owner_user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("is_system", sa.Boolean(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("account_type IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')", name="ck_ledger_account_type"),
        sa.CheckConstraint("currency = 'NGN'", name="ck_ledger_account_currency_ngn"),
        sa.CheckConstraint("(is_system = true AND owner_user_id IS NULL) OR (is_system = false AND owner_user_id IS NOT NULL)", name="ck_ledger_account_owner"),
    )
    op.create_index("ix_ledger_accounts_owner_user_id", "ledger_accounts", ["owner_user_id"])

    op.create_table(
        "wallets",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("ledger_account_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ledger_account_id"], ["ledger_accounts.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("currency = 'NGN'", name="ck_wallet_currency_ngn"),
        sa.CheckConstraint("status IN ('ACTIVE','FROZEN','CLOSED')", name="ck_wallet_status"),
    )
    op.create_index("ix_wallets_user_id", "wallets", ["user_id"])

    op.create_table(
        "ledger_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("reference", sa.String(160), nullable=False, unique=True),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("status", sa.String(16), nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status = 'POSTED'", name="ck_ledger_transaction_status_posted"),
        sa.CheckConstraint("currency = 'NGN'", name="ck_ledger_transaction_currency_ngn"),
    )
    op.create_index("ix_ledger_transactions_user_id", "ledger_transactions", ["user_id"])

    op.create_table(
        "ledger_entries",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("ledger_transaction_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ledger_account_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("direction", sa.String(6), nullable=False),
        sa.Column("amount_kobo", sa.BigInteger(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["ledger_transaction_id"], ["ledger_transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ledger_account_id"], ["ledger_accounts.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("direction IN ('DEBIT','CREDIT')", name="ck_ledger_entry_direction"),
        sa.CheckConstraint("amount_kobo > 0", name="ck_ledger_entry_amount_positive"),
    )
    op.create_index("ix_ledger_entries_ledger_transaction_id", "ledger_entries", ["ledger_transaction_id"])
    op.create_index("ix_ledger_entries_ledger_account_id", "ledger_entries", ["ledger_account_id"])
    op.create_index("ix_ledger_entries_transaction_account", "ledger_entries", ["ledger_transaction_id", "ledger_account_id"])

    op.create_table(
        "wallet_transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("wallet_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("ledger_transaction_id", postgresql.UUID(as_uuid=True), nullable=False, unique=True),
        sa.Column("transaction_type", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), nullable=False),
        sa.Column("amount_kobo", sa.BigInteger(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("reference", sa.String(160), nullable=False, unique=True),
        sa.Column("provider_reference", sa.String(160), nullable=True, unique=True),
        sa.Column("related_transaction_id", postgresql.UUID(as_uuid=True), nullable=True, unique=True),
        sa.Column("description", sa.String(255), nullable=False),
        sa.Column("metadata", postgresql.JSONB(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["wallet_id"], ["wallets.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ledger_transaction_id"], ["ledger_transactions.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["related_transaction_id"], ["wallet_transactions.id"], ondelete="RESTRICT"),
        sa.CheckConstraint("status IN ('PENDING','SUCCESS','FAILED','REFUNDED','REVERSED')", name="ck_wallet_tx_status"),
        sa.CheckConstraint("amount_kobo > 0", name="ck_wallet_tx_amount_positive"),
        sa.CheckConstraint("currency = 'NGN'", name="ck_wallet_tx_currency_ngn"),
    )
    op.create_index("ix_wallet_transactions_user_created", "wallet_transactions", ["user_id", "created_at"])
    op.create_index("ix_wallet_transactions_user_type_created", "wallet_transactions", ["user_id", "transaction_type", "created_at"])

    op.create_table(
        "idempotency_keys",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("operation", sa.String(40), nullable=False),
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("ledger_transaction_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["ledger_transaction_id"], ["ledger_transactions.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("user_id", "operation", "key_hash", name="uq_idempotency_user_operation_hash"),
    )

    op.create_table(
        "wallet_limits",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, nullable=False),
        sa.Column("scope", sa.String(32), nullable=False, unique=True),
        sa.Column("min_funding_kobo", sa.BigInteger(), nullable=False),
        sa.Column("max_funding_kobo", sa.BigInteger(), nullable=False),
        sa.Column("daily_funding_kobo", sa.BigInteger(), nullable=False),
        sa.Column("monthly_funding_kobo", sa.BigInteger(), nullable=False),
        sa.Column("max_wallet_balance_kobo", sa.BigInteger(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("min_funding_kobo > 0", name="ck_wallet_limit_min_positive"),
        sa.CheckConstraint("max_funding_kobo >= min_funding_kobo", name="ck_wallet_limit_max_ge_min"),
        sa.CheckConstraint("daily_funding_kobo >= max_funding_kobo", name="ck_wallet_limit_daily_ge_max"),
        sa.CheckConstraint("monthly_funding_kobo >= daily_funding_kobo", name="ck_wallet_limit_monthly_ge_daily"),
        sa.CheckConstraint("max_wallet_balance_kobo >= max_funding_kobo", name="ck_wallet_limit_balance_ge_max"),
    )

    op.execute(
        "INSERT INTO ledger_accounts (id, code, name, account_type, owner_user_id, currency, is_system, is_active) "
        f"VALUES ('{SYSTEM_ACCOUNTS['funding']}', 'SYSTEM:FUNDING_CLEARING', 'Funding clearing', 'ASSET', NULL, 'NGN', true, true)"
    )
    op.execute(
        "INSERT INTO ledger_accounts (id, code, name, account_type, owner_user_id, currency, is_system, is_active) "
        f"VALUES ('{SYSTEM_ACCOUNTS['service']}', 'SYSTEM:SERVICE_PAYABLE', 'Service payable', 'LIABILITY', NULL, 'NGN', true, true)"
    )
    op.execute(
        "INSERT INTO wallet_limits (id, scope, min_funding_kobo, max_funding_kobo, daily_funding_kobo, monthly_funding_kobo, max_wallet_balance_kobo) "
        "VALUES ('6f9d11b2-6f6a-49fb-9d3a-4fd8b4f77e01', 'GLOBAL', 10000, 10000000, 100000000, 500000000, 200000000)"
    )


def downgrade() -> None:
    op.drop_index("uq_webhook_provider_payload_hash", table_name="webhook_events")
    op.drop_index("uq_webhook_provider_event", table_name="webhook_events")
    op.create_index("ix_webhook_provider_event", "webhook_events", ["provider", "event_id"])
    op.create_index("ix_webhook_payload_hash", "webhook_events", ["payload_hash"])
    op.drop_table("wallet_limits")
    op.drop_table("idempotency_keys")
    op.drop_index("ix_wallet_transactions_user_type_created", table_name="wallet_transactions")
    op.drop_index("ix_wallet_transactions_user_created", table_name="wallet_transactions")
    op.drop_table("wallet_transactions")
    op.drop_index("ix_ledger_entries_transaction_account", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_ledger_account_id", table_name="ledger_entries")
    op.drop_index("ix_ledger_entries_ledger_transaction_id", table_name="ledger_entries")
    op.drop_table("ledger_entries")
    op.drop_index("ix_ledger_transactions_user_id", table_name="ledger_transactions")
    op.drop_table("ledger_transactions")
    op.drop_index("ix_wallets_user_id", table_name="wallets")
    op.drop_table("wallets")
    op.drop_index("ix_ledger_accounts_owner_user_id", table_name="ledger_accounts")
    op.drop_table("ledger_accounts")
