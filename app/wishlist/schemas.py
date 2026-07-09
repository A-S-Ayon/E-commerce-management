from pydantic import BaseModel
from datetime import datetime

class WishlistAdd(BaseModel):
    product_id: int

class WishlistItemOut(BaseModel):
    id: int
    product_id: int
    name: str
    price: float
    image_url: str | None
    stock: int
    created_at: datetime