from logging.config import fileConfig
import asyncio

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_engine_from_config

from app.core.config import settings
from app.models.base import Base
from app.models.user import User  # noqa: F401
from app.models.user_profile import UserProfile  # noqa: F401
from app.models.auth import EmailVerification, PasswordReset, PhoneVerification, Session  # noqa: F401
from app.models.kyc import KYCVerification  # noqa: F401
from app.models.payment import CustomerProfile, VirtualAccount, PaymentTransaction, WebhookEvent  # noqa: F401
from app.models.wallet import Wallet, LedgerAccount, LedgerTransaction, LedgerEntry, WalletTransaction, IdempotencyKey, WalletLimit  # noqa: F401
from app.models.rate_limit import AuthRateLimitEvent  # noqa: F401


config = context.config
config.set_main_option("sqlalchemy.url", settings.database_url.replace("%", "%%"))

if config.config_file_name:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata


def sync_database_url() -> str:
    url = make_url(settings.database_url)
    if url.drivername == "postgresql+asyncpg":
        url = url.set(drivername="postgresql")
    return url.render_as_string(hide_password=False)


def run_migrations_offline() -> None:
    context.configure(
        url=sync_database_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata)
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online() -> None:
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
