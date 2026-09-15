from pydantic import BaseModel, Field


class VirtualAccountRequest(BaseModel):
    verified_identifier: str = Field(min_length=11, max_length=11, pattern=r"^[0-9]{11}$")


class VirtualAccountResponse(BaseModel):
    account_number: str
    bank_name: str
    bank_code: str | None = None
    currency: str
    account_type: str
    status: str
    reference: str
