import asyncpg

async def list_addresses(conn: asyncpg.Connection, user_id: str):
    return await conn.fetch(
        "SELECT * FROM shop_addresses WHERE user_id = $1 ORDER BY is_default DESC, id",
        user_id,
    )


async def create_address(conn: asyncpg.Connection, user_id: str, data: dict):
    async with conn.transaction():
        if data["is_default"]:
            await conn.execute(
                "UPDATE shop_addresses SET is_default = FALSE WHERE user_id = $1",
                user_id,
            )
        return await conn.fetchrow(
            """
            INSERT INTO shop_addresses (
                user_id, label, recipient_name, phone, address_line1, address_line2,
                city, state, postal_code, country, is_default
            ) VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
            RETURNING *
            """,
            user_id, data["label"], data["recipient_name"], data["phone"],
            data["address_line1"], data["address_line2"], data["city"],
            data["state"], data["postal_code"], data["country"], data["is_default"],
        )


async def get_address(conn: asyncpg.Connection, address_id: int, user_id: str):
    return await conn.fetchrow(
        "SELECT * FROM shop_addresses WHERE id = $1 AND user_id = $2",
        address_id, user_id,
    )


async def delete_address(conn: asyncpg.Connection, address_id: int, user_id: str):
    result = await conn.execute(
        "DELETE FROM shop_addresses WHERE id = $1 AND user_id = $2",
        address_id, user_id,
    )
    return result