import hashlib
import re
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.kyc import KYCVerification
from app.models.user import User
from app.providers.factory import identity_provider


def identifier_hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _valid_number(value: str) -> bool:
    return bool(re.fullmatch(r"[1-9][0-9]{10}", value))


async def submit_kyc(db: AsyncSession, *, user: User, method: str, value: str) -> KYCVerification:
    method = method.upper()
    if method not in {"BVN", "NIN"} or not _valid_number(value):
        raise ValueError("Invalid KYC number")

    reference = "KYC-" + uuid.uuid4().hex
    provider = identity_provider()
    record = KYCVerification(
        user_id=user.id,
        method=method,
        status="PROCESSING",
        provider=getattr(provider, "name", "unknown"),
        provider_reference=reference,
        identifier_hash=identifier_hash(value),
    )
    db.add(record)
    await db.flush()

    # The raw identifier is used only during this provider call and is never
    # logged, returned, or stored.
    if method == "BVN":
        result = await provider.verify_bvn(
            full_name=user.profile.full_name,
            phone_number=user.phone_number,
            bvn=value,
            reference=reference,
        )
    else:
        result = await provider.verify_nin(
            full_name=user.profile.full_name,
            phone_number=user.phone_number,
            nin=value,
            reference=reference,
        )

    record.status = result.status
    record.failure_reason = result.reason
    if result.status == "VERIFIED":
        record.verified_at = datetime.now(timezone.utc)
    await db.flush()
    return record


async def verified_kyc_for_identifier(db: AsyncSession, user_id, value: str):
    digest = identifier_hash(value)
    return await db.scalar(
        select(KYCVerification)
        .where(
            KYCVerification.user_id == user_id,
            KYCVerification.status == "VERIFIED",
            KYCVerification.identifier_hash == digest,
        )
        .order_by(KYCVerification.verified_at.desc())
        .limit(1)
    )
