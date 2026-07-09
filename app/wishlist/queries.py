import asyncpg

async def add_to_wishlist(conn: asyncpg.Connection, user_id: str, product_id: int):
    return await conn.fetchrow(
        """
        INSERT INTO shop_wishlist (user_id, product_id)
        VALUES ($1, $2)
        ON CONFLICT (user_id, product_id) DO NOTHING
        RETURNING id, user_id, product_id, created_at
        """,
        user_id, product_id,
    )


async def remove_from_wishlist(conn: asyncpg.Connection, user_id: str, product_id: int):
    return await conn.execute(
        "DELETE FROM shop_wishlist WHERE user_id = $1 AND product_id = $2",
        user_id, product_id,
    )


async def list_wishlist(conn: asyncpg.Connection, user_id: str):
    return await conn.fetch(
        """
        SELECT w.id, w.product_id, p.name, p.price, p.image_url,
               COALESCE(i.quantity, 0) AS stock, w.created_at
        FROM shop_wishlist w
        JOIN shop_products p ON p.id = w.product_id
        LEFT JOIN shop_inventory i ON i.product_id = w.product_id
        WHERE w.user_id = $1
        ORDER BY w.created_at DESC
        """,
        user_id,
    )