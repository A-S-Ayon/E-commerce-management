import asyncpg

async def create_review(conn: asyncpg.Connection, user_id: str, product_id: int, rating: int, comment: str | None):
    return await conn.fetchrow(
        """
        INSERT INTO shop_reviews (user_id, product_id, rating, comment)
        VALUES ($1, $2, $3, $4)
        RETURNING id, user_id, product_id, rating, comment, created_at
        """,
        user_id, product_id, rating, comment,
    )


async def list_product_reviews(conn: asyncpg.Connection, product_id: int):
    return await conn.fetch(
        """
        SELECT r.id, r.user_id, u.name AS user_name, r.rating, r.comment, r.created_at
        FROM shop_reviews r
        JOIN shop_users u ON u.id = r.user_id
        WHERE r.product_id = $1
        ORDER BY r.created_at DESC
        """,
        product_id,
    )


async def get_product_rating_summary(conn: asyncpg.Connection, product_id: int):
    return await conn.fetchrow(
        """
        SELECT COUNT(*) AS review_count, COALESCE(AVG(rating), 0)::NUMERIC(3,2) AS avg_rating
        FROM shop_reviews WHERE product_id = $1
        """,
        product_id,
    )