import hashlib
import httpx
from decimal import Decimal

from app.core.config import settings
from app.providers.payment import CustomerResult, VirtualAccountResult, VerifiedPaymentResult


class FlutterwavePaymentProvider:
    name = "flutterwave"

    async def _post(self, path: str, payload: dict, idempotency_key: str) -> dict:
        headers = {
            "Authorization": f"Bearer {settings.flutterwave_secret_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-Idempotency-Key": idempotency_key,
        }
        async with httpx.AsyncClient(timeout=settings.flutterwave_timeout_seconds) as client:
            response = await client.post(
                f"{settings.flutterwave_api_base.rstrip('/')}/{path.lstrip('/')}",
                json=payload,
                headers=headers,
            )
            response.raise_for_status()
            return response.json()

    async def create_customer(self, *, full_name: str, email: str, phone_number: str, idempotency_key: str) -> CustomerResult:
        parts = full_name.split(maxsplit=1)
        payload = {
            "name": {"first": parts[0], "last": parts[1] if len(parts) > 1 else parts[0]},
            "email": email,
            "phone": {"number": phone_number},
        }
        data = await self._post("customers", payload, idempotency_key)
        customer = data.get("data") or {}
        provider_id = customer.get("id")
        if not provider_id:
            raise RuntimeError("Flutterwave customer response did not contain an id")
        return CustomerResult(provider_customer_id=provider_id, provider=self.name)

    async def create_static_virtual_account(
        self, *, customer_id: str, full_name: str, email: str, phone_number: str,
        bvn: str | None, nin: str | None, reference: str, idempotency_key: str
    ) -> VirtualAccountResult:
        if not bvn and not nin:
            raise ValueError("BVN or NIN is required for a static virtual account")
        payload = {
            "reference": reference,
            "customer_id": customer_id,
            "amount": 0,
            "currency": "NGN",
            "account_type": "static",
            "narration": full_name[:70],
        }
        if bvn:
            payload["bvn"] = bvn
        else:
            payload["nin"] = nin

        data = await self._post("virtual-accounts", payload, idempotency_key)
        item = data.get("data") or {}
        account_number = item.get("account_number")
        bank_name = item.get("bank_name")
        if not account_number or not bank_name:
            raise RuntimeError("Flutterwave virtual-account response was incomplete")
        return VirtualAccountResult(
            provider=self.name,
            provider_account_id=item.get("id") or item.get("account_id"),
            account_number=account_number,
            bank_name=bank_name,
            bank_code=item.get("bank_code"),
            reference=reference,
        )


    async def verify_payment(self, *, provider_transaction_id: str) -> VerifiedPaymentResult:
        # Current Flutterwave Orchestrator/webhook payloads use charge IDs such as
        # chg_*. Retrieve the charge server-to-server before giving wallet value.
        trace_id = hashlib.sha256(provider_transaction_id.encode("utf-8")).hexdigest()[:32]
        headers = {
            "Authorization": f"Bearer {settings.flutterwave_secret_key}",
            "Accept": "application/json",
            "X-Trace-Id": trace_id,
        }
        async with httpx.AsyncClient(timeout=settings.flutterwave_timeout_seconds) as client:
            response = await client.get(
                f"{settings.flutterwave_api_base.rstrip('/')}/charges/{provider_transaction_id}",
                headers=headers,
            )
            if response.is_success:
                body = response.json()
            elif provider_transaction_id.isdigit():
                # Flutterwave's current virtual-account webhook examples can expose
                # a numeric transaction id while the newer charge API uses chg_* ids.
                # Support that documented legacy verification shape without trusting
                # the webhook payload itself.
                legacy_base = settings.flutterwave_legacy_api_base.rstrip("/")
                legacy_url = f"{legacy_base}/transactions/{provider_transaction_id}/verify"
                legacy_response = await client.get(legacy_url, headers={"Authorization": f"Bearer {settings.flutterwave_secret_key}", "Accept": "application/json"})
                legacy_response.raise_for_status()
                body = legacy_response.json()
            else:
                response.raise_for_status()

        data = body.get("data") or {}
        charge_id = str(data.get("id") or provider_transaction_id)
        tx_ref = str(data.get("reference") or data.get("tx_ref") or "")
        if not tx_ref:
            raise RuntimeError("Flutterwave verification response did not contain a transaction reference")
        try:
            amount_kobo = int((Decimal(str(data["amount"])) * Decimal("100")).quantize(Decimal("1")))
        except (KeyError, ValueError, ArithmeticError) as exc:
            raise RuntimeError("Flutterwave verification response contained an invalid amount") from exc
        customer = data.get("customer")
        customer_id = customer if isinstance(customer, str) else (str(customer.get("id")) if isinstance(customer, dict) and customer.get("id") else None)
        return VerifiedPaymentResult(
            provider=self.name,
            provider_transaction_id=charge_id,
            tx_ref=tx_ref,
            status=str(data.get("status") or "").lower(),
            amount_kobo=amount_kobo,
            currency=str(data.get("currency") or "").upper(),
            customer_id=customer_id,
        )
