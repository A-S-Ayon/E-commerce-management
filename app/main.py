
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.db import init_db_pool, close_db_pool
from app.analytics.routes import router as analytics_router

from app.db import init_db_pool, close_db_pool, init_support_checkpointer, close_support_checkpointer
from app.support.routes import router as support_router

@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db_pool()
    await init_support_checkpointer()
    yield
    await close_support_checkpointer()
    await close_db_pool()


app = FastAPI(lifespan=lifespan)


# ── CORS middleware goes here, right after app is created ──


app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://127.0.0.1:5500",
        "http://localhost:5500",
        "https://frontend-shop-mauve.vercel.app"
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Then your routers, in whatever order they're currently in ──
from app.auth.routes import router as auth_router
from app.products.routes import router as products_router, categories_router
from app.cart.routes import router as cart_router
from app.wallet.routes import router as wallet_router
from app.orders.routes import router as orders_router
from app.addresses.routes import router as addresses_router
from app.reviews.routes import router as reviews_router
from app.wishlist.routes import router as wishlist_router
from app.support.routes import router as support_router

app.include_router(support_router)
app.include_router(support_router)
app.include_router(auth_router)
app.include_router(categories_router)
app.include_router(products_router)
app.include_router(cart_router)
app.include_router(wallet_router)
app.include_router(orders_router)
app.include_router(addresses_router)
app.include_router(reviews_router)
app.include_router(wishlist_router)
app.include_router(analytics_router)
