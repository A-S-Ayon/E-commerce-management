import asyncpg

async def run_checkout(conn: asyncpg.Connection, user_id: str) -> int:
    row = await conn.fetchrow("SELECT checkout($1) AS order_id", user_id)
    return row["order_id"]


async def get_order_with_items(conn: asyncpg.Connection, order_id: int):
    order = await conn.fetchrow(
        "SELECT id, user_id, total_amount, status, created_at FROM shop_orders WHERE id = $1",
        order_id,
    )
    items = await conn.fetch(
        """
        SELECT oi.product_id, p.name, oi.quantity, oi.unit_price,
               (oi.unit_price * oi.quantity) AS line_total
        FROM shop_order_items oi
        JOIN shop_products p ON p.id = oi.product_id
        WHERE oi.order_id = $1
        """,
        order_id,
    )
    invoice = await conn.fetchrow(
        "SELECT invoice_number, generated_at FROM shop_invoices WHERE order_id = $1",
        order_id,
    )
    return order, items, invoice


async def list_user_orders(conn: asyncpg.Connection, user_id: str):
    return await conn.fetch(
        """
        SELECT id, total_amount, status, created_at
        FROM shop_orders WHERE user_id = $1
        ORDER BY created_at DESC
        """,
        user_id,
    )


async def list_all_orders(conn: asyncpg.Connection, status: str | None = None):
    if status:
        return await conn.fetch(
            """
            SELECT o.id, o.user_id, u.name AS customer_name, u.email,
                   o.total_amount, o.status, o.created_at
            FROM shop_orders o
            JOIN shop_users u ON u.id = o.user_id
            WHERE o.status = $1
            ORDER BY o.created_at DESC
            """,
            status,
        )
    return await conn.fetch(
        """
        SELECT o.id, o.user_id, u.name AS customer_name, u.email,
               o.total_amount, o.status, o.created_at
        FROM shop_orders o
        JOIN shop_users u ON u.id = o.user_id
        ORDER BY o.created_at DESC
        """
    )