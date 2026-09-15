import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from decimal import Decimal, ROUND_HALF_UP
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.user import User
from app.models.wallet import (
    IdempotencyKey,
    LedgerAccount,
    LedgerEntry,
    LedgerTransaction,
    Wallet,
    WalletLimit,
    WalletTransaction,
)

NGN = "NGN"
LAGOS = ZoneInfo("Africa/Lagos")


def amount_to_kobo(value: str | int | Decimal) -> int:
    if isinstance(value, int):
        if value <= 0:
            raise ValueError("Amount must be positive")
        return value
    try:
        amount = Decimal(str(value)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except Exception as exc:
        raise ValueError("Invalid amount") from exc
    if amount <= 0:
        raise ValueError("Amount must be positive")
    return int(amount * 100)


def kobo_to_ngn(kobo: int) -> Decimal:
    return (Decimal(kobo) / Decimal(100)).quantize(Decimal("0.01"))


def _hash_idempotency(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


async def _get_or_create_system_account(db: AsyncSession, code: str, name: str, account_type: str) -> LedgerAccount:
    account = await db.scalar(select(LedgerAccount).where(LedgerAccount.code == code).with_for_update())
    if account:
        return account
    account = LedgerAccount(code=code, name=name, account_type=account_type, is_system=True, owner_user_id=None, currency=NGN)
    db.add(account)
    await db.flush()
    return account


async def ensure_wallet(db: AsyncSession, user_id: uuid.UUID, *, lock: bool = False) -> Wallet:
    stmt = select(Wallet).where(Wallet.user_id == user_id)
    if lock:
        stmt = stmt.with_for_update()
    wallet = await db.scalar(stmt)
    if wallet:
        return wallet

    # Lock the parent user row so two concurrent requests cannot both create the wallet/account pair.
    user = await db.scalar(select(User).where(User.id == user_id).with_for_update())
    if not user:
        raise ValueError("User not found")
    wallet = await db.scalar(select(Wallet).where(Wallet.user_id == user_id).with_for_update())
    if wallet:
        return wallet

    account = LedgerAccount(
        code=f"USER_WALLET:{user_id}",
        name=f"Labour Pay wallet for {user_id}",
        account_type="LIABILITY",
        owner_user_id=user_id,
        currency=NGN,
        is_system=False,
    )
    db.add(account)
    await db.flush()
    wallet = Wallet(user_id=user_id, ledger_account_id=account.id, currency=NGN, status="ACTIVE")
    db.add(wallet)
    await db.flush()
    return wallet


async def get_wallet_balance_kobo(db: AsyncSession, wallet: Wallet) -> int:
    credit = func.coalesce(func.sum(case((LedgerEntry.direction == "CREDIT", LedgerEntry.amount_kobo), else_=0)), 0)
    debit = func.coalesce(func.sum(case((LedgerEntry.direction == "DEBIT", LedgerEntry.amount_kobo), else_=0)), 0)
    row = await db.execute(
        select(credit.label("credit"), debit.label("debit"))
        .where(LedgerEntry.ledger_account_id == wallet.ledger_account_id)
    )
    result = row.one()
    return int(result.credit) - int(result.debit)


async def get_wallet_limits(db: AsyncSession) -> WalletLimit:
    limits = await db.scalar(select(WalletLimit).where(WalletLimit.scope == "GLOBAL"))
    if not limits:
        limits = WalletLimit(
            scope="GLOBAL",
            min_funding_kobo=10_000,
            max_funding_kobo=10_000_000,
            daily_funding_kobo=100_000_000,
            monthly_funding_kobo=500_000_000,
            max_wallet_balance_kobo=200_000_000,
        )
        db.add(limits)
        await db.flush()
    return limits


async def _funding_sum_since(db: AsyncSession, user_id: uuid.UUID, start: datetime) -> int:
    value = await db.scalar(
        select(func.coalesce(func.sum(WalletTransaction.amount_kobo), 0)).where(
            WalletTransaction.user_id == user_id,
            WalletTransaction.transaction_type == "FUNDING",
            WalletTransaction.status == "SUCCESS",
            WalletTransaction.created_at >= start,
        )
    )
    return int(value or 0)


async def _create_idempotency(db: AsyncSession, *, user_id: uuid.UUID, operation: str, key: str) -> IdempotencyKey:
    digest = _hash_idempotency(key)
    stmt = insert(IdempotencyKey).values(user_id=user_id, operation=operation, key_hash=digest).on_conflict_do_nothing(
        index_elements=["user_id", "operation", "key_hash"]
    )
    await db.execute(stmt)
    record = await db.scalar(
        select(IdempotencyKey).where(
            IdempotencyKey.user_id == user_id,
            IdempotencyKey.operation == operation,
            IdempotencyKey.key_hash == digest,
        ).with_for_update()
    )
    if not record:
        raise RuntimeError("Unable to establish idempotency record")
    return record


async def _post_balanced_transaction(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    wallet: Wallet,
    operation: str,
    reference: str,
    description: str,
    amount_kobo: int,
    debit_account: LedgerAccount,
    credit_account: LedgerAccount,
    wallet_tx_type: str,
    provider_reference: str | None,
    metadata: dict,
    related_transaction_id: uuid.UUID | None = None,
) -> WalletTransaction:
    if amount_kobo <= 0:
        raise ValueError("Amount must be positive")
    if debit_account.currency != NGN or credit_account.currency != NGN:
        raise ValueError("Only NGN ledger accounts are supported")

    ledger_tx = LedgerTransaction(
        reference=reference,
        operation=operation,
        status="POSTED",
        user_id=user_id,
        currency=NGN,
        description=description,
        extra_metadata=metadata,
    )
    db.add(ledger_tx)
    await db.flush()

    db.add_all([
        LedgerEntry(ledger_transaction_id=ledger_tx.id, ledger_account_id=debit_account.id, direction="DEBIT", amount_kobo=amount_kobo),
        LedgerEntry(ledger_transaction_id=ledger_tx.id, ledger_account_id=credit_account.id, direction="CREDIT", amount_kobo=amount_kobo),
    ])
    wallet_tx = WalletTransaction(
        user_id=user_id,
        wallet_id=wallet.id,
        ledger_transaction_id=ledger_tx.id,
        transaction_type=wallet_tx_type,
        status="SUCCESS",
        amount_kobo=amount_kobo,
        currency=NGN,
        reference=reference,
        provider_reference=provider_reference,
        related_transaction_id=related_transaction_id,
        description=description,
        extra_metadata=metadata,
    )
    db.add(wallet_tx)
    await db.flush()
    return wallet_tx


async def credit_wallet_from_verified_funding(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount_kobo: int,
    provider_reference: str,
    tx_ref: str,
    metadata: dict | None = None,
) -> WalletTransaction:
    wallet = await ensure_wallet(db, user_id, lock=True)
    if wallet.status != "ACTIVE":
        raise PermissionError("Wallet is not active")

    idempotency = await _create_idempotency(db, user_id=user_id, operation="WALLET_FUNDING", key=f"flutterwave:{provider_reference}")
    if idempotency.ledger_transaction_id:
        existing = await db.scalar(select(WalletTransaction).where(WalletTransaction.ledger_transaction_id == idempotency.ledger_transaction_id))
        if existing:
            return existing

    limits = await get_wallet_limits(db)
    if amount_kobo < limits.min_funding_kobo:
        raise ValueError("Funding amount is below the minimum allowed")
    if amount_kobo > limits.max_funding_kobo:
        raise ValueError("Funding amount exceeds the maximum allowed per transaction")

    balance = await get_wallet_balance_kobo(db, wallet)
    if balance + amount_kobo > limits.max_wallet_balance_kobo:
        raise ValueError("Funding would exceed the maximum wallet balance")

    now = datetime.now(timezone.utc)
    local_now = now.astimezone(LAGOS)
    day_start_local = local_now.replace(hour=0, minute=0, second=0, microsecond=0)
    month_start_local = local_now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    day_start = day_start_local.astimezone(timezone.utc)
    month_start = month_start_local.astimezone(timezone.utc)
    if await _funding_sum_since(db, user_id, day_start) + amount_kobo > limits.daily_funding_kobo:
        raise ValueError("Daily funding limit exceeded")
    if await _funding_sum_since(db, user_id, month_start) + amount_kobo > limits.monthly_funding_kobo:
        raise ValueError("Monthly funding limit exceeded")

    clearing = await _get_or_create_system_account(db, "SYSTEM:FUNDING_CLEARING", "Funding clearing", "ASSET")
    wallet_account = await db.scalar(select(LedgerAccount).where(LedgerAccount.id == wallet.ledger_account_id).with_for_update())
    if not wallet_account:
        raise RuntimeError("Wallet ledger account not found")

    wallet_tx = await _post_balanced_transaction(
        db,
        user_id=user_id,
        wallet=wallet,
        operation="FUNDING",
        reference=f"WALLET-FUND-{uuid.uuid4().hex}",
        description="Wallet funding received",
        amount_kobo=amount_kobo,
        debit_account=clearing,
        credit_account=wallet_account,
        wallet_tx_type="FUNDING",
        provider_reference=provider_reference,
        metadata={"tx_ref": tx_ref, **(metadata or {})},
    )
    idempotency.ledger_transaction_id = wallet_tx.ledger_transaction_id
    await db.flush()
    return wallet_tx


async def debit_wallet(
    db: AsyncSession,
    *,
    user_id: uuid.UUID,
    amount_kobo: int,
    idempotency_key: str,
    transaction_type: str,
    description: str,
    provider_reference: str | None = None,
    metadata: dict | None = None,
) -> WalletTransaction:
    wallet = await ensure_wallet(db, user_id, lock=True)
    if wallet.status != "ACTIVE":
        raise PermissionError("Wallet is not active")

    idempotency = await _create_idempotency(db, user_id=user_id, operation="WALLET_DEBIT", key=idempotency_key)
    if idempotency.ledger_transaction_id:
        existing = await db.scalar(select(WalletTransaction).where(WalletTransaction.ledger_transaction_id == idempotency.ledger_transaction_id))
        if existing:
            return existing

    balance = await get_wallet_balance_kobo(db, wallet)
    if amount_kobo <= 0:
        raise ValueError("Amount must be positive")
    if amount_kobo > balance:
        raise ValueError("Insufficient wallet balance")

    wallet_account = await db.scalar(select(LedgerAccount).where(LedgerAccount.id == wallet.ledger_account_id).with_for_update())
    service_payable = await _get_or_create_system_account(db, "SYSTEM:SERVICE_PAYABLE", "Service payable", "LIABILITY")
    wallet_tx = await _post_balanced_transaction(
        db,
        user_id=user_id,
        wallet=wallet,
        operation="DEBIT",
        reference=f"WALLET-DEBIT-{uuid.uuid4().hex}",
        description=description,
        amount_kobo=amount_kobo,
        debit_account=wallet_account,
        credit_account=service_payable,
        wallet_tx_type=transaction_type,
        provider_reference=provider_reference,
        metadata=metadata or {},
    )
    idempotency.ledger_transaction_id = wallet_tx.ledger_transaction_id
    await db.flush()
    return wallet_tx


async def refund_wallet_debit(
    db: AsyncSession,
    *,
    original_wallet_transaction_id: uuid.UUID,
    idempotency_key: str,
    reason: str,
) -> WalletTransaction:
    original = await db.scalar(select(WalletTransaction).where(WalletTransaction.id == original_wallet_transaction_id))
    if not original:
        raise ValueError("Original wallet transaction not found")
    if original.transaction_type == "FUNDING":
        raise ValueError("Funding transactions must not be refunded through the purchase refund path")

    existing_refund = await db.scalar(
        select(WalletTransaction).where(WalletTransaction.related_transaction_id == original.id)
    )
    if existing_refund:
        return existing_refund

    idempotency = await _create_idempotency(db, user_id=original.user_id, operation="WALLET_REFUND", key=idempotency_key)
    if idempotency.ledger_transaction_id:
        existing = await db.scalar(select(WalletTransaction).where(WalletTransaction.ledger_transaction_id == idempotency.ledger_transaction_id))
        if existing:
            return existing

    wallet = await ensure_wallet(db, original.user_id, lock=True)
    wallet_account = await db.scalar(select(LedgerAccount).where(LedgerAccount.id == wallet.ledger_account_id).with_for_update())
    service_payable = await _get_or_create_system_account(db, "SYSTEM:SERVICE_PAYABLE", "Service payable", "LIABILITY")
    wallet_tx = await _post_balanced_transaction(
        db,
        user_id=original.user_id,
        wallet=wallet,
        operation="REFUND",
        reference=f"WALLET-REFUND-{uuid.uuid4().hex}",
        description=reason,
        amount_kobo=original.amount_kobo,
        debit_account=service_payable,
        credit_account=wallet_account,
        wallet_tx_type="REFUND",
        provider_reference=None,
        metadata={"original_wallet_transaction_id": str(original.id)},
        related_transaction_id=original.id,
    )
    idempotency.ledger_transaction_id = wallet_tx.ledger_transaction_id
    await db.flush()
    return wallet_tx


async def list_wallet_transactions(db: AsyncSession, *, user_id: uuid.UUID, limit: int = 50, offset: int = 0) -> list[WalletTransaction]:
    result = await db.scalars(
        select(WalletTransaction)
        .where(WalletTransaction.user_id == user_id)
        .order_by(WalletTransaction.created_at.desc())
        .limit(min(limit, 100))
        .offset(max(offset, 0))
    )
    return list(result)
