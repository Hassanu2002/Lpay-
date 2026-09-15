import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.payment import CustomerProfile, VirtualAccount
from app.models.user import User
from app.providers.factory import payment_provider
from app.services.kyc import verified_kyc_for_identifier


async def create_or_get_virtual_account(
    db: AsyncSession, user: User, *, verified_identifier: str
) -> VirtualAccount:
    existing = await db.scalar(
        select(VirtualAccount)
        .where(VirtualAccount.user_id == user.id, VirtualAccount.status == "ACTIVE")
        .order_by(VirtualAccount.created_at.desc())
        .limit(1)
    )
    if existing:
        return existing

    kyc = await verified_kyc_for_identifier(db, user.id, verified_identifier)
    if not kyc:
        raise PermissionError("KYC verification is required before wallet funding")

    provider = payment_provider()
    customer = await db.scalar(
        select(CustomerProfile)
        .where(CustomerProfile.user_id == user.id)
        .with_for_update()
    )

    if not customer:
        result = await provider.create_customer(
            full_name=user.profile.full_name,
            email=user.email,
            phone_number=user.phone_number,
            idempotency_key=f"customer-{user.id}",
        )
        customer = CustomerProfile(
            user_id=user.id,
            provider=result.provider,
            provider_customer_id=result.provider_customer_id,
        )
        db.add(customer)
        await db.flush()

    reference = "VA-" + uuid.uuid4().hex
    result = await provider.create_static_virtual_account(
        customer_id=customer.provider_customer_id,
        full_name=user.profile.full_name,
        email=user.email,
        phone_number=user.phone_number,
        bvn=verified_identifier if kyc.method == "BVN" else None,
        nin=verified_identifier if kyc.method == "NIN" else None,
        reference=reference,
        idempotency_key=f"virtual-account-{user.id}",
    )

    account = VirtualAccount(
        user_id=user.id,
        provider=result.provider,
        provider_account_id=result.provider_account_id,
        account_number=result.account_number,
        bank_name=result.bank_name,
        bank_code=result.bank_code,
        currency="NGN",
        account_type="static",
        status="ACTIVE",
        reference=result.reference,
    )
    db.add(account)
    await db.flush()
    return account
