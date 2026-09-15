from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.payment import VirtualAccountRequest, VirtualAccountResponse
from app.services.payments import create_or_get_virtual_account

router = APIRouter(prefix="/payments")


@router.post("/virtual-account", response_model=VirtualAccountResponse)
async def create_virtual_account(
    payload: VirtualAccountRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    try:
        account = await create_or_get_virtual_account(
            db, user, verified_identifier=payload.verified_identifier
        )
        await db.commit()
    except PermissionError as exc:
        await db.rollback()
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=502, detail="Payment provider is temporarily unavailable")

    return VirtualAccountResponse(
        account_number=account.account_number,
        bank_name=account.bank_name,
        bank_code=account.bank_code,
        currency=account.currency,
        account_type=account.account_type,
        status=account.status,
        reference=account.reference,
    )
