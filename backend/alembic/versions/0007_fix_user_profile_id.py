"""fix user profile primary key to UUID"""

from alembic import op

revision = "0007_profile_uuid"
down_revision = "0006_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto")

    op.execute(
        "ALTER TABLE user_profiles "
        "ALTER COLUMN id DROP DEFAULT"
    )

    op.execute(
        "ALTER TABLE user_profiles "
        "ALTER COLUMN id TYPE uuid "
        "USING gen_random_uuid()"
    )


def downgrade() -> None:
    raise RuntimeError(
        "Downgrade from UUID profile ids to integer ids is intentionally unsupported"
    )
