import hashlib
import hmac
import json

from fastapi import APIRouter, Header, Request, Response, status
from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from datetime import datetime, timezone

from app.core.config import settings
from app.core.database import AsyncSessionLocal
from app.models.payment import CustomerProfile, PaymentTransaction, WebhookEvent
from app.models.wallet import WalletTransaction
from app.providers.factory import payment_provider
from app.services.wallet import credit_wallet_from_verified_funding

router = APIRouter(prefix="/webhooks")


def _extract_customer_id(data: dict) -> str | None:
    customer = data.get("customer")
    if isinstance(customer, str):
        return customer
    if isinstance(customer, dict) and customer.get("id") is not None:
        return str(customer["id"])
    return None


def _sanitized_payload(payload: dict) -> dict:
    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    return {
        "event": payload.get("event") or payload.get("type"),
        "event_id": payload.get("id") or payload.get("webhook_id"),
        "data": {
            "id": data.get("id"),
            "tx_ref": data.get("tx_ref") or data.get("reference"),
            "amount": data.get("amount"),
            "currency": data.get("currency"),
            "status": data.get("status"),
            "customer_id": _extract_customer_id(data),
            "payment_type": data.get("payment_type"),
        },
    }


@router.post("/flutterwave", status_code=200)
async def flutterwave_webhook(
    request: Request,
    response: Response,
    verif_hash: str | None = Header(default=None, alias="verif-hash"),
):
    body = await request.body()
    payload_hash = hashlib.sha256(body).hexdigest()

    valid = bool(
        settings.flutterwave_secret_hash
        and verif_hash
        and hmac.compare_digest(verif_hash, settings.flutterwave_secret_hash)
    )
    if not valid:
        return {"status": "ignored"}

    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return {"status": "ignored"}

    data = payload.get("data") if isinstance(payload.get("data"), dict) else {}
    event_id = str(payload.get("webhook_id") or payload.get("id") or "") or None
    event_type = str(payload.get("event") or payload.get("type") or "") or None
    provider_transaction_id = str(data.get("id") or "") or None
    if not provider_transaction_id:
        return {"status": "ignored"}

    sanitized = _sanitized_payload(payload)
    async with AsyncSessionLocal() as db:
        existing = None
        if event_id:
            existing = await db.scalar(
                select(WebhookEvent).where(
                    WebhookEvent.provider == "flutterwave",
                    WebhookEvent.event_id == event_id,
                )
            )
        if not existing:
            existing = await db.scalar(
                select(WebhookEvent).where(
                    WebhookEvent.provider == "flutterwave",
                    WebhookEvent.payload_hash == payload_hash,
                )
            )
        if existing and existing.status == "PROCESSED":
            return {"status": "ok"}
        if not existing:
            stmt = insert(WebhookEvent).values(
                provider="flutterwave",
                event_id=event_id,
                event_type=event_type,
                signature_valid=True,
                payload_hash=payload_hash,
                status="RECEIVED",
                payload=sanitized,
            ).on_conflict_do_nothing()
            await db.execute(stmt)
            await db.commit()

    # Never credit from webhook fields alone. Re-query Flutterwave and validate
    # status, currency, reference, amount, and customer ownership server-side.
    provider = payment_provider()
    try:
        verified = await provider.verify_payment(provider_transaction_id=provider_transaction_id)
    except Exception:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "retry"}

    if verified.currency != "NGN" or verified.amount_kobo <= 0 or verified.status not in {"succeeded", "successful"}:
        async with AsyncSessionLocal() as db:
            event = await db.scalar(select(WebhookEvent).where(WebhookEvent.payload_hash == payload_hash).with_for_update())
            if event:
                event.status = "REJECTED"
                event.processing_error = "Provider verification was not a successful NGN payment"
                await db.commit()
        return {"status": "rejected"}

    async with AsyncSessionLocal() as db:
        event = await db.scalar(
            select(WebhookEvent).where(WebhookEvent.payload_hash == payload_hash).with_for_update()
        )
        if event and event.status == "PROCESSED":
            return {"status": "ok"}

        customer_id = verified.customer_id or _extract_customer_id(data)
        if not customer_id:
            if event:
                event.status = "REVIEW"
                event.processing_error = "Verified payment did not contain a provider customer id"
                await db.commit()
            return {"status": "review"}

        customer = await db.scalar(
            select(CustomerProfile).where(
                CustomerProfile.provider == verified.provider,
                CustomerProfile.provider_customer_id == customer_id,
            ).with_for_update()
        )
        if not customer:
            if event:
                event.status = "REVIEW"
                event.processing_error = "Provider customer could not be mapped to a Labour Pay user"
                await db.commit()
            return {"status": "review"}

        existing_payment = await db.scalar(
            select(PaymentTransaction).where(
                PaymentTransaction.provider == verified.provider,
                PaymentTransaction.provider_reference == verified.provider_transaction_id,
            ).with_for_update()
        )
        if existing_payment and existing_payment.status == "SUCCESS":
            if event:
                event.status = "PROCESSED"
                event.processed_at = datetime.now(timezone.utc)
            await db.commit()
            return {"status": "ok"}

        if not existing_payment:
            existing_payment = PaymentTransaction(
                user_id=customer.user_id,
                provider=verified.provider,
                transaction_type="WALLET_FUNDING",
                status="PENDING",
                currency="NGN",
                amount=verified.amount_kobo / 100,
                provider_reference=verified.provider_transaction_id,
                tx_ref=verified.tx_ref,
                raw_status=verified.status,
                idempotency_key=f"funding:{verified.provider_transaction_id}",
            )
            db.add(existing_payment)
            await db.flush()
        else:
            if existing_payment.user_id != customer.user_id:
                if event:
                    event.status = "REVIEW"
                    event.processing_error = "Provider reference mapped to a different user"
                    await db.commit()
                return {"status": "review"}
            existing_payment.status = "PENDING"
            existing_payment.raw_status = verified.status
            existing_payment.amount = verified.amount_kobo / 100

        try:
            wallet_tx = await credit_wallet_from_verified_funding(
                db,
                user_id=customer.user_id,
                amount_kobo=verified.amount_kobo,
                provider_reference=verified.provider_transaction_id,
                tx_ref=verified.tx_ref,
                metadata={"provider": verified.provider},
            )
        except ValueError as exc:
            existing_payment.status = "FAILED"
            existing_payment.failure_reason = str(exc)
            if event:
                event.status = "REJECTED"
                event.processing_error = str(exc)
            await db.commit()
            return {"status": "rejected"}
        except PermissionError as exc:
            existing_payment.status = "FAILED"
            existing_payment.failure_reason = str(exc)
            if event:
                event.status = "REVIEW"
                event.processing_error = str(exc)
            await db.commit()
            return {"status": "review"}

        existing_payment.status = "SUCCESS"
        existing_payment.raw_status = verified.status
        if event:
            event.status = "PROCESSED"
            event.processed_at = datetime.now(timezone.utc)
        await db.commit()
        return {"status": "ok", "wallet_transaction_id": str(wallet_tx.id)}
