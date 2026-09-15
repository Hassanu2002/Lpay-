from datetime import datetime, timezone

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_otp,
    hash_otp_or_token,
    hash_password,
    verify_password,
)


def test_password_hash_is_not_plaintext():
    password = "StrongPassword123"
    hashed = hash_password(password)
    assert hashed != password
    assert hashed.startswith("$argon2")
    assert verify_password(password, hashed)
    assert not verify_password("WrongPassword123", hashed)


def test_otp_is_six_digits_and_only_hash_is_stored():
    otp = generate_otp()
    assert len(otp) == 6
    assert otp.isdigit()
    assert hash_otp_or_token(otp) != otp


def test_access_token_type_and_subject():
    token = create_access_token("user-id")
    payload = decode_token(token, "access")
    assert payload["sub"] == "user-id"
    assert payload["type"] == "access"


def test_refresh_token_rotation_material():
    token, jti, expires_at = create_refresh_token("user-id")
    payload = decode_token(token, "refresh")
    assert payload["sub"] == "user-id"
    assert payload["jti"] == jti
    assert expires_at > datetime.now(timezone.utc)
