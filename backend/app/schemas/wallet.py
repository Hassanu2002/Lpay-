from decimal import Decimal
from pydantic import BaseModel, Field


class WalletResponse(BaseModel):
    currency: str
    balance: Decimal
    status: str


class WalletTransactionResponse(BaseModel):
    id: str
    transaction_type: str
    status: str
    amount: Decimal
    currency: str
    reference: str
    provider_reference: str | None = None
    description: str
    created_at: str
