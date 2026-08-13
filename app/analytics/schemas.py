from pydantic import BaseModel
from datetime import date

class SalesSummary(BaseModel):
    range: str
    revenue: float
    order_count: int
    avg_order_value: float
    cancellation_rate: float

class TopProduct(BaseModel):
    product_id: int
    name: str
    units_sold: int
    revenue: float

class RevenuePoint(BaseModel):
    day: date
    revenue: float
    order_count: int

class StatusBreakdown(BaseModel):
    status: str
    count: int

class LowStockItem(BaseModel):
    product_id: int
    name: str
    quantity: int

class NewCustomers(BaseModel):
    range: str
    count: int