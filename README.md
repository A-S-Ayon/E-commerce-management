# E-Commerce Backend — FastAPI + PostgreSQL (Raw SQL)

A full-stack e-commerce platform built to demonstrate database design and backend engineering fundamentals — no ORM, hand-written SQL throughout, with a transactional checkout system that uses row-level locking to guarantee correctness under concurrent load.

**Live demo:** [ecommerce-frontend-zeta-lime.vercel.app](https://ecommerce-frontend-zeta-lime.vercel.app)
**API docs (Swagger):** `<your-render-url>/docs`

---

## Why no ORM

This project intentionally uses `asyncpg` with raw parameterized SQL instead of SQLAlchemy or any ORM. The goal was to demonstrate direct command of relational database design — schema normalization, constraints, indexing, stored procedures, triggers, and transaction control — rather than relying on an abstraction layer to generate queries. Every query in this codebase was written and reasoned about by hand.

---

## Tech Stack

| Layer | Choice |
|---|---|
| API framework | FastAPI |
| Database driver | asyncpg (async, no ORM) |
| Database | PostgreSQL (hosted on Supabase) |
| Auth | JWT (python-jose) + bcrypt password hashing |
| Email | Brevo HTTP API (transactional email) |
| PDF generation | ReportLab |
| Package management | uv |
| Deployment | Render |
| Conversational assistant | LangGraph + Telegram (separate service) |

---

## Architecture Highlights

### 1. Transactional checkout with row-level locking

The checkout flow is implemented as a single PostgreSQL stored procedure (`checkout()`), not orchestrated across multiple application-layer calls. This was a deliberate design choice to guarantee atomicity:

```sql
BEGIN
  → Lock wallet row (FOR UPDATE)
  → Lock each inventory row (FOR UPDATE)
  → Validate stock and balance
  → Debit wallet
  → Create order + order_items (price snapshot)
  → Decrement inventory
  → Create payment + invoice
  → Snapshot shipping address onto the order
  → Clear cart
COMMIT — or ROLLBACK entirely on any failure
```

The `FOR UPDATE` locks on the wallet and inventory rows prevent two concurrent requests from double-charging a wallet or overselling stock — a classic race condition if checkout were implemented as separate `SELECT` → `UPDATE` calls from the application layer instead of one locked transaction. The FastAPI route calls this procedure as a single query:

```sql
SELECT checkout($1, $2);
```

Any `RAISE EXCEPTION` inside the procedure (insufficient stock, insufficient balance, empty cart) rolls back every write in the transaction — verified by testing that failed checkouts leave zero trace in orders, wallet balance, or inventory.

### 2. Historical snapshot pattern

Order line items store `unit_price` at time of purchase rather than joining live to `products.price`, and orders store a full snapshotted shipping address rather than a foreign key to a mutable `addresses` row. This ensures order history remains accurate even if a product's price changes or a user edits/deletes an address after the fact — the same pattern used by real payment and fulfillment systems.

### 3. Trigger-enforced business rules

Two independent business rules are enforced at the database level rather than in application code, so they hold regardless of which client or code path writes to the tables:

**Verified-purchase reviews** — a customer can only review a product they've actually bought:

```sql
CREATE TRIGGER trg_verified_purchase
BEFORE INSERT ON shop_reviews
FOR EACH ROW EXECUTE FUNCTION check_verified_purchase();
```

**Sequential order fulfillment** — an order's fulfillment status can only move forward one step at a time (`Shipped → Out for Delivery → Delivered`), never skipped or reversed. A `BEFORE UPDATE` trigger validates the transition, stamps the update timestamp, and writes an entry to a status history table automatically — all inside the same trigger, so no code path can update the status without the audit trail being created:

```sql
CREATE TRIGGER trg_log_fulfillment_status
BEFORE UPDATE ON shop_orders
FOR EACH ROW EXECUTE FUNCTION log_fulfillment_status_change();
```

Tested by attempting an invalid transition directly via SQL (bypassing the API entirely) — the trigger rejects it the same way the API does, confirming the guarantee lives in the database, not just the route handler.

### 4. Repository-style query organization

Each domain (`auth`, `products`, `cart`, `orders`, `wallet`, `reviews`, `addresses`, `wishlist`) has its own `queries.py` acting as a thin repository layer — isolated, parameterized SQL functions that routes call into. This keeps SQL centralized and testable without an ORM's model layer.

### 5. Connection pooling via lifespan

A single `asyncpg` connection pool is created on app startup and closed on shutdown using FastAPI's `lifespan` context manager, avoiding per-request connection overhead.

---

## Database Schema

15+ tables covering the full commerce lifecycle:

`shop_users`, `shop_roles`, `shop_products`, `shop_categories`, `shop_inventory`, `shop_wallets`, `shop_wallet_transactions`, `shop_carts`, `shop_cart_items`, `shop_orders`, `shop_order_items`, `shop_payments`, `shop_invoices`, `shop_addresses`, `shop_reviews`, `shop_wishlist`, `shop_audit_logs`, `shop_verification_codes`, `shop_password_resets`, `shop_order_status_history`

Key relational design elements:
- Primary/foreign keys with `ON DELETE CASCADE` where appropriate
- `CHECK` constraints for data integrity (e.g. `price > 0`, `rating BETWEEN 1 AND 5`, `quantity >= 0`)
- `UNIQUE` constraints enforcing business rules (one review per user per product, one cart item row per product)
- Indexes on frequently filtered/joined columns (`category_id`, `user_id`, `order_id`, etc.)
- ENUM types for constrained status fields (`order_status`, `payment_status`, `wallet_tx_type`, `fulfillment_status`)

The full schema is in [`schema.sql`](./schema.sql).

---

## Features

- **Auth**: signup with email verification (6-digit code via email), JWT login, password reset via emailed token, role-based access control (Customer / Admin)
- **Catalog**: categories, products with stock tracking, admin CRUD
- **Cart**: add/update/remove items with upsert-on-duplicate logic
- **Wallet**: balance tracking, admin credit (stand-in for a payment gateway), transaction history
- **Checkout**: atomic stored-procedure transaction with locking (see above)
- **Orders**: order history, full order detail with shipping snapshot, admin order visibility
- **Fulfillment tracking**: admin-driven Shipped → Out for Delivery → Delivered progression, enforced sequentially by a database trigger, with full status history
- **Receipt confirmation**: customer can confirm receipt of an order only once it's marked Delivered
- **Invoices**: server-generated PDF invoices with itemized breakdown and shipping address, built fresh from live data on every request
- **Reviews**: 1–5 star ratings, verified-purchase enforcement via trigger, product rating aggregation
- **Wishlist**: save products for later
- **Addresses**: multiple shipping addresses per user, default address support
- **Audit logging**: admin actions (product changes, wallet credits) are logged
- **Telegram assistant**: a LangGraph-based bot that answers product availability questions by querying `shop_products`/`shop_inventory` directly, plus RAG-based answers over ingested store policy documents

---

## API Overview

Full interactive documentation is available at `/docs` (Swagger UI) once running. Endpoint groups:

| Prefix | Purpose |
|---|---|
| `/auth` | signup, email verification, login, password reset |
| `/products`, `/categories` | catalog browsing + admin CRUD |
| `/cart` | cart management |
| `/wallet` | balance, transactions, admin credit |
| `/addresses` | shipping address management |
| `/orders` | checkout, order history, fulfillment status, receipt confirmation, invoice PDF, admin order view |
| `/reviews` | product reviews + rating summaries |
| `/wishlist` | saved products |

---

## Running Locally

```bash
# clone and install
git clone <your-repo-url>
cd ecommerce-backend
uv sync

# set up environment variables
cp .env.example .env   # then fill in real values

# run
uv run uvicorn app.main:app --reload
```

Visit `http://localhost:8000/docs` for the interactive API explorer.

### Required environment variables

```
DATABASE_URL=
JWT_SECRET=
JWT_ALGORITHM=HS256
JWT_EXPIRE_MINUTES=1440
BREVO_API_KEY=
MAIL_FROM=
FRONTEND_RESET_URL=
```

---

## Deployment

- **Backend**: Render (Docker/Python web service)
- **Database**: Supabase (managed PostgreSQL)
- **Email**: Brevo (HTTP API — chosen specifically because most cloud hosts, including Render's free tier, block outbound SMTP ports 25/465/587; an HTTPS-based email API avoids that restriction entirely)
- **Frontend**: static HTML/CSS/JS hosted on Vercel

---

## Known Limitations / Future Work

Built as a focused demonstration of relational database design under a real time constraint — the following are deliberately out of scope for now:

- Single short-lived JWT (no refresh token rotation)
- Bearer token stored client-side rather than HttpOnly cookies
- No OAuth (Google Sign-In) support
- No MFA/TOTP for admin accounts
- No rate limiting on auth endpoints
- No pagination on list endpoints (fine at current scale; would need it at production scale)
- No automated test suite (checkout and fulfillment transaction behavior were verified manually, including rollback-on-failure and invalid-transition scenarios)
- An admin can currently place, fulfill, and confirm receipt of their own order with no conflict-of-interest check
- No order cancellation/refund flow, despite `order_status` including a `Cancelled` state

---

## Author

1. Animesh Singha Ayon (Backend developer) 51% 
2. Soumik Dev (Frontend developer) 49%
