import uuid
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, CheckConstraint, DateTime, ForeignKey, Index, Integer, JSON, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Wallet(Base):
    __tablename__ = "wallets"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), unique=True, nullable=False)
    ledger_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledger_accounts.id", ondelete="RESTRICT"), unique=True, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        Index("ix_wallets_user_id", "user_id"),
        CheckConstraint("currency = 'NGN'", name="ck_wallet_currency_ngn"),
        CheckConstraint("status IN ('ACTIVE','FROZEN','CLOSED')", name="ck_wallet_status"),
    )


class LedgerAccount(Base):
    __tablename__ = "ledger_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    code: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    account_type: Mapped[str] = mapped_column(String(16), nullable=False)
    owner_user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("account_type IN ('ASSET','LIABILITY','EQUITY','REVENUE','EXPENSE')", name="ck_ledger_account_type"),
        CheckConstraint("currency = 'NGN'", name="ck_ledger_account_currency_ngn"),
        CheckConstraint("(is_system = true AND owner_user_id IS NULL) OR (is_system = false AND owner_user_id IS NOT NULL)", name="ck_ledger_account_owner"),
    )


class LedgerTransaction(Base):
    __tablename__ = "ledger_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    reference: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="POSTED")
    user_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, index=True)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status = 'POSTED'", name="ck_ledger_transaction_status_posted"),
        CheckConstraint("currency = 'NGN'", name="ck_ledger_transaction_currency_ngn"),
    )


class LedgerEntry(Base):
    __tablename__ = "ledger_entries"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    ledger_transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), nullable=False, index=True)
    ledger_account_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledger_accounts.id", ondelete="RESTRICT"), nullable=False, index=True)
    direction: Mapped[str] = mapped_column(String(6), nullable=False)
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("direction IN ('DEBIT','CREDIT')", name="ck_ledger_entry_direction"),
        CheckConstraint("amount_kobo > 0", name="ck_ledger_entry_amount_positive"),
        Index("ix_ledger_entries_transaction_account", "ledger_transaction_id", "ledger_account_id"),
    )


class WalletTransaction(Base):
    __tablename__ = "wallet_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    wallet_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("wallets.id", ondelete="RESTRICT"), nullable=False)
    ledger_transaction_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), unique=True, nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="SUCCESS")
    amount_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    reference: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(160), unique=True)
    related_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("wallet_transactions.id", ondelete="RESTRICT"), unique=True, nullable=True)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    extra_metadata: Mapped[dict] = mapped_column("metadata", JSONB, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("status IN ('PENDING','SUCCESS','FAILED','REFUNDED','REVERSED')", name="ck_wallet_tx_status"),
        CheckConstraint("amount_kobo > 0", name="ck_wallet_tx_amount_positive"),
        CheckConstraint("currency = 'NGN'", name="ck_wallet_tx_currency_ngn"),
        Index("ix_wallet_transactions_user_created", "user_id", "created_at"),
        Index("ix_wallet_transactions_user_type_created", "user_id", "transaction_type", "created_at"),
    )


class IdempotencyKey(Base):
    __tablename__ = "idempotency_keys"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    operation: Mapped[str] = mapped_column(String(40), nullable=False)
    key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    ledger_transaction_id: Mapped[uuid.UUID | None] = mapped_column(ForeignKey("ledger_transactions.id", ondelete="RESTRICT"), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    __table_args__ = (
        UniqueConstraint("user_id", "operation", "key_hash", name="uq_idempotency_user_operation_hash"),
    )


class WalletLimit(Base):
    __tablename__ = "wallet_limits"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    scope: Mapped[str] = mapped_column(String(32), unique=True, nullable=False, default="GLOBAL")
    min_funding_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_funding_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    daily_funding_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    monthly_funding_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    max_wallet_balance_kobo: Mapped[int] = mapped_column(BigInteger, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)

    __table_args__ = (
        CheckConstraint("min_funding_kobo > 0", name="ck_wallet_limit_min_positive"),
        CheckConstraint("max_funding_kobo >= min_funding_kobo", name="ck_wallet_limit_max_ge_min"),
        CheckConstraint("daily_funding_kobo >= max_funding_kobo", name="ck_wallet_limit_daily_ge_max"),
        CheckConstraint("monthly_funding_kobo >= daily_funding_kobo", name="ck_wallet_limit_monthly_ge_daily"),
        CheckConstraint("max_wallet_balance_kobo >= max_funding_kobo", name="ck_wallet_limit_balance_ge_max"),
    )
