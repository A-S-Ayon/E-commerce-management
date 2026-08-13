from fastapi import APIRouter, Depends, Query, HTTPException
from app.db import get_pool
from app.auth.dependencies import require_admin
from app.analytics.queries import (
    get_sales_summary, get_top_products, get_revenue_trend,
    get_status_breakdown, get_low_stock, get_new_customers,
)
from app.analytics.schemas import (
    SalesSummary, TopProduct, RevenuePoint, StatusBreakdown, LowStockItem, NewCustomers,
)

router = APIRouter(prefix="/analytics", tags=["analytics"])


@router.get("/sales", response_model=SalesSummary)
async def sales_summary(range: str = Query(default="today"), admin: dict = Depends(require_admin)):
    if range not in ("today", "7d", "30d"):
        raise HTTPException(400, "range must be one of: today, 7d, 30d")
    pool = get_pool()
    async with pool.acquire() as conn:
        return await get_sales_summary(conn, range)


@router.get("/top-products", response_model=list[TopProduct])
async def top_products(range: str = Query(default="30d"), admin: dict = Depends(require_admin)):
    if range not in ("today", "7d", "30d"):
        raise HTTPException(400, "range must be one of: today, 7d, 30d")
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await get_top_products(conn, range)
    return [dict(r) for r in rows]


@router.get("/revenue-trend", response_model=list[RevenuePoint])
async def revenue_trend(days: int = Query(default=30, ge=1, le=90), admin: dict = Depends(require_admin)):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await get_revenue_trend(conn, days)
    return [dict(r) for r in rows]


@router.get("/status-breakdown", response_model=list[StatusBreakdown])
async def status_breakdown(admin: dict = Depends(require_admin)):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await get_status_breakdown(conn)
    return [dict(r) for r in rows]


@router.get("/low-stock", response_model=list[LowStockItem])
async def low_stock(threshold: int = Query(default=10, ge=1), admin: dict = Depends(require_admin)):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await get_low_stock(conn, threshold)
    return [dict(r) for r in rows]


@router.get("/new-customers", response_model=NewCustomers)
async def new_customers(range: str = Query(default="7d"), admin: dict = Depends(require_admin)):
    if range not in ("today", "7d", "30d"):
        raise HTTPException(400, "range must be one of: today, 7d, 30d")
    pool = get_pool()
    async with pool.acquire() as conn:
        count = await get_new_customers(conn, range)
    return {"range": range, "count": count}