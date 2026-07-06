from fastapi import APIRouter, Depends, HTTPException
from app.db import get_pool
from app.auth.dependencies import get_current_user
from app.cart.queries import (
    get_or_create_cart, add_item, update_item_quantity, remove_item, get_cart_contents
)
from app.cart.schemas import AddItemRequest, UpdateItemRequest, CartItemOut

router = APIRouter(prefix="/cart", tags=["cart"])


@router.get("", response_model=list[CartItemOut])
async def view_cart(current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        cart_id = await get_or_create_cart(conn, current_user["user_id"])
        rows = await get_cart_contents(conn, cart_id)
    return [dict(r) for r in rows]


@router.post("/items", status_code=201)
async def add_to_cart(payload: AddItemRequest, current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        cart_id = await get_or_create_cart(conn, current_user["user_id"])
        if payload.quantity <= 0:
            raise HTTPException(400, "Quantity must be positive")
        item = await add_item(conn, cart_id, payload.product_id, payload.quantity)
    return dict(item)


@router.put("/items/{product_id}")
async def update_cart_item(
    product_id: int, payload: UpdateItemRequest, current_user: dict = Depends(get_current_user)
):
    pool = get_pool()
    async with pool.acquire() as conn:
        cart_id = await get_or_create_cart(conn, current_user["user_id"])
        if payload.quantity <= 0:
            raise HTTPException(400, "Quantity must be positive; use DELETE to remove")
        item = await update_item_quantity(conn, cart_id, product_id, payload.quantity)
        if not item:
            raise HTTPException(404, "Item not in cart")
    return dict(item)


@router.delete("/items/{product_id}", status_code=204)
async def delete_cart_item(product_id: int, current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        cart_id = await get_or_create_cart(conn, current_user["user_id"])
        result = await remove_item(conn, cart_id, product_id)
        if result == "DELETE 0":
            raise HTTPException(404, "Item not in cart")
    return None