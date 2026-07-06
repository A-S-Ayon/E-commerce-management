import asyncpg

async def get_user_by_email(conn: asyncpg.Connection, email: str):
    return await conn.fetchrow(
        "SELECT id, name, email, password_hash, role_id FROM shop_users WHERE email = $1",
        email,
    )

async def create_user_with_wallet(
    conn: asyncpg.Connection, name: str, email: str, password_hash: str, role_id: int
):
    async with conn.transaction():
        user = await conn.fetchrow(
            """
            INSERT INTO shop_users (name, email, password_hash, role_id)
            VALUES ($1, $2, $3, $4)
            RETURNING id, name, email, role_id
            """,
            name, email, password_hash, role_id,
        )
        await conn.execute(
            "INSERT INTO shop_wallets (user_id, balance) VALUES ($1, 0)",
            user["id"],
        )
        return user

async def get_customer_role_id(conn: asyncpg.Connection) -> int:
    row = await conn.fetchrow("SELECT id FROM shop_roles WHERE role_name = 'Customer'")
    return row["id"]