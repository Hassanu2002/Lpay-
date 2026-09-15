from pydantic import BaseModel, Field


class KYCSubmitRequest(BaseModel):
    method: str = Field(pattern=r"^(?i:BVN|NIN)$")
    value: str = Field(min_length=11, max_length=11, pattern=r"^[0-9]{11}$")


class KYCResponse(BaseModel):
    id: str
    method: str
    status: str
    provider: str
    provider_reference: str
    verified_at: str | None = None
