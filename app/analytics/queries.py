import asyncpg
from datetime import datetime, timezone, timedelta


def _range_to_start_date(range_key: str) -> datetime:
    now = datetime.now(timezone.utc)
    if range_key == "today":
        return now.replace(hour=0, minute=0, second=0, microsecond=0)
    if range_key == "7d":
        return now - timedelta(days=7)
    if range_key == "30d":
        return now - timedelta(days=30)
    raise ValueError("range must be one of: today, 7d, 30d")


async def get_sales_summary(conn: asyncpg.Connection, range_key: str):
    start = _range_to_start_date(range_key)
    row = await conn.fetchrow(
        """
        SELECT
            COUNT(*) FILTER (WHERE status = 'Paid') AS order_count,
            COALESCE(SUM(total_amount) FILTER (WHERE status = 'Paid'), 0) AS revenue,
            COUNT(*) FILTER (WHERE status = 'Cancelled') AS cancelled_count,
            COUNT(*) AS total_count
        FROM shop_orders
        WHERE created_at >= $1
        """,
        start,
    )
    order_count = row["order_count"]
    revenue = row["revenue"]
    avg_order_value = (revenue / order_count) if order_count > 0 else 0
    cancellation_rate = (row["cancelled_count"] / row["total_count"]) if row["total_count"] > 0 else 0

    return {
        "range": range_key,
        "revenue": revenue,
        "order_count": order_count,
        "avg_order_value": round(float(avg_order_value), 2),
        "cancellation_rate": round(float(cancellation_rate), 4),
    }


async def get_top_products(conn: asyncpg.Connection, range_key: str, limit: int = 10):
    start = _range_to_start_date(range_key)
    return await conn.fetch(
        """
        SELECT p.id AS product_id, p.name,
               SUM(oi.quantity) AS units_sold,
               SUM(oi.quantity * oi.unit_price) AS revenue
        FROM shop_order_items oi
        JOIN shop_orders o ON o.id = oi.order_id
        JOIN shop_products p ON p.id = oi.product_id
        WHERE o.status = 'Paid' AND o.created_at >= $1
        GROUP BY p.id, p.name
        ORDER BY revenue DESC
        LIMIT $2
        """,
        start, limit,
    )


async def get_revenue_trend(conn: asyncpg.Connection, days: int = 30):
    start = datetime.now(timezone.utc) - timedelta(days=days)
    return await conn.fetch(
        """
        SELECT DATE(created_at) AS day, SUM(total_amount) AS revenue, COUNT(*) AS order_count
        FROM shop_orders
        WHERE status = 'Paid' AND created_at >= $1
        GROUP BY DATE(created_at)
        ORDER BY day
        """,
        start,
    )


async def get_status_breakdown(conn: asyncpg.Connection):
    return await conn.fetch(
        "SELECT status, COUNT(*) AS count FROM shop_orders GROUP BY status"
    )


async def get_low_stock(conn: asyncpg.Connection, threshold: int = 10):
    return await conn.fetch(
        """
        SELECT p.id AS product_id, p.name, i.quantity
        FROM shop_inventory i
        JOIN shop_products p ON p.id = i.product_id
        WHERE i.quantity < $1 AND p.is_active = TRUE
        ORDER BY i.quantity ASC
        """,
        threshold,
    )


async def get_new_customers(conn: asyncpg.Connection, range_key: str):
    start = _range_to_start_date(range_key)
    row = await conn.fetchrow(
        "SELECT COUNT(*) AS count FROM shop_users WHERE created_at >= $1", start
    )
    return row["count"]