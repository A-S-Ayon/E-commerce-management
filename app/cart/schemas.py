from pydantic import BaseModel

class AddItemRequest(BaseModel):
    product_id: int
    quantity: int

class UpdateItemRequest(BaseModel):
    quantity: int

class CartItemOut(BaseModel):
    product_id: int
    name: str
    price: float
    quantity: int
    line_total: float
    stock: int