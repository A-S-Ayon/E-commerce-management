from pydantic import BaseModel
from datetime import datetime

class AddressCreate(BaseModel):
    label: str | None = None
    recipient_name: str
    phone: str | None = None
    address_line1: str
    address_line2: str | None = None
    city: str
    state: str | None = None
    postal_code: str
    country: str
    is_default: bool = False

class AddressOut(AddressCreate):
    id: int
    user_id: str
    created_at: datetime