import ast
from pathlib import Path

from app.providers.factory import payment_provider

ROOT = Path(__file__).resolve().parents[1]


def test_phase3_modules_parse():
    files = [
        ROOT / "app/models/kyc.py",
        ROOT / "app/models/payment.py",
        ROOT / "app/providers/flutterwave.py",
        ROOT / "app/services/kyc.py",
        ROOT / "app/services/payments.py",
        ROOT / "app/api/routes/webhooks.py",
    ]
    for file in files:
        ast.parse(file.read_text(encoding="utf-8"))


def test_payment_provider_defaults_to_mock():
    assert payment_provider().name == "mock"


def test_kyc_model_stores_hash_not_raw_identifier():
    text = (ROOT / "app/models/kyc.py").read_text(encoding="utf-8")
    assert "identifier_hash" in text
    assert "bvn:" not in text.lower()
    assert "nin:" not in text.lower()


def test_webhook_uses_constant_time_signature_comparison():
    text = (ROOT / "app/api/routes/webhooks.py").read_text(encoding="utf-8")
    assert "hmac.compare_digest" in text
    assert 'alias="verif-hash"' in text


def test_flutterwave_provider_sends_idempotency_key():
    text = (ROOT / "app/providers/flutterwave.py").read_text(encoding="utf-8")
    assert "X-Idempotency-Key" in text
