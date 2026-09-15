from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.wallet import WalletResponse, WalletTransactionResponse
from app.services.wallet import ensure_wallet, get_wallet_balance_kobo, kobo_to_ngn, list_wallet_transactions

router = APIRouter(prefix="/wallet")


@router.get("", response_model=WalletResponse)
async def get_wallet(user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    wallet = await ensure_wallet(db, user.id)
    balance = await get_wallet_balance_kobo(db, wallet)
    await db.commit()
    return WalletResponse(currency=wallet.currency, balance=kobo_to_ngn(balance), status=wallet.status)


@router.get("/transactions", response_model=list[WalletTransactionResponse])
async def get_wallet_transactions(
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    rows = await list_wallet_transactions(db, user_id=user.id, limit=limit, offset=offset)
    return [
        WalletTransactionResponse(
            id=str(row.id),
            transaction_type=row.transaction_type,
            status=row.status,
            amount=kobo_to_ngn(row.amount_kobo),
            currency=row.currency,
            reference=row.reference,
            provider_reference=row.provider_reference,
            description=row.description,
            created_at=row.created_at.isoformat(),
        )
        for row in rows
    ]
