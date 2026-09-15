from datetime import datetime, timedelta, timezone

from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    generate_otp,
    generate_verification_token,
    hash_otp_or_token,
    hash_password,
    needs_password_rehash,
    verify_password,
)
from app.models.auth import EmailVerification, PasswordReset, PhoneVerification, Session
from app.models.user import User
from app.providers.notifications import notification_provider

OTP_TTL_MINUTES = 10
OTP_RESEND_SECONDS = 60
EMAIL_TOKEN_TTL_HOURS = 24
RESET_TOKEN_TTL_MINUTES = 30


def now_utc() -> datetime:
    return datetime.now(timezone.utc)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def normalize_phone(phone: str) -> str:
    value = "".join(ch for ch in phone.strip() if ch.isdigit() or ch == "+")
    if value.startswith("00"):
        value = "+" + value[2:]
    elif value.startswith("234"):
        value = "+" + value
    elif value.startswith("0") and len(value) == 11:
        value = "+234" + value[1:]
    if not value.startswith("+") or len(value) < 10:
        raise ValueError("Invalid phone number")
    return value


async def create_session(
    db: AsyncSession,
    user: User,
    device_name: str | None,
    ip_address: str | None,
    user_agent: str | None,
):
    refresh_token, jti, expires_at = create_refresh_token(str(user.id))
    db.add(
        Session(
            user_id=user.id,
            refresh_token_jti_hash=hash_otp_or_token(jti),
            device_name=device_name[:120] if device_name else None,
            ip_address=ip_address[:64] if ip_address else None,
            user_agent=user_agent[:2000] if user_agent else None,
            expires_at=expires_at,
            last_used_at=now_utc(),
        )
    )
    await db.flush()
    return create_access_token(str(user.id)), refresh_token


async def issue_phone_otp(db: AsyncSession, user: User) -> None:
    current = now_utc()
    latest = await db.scalar(
        select(PhoneVerification)
        .where(PhoneVerification.user_id == user.id)
        .order_by(PhoneVerification.created_at.desc())
        .limit(1)
    )
    if latest and (current - latest.created_at).total_seconds() < OTP_RESEND_SECONDS:
        raise ValueError("OTP resend cooldown")

    code = generate_otp()
    db.add(
        PhoneVerification(
            user_id=user.id,
            code_hash=hash_otp_or_token(code),
            expires_at=current + timedelta(minutes=OTP_TTL_MINUTES),
            attempts=0,
            max_attempts=5,
        )
    )
    await db.flush()
    await notification_provider.send_phone_otp(user.phone_number, code)


async def verify_phone_otp(db: AsyncSession, user: User, code: str) -> bool:
    current = now_utc()
    record = await db.scalar(
        select(PhoneVerification)
        .where(
            PhoneVerification.user_id == user.id,
            PhoneVerification.consumed_at.is_(None),
        )
        .order_by(PhoneVerification.created_at.desc())
        .limit(1)
        .with_for_update()
    )
    if not record or record.expires_at <= current or record.attempts >= record.max_attempts:
        return False

    record.attempts += 1
    if hash_otp_or_token(code) != record.code_hash:
        await db.flush()
        return False

    record.consumed_at = current
    user.phone_verified = True
    if user.email_verified:
        user.is_active = True
    await db.flush()
    return True


async def issue_email_verification(db: AsyncSession, user: User) -> None:
    token = generate_verification_token()
    db.add(
        EmailVerification(
            user_id=user.id,
            token_hash=hash_otp_or_token(token),
            expires_at=now_utc() + timedelta(hours=EMAIL_TOKEN_TTL_HOURS),
        )
    )
    await db.flush()
    await notification_provider.send_email_verification(user.email, token)


async def verify_email_token(db: AsyncSession, token: str) -> bool:
    record = await db.scalar(
        select(EmailVerification)
        .where(
            EmailVerification.token_hash == hash_otp_or_token(token),
            EmailVerification.consumed_at.is_(None),
        )
        .with_for_update()
    )
    current = now_utc()
    if not record or record.expires_at <= current:
        return False

    user = await db.scalar(select(User).where(User.id == record.user_id).with_for_update())
    if not user:
        return False

    record.consumed_at = current
    user.email_verified = True
    if user.phone_verified:
        user.is_active = True
    await db.flush()
    return True


async def create_password_reset(db: AsyncSession, user: User) -> None:
    token = generate_verification_token()
    db.add(
        PasswordReset(
            user_id=user.id,
            token_hash=hash_otp_or_token(token),
            expires_at=now_utc() + timedelta(minutes=RESET_TOKEN_TTL_MINUTES),
        )
    )
    await db.flush()
    await notification_provider.send_password_reset(user.email, token)


async def reset_password(db: AsyncSession, token: str, new_password: str) -> bool:
    record = await db.scalar(
        select(PasswordReset)
        .where(
            PasswordReset.token_hash == hash_otp_or_token(token),
            PasswordReset.consumed_at.is_(None),
        )
        .with_for_update()
    )
    current = now_utc()
    if not record or record.expires_at <= current:
        return False

    user = await db.scalar(select(User).where(User.id == record.user_id).with_for_update())
    if not user:
        return False

    user.password_hash = hash_password(new_password)
    record.consumed_at = current

    await db.execute(
        update(Session)
        .where(Session.user_id == user.id, Session.revoked_at.is_(None))
        .values(revoked_at=current)
    )
    await db.flush()
    return True


async def authenticate(db: AsyncSession, identifier: str, password: str) -> User | None:
    value = identifier.strip()
    email = normalize_email(value)
    try:
        phone = normalize_phone(value)
    except ValueError:
        phone = None

    user = await db.scalar(
        select(User).where((User.email == email) | (User.phone_number == phone))
    )
    if not user or not verify_password(password, user.password_hash):
        return None

    if needs_password_rehash(user.password_hash):
        user.password_hash = hash_password(password)

    return user


async def revoke_refresh_session(db: AsyncSession, refresh_token_jti_hash: str) -> bool:
    session = await db.scalar(
        select(Session)
        .where(
            Session.refresh_token_jti_hash == refresh_token_jti_hash,
            Session.revoked_at.is_(None),
        )
        .with_for_update()
    )
    if not session:
        return False
    session.revoked_at = now_utc()
    await db.flush()
    return True
