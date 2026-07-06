import asyncpg

async def credit_wallet(conn: asyncpg.Connection, user_id: str, amount: float):
    async with conn.transaction():
        wallet = await conn.fetchrow(
            "SELECT id FROM shop_wallets WHERE user_id = $1 FOR UPDATE",
            user_id,
        )
        if not wallet:
            return None
        await conn.execute(
            "UPDATE shop_wallets SET balance = balance + $2 WHERE id = $1",
            wallet["id"], amount,
        )
        await conn.execute(
            "INSERT INTO shop_wallet_transactions (wallet_id, amount, type) VALUES ($1, $2, 'Credit')",
            wallet["id"], amount,
        )
        return await conn.fetchrow(
            "SELECT id, user_id, balance FROM shop_wallets WHERE id = $1", wallet["id"]
        )


async def get_wallet(conn: asyncpg.Connection, user_id: str):
    return await conn.fetchrow(
        "SELECT id, user_id, balance FROM shop_wallets WHERE user_id = $1", user_id
    )


async def get_wallet_transactions(conn: asyncpg.Connection, user_id: str):
    return await conn.fetch(
        """
        SELECT wt.id, wt.amount, wt.type, wt.created_at
        FROM shop_wallet_transactions wt
        JOIN shop_wallets w ON w.id = wt.wallet_id
        WHERE w.user_id = $1
        ORDER BY wt.created_at DESC
        """,
        user_id,
    )