
import csv
from pathlib import Path
from getpass import getpass
import psycopg
from decimal import Decimal

# Project paths
BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"

# Read CSV files
with open(DATA_DIR / "customers.csv", newline="", encoding="utf-8") as f:
    customers = list(csv.DictReader(f))

with open(DATA_DIR / "categories.csv", newline="", encoding="utf-8") as f:
    categories = list(csv.DictReader(f))


with open(DATA_DIR / "products.csv", newline="", encoding="utf-8") as f:
    products = list(csv.DictReader(f))

with open(DATA_DIR / "orders.csv", newline="", encoding="utf-8") as f:
    orders = list(csv.DictReader(f))

with open(DATA_DIR / "order_items.csv", newline="", encoding="utf-8") as f:
    order_items = list(csv.DictReader(f))


# Database configuration
db_config = {
    "host": "localhost",
    "port": 5432,
    "dbname": "ecommerce_pipeline_db",
    "user": "postgres",
    "password": getpass("PostgreSQL password: ")
}

# Connect and load data
with psycopg.connect(**db_config) as conn:
    with conn.cursor() as cur:

        # Load customers
        cur.executemany(
            """
            INSERT INTO public.customers
                (customer_name, email, city)
            VALUES (%s, %s, %s)
            ON CONFLICT (email) DO NOTHING
            """,
            [
                (c["customer_name"], c["email"], c["city"])
                for c in customers
            ]
        )

        # Load categories
        cur.executemany(
            """
            INSERT INTO public.categories (category_name)
            VALUES (%s)
            ON CONFLICT (category_name) DO NOTHING
            """,
            [
                (c["category_name"],)
                for c in categories
            ]
        )

        
        # -----------------------------------
        # LOAD PRODUCTS + CATEGORY FK MAPPING
        # -----------------------------------

        # Get real category IDs from PostgreSQL
        cur.execute("""
            SELECT category_id, category_name
            FROM public.categories
        """)

        category_map = {
            category_name: category_id
            for category_id, category_name in cur.fetchall()
        }

        # Prepare products with real category IDs
        product_rows = []

        for p in products:
            category_name = p["category_name"]

            if category_name not in category_map:
                raise ValueError(
                    f"Category not found: {category_name}"
                )

            product_rows.append((
                p["product_name"],
                Decimal(p["price"]),
                int(p["stock"]),
                category_map[category_name],
                p["product_name"]
            ))

        # Insert products
        cur.executemany(
            """
            INSERT INTO public.products
                (product_name, price, stock, category_id)
            SELECT %s, %s, %s, %s
            WHERE NOT EXISTS (
                SELECT 1
                FROM public.products
                WHERE product_name = %s
            )
            """,
            product_rows
        )
        
        # -----------------------------------
        # LOAD ORDERS
        # -----------------------------------

        # Customer email -> real customer_id
        cur.execute("""
            SELECT customer_id, email
            FROM public.customers
        """)

        customer_map = {
            email: customer_id
            for customer_id, email in cur.fetchall()
        }

        # Order reference -> real order_id
        order_map = {}

        for o in orders:
            customer_email = o["customer_email"]

            if customer_email not in customer_map:
                raise ValueError(
                    f"Customer not found: {customer_email}"
                )

            cur.execute(
                """
                INSERT INTO public.orders
                    (order_ref, customer_id, order_date,
                     status, total_amount)
                VALUES (%s, %s, %s, %s, %s)
                ON CONFLICT (order_ref)
                DO UPDATE SET
                    customer_id = EXCLUDED.customer_id,
                    order_date = EXCLUDED.order_date,
                    status = EXCLUDED.status,
                    total_amount = EXCLUDED.total_amount
                RETURNING order_id
                """,
                (
                    o["order_ref"],
                    customer_map[customer_email],
                    o["order_date"],
                    o["status"],
                    Decimal(o["total_amount"])
                )
            )

            order_id = cur.fetchone()[0]
            order_map[o["order_ref"]] = order_id
            
        # -----------------------------------
        # LOAD ORDER ITEMS
        # -----------------------------------

        cur.execute("""
            SELECT product_id, product_name
            FROM public.products
        """)

        product_map = {
            product_name: product_id
            for product_id, product_name in cur.fetchall()
        }

        item_rows = []

        for item in order_items:
            order_ref = item["order_ref"]
            product_name = item["product_name"]

            if order_ref not in order_map:
                raise ValueError(
                    f"Order not found: {order_ref}"
                )

            if product_name not in product_map:
                raise ValueError(
                    f"Product not found: {product_name}"
                )

            item_rows.append((
                order_map[order_ref],
                product_map[product_name],
                int(item["quantity"]),
                Decimal(item["unit_price"])
            ))

        cur.executemany(
            """
            INSERT INTO public.order_items
                (order_id, product_id, quantity, unit_price)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (order_id, product_id)
            DO UPDATE SET
                quantity = EXCLUDED.quantity,
                unit_price = EXCLUDED.unit_price
            """,
            item_rows
        )




print("Customers and Categories loaded successfully!")
print("60 Products loading step completed!")
print("Orders and Order Items loading completed!")