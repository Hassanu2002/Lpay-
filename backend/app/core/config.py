from functools import lru_cache

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Labour Pay"
    app_env: str = Field(default="development", alias="APP_ENV")
    debug: bool = Field(default=False, alias="DEBUG")
    secret_key: str = Field(default="CHANGE_ME", alias="SECRET_KEY")
    database_url: str = Field(
        default="postgresql+asyncpg://labourpay:labourpay@localhost:5432/labourpay",
        alias="DATABASE_URL",
    )
    cors_origins_raw: str = Field(
        default="http://localhost:5173",
        alias="CORS_ORIGINS",
    )
    payment_provider: str = Field(default="mock", alias="PAYMENT_PROVIDER")
    kyc_provider: str = Field(default="mock", alias="KYC_PROVIDER")
    flutterwave_secret_key: str = Field(default="", alias="FLW_SECRET_KEY")
    flutterwave_secret_hash: str = Field(default="", alias="FLW_SECRET_HASH")
    flutterwave_api_base: str = Field(
        default="https://developersandbox-api.flutterwave.com",
        alias="FLW_API_BASE",
    )
    flutterwave_legacy_api_base: str = Field(
        default="https://api.flutterwave.com/v3",
        alias="FLW_LEGACY_API_BASE",
    )
    flutterwave_timeout_seconds: float = Field(default=15.0, alias="FLW_TIMEOUT_SECONDS")

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @field_validator("app_env")
    @classmethod
    def validate_app_env(cls, value: str) -> str:
        value = value.strip().lower()
        allowed = {"development", "testing", "staging", "production"}
        if value not in allowed:
            raise ValueError(f"APP_ENV must be one of: {', '.join(sorted(allowed))}")
        return value

    @property
    def cors_origins(self) -> list[str]:
        return [x.strip() for x in self.cors_origins_raw.split(",") if x.strip()]

    def validate_runtime_security(self) -> None:
        if self.app_env == "production" and (
            not self.secret_key or self.secret_key == "CHANGE_ME"
        ):
            raise ValueError("SECRET_KEY must be explicitly configured in production.")
        if self.payment_provider == "flutterwave" and not self.flutterwave_secret_key:
            raise ValueError("FLW_SECRET_KEY is required when PAYMENT_PROVIDER=flutterwave")
        if self.payment_provider == "flutterwave" and not self.flutterwave_secret_hash:
            raise ValueError("FLW_SECRET_HASH is required when PAYMENT_PROVIDER=flutterwave")


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
settings.validate_runtime_security()
