from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class CustomerResult:
    provider_customer_id: str
    provider: str


@dataclass(frozen=True)
class VirtualAccountResult:
    provider: str
    provider_account_id: str | None
    account_number: str
    bank_name: str
    bank_code: str | None
    reference: str


@dataclass(frozen=True)
class VerifiedPaymentResult:
    provider: str
    provider_transaction_id: str
    tx_ref: str
    status: str
    amount_kobo: int
    currency: str
    customer_id: str | None


class PaymentProvider(Protocol):
    async def create_customer(self, *, full_name: str, email: str, phone_number: str, idempotency_key: str) -> CustomerResult: ...
    async def create_static_virtual_account(
        self, *, customer_id: str, full_name: str, email: str, phone_number: str,
        bvn: str | None, nin: str | None, reference: str, idempotency_key: str
    ) -> VirtualAccountResult: ...
    async def verify_payment(self, *, provider_transaction_id: str) -> VerifiedPaymentResult: ...
