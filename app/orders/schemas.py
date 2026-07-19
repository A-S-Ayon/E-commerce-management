from pydantic import BaseModel
from datetime import datetime
class OrderItemOut(BaseModel):
    product_id: int
    name: str
    quantity: int
    unit_price: float
    line_total: float

class OrderSummary(BaseModel):
    id: int
    total_amount: float
    status: str
    created_at: datetime


class AdminOrderOut(BaseModel):
    id: int
    user_id: str
    customer_name: str
    email: str
    total_amount: float
    status: str
    created_at: datetime

class CheckoutRequest(BaseModel):
    address_id: int

class OrderOut(BaseModel):
    id: int
    user_id: str
    total_amount: float
    status: str
    created_at: datetime
    recipient_name: str | None
    phone: str | None
    address_line1: str | None
    address_line2: str | None
    city: str | None
    state: str | None
    postal_code: str | None
    country: str | None
    fulfillment_status: str | None
    fulfillment_updated_at: datetime | None
    received_confirmed_at: datetime | None
    items: list[OrderItemOut]
    invoice_number: str | None


class FulfillmentUpdate(BaseModel):
    status: str  # "Shipped" | "Out for Delivery" | "Delivered"

class FulfillmentOut(BaseModel):
    id: int
    fulfillment_status: str | None
    fulfillment_updated_at: datetime | None

class ReceiptConfirmOut(BaseModel):
    id: int
    received_confirmed_at: datetime

class StatusHistoryOut(BaseModel):
    status: str
    changed_at: datetime
    changed_by_name: str | None