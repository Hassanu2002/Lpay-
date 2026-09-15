import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Index, Numeric, String, Text, func
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class CustomerProfile(Base):
    __tablename__ = "payment_customer_profiles"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), unique=True, nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_customer_id: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )


class VirtualAccount(Base):
    __tablename__ = "virtual_accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    provider_account_id: Mapped[str | None] = mapped_column(String(160))
    account_number: Mapped[str] = mapped_column(String(32), nullable=False)
    bank_name: Mapped[str] = mapped_column(String(120), nullable=False)
    bank_code: Mapped[str | None] = mapped_column(String(32))
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    account_type: Mapped[str] = mapped_column(String(16), nullable=False, default="static")
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="ACTIVE")
    reference: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_virtual_accounts_user_status", "user_id", "status"),)


class PaymentTransaction(Base):
    __tablename__ = "payment_transactions"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    transaction_type: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="PENDING")
    currency: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    amount: Mapped[object] = mapped_column(Numeric(18, 2), nullable=False)
    provider_reference: Mapped[str | None] = mapped_column(String(160), unique=True)
    tx_ref: Mapped[str] = mapped_column(String(160), unique=True, nullable=False)
    idempotency_key: Mapped[str | None] = mapped_column(String(255), unique=True)
    raw_status: Mapped[str | None] = mapped_column(String(64))
    failure_reason: Mapped[str | None] = mapped_column(Text())
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    __table_args__ = (Index("ix_payment_user_status_created", "user_id", "status", "created_at"),)


class WebhookEvent(Base):
    __tablename__ = "webhook_events"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    event_id: Mapped[str | None] = mapped_column(String(160))
    event_type: Mapped[str | None] = mapped_column(String(120))
    signature_valid: Mapped[bool] = mapped_column(nullable=False, default=False)
    payload_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(24), nullable=False, default="RECEIVED")
    processing_error: Mapped[str | None] = mapped_column(Text())
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    __table_args__ = (
        Index("ix_webhook_provider_event", "provider", "event_id"),
        Index("ix_webhook_payload_hash", "payload_hash"),
    )
