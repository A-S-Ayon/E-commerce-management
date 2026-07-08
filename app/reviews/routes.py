from fastapi import APIRouter, Depends, HTTPException
import asyncpg
from app.db import get_pool
from app.auth.dependencies import get_current_user
from app.reviews.queries import create_review, list_product_reviews, get_product_rating_summary
from app.reviews.schemas import ReviewCreate, ReviewOut, RatingSummary

router = APIRouter(prefix="/reviews", tags=["reviews"])


@router.post("", status_code=201)
async def add_review(payload: ReviewCreate, current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            row = await create_review(
                conn, current_user["user_id"], payload.product_id, payload.rating, payload.comment
            )
        except asyncpg.PostgresError as e:
            # covers both the verified-purchase trigger and duplicate-review UNIQUE constraint
            raise HTTPException(400, str(e))
    return {**dict(row), "user_id": str(row["user_id"])}


@router.get("/product/{product_id}", response_model=list[ReviewOut])
async def get_reviews_for_product(product_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await list_product_reviews(conn, product_id)
    return [{**dict(r), "user_id": str(r["user_id"])} for r in rows]


@router.get("/product/{product_id}/summary", response_model=RatingSummary)
async def get_rating_summary(product_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await get_product_rating_summary(conn, product_id)
    return dict(row)