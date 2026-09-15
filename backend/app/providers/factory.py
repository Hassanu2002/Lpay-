from app.core.config import settings
from app.providers.flutterwave import FlutterwavePaymentProvider
from app.providers.mock_identity import MockIdentityVerificationProvider
from app.providers.mock_payment import MockPaymentProvider


def identity_provider():
    return MockIdentityVerificationProvider()


def payment_provider():
    if settings.payment_provider == "flutterwave":
        return FlutterwavePaymentProvider()
    return MockPaymentProvider()
