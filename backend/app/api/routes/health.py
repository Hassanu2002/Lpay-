from fastapi import APIRouter, HTTPException, status
from sqlalchemy import text

from app.core.database import engine

router = APIRouter()


@router.get("")
async def health():
    return {"status": "ok", "service": "labour-pay-api"}


@router.get("/ready")
async def readiness():
    try:
        async with engine.connect() as conn:
            await conn.execute(text("SELECT 1"))
    except Exception:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service is not ready.",
        )

    return {"status": "ready", "database": "ok"}
