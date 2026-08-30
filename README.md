# Shopify — E-Commerce Backend

A full-featured e-commerce backend built with FastAPI and raw SQL (no ORM) on top of PostgreSQL. The database is designed around real relational integrity — foreign keys, constraints, stored procedures, and triggers — rather than delegating that logic to the application layer. The centerpiece is a `checkout()` stored procedure that runs stock validation, wallet debit, order creation, and cart clearing inside a single atomic transaction with row-level locking, so concurrent checkouts on limited stock cannot oversell or double-charge.

Beyond the storefront basics (catalog, cart, checkout, orders), the project includes wallet-based payments, address management, PDF invoice generation, verified-purchase-only product reviews, an admin analytics dashboard, and a login-gated AI support chatbot built on LangGraph that can answer questions and perform actions (cancel an order, add to cart) scoped strictly to the authenticated user's own data.

## Key Features

**Authentication & Accounts**
- Email/password signup with bcrypt password hashing
- Email verification via a 6-digit code (login blocked until verified)
- Password reset via single-use, expiring email tokens
- JWT-based auth with role-based access control (Admin / Customer)
- Admin action audit logging

**Catalog & Shopping**
- Product catalog with categories, stock tracking, and active/inactive flags
- Shopping cart (add, update, remove, upsert on duplicate add)
- Wishlist
- Saved shipping addresses with a default-address flag

**Orders & Payments**
- Internal wallet system (balance, credit, transaction history)
- Atomic, row-locked checkout via a PostgreSQL stored procedure
- Shipping address and customer identity snapshotted onto each order at checkout time (immune to later profile/address edits)
- Estimated delivery window (5–7 days from order date)
- Order cancellation with automatic stock restoration and wallet refund, restricted to a valid pre-shipping window
- Fulfillment tracking (Shipped → Out for Delivery → Delivered) enforced as a forward-only state machine at the database level via a trigger
- Full fulfillment status history, logged automatically
- Customer receipt confirmation
- PDF invoice generation, rendered live from current order data

**Reviews**
- Product reviews restricted to verified purchasers, enforced by a database trigger (not just application logic)

**Admin Analytics**
- Sales summary (revenue, order count, average order value, cancellation rate) by time range
- Top-selling products by revenue
- Daily revenue trend
- Order status breakdown
- Low-stock alerts
- New customer counts

**AI Support Chatbot**
- LangGraph-based conversational agent, available only to authenticated users
- Persistent per-user conversation memory (PostgreSQL-backed checkpointer)
- Tools scoped to the authenticated user's own data at the query level — the agent cannot access another user's orders or wallet regardless of what is asked
- Can answer order/product/policy questions and perform actions (add to cart, cancel an order) with an explicit confirmation step before any state-changing action
- Retrieval-augmented answers for store policy / terms & conditions questions

## Tech Stack

| Layer | Technology |
|---|---|
| API framework | FastAPI |
| Database driver | `asyncpg` (raw SQL, no ORM) |
| Database | PostgreSQL (Supabase) |
| Auth | JWT (`python-jose`), `passlib` + `bcrypt` |
| Email | Brevo HTTP API |
| PDF generation | ReportLab |
| Chatbot / agent | LangGraph, LangChain, Cohere (`ChatCohere`) |
| Chatbot memory | `AsyncPostgresSaver` (PostgreSQL-backed LangGraph checkpointer) |
| Package management | `uv` |
| Deployment | Render |

## Architecture

```
Client (web frontend / Swagger UI)
        │
        ▼
   FastAPI application
   ├── auth          — signup, login, verification, password reset
   ├── products       — catalog, categories, admin CRUD
   ├── cart / wishlist
   ├── wallet         — balance, transactions, admin credit
   ├── addresses
   ├── orders         — checkout, cancellation, fulfillment, invoices
   ├── reviews
   ├── analytics       — admin dashboards
   └── support         — LangGraph chatbot endpoint
        │
        ▼
   PostgreSQL (Supabase)
   ├── Tables: users, products, inventory, cart, orders, wallets, etc.
   ├── Stored procedures: checkout(), cancel_order()
   ├── Triggers: verified-purchase reviews, fulfillment state machine
   └── LangGraph checkpoint tables (chatbot conversation memory)
```

Business-critical operations — checkout and cancellation — are implemented as PostgreSQL stored procedures rather than multi-step application code. Each runs as a single transaction with `FOR UPDATE` row locking on wallet and inventory rows, so the database itself guarantees correctness under concurrent access, independent of the calling code.

The fulfillment status trigger enforces valid state transitions (`Shipped → Out for Delivery → Delivered`) at the database layer, so no code path — including a direct SQL statement bypassing the API — can skip or reverse a step.

## Project Structure

```
app/
├── main.py               # FastAPI app setup, CORS, router registration, lifespan
├── db.py                 # asyncpg connection pool + LangGraph checkpointer setup
├── config.py              # Environment-based settings (pydantic-settings)
├── auth/                  # Signup, login, email verification, password reset, JWT
├── products/               # Catalog CRUD, categories
├── cart/
├── wishlist/
├── wallet/
├── addresses/
├── orders/                 # Checkout, cancellation, fulfillment, order history
├── invoices/               # PDF invoice generation
├── reviews/
├── analytics/               # Admin dashboard aggregate queries
├── support/                 # LangGraph chatbot: tools, graph, chat endpoint
└── email/                   # Transactional email (Brevo)

schema.sql                  # Full consolidated database schema
```

Each feature module follows the same internal structure: `queries.py` (raw SQL against `asyncpg`), `schemas.py` (Pydantic request/response models), and `routes.py` (FastAPI route handlers).

## Prerequisites

- Python 3.13+
- [`uv`](https://docs.astral.sh/uv/) for dependency management
- A PostgreSQL database (this project uses [Supabase](https://supabase.com))
- A [Brevo](https://www.brevo.com) account for transactional email
- A [Cohere](https://cohere.com) API key for the support chatbot

## Installation

```bash
git clone <repository-url>
cd ecommerce-backend
uv sync
```

Set up the database schema by running `schema.sql` against a fresh PostgreSQL database (e.g. via the Supabase SQL editor).

## Configuration

Create a `.env` file in the project root:

```env
# Database
DATABASE_URL=postgresql://user:password@your-db-host:5432/postgres

# JWT
JWT_SECRET=your_jwt_secret_here
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440

# Email (Brevo)
BREVO_API_KEY=your_brevo_api_key_here
MAIL_FROM=your_verified_sender@example.com
FRONTEND_RESET_URL=http://localhost:3000/reset-password

# Support chatbot
DB_URI=postgresql://user:password@your-db-host:5432/postgres
COHERE_API_KEY=your_cohere_api_key_here
```

`DATABASE_URL` is used by the main application (`asyncpg`); `DB_URI` is used by the chatbot's LangGraph checkpointer for conversation memory. They can point to the same database.

If deploying behind a connection pooler with a low session limit (e.g. Supabase's free-tier session pooler), use the transaction pooler connection string for `DATABASE_URL` and set `statement_cache_size=0` on the `asyncpg` pool, since transaction-mode poolers do not support prepared statements.

Never commit `.env` — it is excluded via `.gitignore`.

## Running the Project

```bash
uv run uvicorn app.main:app --reload
```

The API is available at `http://localhost:8000`, with interactive documentation at `http://localhost:8000/docs`.

## Usage

All protected endpoints require a JWT in the `Authorization` header:

```
Authorization: Bearer <token>
```

### Example: sign up and verify an account

```bash
curl -X POST http://localhost:8000/auth/signup \
  -H "Content-Type: application/json" \
  -d '{"name": "Jane Doe", "email": "jane@example.com", "password": "secure_password"}'
```

A 6-digit verification code is emailed to the address provided. Verify with:

```bash
curl -X POST http://localhost:8000/auth/verify-email \
  -H "Content-Type: application/json" \
  -d '{"email": "jane@example.com", "code": "123456"}'
```

This returns an access token. Login is blocked until verification is complete.

### Example: checkout

```bash
curl -X POST http://localhost:8000/orders/checkout \
  -H "Authorization: Bearer <token>" \
  -H "Content-Type: application/json" \
  -d '{"address_id": 1}'
```

Response:

```json
{
  "id": 12,
  "total_amount": 149.99,
  "status": "Paid",
  "fulfillment_status": null,
  "estimated_delivery_min": "2026-08-05",
  "estimated_delivery_max": "2026-08-07",
  "items": [
    { "product_id": 3, "name": "Wireless Mouse", "quantity": 1, "unit_price": 149.99, "line_total": 149.99 }
  ],
  "invoice_number": "INV-12-20260731153000"
}
```

Checkout fails with `400` and a descriptive message if the cart is empty, stock is insufficient, or the wallet balance is too low — no partial state is ever written, since the entire operation runs inside one database transaction.

## API Documentation

Full interactive API documentation (all endpoints, request/response schemas) is auto-generated by FastAPI and available at `/docs` (Swagger UI) once the server is running.

### Endpoint groups

| Prefix | Description |
|---|---|
| `/auth` | Signup, login, email verification, password reset |
| `/products`, `/categories` | Catalog browsing and admin management |
| `/cart` | Shopping cart |
| `/wishlist` | Wishlist |
| `/wallet` | Wallet balance, transactions, admin credit |
| `/addresses` | Shipping addresses |
| `/orders` | Checkout, order history, cancellation, fulfillment, invoices |
| `/reviews` | Product reviews |
| `/analytics` | Admin sales and inventory dashboards |
| `/support/chat` | AI support chatbot (authenticated users only) |

## Testing

No automated test suite is currently included. All functionality has been verified manually via the Swagger UI, including concurrency and rollback behavior for the checkout and cancellation transactions.

## Deployment

The application is deployed on [Render](https://e-commerce-management-lhdp.onrender.com/docs):

```bash
uv export --no-hashes --format requirements-txt > requirements.txt
```

- **Build command:** `pip install -r requirements.txt`
- **Start command:** `uvicorn app.main:app --host 0.0.0.0 --port $PORT`

All environment variables listed in [Configuration](#configuration) must be set in the Render dashboard.

## Future Improvements

- Automated test suite (pytest), particularly concurrency tests for the checkout transaction
- Refresh tokens and HttpOnly cookie-based auth (currently a single long-lived JWT)
- Real payment gateway integration (currently wallet-based only)
- Rate limiting on authentication endpoints
- Pagination on list endpoints
- Product search endpoint using the existing trigram index
- Order returns (post-delivery), as distinct from pre-shipping cancellation
- MFA for admin accounts
- Seller role and multi-vendor support

## License

Not currently specified.
