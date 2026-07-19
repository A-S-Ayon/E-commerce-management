import asyncpg

async def run_checkout(conn: asyncpg.Connection, user_id: str, address_id: int) -> int:
    row = await conn.fetchrow(
        "SELECT checkout($1, $2) AS order_id", user_id, address_id
    )
    return row["order_id"]


async def get_order_with_items(conn: asyncpg.Connection, order_id: int):
    order = await conn.fetchrow(
    """
    SELECT id, user_id, total_amount, status, created_at,
           recipient_name, phone, address_line1, address_line2,
           city, state, postal_code, country,
           fulfillment_status, fulfillment_updated_at, received_confirmed_at
    FROM shop_orders WHERE id = $1
    """,
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

VALID_TRANSITIONS = {
    None: "Shipped",
    "Shipped": "Out for Delivery",
    "Out for Delivery": "Delivered",
}

async def update_fulfillment_status(conn: asyncpg.Connection, order_id: int, new_status: str, admin_id: str):
    order = await conn.fetchrow(
        "SELECT status FROM shop_orders WHERE id = $1", order_id
    )
    if not order:
        return None, "Order not found"
    if order["status"] != "Paid":
        return None, "Only Paid orders can be moved through fulfillment"

    try:
        updated = await conn.fetchrow(
            """
            UPDATE shop_orders
            SET fulfillment_status = $2, status_change_actor_id = $3
            WHERE id = $1
            RETURNING id, fulfillment_status, fulfillment_updated_at
            """,
            order_id, new_status, admin_id,
        )
    except asyncpg.PostgresError as e:
        # Trigger raised — invalid transition or missing actor id
        return None, str(e)

    return updated, None


async def confirm_receipt(conn: asyncpg.Connection, order_id: int, user_id: str):
    order = await conn.fetchrow(
        "SELECT user_id, fulfillment_status, received_confirmed_at FROM shop_orders WHERE id = $1",
        order_id,
    )
    if not order or str(order["user_id"]) != user_id:
        return None, "Order not found"
    if order["fulfillment_status"] != "Delivered":
        return None, "Order must be marked as Delivered before you can confirm receipt"
    if order["received_confirmed_at"] is not None:
        return None, "Receipt already confirmed"

    updated = await conn.fetchrow(
        """
        UPDATE shop_orders SET received_confirmed_at = NOW()
        WHERE id = $1
        RETURNING id, received_confirmed_at
        """,
        order_id,
    )
    return updated, None


async def get_status_history(conn: asyncpg.Connection, order_id: int):
    return await conn.fetch(
        """
        SELECT h.status, h.changed_at, u.name AS changed_by_name
        FROM shop_order_status_history h
        LEFT JOIN shop_users u ON u.id = h.changed_by
        WHERE h.order_id = $1
        ORDER BY h.changed_at
        """,
        order_id,
    )