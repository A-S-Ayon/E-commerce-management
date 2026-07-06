from pydantic import BaseModel

class CategoryOut(BaseModel):
    id: int
    name: str

class ProductOut(BaseModel):
    id: int
    name: str
    description: str | None
    price: float
    image_url: str | None
    category_id: int
    category_name: str
    stock: int


class ProductCreate(BaseModel):
    category_id: int
    name: str
    description: str | None = None
    price: float
    image_url: str | None = None

class ProductUpdate(ProductCreate):
    is_active: bool = True

class StockUpdate(BaseModel):
    quantity: int