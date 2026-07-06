from pydantic import BaseModel
from datetime import datetime

class OrderItemOut(BaseModel):
    product_id: int
    name: str
    quantity: int
    unit_price: float
    line_total: float

class OrderOut(BaseModel):
    id: int
    user_id: str
    total_amount: float
    status: str
    created_at: datetime
    items: list[OrderItemOut]
    invoice_number: str | None

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