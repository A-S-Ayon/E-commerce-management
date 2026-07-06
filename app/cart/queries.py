import asyncpg

async def get_or_create_cart(conn: asyncpg.Connection, user_id: str) -> int:
    cart = await conn.fetchrow("SELECT id FROM shop_carts WHERE user_id = $1", user_id)
    if cart:
        return cart["id"]
    cart = await conn.fetchrow(
        "INSERT INTO shop_carts (user_id) VALUES ($1) RETURNING id", user_id
    )
    return cart["id"]


async def add_item(conn: asyncpg.Connection, cart_id: int, product_id: int, quantity: int):
    return await conn.fetchrow(
        """
        INSERT INTO shop_cart_items (cart_id, product_id, quantity)
        VALUES ($1, $2, $3)
        ON CONFLICT (cart_id, product_id)
        DO UPDATE SET quantity = shop_cart_items.quantity + EXCLUDED.quantity
        RETURNING id, cart_id, product_id, quantity
        """,
        cart_id, product_id, quantity,
    )


async def update_item_quantity(conn: asyncpg.Connection, cart_id: int, product_id: int, quantity: int):
    return await conn.fetchrow(
        """
        UPDATE shop_cart_items SET quantity = $3
        WHERE cart_id = $1 AND product_id = $2
        RETURNING id, cart_id, product_id, quantity
        """,
        cart_id, product_id, quantity,
    )


async def remove_item(conn: asyncpg.Connection, cart_id: int, product_id: int):
    result = await conn.execute(
        "DELETE FROM shop_cart_items WHERE cart_id = $1 AND product_id = $2",
        cart_id, product_id,
    )
    return result  # e.g. "DELETE 1" or "DELETE 0"


async def get_cart_contents(conn: asyncpg.Connection, cart_id: int):
    return await conn.fetch(
        """
        SELECT ci.product_id, p.name, p.price, ci.quantity,
               (p.price * ci.quantity) AS line_total,
               COALESCE(i.quantity, 0) AS stock
        FROM shop_cart_items ci
        JOIN shop_products p ON p.id = ci.product_id
        LEFT JOIN shop_inventory i ON i.product_id = ci.product_id
        WHERE ci.cart_id = $1
        ORDER BY ci.id
        """,
        cart_id,
    )