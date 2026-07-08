from pydantic import BaseModel, Field
from datetime import datetime

class ReviewCreate(BaseModel):
    product_id: int
    rating: int = Field(ge=1, le=5)
    comment: str | None = None

class ReviewOut(BaseModel):
    id: int
    user_id: str
    user_name: str
    rating: int
    comment: str | None
    created_at: datetime

class RatingSummary(BaseModel):
    review_count: int
    avg_rating: float