import re
from pydantic import BaseModel, EmailStr, Field, field_validator


def validate_strong_password(value: str) -> str:
    if not re.search(r"[A-Z]", value) or not re.search(r"[a-z]", value) or not re.search(r"\d", value):
        raise ValueError("Password must contain upper-case, lower-case and a number")
    return value


class RegisterRequest(BaseModel):
    full_name: str = Field(min_length=2, max_length=160)
    phone_number: str = Field(min_length=7, max_length=32)
    email: EmailStr
    password: str = Field(min_length=10, max_length=128)

    @field_validator("full_name", "phone_number")
    @classmethod
    def strip_value(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Value is required")
        return value

    @field_validator("password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_strong_password(value)


class LoginRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=128)


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = 900


class MessageResponse(BaseModel):
    message: str


class PhoneOTPRequest(BaseModel):
    phone_number: str = Field(min_length=7, max_length=32)


class VerifyPhoneRequest(BaseModel):
    phone_number: str = Field(min_length=7, max_length=32)
    code: str = Field(min_length=6, max_length=6)


class EmailVerificationRequest(BaseModel):
    token: str = Field(min_length=20, max_length=200)


class PasswordResetRequest(BaseModel):
    identifier: str = Field(min_length=3, max_length=320)


class PasswordResetConfirm(BaseModel):
    token: str = Field(min_length=20, max_length=200)
    new_password: str = Field(min_length=10, max_length=128)

    @field_validator("new_password")
    @classmethod
    def strong_password(cls, value: str) -> str:
        return validate_strong_password(value)


class RefreshRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)


class LogoutRequest(BaseModel):
    refresh_token: str = Field(min_length=20, max_length=4096)


class UserResponse(BaseModel):
    id: str
    email: EmailStr
    phone_number: str
    full_name: str
    email_verified: bool
    phone_verified: bool
    is_active: bool
