from fastapi import APIRouter, HTTPException, Query
from app.db import get_pool
from app.products.queries import list_categories, list_products, get_product
from app.products.schemas import CategoryOut, ProductOut

router = APIRouter(prefix="/products", tags=["products"])
categories_router = APIRouter(prefix="/categories", tags=["categories"])

from fastapi import Depends
from app.auth.dependencies import require_admin
from app.products.queries import create_product, update_product, update_stock, log_admin_action
from app.products.schemas import ProductCreate, ProductUpdate, StockUpdate


@router.post("", response_model=ProductOut, status_code=201)
async def create_new_product(payload: ProductCreate, admin: dict = Depends(require_admin)):
    pool = get_pool()
    async with pool.acquire() as conn:
        product = await create_product(
            conn, payload.category_id, payload.name,
            payload.description, payload.price, payload.image_url,
        )
        await log_admin_action(conn, admin["user_id"], f"Created product {product['id']}: {payload.name}")
    return {**dict(product), "category_name": "", "stock": 0}


@router.put("/{product_id}", response_model=ProductOut)
async def update_existing_product(
    product_id: int, payload: ProductUpdate, admin: dict = Depends(require_admin)
):
    pool = get_pool()
    async with pool.acquire() as conn:
        product = await update_product(
            conn, product_id, payload.category_id, payload.name,
            payload.description, payload.price, payload.image_url, payload.is_active,
        )
        if not product:
            raise HTTPException(404, "Product not found")
        await log_admin_action(conn, admin["user_id"], f"Updated product {product_id}")
        full = await get_product(conn, product_id)
    return dict(full)


@router.patch("/{product_id}/stock", response_model=ProductOut)
async def update_product_stock(
    product_id: int, payload: StockUpdate, admin: dict = Depends(require_admin)
):
    pool = get_pool()
    async with pool.acquire() as conn:
        stock_row = await update_stock(conn, product_id, payload.quantity)
        if not stock_row:
            raise HTTPException(404, "Product not found")
        await log_admin_action(conn, admin["user_id"], f"Set stock for product {product_id} to {payload.quantity}")
        full = await get_product(conn, product_id)
    return dict(full)


@categories_router.get("", response_model=list[CategoryOut])
async def get_categories():
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await list_categories(conn)
    return [dict(r) for r in rows]


@router.get("", response_model=list[ProductOut])
async def get_products(category_id: int | None = Query(default=None)):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await list_products(conn, category_id)
    return [dict(r) for r in rows]


@router.get("/{product_id}", response_model=ProductOut)
async def get_product_detail(product_id: int):
    pool = get_pool()
    async with pool.acquire() as conn:
        row = await get_product(conn, product_id)
    if not row:
        raise HTTPException(404, "Product not found")
    return dict(row)