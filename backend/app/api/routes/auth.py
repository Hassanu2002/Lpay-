from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import decode_token, hash_otp_or_token, hash_password
from app.dependencies import get_current_user, get_db
from app.models.auth import Session
from app.models.user import User
from app.models.user_profile import UserProfile
from app.schemas.auth import (
    EmailVerificationRequest,
    LoginRequest,
    LogoutRequest,
    MessageResponse,
    PasswordResetConfirm,
    PasswordResetRequest,
    PhoneOTPRequest,
    RefreshRequest,
    RegisterRequest,
    TokenResponse,
    UserResponse,
    VerifyPhoneRequest,
)
from app.services.auth import (
    authenticate,
    create_password_reset,
    create_session,
    issue_email_verification,
    issue_phone_otp,
    normalize_email,
    normalize_phone,
    reset_password,
    revoke_refresh_session,
    verify_email_token,
    verify_phone_otp,
)
from app.services.rate_limit import enforce_rate_limit

router = APIRouter(prefix="/auth")


def get_client_ip(request: Request) -> str | None:
    # Only use request.client here. Forwarded headers require a trusted proxy configuration.
    return request.client.host if request.client else None


async def find_user(db: AsyncSession, identifier: str) -> User | None:
    email = normalize_email(identifier)
    try:
        phone = normalize_phone(identifier)
    except ValueError:
        phone = None
    return await db.scalar(
        select(User).where((User.email == email) | (User.phone_number == phone))
    )


@router.post("/register", response_model=MessageResponse, status_code=201)
async def register(
    payload: RegisterRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = get_client_ip(request) or "unknown"
    allowed = await enforce_rate_limit(
        db, bucket_key=f"ip:{ip}", action="register", max_attempts=5, window_seconds=3600
    )
    if not allowed:
        await db.rollback()
        raise HTTPException(status_code=429, detail="Too many registration attempts. Please try again later.")

    try:
        email = normalize_email(str(payload.email))
        phone = normalize_phone(payload.phone_number)
    except ValueError:
        await db.rollback()
        raise HTTPException(status_code=422, detail="Invalid phone number")

    existing = await db.scalar(
        select(User).where((User.email == email) | (User.phone_number == phone))
    )
    if existing:
        await db.rollback()
        raise HTTPException(status_code=409, detail="An account with those details already exists")

    user = User(
        email=email,
        phone_number=phone,
        password_hash=hash_password(payload.password),
        is_active=False,
        email_verified=False,
        phone_verified=False,
    )
    user.profile = UserProfile(full_name=payload.full_name.strip())
    db.add(user)

    try:
        await db.flush()
        await issue_phone_otp(db, user)
        await issue_email_verification(db, user)
        await db.commit()
    except ValueError:
        await db.rollback()
        raise HTTPException(status_code=429, detail="Please wait before requesting another verification code")
    except IntegrityError:
        await db.rollback()
        raise HTTPException(status_code=409, detail="An account with those details already exists")

    return MessageResponse(message="Account created. Complete phone and email verification.")


@router.post("/verify-phone", response_model=MessageResponse)
async def verify_phone(payload: VerifyPhoneRequest, db: AsyncSession = Depends(get_db)):
    try:
        phone = normalize_phone(payload.phone_number)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid phone number")

    user = await db.scalar(select(User).where(User.phone_number == phone))
    if not user:
        raise HTTPException(status_code=400, detail="Invalid verification request")

    if not await verify_phone_otp(db, user, payload.code):
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired verification code")

    await db.commit()
    return MessageResponse(message="Phone number verified.")


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(payload: EmailVerificationRequest, db: AsyncSession = Depends(get_db)):
    if not await verify_email_token(db, payload.token):
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired verification link")

    await db.commit()
    return MessageResponse(message="Email address verified.")


@router.post("/resend-phone-otp", response_model=MessageResponse)
async def resend_phone_otp(
    payload: PhoneOTPRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = get_client_ip(request) or "unknown"
    if not await enforce_rate_limit(
        db, bucket_key=f"ip:{ip}", action="otp_resend", max_attempts=10, window_seconds=3600
    ):
        await db.rollback()
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    try:
        phone = normalize_phone(payload.phone_number)
    except ValueError:
        await db.rollback()
        raise HTTPException(status_code=422, detail="Invalid phone number")

    user = await db.scalar(select(User).where(User.phone_number == phone))
    if user and not user.phone_verified:
        try:
            await issue_phone_otp(db, user)
            await db.commit()
        except ValueError:
            await db.rollback()
            raise HTTPException(status_code=429, detail="Please wait before requesting another code")
    else:
        await db.rollback()

    return MessageResponse(message="If the account can receive a code, a verification code has been sent.")


@router.post("/login", response_model=TokenResponse)
async def login(
    payload: LoginRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_device_name: str | None = Header(default=None),
):
    ip = get_client_ip(request) or "unknown"
    identifier_key = payload.identifier.strip().lower()

    ip_allowed = await enforce_rate_limit(
        db, bucket_key=f"ip:{ip}", action="login", max_attempts=20, window_seconds=900
    )
    identifier_allowed = await enforce_rate_limit(
        db, bucket_key=f"id:{identifier_key}", action="login", max_attempts=8, window_seconds=900
    )
    if not ip_allowed or not identifier_allowed:
        await db.rollback()
        raise HTTPException(status_code=429, detail="Too many login attempts. Please try again later.")

    user = await authenticate(db, payload.identifier, payload.password)
    if not user:
        await db.commit()
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not user.email_verified or not user.phone_verified or not user.is_active:
        await db.rollback()
        raise HTTPException(status_code=403, detail="Account verification is incomplete")

    access_token, refresh_token = await create_session(
        db,
        user,
        x_device_name,
        get_client_ip(request),
        request.headers.get("user-agent"),
    )
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=refresh_token)


@router.post("/refresh", response_model=TokenResponse)
async def refresh(
    payload: RefreshRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    x_device_name: str | None = Header(default=None),
):
    try:
        token_payload = decode_token(payload.refresh_token, "refresh")
        jti_hash = hash_otp_or_token(token_payload["jti"])
    except Exception:
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    session = await db.scalar(
        select(Session)
        .where(
            Session.refresh_token_jti_hash == jti_hash,
            Session.revoked_at.is_(None),
        )
        .with_for_update()
    )
    if not session or session.expires_at <= datetime.now(timezone.utc):
        await db.rollback()
        raise HTTPException(status_code=401, detail="Invalid or expired refresh token")

    user = await db.scalar(select(User).where(User.id == session.user_id).with_for_update())
    if not user or not user.is_active:
        await db.rollback()
        raise HTTPException(status_code=401, detail="Invalid session")

    session.revoked_at = datetime.now(timezone.utc)
    access_token, new_refresh = await create_session(
        db,
        user,
        x_device_name or session.device_name,
        get_client_ip(request),
        request.headers.get("user-agent"),
    )
    await db.commit()
    return TokenResponse(access_token=access_token, refresh_token=new_refresh)


@router.post("/logout", response_model=MessageResponse)
async def logout(payload: LogoutRequest, db: AsyncSession = Depends(get_db)):
    try:
        token_payload = decode_token(payload.refresh_token, "refresh")
        revoked = await revoke_refresh_session(db, hash_otp_or_token(token_payload["jti"]))
    except Exception:
        revoked = False

    await db.commit()
    return MessageResponse(message="Session ended.")


@router.post("/password-reset/request", response_model=MessageResponse)
async def password_reset_request(
    payload: PasswordResetRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    ip = get_client_ip(request) or "unknown"
    if not await enforce_rate_limit(
        db, bucket_key=f"ip:{ip}", action="password_reset", max_attempts=10, window_seconds=3600
    ):
        await db.rollback()
        raise HTTPException(status_code=429, detail="Too many requests. Please try again later.")

    user = await find_user(db, payload.identifier)
    if user and user.is_active:
        await create_password_reset(db, user)
        await db.commit()
    else:
        await db.rollback()

    return MessageResponse(message="If an eligible account exists, password reset instructions have been sent.")


@router.post("/password-reset/confirm", response_model=MessageResponse)
async def password_reset_confirm(payload: PasswordResetConfirm, db: AsyncSession = Depends(get_db)):
    if not await reset_password(db, payload.token, payload.new_password):
        await db.rollback()
        raise HTTPException(status_code=400, detail="Invalid or expired reset token")

    await db.commit()
    return MessageResponse(message="Password reset successfully.")


@router.get("/me", response_model=UserResponse)
async def me(current_user: User = Depends(get_current_user)):
    return UserResponse(
        id=str(current_user.id),
        email=current_user.email,
        phone_number=current_user.phone_number,
        full_name=current_user.profile.full_name if current_user.profile else "",
        email_verified=current_user.email_verified,
        phone_verified=current_user.phone_verified,
        is_active=current_user.is_active,
    )
