import asyncpg
from app.config import settings

pool: asyncpg.Pool | None = None

async def init_db_pool():
    global pool
    pool = await asyncpg.create_pool(dsn=settings.DATABASE_URL, min_size=2, max_size=10)

async def close_db_pool():
    await pool.close()


def get_pool() -> asyncpg.Pool:
    if pool is None:
        raise RuntimeError("Database pool not initialized. Did lifespan startup run?")
    return pool