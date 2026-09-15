from app.providers.identity import KYCResult


class MockIdentityVerificationProvider:
    name = "mock"

    @staticmethod
    def _result(value: str, reference: str) -> KYCResult:
        if value.startswith("000"):
            return KYCResult("FAILED", "mock", reference, "MOCK_REJECTED")
        return KYCResult("VERIFIED", "mock", reference)

    async def verify_bvn(self, *, full_name: str, phone_number: str, bvn: str, reference: str) -> KYCResult:
        return self._result(bvn, reference)

    async def verify_nin(self, *, full_name: str, phone_number: str, nin: str, reference: str) -> KYCResult:
        return self._result(nin, reference)
