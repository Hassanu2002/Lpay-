from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class KYCResult:
    status: str
    provider: str
    reference: str
    reason: str | None = None


class IdentityVerificationProvider(Protocol):
    async def verify_bvn(self, *, full_name: str, phone_number: str, bvn: str, reference: str) -> KYCResult: ...
    async def verify_nin(self, *, full_name: str, phone_number: str, nin: str, reference: str) -> KYCResult: ...
