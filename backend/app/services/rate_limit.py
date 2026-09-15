from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.rate_limit import AuthRateLimitEvent


async def enforce_rate_limit(
    db: AsyncSession,
    *,
    bucket_key: str,
    action: str,
    max_attempts: int,
    window_seconds: int,
) -> bool:
    cutoff = datetime.now(timezone.utc) - timedelta(seconds=window_seconds)
    count = await db.scalar(
        select(func.count())
        .select_from(AuthRateLimitEvent)
        .where(
            AuthRateLimitEvent.bucket_key == bucket_key,
            AuthRateLimitEvent.action == action,
            AuthRateLimitEvent.created_at >= cutoff,
        )
    )
    if count >= max_attempts:
        return False

    db.add(AuthRateLimitEvent(bucket_key=bucket_key, action=action))
    await db.flush()
    return True
