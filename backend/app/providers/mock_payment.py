import hashlib
from app.providers.payment import CustomerResult, VirtualAccountResult, VerifiedPaymentResult


class MockPaymentProvider:
    name = "mock"

    async def create_customer(self, *, full_name: str, email: str, phone_number: str, idempotency_key: str) -> CustomerResult:
        return CustomerResult(
            provider_customer_id="mock_cus_" + hashlib.sha256(email.encode()).hexdigest()[:20],
            provider=self.name,
        )

    async def create_static_virtual_account(
        self, *, customer_id: str, full_name: str, email: str, phone_number: str,
        bvn: str | None, nin: str | None, reference: str, idempotency_key: str
    ) -> VirtualAccountResult:
        digest = hashlib.sha256(reference.encode()).hexdigest()
        return VirtualAccountResult(
            provider=self.name,
            provider_account_id="mock_va_" + digest[:16],
            account_number="09" + str(int(digest[:8], 16))[-8:],
            bank_name="Mock Bank (TEST ONLY)",
            bank_code="000000",
            reference=reference,
        )

    async def verify_payment(self, *, provider_transaction_id: str) -> VerifiedPaymentResult:
        # Deterministic development adapter. Production never treats this as real money.
        return VerifiedPaymentResult(
            provider=self.name,
            provider_transaction_id=provider_transaction_id,
            tx_ref=f"MOCK-{provider_transaction_id}",
            status="succeeded",
            amount_kobo=100_000,
            currency="NGN",
            customer_id=None,
        )
