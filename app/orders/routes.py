from fastapi import APIRouter, Depends, HTTPException
import asyncpg
from app.db import get_pool
from app.auth.dependencies import get_current_user
from app.orders.queries import run_checkout, get_order_with_items, list_user_orders
from app.orders.schemas import OrderOut, OrderSummary
from fastapi import Query
from app.auth.dependencies import require_admin
from app.orders.queries import list_all_orders
from app.orders.schemas import AdminOrderOut
from fastapi import Response
from app.invoices.pdf import generate_invoice_pdf


router = APIRouter(prefix="/orders", tags=["orders"])



@router.post("/checkout", response_model=OrderOut, status_code=201)
async def checkout(current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        try:
            order_id = await run_checkout(conn, current_user["user_id"])
        except asyncpg.PostgresError as e:
            raise HTTPException(400, str(e))

        order, items, invoice = await get_order_with_items(conn, order_id)

    return {
        **dict(order),
        "user_id": str(order["user_id"]),
        "items": [dict(i) for i in items],
        "invoice_number": invoice["invoice_number"] if invoice else None,
    }


@router.get("", response_model=list[OrderSummary])
async def my_orders(current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await list_user_orders(conn, current_user["user_id"])
    return [dict(r) for r in rows]


@router.get("/admin/all", response_model=list[AdminOrderOut])
async def admin_list_orders(
    status: str | None = Query(default=None),
    admin: dict = Depends(require_admin),
):
    pool = get_pool()
    async with pool.acquire() as conn:
        rows = await list_all_orders(conn, status)
    return [{**dict(r), "user_id": str(r["user_id"])} for r in rows]


@router.get("/{order_id}", response_model=OrderOut)
async def order_detail(order_id: int, current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        order, items, invoice = await get_order_with_items(order_id=order_id, conn=conn)
        if not order or str(order["user_id"]) != current_user["user_id"]:
            raise HTTPException(404, "Order not found")
    return {
        **dict(order),
        "user_id": str(order["user_id"]),
        "items": [dict(i) for i in items],
        "invoice_number": invoice["invoice_number"] if invoice else None,
    }


@router.get("/{order_id}/invoice")
async def download_invoice(order_id: int, current_user: dict = Depends(get_current_user)):
    pool = get_pool()
    async with pool.acquire() as conn:
        order, items, invoice = await get_order_with_items(conn, order_id)

    if not order:
        raise HTTPException(404, "Order not found")

    # Ownership check: only the order's own customer, or an admin, can download it
    if str(order["user_id"]) != current_user["user_id"] and current_user["role_id"] != 1:
        raise HTTPException(404, "Order not found")

    if not invoice:
        raise HTTPException(404, "Invoice not generated for this order")

    pdf_bytes = generate_invoice_pdf(
        dict(order), [dict(i) for i in items], invoice["invoice_number"]
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'attachment; filename="{invoice["invoice_number"]}.pdf"'
        },
    )