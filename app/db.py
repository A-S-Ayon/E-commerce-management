import asyncpg
from psycopg_pool import AsyncConnectionPool
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

from app.config import settings

# ---------- Application Database Pool ----------

pool: asyncpg.Pool | None = None


async def init_db_pool():
    """Initialize asyncpg connection pool for application queries."""
    global pool

    pool = await asyncpg.create_pool(
        dsn=settings.DATABASE_URL,
        min_size=2,
        max_size=3,
    )


async def close_db_pool():

    global pool

    if pool is not None:
        await pool.close()
        pool = None


def get_pool() -> asyncpg.Pool:

    if pool is None:
        raise RuntimeError("Database pool not initialized.")
    return pool


# ---------- LangGraph Checkpointer ----------

support_checkpointer_pool: AsyncConnectionPool | None = None
support_checkpointer: AsyncPostgresSaver | None = None


async def init_support_checkpointer():
    """Initialize LangGraph PostgreSQL checkpointer."""
    global support_checkpointer_pool, support_checkpointer

    support_checkpointer_pool = AsyncConnectionPool(
        conninfo=settings.DATABASE_URL,
        max_size=5,
        kwargs={
            "autocommit": True,
            "prepare_threshold": None,
        },
        open=False,
    )

    await support_checkpointer_pool.open()

    support_checkpointer = AsyncPostgresSaver(support_checkpointer_pool)
    await support_checkpointer.setup()


async def close_support_checkpointer():
    """Close LangGraph connection pool."""
    global support_checkpointer_pool, support_checkpointer

    if support_checkpointer_pool is not None:
        await support_checkpointer_pool.close()
        support_checkpointer_pool = None
        support_checkpointer = None


def get_support_checkpointer() -> AsyncPostgresSaver:
    """Return initialized LangGraph checkpointer."""
    if support_checkpointer is None:
        raise RuntimeError("Support checkpointer not initialized.")
    return support_checkpointer
