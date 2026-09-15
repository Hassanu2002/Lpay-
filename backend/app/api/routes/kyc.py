from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from app.dependencies import get_current_user, get_db
from app.models.user import User
from app.schemas.kyc import KYCResponse, KYCSubmitRequest
from app.services.kyc import submit_kyc

router = APIRouter(prefix="/kyc")


@router.post("/verify", response_model=KYCResponse)
async def verify_kyc(payload: KYCSubmitRequest, user: User = Depends(get_current_user), db: AsyncSession = Depends(get_db)):
    try:
        record = await submit_kyc(db, user=user, method=payload.method, value=payload.value)
        await db.commit()
    except ValueError as exc:
        await db.rollback()
        raise HTTPException(status_code=422, detail=str(exc))
    except Exception:
        await db.rollback()
        raise HTTPException(status_code=502, detail="KYC provider is temporarily unavailable")

    return KYCResponse(
        id=str(record.id),
        method=record.method,
        status=record.status,
        provider=record.provider,
        provider_reference=record.provider_reference or "",
        verified_at=record.verified_at.isoformat() if record.verified_at else None,
    )
