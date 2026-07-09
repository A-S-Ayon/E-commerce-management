import asyncpg
import random
import secrets
from datetime import datetime, timedelta, timezone

async def get_user_by_id(conn: asyncpg.Connection, user_id: str):
    return await conn.fetchrow(
        "SELECT id, name, email, role_id FROM shop_users WHERE id = $1", user_id
    )


async def create_password_reset(conn: asyncpg.Connection, user_id: str) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=30)
    await conn.execute(
        "INSERT INTO shop_password_resets (user_id, token, expires_at) VALUES ($1, $2, $3)",
        user_id, token, expires_at,
    )
    return token


async def get_valid_reset(conn: asyncpg.Connection, token: str):
    return await conn.fetchrow(
        """
        SELECT id, user_id, expires_at, used
        FROM shop_password_resets
        WHERE token = $1
        """,
        token,
    )


async def mark_reset_used(conn: asyncpg.Connection, reset_id: int):
    await conn.execute("UPDATE shop_password_resets SET used = TRUE WHERE id = $1", reset_id)


async def update_user_password(conn: asyncpg.Connection, user_id: str, new_hash: str):
    await conn.execute("UPDATE shop_users SET password_hash = $2 WHERE id = $1", user_id, new_hash)

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




def generate_code() -> str:
    return f"{random.randint(0, 999999):06d}"


async def create_verification_code(conn: asyncpg.Connection, user_id: str) -> str:
    code = generate_code()
    expires_at = datetime.now(timezone.utc) + timedelta(minutes=15)
    await conn.execute(
        "INSERT INTO shop_verification_codes (user_id, code, expires_at) VALUES ($1, $2, $3)",
        user_id, code, expires_at,
    )
    return code


async def get_valid_code(conn: asyncpg.Connection, user_id: str, code: str):
    return await conn.fetchrow(
        """
        SELECT id, expires_at, used FROM shop_verification_codes
        WHERE user_id = $1 AND code = $2
        ORDER BY created_at DESC LIMIT 1
        """,
        user_id, code,
    )


async def mark_code_used(conn: asyncpg.Connection, code_id: int):
    await conn.execute("UPDATE shop_verification_codes SET used = TRUE WHERE id = $1", code_id)


async def mark_user_verified(conn: asyncpg.Connection, user_id: str):
    await conn.execute("UPDATE shop_users SET is_verified = TRUE WHERE id = $1", user_id)

async def get_user_by_email(conn: asyncpg.Connection, email: str):
    return await conn.fetchrow(
        "SELECT id, name, email, password_hash, role_id, is_verified FROM shop_users WHERE email = $1",
        email,
    )