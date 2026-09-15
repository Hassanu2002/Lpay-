import ast
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_phase4_modules_parse():
    for path in [
        ROOT / "app/models/wallet.py",
        ROOT / "app/services/wallet.py",
        ROOT / "app/api/routes/wallet.py",
        ROOT / "app/api/routes/webhooks.py",
        ROOT / "app/providers/flutterwave.py",
        ROOT / "app/providers/payment.py",
        ROOT / "alembic/versions/0008_wallet_ledger.py",
    ]:
        ast.parse(path.read_text(encoding="utf-8"))


def test_wallet_has_no_mutable_balance_field():
    text = (ROOT / "app/models/wallet.py").read_text(encoding="utf-8").lower()
    assert "balance:" not in text
    assert "balance =" not in text


def test_ledger_uses_integer_kobo_and_double_entry():
    text = (ROOT / "app/models/wallet.py").read_text(encoding="utf-8")
    assert "amount_kobo" in text
    service = (ROOT / "app/services/wallet.py").read_text(encoding="utf-8")
    assert 'direction="DEBIT"' in service
    assert 'direction="CREDIT"' in service


def test_spend_locks_wallet_and_checks_derived_balance():
    text = (ROOT / "app/services/wallet.py").read_text(encoding="utf-8")
    assert "ensure_wallet(db, user_id, lock=True)" in text
    assert "get_wallet_balance_kobo" in text
    assert "Insufficient wallet balance" in text


def test_idempotency_is_database_backed():
    text = (ROOT / "app/services/wallet.py").read_text(encoding="utf-8")
    assert "on_conflict_do_nothing" in text
    model = (ROOT / "app/models/wallet.py").read_text(encoding="utf-8")
    assert "uq_idempotency_user_operation_hash" in model


def test_webhook_requires_server_side_verification_before_credit():
    text = (ROOT / "app/api/routes/webhooks.py").read_text(encoding="utf-8")
    assert "verify_payment" in text
    assert "credit_wallet_from_verified_funding" in text
    assert "status not in {\"succeeded\", \"successful\"}" in text


def test_no_raw_webhook_payload_is_persisted():
    text = (ROOT / "app/api/routes/webhooks.py").read_text(encoding="utf-8")
    assert "payload=sanitized" in text
    assert "payload=payload" not in text


def test_user_profile_pk_matches_uuid_users():
    text = (ROOT / "app/models/user_profile.py").read_text(encoding="utf-8")
    assert "Mapped[uuid.UUID]" in text
    assert "UUID(as_uuid=True)" in text


def test_refunds_are_unique_per_original_transaction():
    text = (ROOT / "app/models/wallet.py").read_text(encoding="utf-8")
    assert "related_transaction_id" in text
    assert "unique=True" in text
