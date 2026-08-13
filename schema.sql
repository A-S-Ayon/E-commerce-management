-- =========================================================
-- ShopX E-Commerce Database Schema
-- Consolidated final version — Supabase project djfqjyqipvbncvltjvml
-- =========================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm; -- used by trigram index on product name search

-- =========================================================
-- ENUM TYPES
-- =========================================================

CREATE TYPE order_status        AS ENUM ('Pending', 'Paid', 'Cancelled');
CREATE TYPE payment_status      AS ENUM ('Success', 'Failed');
CREATE TYPE payment_method      AS ENUM ('Wallet');
CREATE TYPE wallet_tx_type      AS ENUM ('Credit', 'Debit');
CREATE TYPE fulfillment_status  AS ENUM ('Shipped', 'Out for Delivery', 'Delivered');

-- =========================================================
-- ROLES & USERS
-- =========================================================

CREATE TABLE shop_roles (
    id        SERIAL PRIMARY KEY,
    role_name VARCHAR(50) NOT NULL UNIQUE
);

INSERT INTO shop_roles (role_name) VALUES ('Admin'), ('Customer');

CREATE TABLE shop_users (
    id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    name          VARCHAR(150) NOT NULL,
    email         VARCHAR(255) NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    role_id       INT NOT NULL REFERENCES shop_roles(id),
    is_verified   BOOLEAN NOT NULL DEFAULT FALSE,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shop_users_role_id ON shop_users(role_id);

-- =========================================================
-- EMAIL VERIFICATION & PASSWORD RESET
-- =========================================================

CREATE TABLE shop_verification_codes (
    id         SERIAL PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES shop_users(id) ON DELETE CASCADE,
    code       VARCHAR(6) NOT NULL,
    expires_at TIMESTAMPTZ NOT NULL,
    used       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shop_verification_codes_user_id ON shop_verification_codes(user_id);

CREATE TABLE shop_password_resets (
    id         SERIAL PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES shop_users(id) ON DELETE CASCADE,
    token      TEXT NOT NULL UNIQUE,
    expires_at TIMESTAMPTZ NOT NULL,
    used       BOOLEAN NOT NULL DEFAULT FALSE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shop_password_resets_token ON shop_password_resets(token);

-- =========================================================
-- CATALOG
-- =========================================================

CREATE TABLE shop_categories (
    id   SERIAL PRIMARY KEY,
    name VARCHAR(100) NOT NULL UNIQUE
);

CREATE TABLE shop_products (
    id          SERIAL PRIMARY KEY,
    category_id INT NOT NULL REFERENCES shop_categories(id),
    name        VARCHAR(200) NOT NULL,
    description TEXT,
    price       NUMERIC(12,2) NOT NULL CHECK (price > 0),
    image_url   TEXT,
    is_active   BOOLEAN NOT NULL DEFAULT TRUE
);

CREATE INDEX idx_shop_products_category_id ON shop_products(category_id);
CREATE INDEX idx_shop_products_name_trgm ON shop_products USING GIN (name gin_trgm_ops);

CREATE TABLE shop_inventory (
    product_id INT PRIMARY KEY REFERENCES shop_products(id) ON DELETE CASCADE,
    quantity   INTEGER NOT NULL DEFAULT 0 CHECK (quantity >= 0),
    updated_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================================
-- WALLET
-- =========================================================

CREATE TABLE shop_wallets (
    id      SERIAL PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE REFERENCES shop_users(id) ON DELETE CASCADE,
    balance NUMERIC(12,2) NOT NULL DEFAULT 0 CHECK (balance >= 0)
);

CREATE TABLE shop_wallet_transactions (
    id         SERIAL PRIMARY KEY,
    wallet_id  INT NOT NULL REFERENCES shop_wallets(id) ON DELETE CASCADE,
    amount     NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    type       wallet_tx_type NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shop_wallet_tx_wallet_id ON shop_wallet_transactions(wallet_id);

-- =========================================================
-- CART
-- =========================================================

CREATE TABLE shop_carts (
    id      SERIAL PRIMARY KEY,
    user_id UUID NOT NULL UNIQUE REFERENCES shop_users(id) ON DELETE CASCADE
);

CREATE TABLE shop_cart_items (
    id         SERIAL PRIMARY KEY,
    cart_id    INT NOT NULL REFERENCES shop_carts(id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES shop_products(id),
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    UNIQUE (cart_id, product_id)
);

CREATE INDEX idx_shop_cart_items_cart_id ON shop_cart_items(cart_id);

-- =========================================================
-- ADDRESSES
-- =========================================================

CREATE TABLE shop_addresses (
    id             SERIAL PRIMARY KEY,
    user_id        UUID NOT NULL REFERENCES shop_users(id) ON DELETE CASCADE,
    label          VARCHAR(50),
    recipient_name VARCHAR(150) NOT NULL,
    phone          VARCHAR(30),
    address_line1  VARCHAR(255) NOT NULL,
    address_line2  VARCHAR(255),
    city           VARCHAR(100) NOT NULL,
    state          VARCHAR(100),
    postal_code    VARCHAR(20) NOT NULL,
    country        VARCHAR(100) NOT NULL,
    is_default     BOOLEAN NOT NULL DEFAULT FALSE,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shop_addresses_user_id ON shop_addresses(user_id);

-- =========================================================
-- ORDERS
-- Shipping fields are a snapshot of shop_addresses at
-- checkout time — same reasoning as unit_price snapshot in
-- shop_order_items: order history must stay accurate even
-- if the address is later edited or deleted.
--
-- fulfillment_status/related columns track post-payment
-- delivery progress. status_change_actor_id is write-only
-- scratch space used to pass "who made this change" into
-- the trg_log_fulfillment_status trigger; it is always
-- cleared back to NULL by the trigger before the row is
-- persisted, so it never looks like a persistent "current
-- owner" column.
-- =========================================================

CREATE TABLE shop_orders (
    id                      SERIAL PRIMARY KEY,
    user_id                 UUID NOT NULL REFERENCES shop_users(id),
    total_amount            NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
    status                  order_status NOT NULL DEFAULT 'Pending',
    created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),

    -- shipping snapshot
    recipient_name          VARCHAR(150),
    phone                   VARCHAR(30),
    address_line1           VARCHAR(255),
    address_line2           VARCHAR(255),
    city                    VARCHAR(100),
    state                   VARCHAR(100),
    postal_code             VARCHAR(20),
    country                 VARCHAR(100),

    -- fulfillment tracking
    fulfillment_status      fulfillment_status,
    fulfillment_updated_at  TIMESTAMPTZ,
    received_confirmed_at   TIMESTAMPTZ,
    status_change_actor_id  UUID -- write-only; cleared by trigger, never queried directly
);

CREATE INDEX idx_shop_orders_user_id ON shop_orders(user_id);

CREATE TABLE shop_order_items (
    id         SERIAL PRIMARY KEY,
    order_id   INT NOT NULL REFERENCES shop_orders(id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES shop_products(id),
    quantity   INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price > 0) -- price snapshot at purchase time; never join to shop_products.price for historical totals
);

CREATE INDEX idx_shop_order_items_order_id ON shop_order_items(order_id);

CREATE TABLE shop_order_status_history (
    id         SERIAL PRIMARY KEY,
    order_id   INT NOT NULL REFERENCES shop_orders(id) ON DELETE CASCADE,
    status     fulfillment_status NOT NULL,
    changed_by UUID REFERENCES shop_users(id),
    changed_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shop_order_status_history_order_id ON shop_order_status_history(order_id);

-- =========================================================
-- PAYMENTS & INVOICES
-- =========================================================

CREATE TABLE shop_payments (
    id             SERIAL PRIMARY KEY,
    order_id       INT NOT NULL REFERENCES shop_orders(id),
    payment_method payment_method NOT NULL DEFAULT 'Wallet',
    amount         NUMERIC(12,2) NOT NULL CHECK (amount > 0),
    status         payment_status NOT NULL,
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shop_payments_order_id ON shop_payments(order_id);

CREATE TABLE shop_invoices (
    id             SERIAL PRIMARY KEY,
    order_id       INT NOT NULL UNIQUE REFERENCES shop_orders(id),
    invoice_number VARCHAR(50) NOT NULL UNIQUE,
    generated_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

-- =========================================================
-- REVIEWS (verified-purchase enforced via trigger)
-- =========================================================

CREATE TABLE shop_reviews (
    id         SERIAL PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES shop_users(id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES shop_products(id) ON DELETE CASCADE,
    rating     SMALLINT NOT NULL CHECK (rating BETWEEN 1 AND 5),
    comment    TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, product_id)
);

CREATE INDEX idx_shop_reviews_product_id ON shop_reviews(product_id);

-- =========================================================
-- WISHLIST
-- =========================================================

CREATE TABLE shop_wishlist (
    id         SERIAL PRIMARY KEY,
    user_id    UUID NOT NULL REFERENCES shop_users(id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES shop_products(id) ON DELETE CASCADE,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    UNIQUE (user_id, product_id)
);

CREATE INDEX idx_shop_wishlist_user_id ON shop_wishlist(user_id);

-- =========================================================
-- AUDIT LOG
-- =========================================================

CREATE TABLE shop_audit_logs (
    id         SERIAL PRIMARY KEY,
    admin_id   UUID NOT NULL REFERENCES shop_users(id),
    action     TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_shop_audit_logs_admin_id ON shop_audit_logs(admin_id);

-- =========================================================
-- FUNCTION: checkout()
-- Validates stock + wallet balance, debits wallet, creates
-- order/order_items/payment/invoice with the given shipping
-- address snapshotted onto the order, and clears the cart.
-- All in one transaction — any RAISE rolls back everything.
-- FOR UPDATE locks on wallet + inventory rows prevent
-- concurrent double-charge / oversell. Empty-cart check
-- prevents a double-submit creating a $0 ghost order.
-- =========================================================

CREATE OR REPLACE FUNCTION checkout(p_user_id UUID, p_address_id INT)
RETURNS INT AS $$
DECLARE
    v_cart_id   INT;
    v_wallet_id INT;
    v_balance   NUMERIC(12,2);
    v_total     NUMERIC(12,2) := 0;
    v_order_id  INT;
    v_item      RECORD;
    v_stock     INTEGER;
    v_addr      RECORD;
BEGIN
    SELECT recipient_name, phone, address_line1, address_line2, city, state, postal_code, country
    INTO v_addr
    FROM shop_addresses
    WHERE id = p_address_id AND user_id = p_user_id;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'Address not found for user %', p_user_id;
    END IF;

    SELECT id INTO v_cart_id FROM shop_carts WHERE user_id = p_user_id;
    IF v_cart_id IS NULL THEN
        RAISE EXCEPTION 'No cart found for user %', p_user_id;
    END IF;

    SELECT id, balance INTO v_wallet_id, v_balance
    FROM shop_wallets WHERE user_id = p_user_id FOR UPDATE;

    IF v_wallet_id IS NULL THEN
        RAISE EXCEPTION 'No wallet found for user %', p_user_id;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM shop_cart_items WHERE cart_id = v_cart_id) THEN
        RAISE EXCEPTION 'Cart is empty';
    END IF;

    FOR v_item IN
        SELECT ci.product_id, ci.quantity, p.price
        FROM shop_cart_items ci
        JOIN shop_products p ON p.id = ci.product_id
        WHERE ci.cart_id = v_cart_id
    LOOP
        SELECT quantity INTO v_stock FROM shop_inventory
        WHERE product_id = v_item.product_id FOR UPDATE;

        IF v_stock IS NULL OR v_stock < v_item.quantity THEN
            RAISE EXCEPTION 'Insufficient stock for product %', v_item.product_id;
        END IF;

        v_total := v_total + (v_item.price * v_item.quantity);
    END LOOP;

    IF v_balance < v_total THEN
        RAISE EXCEPTION 'Insufficient wallet balance';
    END IF;

    UPDATE shop_wallets SET balance = balance - v_total WHERE id = v_wallet_id;
    INSERT INTO shop_wallet_transactions (wallet_id, amount, type)
    VALUES (v_wallet_id, v_total, 'Debit');

    INSERT INTO shop_orders (
        user_id, total_amount, status,
        recipient_name, phone, address_line1, address_line2, city, state, postal_code, country
    )
    VALUES (
        p_user_id, v_total, 'Paid',
        v_addr.recipient_name, v_addr.phone, v_addr.address_line1, v_addr.address_line2,
        v_addr.city, v_addr.state, v_addr.postal_code, v_addr.country
    )
    RETURNING id INTO v_order_id;

    FOR v_item IN
        SELECT ci.product_id, ci.quantity, p.price
        FROM shop_cart_items ci
        JOIN shop_products p ON p.id = ci.product_id
        WHERE ci.cart_id = v_cart_id
    LOOP
        INSERT INTO shop_order_items (order_id, product_id, quantity, unit_price)
        VALUES (v_order_id, v_item.product_id, v_item.quantity, v_item.price);

        UPDATE shop_inventory SET quantity = quantity - v_item.quantity, updated_at = NOW()
        WHERE product_id = v_item.product_id;
    END LOOP;

    INSERT INTO shop_payments (order_id, payment_method, amount, status)
    VALUES (v_order_id, 'Wallet', v_total, 'Success');

    INSERT INTO shop_invoices (order_id, invoice_number)
    VALUES (v_order_id, 'INV-' || v_order_id || '-' || to_char(NOW(), 'YYYYMMDDHH24MISS'));

    DELETE FROM shop_cart_items WHERE cart_id = v_cart_id;

    RETURN v_order_id;
END;
$$ LANGUAGE plpgsql;

-- =========================================================
-- TRIGGER: verified-purchase enforcement on shop_reviews
-- A review can only be inserted if the reviewing user has a
-- Paid order containing the product being reviewed.
-- =========================================================

CREATE OR REPLACE FUNCTION check_verified_purchase()
RETURNS TRIGGER AS $$
BEGIN
    IF NOT EXISTS (
        SELECT 1
        FROM shop_order_items oi
        JOIN shop_orders o ON o.id = oi.order_id
        WHERE o.user_id = NEW.user_id
          AND oi.product_id = NEW.product_id
          AND o.status = 'Paid'
    ) THEN
        RAISE EXCEPTION 'You can only review products you have purchased';
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_verified_purchase
BEFORE INSERT ON shop_reviews
FOR EACH ROW EXECUTE FUNCTION check_verified_purchase();

-- =========================================================
-- TRIGGER: fulfillment status state machine + audit log
--
-- Runs BEFORE UPDATE (not AFTER) specifically so it can
-- modify NEW.fulfillment_updated_at before the row is
-- written — an AFTER trigger cannot change the row being
-- updated, since the write has already happened by then.
--
-- Responsibilities:
--   1. Enforce forward-only, sequential transitions
--      (Shipped -> Out for Delivery -> Delivered) at the
--      DB level. This is defense-in-depth: even a direct
--      SQL UPDATE bypassing the API cannot skip or reverse
--      a step.
--   2. Require the caller to identify who made the change
--      via status_change_actor_id, so shop_order_status_
--      history.changed_by is always accurate rather than
--      possibly stale from a previous update.
--   3. Log every valid transition to shop_order_status_
--      history automatically, so history is guaranteed
--      regardless of which code path performs the update.
--   4. Stamp fulfillment_updated_at with the current time.
--   5. Clear status_change_actor_id back to NULL before the
--      row is persisted, so it never lingers looking like a
--      real "current owner" column when queried directly.
-- =========================================================

CREATE OR REPLACE FUNCTION log_fulfillment_status_change()
RETURNS TRIGGER AS $$
DECLARE
    expected fulfillment_status;
BEGIN
    IF NEW.fulfillment_status IS DISTINCT FROM OLD.fulfillment_status
       AND NEW.fulfillment_status IS NOT NULL THEN

        expected := CASE
            WHEN OLD.fulfillment_status IS NULL THEN 'Shipped'
            WHEN OLD.fulfillment_status = 'Shipped' THEN 'Out for Delivery'
            WHEN OLD.fulfillment_status = 'Out for Delivery' THEN 'Delivered'
            ELSE NULL
        END;

        IF NEW.fulfillment_status IS DISTINCT FROM expected THEN
            RAISE EXCEPTION 'Invalid fulfillment transition: % -> % (expected %)',
                OLD.fulfillment_status, NEW.fulfillment_status, expected;
        END IF;

        IF NEW.status_change_actor_id IS NULL THEN
            RAISE EXCEPTION 'status_change_actor_id must be set when changing fulfillment_status';
        END IF;

        INSERT INTO shop_order_status_history (order_id, status, changed_by)
        VALUES (NEW.id, NEW.fulfillment_status, NEW.status_change_actor_id);

        NEW.fulfillment_updated_at := NOW();
    END IF;

    NEW.status_change_actor_id := NULL;

    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trg_log_fulfillment_status
BEFORE UPDATE ON shop_orders
FOR EACH ROW EXECUTE FUNCTION log_fulfillment_status_change();
