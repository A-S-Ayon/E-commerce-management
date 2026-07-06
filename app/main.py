from contextlib import asynccontextmanager
from fastapi import FastAPI
from app.db import init_db_pool, close_db_pool
from app.db import get_pool
from app.auth.routes import router as auth_router
from app.products.routes import router as products_router, categories_router
from app.cart.routes import router as cart_router
from app.orders.routes import router as orders_router
from app.wallet.routes import router as wallet_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    yield
    await close_db_pool()

app = FastAPI(lifespan=lifespan)


@app.get("/health/db")
async def db_health():
    async with get_pool().acquire() as conn:
        row = await conn.fetchrow("SELECT COUNT(*) AS n FROM shop_products")
    return {"products": row["n"]}

app.include_router(auth_router)
app.include_router(categories_router)
app.include_router(products_router)
app.include_router(cart_router)
app.include_router(orders_router)
app.include_router(wallet_router)
