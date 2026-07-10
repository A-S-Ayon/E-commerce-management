-- =========================================================
-- E-commerce database schema — consolidated
-- All tables, types, indexes, triggers, and stored procedures
-- Run this once against a fresh PostgreSQL/Supabase database.
-- =========================================================

CREATE EXTENSION IF NOT EXISTS pgcrypto;
CREATE EXTENSION IF NOT EXISTS pg_trgm;  -- required for GIN trigram index on product name

-- =========================================================
-- ENUM TYPES
-- =========================================================

CREATE TYPE order_status   AS ENUM ('Pending', 'Paid', 'Cancelled');
CREATE TYPE payment_status AS ENUM ('Success', 'Failed');
CREATE TYPE payment_method AS ENUM ('Wallet');
CREATE TYPE wallet_tx_type AS ENUM ('Credit', 'Debit');

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
-- CATALOG: CATEGORIES, PRODUCTS, INVENTORY
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
-- SHIPPING ADDRESSES
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
-- ORDERS, ORDER ITEMS, PAYMENTS, INVOICES
-- (orders include a snapshotted shipping address, captured
-- at checkout time — see checkout() below)
-- =========================================================

CREATE TABLE shop_orders (
    id             SERIAL PRIMARY KEY,
    user_id        UUID NOT NULL REFERENCES shop_users(id),
    total_amount   NUMERIC(12,2) NOT NULL CHECK (total_amount >= 0),
    status         order_status NOT NULL DEFAULT 'Pending',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT NOW(),
    -- shipping snapshot (copied from shop_addresses at checkout time;
    -- never joined live, so order history stays accurate even if the
    -- address is later edited or deleted)
    recipient_name VARCHAR(150),
    phone          VARCHAR(30),
    address_line1  VARCHAR(255),
    address_line2  VARCHAR(255),
    city           VARCHAR(100),
    state          VARCHAR(100),
    postal_code    VARCHAR(20),
    country        VARCHAR(100)
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
-- REVIEWS (verified-purchase enforced via trigger below)
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
-- TRIGGER FUNCTION: enforce verified-purchase reviews
-- A user may only review a product they have an order_item
-- for, on an order with status = 'Paid'.
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
-- checkout(): the core transactional stored procedure.
--
-- Validates the user's shipping address, cart contents, stock
-- levels, and wallet balance; then atomically debits the wallet,
-- creates the order (with a snapshotted shipping address and
-- price-snapshotted line items), decrements inventory, records
-- the payment, generates an invoice, and clears the cart.
--
-- FOR UPDATE locks on the wallet row and each inventory row
-- prevent two concurrent checkouts from the same user (or
-- concurrent buyers of the same product) from double-charging
-- a wallet or overselling stock. Any RAISE EXCEPTION rolls back
-- every write made so far in the transaction — verified by
-- testing that a failed checkout leaves zero trace in orders,
-- wallet balance, or inventory.
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
    -- Look up and validate the shipping address belongs to this user
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

    -- Lock the wallet row to prevent concurrent double-charge
    SELECT id, balance INTO v_wallet_id, v_balance
    FROM shop_wallets WHERE user_id = p_user_id FOR UPDATE;

    IF v_wallet_id IS NULL THEN
        RAISE EXCEPTION 'No wallet found for user %', p_user_id;
    END IF;

    IF NOT EXISTS (SELECT 1 FROM shop_cart_items WHERE cart_id = v_cart_id) THEN
        RAISE EXCEPTION 'Cart is empty';
    END IF;

    -- First pass: lock inventory rows and validate stock + compute total
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

    -- Debit wallet
    UPDATE shop_wallets SET balance = balance - v_total WHERE id = v_wallet_id;
    INSERT INTO shop_wallet_transactions (wallet_id, amount, type)
    VALUES (v_wallet_id, v_total, 'Debit');

    -- Create order with snapshotted shipping address
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

    -- Second pass: create order_items (price snapshot) and decrement inventory
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
-- SEED DATA (optional — remove or edit before production use)
-- =========================================================

-- INSERT INTO shop_categories (name) VALUES
--   ('Laptops'), ('Phones'), ('Accessories');
--
-- INSERT INTO shop_products (category_id, name, description, price, image_url, is_active)
-- VALUES
--   (1, 'ThinkPad X1 Carbon', '14-inch business ultrabook', 1299.00, NULL, TRUE),
--   (1, 'MacBook Air M2', '13-inch, 8GB RAM', 999.00, NULL, TRUE),
--   (2, 'Pixel 8', '128GB, Obsidian', 699.00, NULL, TRUE),
--   (2, 'iPhone 15', '128GB, Blue', 799.00, NULL, TRUE),
--   (3, 'USB-C Hub', '7-in-1 adapter', 39.99, NULL, TRUE);
--
-- INSERT INTO shop_inventory (product_id, quantity)
-- SELECT id, 25 FROM shop_products;
