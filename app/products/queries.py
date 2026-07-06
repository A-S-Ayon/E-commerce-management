import asyncpg

async def list_categories(conn: asyncpg.Connection):
    return await conn.fetch("SELECT id, name FROM shop_categories ORDER BY name")


async def list_products(conn: asyncpg.Connection, category_id: int | None = None):
    if category_id is not None:
        return await conn.fetch(
            """
            SELECT p.id, p.name, p.description, p.price, p.image_url,
                   p.category_id, c.name AS category_name,
                   COALESCE(i.quantity, 0) AS stock
            FROM shop_products p
            JOIN shop_categories c ON c.id = p.category_id
            LEFT JOIN shop_inventory i ON i.product_id = p.id
            WHERE p.is_active = TRUE AND p.category_id = $1
            ORDER BY p.id
            """,
            category_id,
        )
    return await conn.fetch(
        """
        SELECT p.id, p.name, p.description, p.price, p.image_url,
               p.category_id, c.name AS category_name,
               COALESCE(i.quantity, 0) AS stock
        FROM shop_products p
        JOIN shop_categories c ON c.id = p.category_id
        LEFT JOIN shop_inventory i ON i.product_id = p.id
        WHERE p.is_active = TRUE
        ORDER BY p.id
        """
    )


async def get_product(conn: asyncpg.Connection, product_id: int):
    return await conn.fetchrow(
        """
        SELECT p.id, p.name, p.description, p.price, p.image_url,
               p.category_id, c.name AS category_name,
               COALESCE(i.quantity, 0) AS stock
        FROM shop_products p
        JOIN shop_categories c ON c.id = p.category_id
        LEFT JOIN shop_inventory i ON i.product_id = p.id
        WHERE p.id = $1 AND p.is_active = TRUE
        """,
        product_id,
    )


async def create_product(
    conn: asyncpg.Connection,
    category_id: int,
    name: str,
    description: str | None,
    price: float,
    image_url: str | None,
):
    async with conn.transaction():
        product = await conn.fetchrow(
            """
            INSERT INTO shop_products (category_id, name, description, price, image_url)
            VALUES ($1, $2, $3, $4, $5)
            RETURNING id, category_id, name, description, price, image_url, is_active
            """,
            category_id, name, description, price, image_url,
        )
        await conn.execute(
            "INSERT INTO shop_inventory (product_id, quantity) VALUES ($1, 0)",
            product["id"],
        )
        return product


async def update_product(
    conn: asyncpg.Connection,
    product_id: int,
    category_id: int,
    name: str,
    description: str | None,
    price: float,
    image_url: str | None,
    is_active: bool,
):
    return await conn.fetchrow(
        """
        UPDATE shop_products
        SET category_id = $2, name = $3, description = $4,
            price = $5, image_url = $6, is_active = $7
        WHERE id = $1
        RETURNING id, category_id, name, description, price, image_url, is_active
        """,
        product_id, category_id, name, description, price, image_url, is_active,
    )


async def update_stock(conn: asyncpg.Connection, product_id: int, quantity: int):
    return await conn.fetchrow(
        """
        UPDATE shop_inventory
        SET quantity = $2, updated_at = NOW()
        WHERE product_id = $1
        RETURNING product_id, quantity, updated_at
        """,
        product_id, quantity,
    )


async def log_admin_action(conn: asyncpg.Connection, admin_id: str, action: str):
    await conn.execute(
        "INSERT INTO shop_audit_logs (admin_id, action) VALUES ($1, $2)",
        admin_id, action,
    )