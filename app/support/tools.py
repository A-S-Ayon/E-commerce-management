import asyncpg

from langchain.tools import tool


from app.db import get_pool
from .retrival import retrieve_context 


def make_tools_for_user(user_id: str):
    """Builds a fresh set of tool instances scoped to one authenticated user.
    Called once per chat request — ensures no tool can be tricked into
    querying another user's data, since user_id is bound here, not
    passed as a model-controlled argument.
    """

    @tool
    async def get_my_orders() -> str:
        """List the current user's recent orders with status and total.
        Use this when the user asks about their orders in general, or
        says things like 'where's my stuff' or 'what have I ordered'.
        """
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, total_amount, status, fulfillment_status, created_at
                FROM shop_orders
                WHERE user_id = $1
                ORDER BY created_at DESC
                LIMIT 10
                """,
                user_id,
            )
        if not rows:
            return "You don't have any orders yet."
        lines = []
        for r in rows:
            fulfillment = r["fulfillment_status"] or "Processing"
            lines.append(
                f"Order #{r['id']} — {r['created_at'].strftime('%Y-%m-%d')} — "
                f"${r['total_amount']:.2f} — {r['status']} — {fulfillment}"
            )
        return "\n".join(lines)

    @tool
    async def get_order_detail(order_id: int) -> str:
        """Get full details for one specific order, including items and delivery status.
        Only works for orders belonging to the current user.
        """
        pool = get_pool()
        async with pool.acquire() as conn:
            order = await conn.fetchrow(
                """
                SELECT id, total_amount, status, fulfillment_status,
                       created_at, cancelled_at,
                       estimated_delivery_min, estimated_delivery_max
                FROM shop_orders
                WHERE id = $1 AND user_id = $2
                """,
                order_id, user_id,
            )
            if not order:
                return f"No order #{order_id} found on your account."

            items = await conn.fetch(
                """
                SELECT p.name, oi.quantity, oi.unit_price
                FROM shop_order_items oi
                JOIN shop_products p ON p.id = oi.product_id
                WHERE oi.order_id = $1
                """,
                order_id,
            )

        item_lines = "\n".join(
            f"  - {i['name']} x{i['quantity']} (${i['unit_price']:.2f} each)" for i in items
        )
        lines = [
            f"Order #{order['id']} — placed {order['created_at'].strftime('%Y-%m-%d')}",
            f"Status: {order['status']}",
            f"Total: ${order['total_amount']:.2f}",
            f"Items:\n{item_lines}",
        ]
        if order["status"] == "Paid":
            fulfillment = order["fulfillment_status"] or "Processing (not yet shipped)"
            lines.append(f"Delivery status: {fulfillment}")
            if order["estimated_delivery_min"] and order["estimated_delivery_max"]:
                lines.append(
                    f"Estimated delivery: {order['estimated_delivery_min']} to {order['estimated_delivery_max']}"
                )
        if order["status"] == "Cancelled" and order["cancelled_at"]:
            lines.append(f"Cancelled on {order['cancelled_at'].strftime('%Y-%m-%d')}")

        return "\n".join(lines)

    @tool
    async def get_my_wallet_balance() -> str:
        """Check the current user's wallet balance."""
        pool = get_pool()
        async with pool.acquire() as conn:
            row = await conn.fetchrow(
                "SELECT balance FROM shop_wallets WHERE user_id = $1", user_id
            )
        if not row:
            return "No wallet found on your account."
        return f"Your current wallet balance is ${row['balance']:.2f}."

    @tool
    async def view_cart() -> str:
        """Show what's currently in the user's cart."""
        pool = get_pool()
        async with pool.acquire() as conn:
            cart = await conn.fetchrow("SELECT id FROM shop_carts WHERE user_id = $1", user_id)
            if not cart:
                return "Your cart is empty."
            items = await conn.fetch(
                """
                SELECT p.name, ci.quantity, p.price, (p.price * ci.quantity) AS line_total
                FROM shop_cart_items ci
                JOIN shop_products p ON p.id = ci.product_id
                WHERE ci.cart_id = $1
                """,
                cart["id"],
            )
        if not items:
            return "Your cart is empty."
        lines = [f"{i['name']} x{i['quantity']} — ${i['line_total']:.2f}" for i in items]
        total = sum(i["line_total"] for i in items)
        lines.append(f"Cart total: ${total:.2f}")
        return "\n".join(lines)

    @tool
    async def add_to_cart(product_name: str, quantity: int) -> str:
        """Add a product to the user's cart by name and quantity.
        Only call this AFTER the user has clearly confirmed they want it added —
        do not add items just because they were mentioned in conversation.
        """
        pool = get_pool()
        async with pool.acquire() as conn:
            product = await conn.fetchrow(
                "SELECT id, name, price FROM shop_products WHERE name ILIKE $1 AND is_active = TRUE LIMIT 1",
                f"%{product_name}%",
            )
            if not product:
                return f"Couldn't find an active product matching '{product_name}'."

            cart = await conn.fetchrow("SELECT id FROM shop_carts WHERE user_id = $1", user_id)
            if not cart:
                cart = await conn.fetchrow(
                    "INSERT INTO shop_carts (user_id) VALUES ($1) RETURNING id", user_id
                )

            await conn.execute(
                """
                INSERT INTO shop_cart_items (cart_id, product_id, quantity)
                VALUES ($1, $2, $3)
                ON CONFLICT (cart_id, product_id)
                DO UPDATE SET quantity = shop_cart_items.quantity + EXCLUDED.quantity
                """,
                cart["id"], product["id"], quantity,
            )
        return f"Added {quantity} x {product['name']} to your cart."

    @tool
    async def cancel_order(order_id: int) -> str:
        """Cancel one of the user's own orders. Only call this AFTER the user has
        explicitly confirmed — restate the order number and total and get a clear
        'yes' before calling this. This action is immediate and refunds the wallet.
        """
        pool = get_pool()
        async with pool.acquire() as conn:
            try:
                await conn.execute(
                    "SELECT cancel_order($1, $2, $3)", order_id, user_id, False
                )
            except asyncpg.PostgresError as e:
                return f"Couldn't cancel order #{order_id}: {str(e)}"
        return f"Order #{order_id} has been cancelled and refunded to your wallet."

    @tool
    async def check_product_availability(product_name: str) -> str:
        """Look up a product's price and stock level by name."""
        pool = get_pool()
        async with pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT p.name, p.price, COALESCE(i.quantity, 0) AS stock
                FROM shop_products p
                LEFT JOIN shop_inventory i ON i.product_id = p.id
                WHERE p.name ILIKE $1 AND p.is_active = TRUE
                ORDER BY p.name
                LIMIT 5
                """,
                f"%{product_name}%",
            )
        if not rows:
            return f"No active products found matching '{product_name}'."
        lines = []
        for r in rows:
            stock_note = f"{r['stock']} in stock" if r["stock"] > 0 else "out of stock"
            lines.append(f"{r['name']} — ${r['price']:.2f} — {stock_note}")
        return "\n".join(lines)

    @tool
    def search_documents(query: str) -> str:
        """Search store policy / terms and conditions documents (refunds, shipping, etc)."""
        return retrieve_context(query)

    return [
        get_my_orders,
        get_order_detail,
        get_my_wallet_balance,
        view_cart,
        add_to_cart,
        cancel_order,
        search_documents,
    ]