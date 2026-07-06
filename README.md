# E-Commerce Backend

A database-focused e-commerce backend built for a DBMS course project. Deliberately avoids an ORM — all queries are raw SQL via `asyncpg` — to showcase stored procedures, transactions, row locking, and normalized schema design directly.

## Tech Stack

- **FastAPI** — web framework
- **asyncpg** — async PostgreSQL driver (no ORM)
- **Supabase** — hosted PostgreSQL database
- **uv** — Python package/project manager
- **JWT (python-jose)** — authentication
- **bcrypt / passlib** — password hashing
- **reportlab** — PDF invoice generation

Core business logic (checkout) runs as a PostgreSQL stored procedure (`checkout()`), called from the API as a single query. This keeps stock validation, wallet debit, order creation, and cart clearing atomic — if anything fails, the whole transaction rolls back.

---

## Project Structure

```
app/
├── main.py              # FastAPI app, router registration, lifespan (DB pool)
├── db.py                # asyncpg connection pool
├── config.py             # env var loading (pydantic-settings)
├── auth/                 # signup, login, JWT, role-check dependencies
├── products/              # public product/category browsing + admin CRUD
├── cart/                  # cart item management
├── wallet/                # wallet balance, transactions, admin credit
└── orders/                # checkout, order history, admin order view, invoice PDF
```

Each domain folder follows the same pattern: `queries.py` (raw SQL), `schemas.py` (Pydantic models), `routes.py` (FastAPI endpoints).

---

## Setup

### 1. Install dependencies

This project uses `uv` for dependency management.

```bash
uv sync
```

This reads `pyproject.toml` / `uv.lock` and creates a `.venv` automatically — you don't need to manually create or activate a virtual environment to run things, since `uv run` handles that for you. If you do want to activate it manually (e.g. for your editor's interpreter):

**Windows:**
```bash
.venv\Scripts\activate
```

**macOS/Linux:**
```bash
source .venv/bin/activate
```

### 2. Environment variables

Create a `.env` file in the project root (same level as `pyproject.toml`):

```env
DATABASE_URL=postgresql://postgres:YOUR_DB_PASSWORD@db.YOUR_PROJECT_REF.supabase.co:5432/postgres
JWT_SECRET=some-long-random-string
```

**How to get `DATABASE_URL`:**
1. Go to your project on [supabase.com](https://supabase.com)
2. **Project Settings → Database → Connection string**
3. Choose the **Direct connection** URI (port 5432) — this is the format `asyncpg` expects
4. Replace `[YOUR-PASSWORD]` in the string with your actual database password (set when the project was created, or resettable from that same settings page)

**How to generate `JWT_SECRET`:**
Any long random string works. Quick way to generate one:(fhfjdsbfhjdbfhshsvvdsvdgsihsjb)
```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

Never commit `.env` to version control.

### 3. Run the server

```bash
uv run uvicorn app.main:app --reload
```

Server runs at `http://localhost:8000`. Interactive API docs (Swagger UI) at `http://localhost:8000/docs`.

---

## Authentication (for frontend integration)

- **Signup:** `POST /auth/signup` — body `{name, email, password}` → returns `{access_token, token_type}`. Automatically creates a wallet (balance 0) for the new user.
- **Login:** `POST /auth/login` — body `{email, password}` → returns `{access_token, token_type}`.
- **Using the token:** send it on every protected request as a header:
  ```
  Authorization: Bearer <access_token>
  ```
- **Current user:** `GET /auth/me` — returns `{user_id, role_id}` from the token. Useful to check who's logged in and their role.

**Roles:** `role_id = 1` is Admin, `role_id = 2` is Customer (from `shop_roles` seed data). All new signups are Customers; there's no self-serve admin signup — admin status is set directly in the database.

Tokens expire after 24 hours (`JWT_EXPIRE_MINUTES` in `config.py`). There's no refresh-token flow yet — the frontend should redirect to login on a `401` response.

---

## API Overview

### Public (no auth required)
| Method | Path | Description |
|---|---|---|
| GET | `/health/db` | Sanity check — returns product count |
| GET | `/categories` | List all categories |
| GET | `/products` | List active products (optional `?category_id=`) |
| GET | `/products/{id}` | Single product detail |

### Customer (requires `Authorization: Bearer <token>`)
| Method | Path | Description |
|---|---|---|
| GET | `/cart` | View current cart with line totals |
| POST | `/cart/items` | Add item — `{product_id, quantity}` (upserts) |
| PUT | `/cart/items/{product_id}` | Update quantity |
| DELETE | `/cart/items/{product_id}` | Remove item |
| GET | `/wallet` | Current balance |
| GET | `/wallet/transactions` | Wallet transaction history |
| POST | `/orders/checkout` | Runs the checkout stored procedure — debits wallet, creates order, clears cart |
| GET | `/orders` | Current user's order history |
| GET | `/orders/{id}` | Single order detail with items |
| GET | `/orders/{id}/invoice` | Downloads a PDF invoice for the order |

### Admin only (requires `role_id = 1` token)
| Method | Path | Description |
|---|---|---|
| POST | `/products` | Create product |
| PUT | `/products/{id}` | Update product |
| PATCH | `/products/{id}/stock` | Set inventory quantity |
| POST | `/wallet/credit` | Credit any user's wallet — `{user_id, amount}` |
| GET | `/orders/admin/all` | View all orders across all customers (optional `?status=`) |

All admin actions (product create/update, stock changes, wallet credits) are logged to `shop_audit_logs`.

---

## Notes for Frontend Dev

- All responses are JSON except `/orders/{id}/invoice`, which returns a PDF file (`Content-Disposition: attachment`) — the browser will trigger a download automatically when hit directly, or you can fetch it as a blob and create a download link programmatically.
- Money fields (`price`, `balance`, `total_amount`, etc.) are returned as JSON numbers (floats), sourced from Postgres `NUMERIC` columns.
- `user_id` fields are UUID strings (e.g. `"90e44b53-6cb2-44dd-b344-72388a305c2c"`).
- Checkout (`POST /orders/checkout`) can fail with a `400` and a message straight from the database, e.g. `"Cart is empty"`, `"Insufficient stock for product 3"`, `"Insufficient wallet balance"` — surface these directly to the user, they're already human-readable.
- There's currently no pagination on list endpoints (`/products`, `/orders`, `/orders/admin/all`) — fine for demo-scale data, something to flag if the dataset grows.

---

## Status

**Implemented:** Auth (JWT), product/category browsing, admin product CRUD, cart, wallet + admin credit, checkout (transactional stored procedure with row locking), admin order view, PDF invoices, audit logging.

**Planned next:** Shipping addresses (snapshotted per order), product reviews (verified-purchase only, trigger-enforced).
