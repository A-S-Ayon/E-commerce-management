from fastapi import APIRouter, Depends, HTTPException
from app.db import get_pool
from app.auth.dependencies import get_current_user
from app.wishlist.queries import add_to_wishlist, remove_from_wishlist, list_wishlist
from app.wishlist.schemas import WishlistAdd, WishlistItemOut

router = APIRouter(prefix="/wishlist", tags=["wishlist"])


@router.get("", response_model=list[WishlistItemOut])
async def get_wishlist(current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await list_wishlist(conn, current_user["user_id"])
    return [dict(r) for r in rows]


@router.post("", status_code=201)
async def add_item(payload: WishlistAdd, current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await add_to_wishlist(conn, current_user["user_id"], payload.product_id)
    if not row:
        return {"message": "Already in wishlist"}
    return dict(row)


@router.delete("/{product_id}", status_code=204)
async def remove_item(product_id: int, current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        result = await remove_from_wishlist(conn, current_user["user_id"], product_id)
        if result == "DELETE 0":
            raise HTTPException(404, "Item not in wishlist")
    return None