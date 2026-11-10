import psycopg
from psycopg.rows import dict_row

import logging
from pathlib import Path
import sys
import os
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

# Create logs directory
log_dir = Path(__file__).resolve().parent.parent / "logs"
log_dir.mkdir(exist_ok=True)

# Configure logging
logging.basicConfig(
    filename=log_dir / "incremental_etl.log",
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
    encoding="utf-8"
)

logger = logging.getLogger("incremental_etl")


# ----------------------------------
# ERROR LOGGING
# ----------------------------------

def log_unhandled_error(exc_type, exc_value, exc_tb):

    logger.error(
        "ETL FAILED",
        exc_info=(exc_type, exc_value, exc_tb)
    )

    sys.__excepthook__(exc_type, exc_value, exc_tb)


sys.excepthook = log_unhandled_error




db_config = {
    "host": "localhost",
    "port": 5432,
    "dbname": "ecommerce_pipeline_db",
    "user": "postgres",
    "password": os.environ["PG_PASSWORD"]
}


# ============================================================
# INCREMENTAL ETL - ONE DATABASE TRANSACTION
# All database operations use the same connection and cursor.
# A failure rolls back SCD2, fact_sales, and watermark together.
# ============================================================

with psycopg.connect(**db_config, row_factory=dict_row) as conn:
    with conn.cursor() as cur:

        # ----------------------------------------------------
        # 1. READ THE PREVIOUS WATERMARK
        # ----------------------------------------------------
        cur.execute("""
            SELECT last_successful_at
            FROM analytics.etl_watermark
            WHERE pipeline_name = %s
        """, ("ecommerce_incremental",))

        result = cur.fetchone()

        if result is None:
            raise ValueError("Watermark not found")

        watermark = result["last_successful_at"]

        # ----------------------------------------------------
        # 2. DEFINE BATCH END
        # ----------------------------------------------------
        cur.execute("""
            SELECT clock_timestamp() AS batch_end
        """)

        batch_end = cur.fetchone()["batch_end"]

        # ----------------------------------------------------
        # 3. INCREMENTAL EXTRACT - CUSTOMERS
        # ----------------------------------------------------
        cur.execute("""
            SELECT
                customer_id,
                customer_name,
                city,
                created_at,
                updated_at
            FROM public.customers
            WHERE updated_at > %s
              AND updated_at <= %s
            ORDER BY updated_at, customer_id
        """, (watermark, batch_end))

        changed_customers = cur.fetchall()

        # ----------------------------------------------------
        # 4. INCREMENTAL EXTRACT - PRODUCTS AND CATEGORIES
        # ----------------------------------------------------
        cur.execute("""
            SELECT
                p.product_id,
                p.product_name,
                c.category_name,
                p.created_at,
                p.updated_at AS product_updated_at,
                c.updated_at AS category_updated_at,

                GREATEST(
                    p.updated_at,
                    c.updated_at
                ) AS source_updated_at

            FROM public.products AS p

            JOIN public.categories AS c
                ON p.category_id = c.category_id

            WHERE GREATEST(
                p.updated_at,
                c.updated_at
            ) > %s

            AND GREATEST(
                p.updated_at,
                c.updated_at
            ) <= %s

            ORDER BY p.product_id
        """, (watermark, batch_end))

        changed_products = cur.fetchall()

        # ----------------------------------------------------
        # 5. INCREMENTAL EXTRACT - ORDERS AND ORDER ITEMS
        # ----------------------------------------------------
        cur.execute("""
            SELECT
                o.order_id,
                o.customer_id,
                o.order_date,
                (o.order_date AT TIME ZONE 'Africa/Casablanca')::date
                    AS full_date,
                o.status,
                oi.product_id,
                oi.quantity,
                oi.unit_price,

                GREATEST(
                    o.updated_at,
                    oi.updated_at
                ) AS source_updated_at

            FROM public.orders AS o

            JOIN public.order_items AS oi
                ON o.order_id = oi.order_id

            WHERE GREATEST(
                o.updated_at,
                oi.updated_at
            ) > %s

              AND GREATEST(
                o.updated_at,
                oi.updated_at
            ) <= %s

            ORDER BY o.order_id, oi.product_id
        """, (watermark, batch_end))

        changed_sales = cur.fetchall()

        # ----------------------------------------------------
        # 6. CUSTOMER SCD2 - DETECT NEW / MODIFIED / UNCHANGED
        # ----------------------------------------------------
        cur.execute("""
            SELECT
                customer_key,
                customer_id,
                customer_name,
                city
            FROM analytics.dim_customer
            WHERE is_current = TRUE
        """)

        current_customer_rows = cur.fetchall()

        # Lookup: customer_id -> active DW version
        current_customers = {
            row["customer_id"]: row
            for row in current_customer_rows
        }

        new_customers = []
        modified_customers = []
        unchanged_count = 0

        for customer in changed_customers:
            customer_id = customer["customer_id"]
            current = current_customers.get(customer_id)

            if current is None:
                new_customers.append(customer)

            elif (
                customer["customer_name"] != current["customer_name"]
                or customer["city"] != current["city"]
            ):
                modified_customers.append((customer, current))

            else:
                unchanged_count += 1

        # ----------------------------------------------------
        # 7. CUSTOMER SCD2 - INSERT NEW / CLOSE OLD + INSERT NEW
        # ----------------------------------------------------
        for customer in new_customers:
            cur.execute("""
                INSERT INTO analytics.dim_customer (
                    customer_id,
                    customer_name,
                    city,
                    valid_from,
                    valid_to,
                    is_current
                )
                VALUES (%s, %s, %s, %s, NULL, TRUE)
            """, (
                customer["customer_id"],
                customer["customer_name"],
                customer["city"],
                customer["created_at"]
            ))

        for new, old in modified_customers:
            change_time = new["updated_at"]

            # Close the previous active version
            cur.execute("""
                UPDATE analytics.dim_customer
                SET
                    valid_to = %s,
                    is_current = FALSE
                WHERE customer_key = %s
                  AND is_current = TRUE
                  AND valid_from < %s
                RETURNING customer_key
            """, (
                change_time,
                old["customer_key"],
                change_time
            ))

            if cur.fetchone() is None:
                raise ValueError(
                    f"Cannot close customer version: "
                    f"{new['customer_id']}"
                )

            # Insert the new active version
            cur.execute("""
                INSERT INTO analytics.dim_customer (
                    customer_id,
                    customer_name,
                    city,
                    valid_from,
                    valid_to,
                    is_current
                )
                VALUES (%s, %s, %s, %s, NULL, TRUE)
            """, (
                new["customer_id"],
                new["customer_name"],
                new["city"],
                change_time
            ))

        # ----------------------------------------------------
        # 8. PRODUCT SCD2 - DETECT NEW / MODIFIED / UNCHANGED
        # ----------------------------------------------------
        cur.execute("""
            SELECT
                product_key,
                product_id,
                product_name,
                category_name
            FROM analytics.dim_product
            WHERE is_current = TRUE
        """)

        current_product_rows = cur.fetchall()

        # Lookup: product_id -> active DW version
        current_products = {
            row["product_id"]: row
            for row in current_product_rows
        }

        new_products = []
        modified_products = []
        unchanged_products_count = 0

        for product in changed_products:
            product_id = product["product_id"]
            current = current_products.get(product_id)

            if current is None:
                new_products.append(product)

            elif (
                product["product_name"] != current["product_name"]
                or product["category_name"] != current["category_name"]
            ):
                modified_products.append((product, current))

            else:
                unchanged_products_count += 1

        # ----------------------------------------------------
        # 9. PRODUCT SCD2 - INSERT NEW / CLOSE OLD + INSERT NEW
        # ----------------------------------------------------
        for product in new_products:
            cur.execute("""
                INSERT INTO analytics.dim_product (
                    product_id,
                    product_name,
                    category_name,
                    valid_from,
                    valid_to,
                    is_current
                )
                VALUES (%s, %s, %s, %s, NULL, TRUE)
            """, (
                product["product_id"],
                product["product_name"],
                product["category_name"],
                product["created_at"]
            ))

        for new, old in modified_products:
            change_time = new["source_updated_at"]

            # Close the previous active version
            cur.execute("""
                UPDATE analytics.dim_product
                SET
                    valid_to = %s,
                    is_current = FALSE
                WHERE product_key = %s
                  AND is_current = TRUE
                  AND valid_from < %s
                RETURNING product_key
            """, (
                change_time,
                old["product_key"],
                change_time
            ))

            if cur.fetchone() is None:
                raise ValueError(
                    f"Cannot close product version: "
                    f"{new['product_id']}"
                )

            # Insert the new active version
            cur.execute("""
                INSERT INTO analytics.dim_product (
                    product_id,
                    product_name,
                    category_name,
                    valid_from,
                    valid_to,
                    is_current
                )
                VALUES (%s, %s, %s, %s, NULL, TRUE)
            """, (
                new["product_id"],
                new["product_name"],
                new["category_name"],
                change_time
            ))

        # ----------------------------------------------------
        # 10. TRANSFORM CHANGED SALES - REVENUE
        # ----------------------------------------------------
        transformed_changed_sales = []

        for sale in changed_sales:
            quantity = sale["quantity"]
            unit_price = sale["unit_price"]

            revenue = quantity * unit_price

            transformed_changed_sales.append({
                **sale,
                "revenue": revenue
            })

        # ----------------------------------------------------
        # 11. CUSTOMER KEY MAPPING - HISTORICAL SCD2 VERSION
        # ----------------------------------------------------
        cur.execute("""
            SELECT
                customer_key,
                customer_id,
                valid_from,
                valid_to
            FROM analytics.dim_customer
        """)

        customer_versions_rows = cur.fetchall()

        customer_versions = {}
        for version in customer_versions_rows:
            customer_id = version["customer_id"]
            customer_versions.setdefault(customer_id, []).append(version)

        for sale in transformed_changed_sales:
            customer_id = sale["customer_id"]
            order_date = sale["order_date"]
            versions = customer_versions.get(customer_id, [])

            matches = [
                v for v in versions
                if order_date >= v["valid_from"]
                and (
                    v["valid_to"] is None
                    or order_date < v["valid_to"]
                )
            ]

            if len(matches) != 1:
                raise ValueError(
                    f"Invalid customer mapping: "
                    f"order_id={sale['order_id']}, "
                    f"customer_id={customer_id}, "
                    f"matches={len(matches)}"
                )

            sale["customer_key"] = matches[0]["customer_key"]

        mapped_count = sum(
            "customer_key" in sale
            for sale in transformed_changed_sales
        )

        # ----------------------------------------------------
        # 12. PRODUCT KEY MAPPING - HISTORICAL SCD2 VERSION
        # ----------------------------------------------------
        cur.execute("""
            SELECT
                product_key,
                product_id,
                valid_from,
                valid_to
            FROM analytics.dim_product
        """)

        product_versions_rows = cur.fetchall()

        product_versions = {}
        for version in product_versions_rows:
            product_id = version["product_id"]
            product_versions.setdefault(product_id, []).append(version)

        for sale in transformed_changed_sales:
            product_id = sale["product_id"]
            order_date = sale["order_date"]
            versions = product_versions.get(product_id, [])

            matches = [
                v for v in versions
                if order_date >= v["valid_from"]
                and (
                    v["valid_to"] is None
                    or order_date < v["valid_to"]
                )
            ]

            if len(matches) != 1:
                raise ValueError(
                    f"Invalid product mapping: "
                    f"order_id={sale['order_id']}, "
                    f"product_id={product_id}, "
                    f"matches={len(matches)}"
                )

            sale["product_key"] = matches[0]["product_key"]

        mapped_count = sum(
            "product_key" in sale
            for sale in transformed_changed_sales
        )

        # ----------------------------------------------------
        # 13. LOAD MISSING DATES - BEFORE DATE KEY MAPPING
        # ----------------------------------------------------
        unique_dates = sorted({
            sale["full_date"]
            for sale in transformed_changed_sales
        })

        month_names = [
            "January", "February", "March", "April",
            "May", "June", "July", "August",
            "September", "October", "November", "December"
        ]

        date_data = []
        for d in unique_dates:
            date_data.append((
                d,
                d.day,
                d.month,
                month_names[d.month - 1],
                (d.month - 1) // 3 + 1,
                d.year
            ))

        cur.executemany("""
            INSERT INTO analytics.dim_date (
                full_date,
                day_number,
                month_number,
                month_name,
                quarter_number,
                year_number
            )
            VALUES (%s, %s, %s, %s, %s, %s)

            ON CONFLICT (full_date) DO NOTHING
        """, date_data)

        # ----------------------------------------------------
        # 14. DATE KEY MAPPING
        # ----------------------------------------------------
        cur.execute("""
            SELECT date_key, full_date
            FROM analytics.dim_date
        """)

        date_rows_dw = cur.fetchall()

        date_map = {}
        for row in date_rows_dw:
            date_map[row["full_date"]] = row["date_key"]

        for sale in transformed_changed_sales:
            full_date = sale["full_date"]
            date_key = date_map.get(full_date)

            if date_key is None:
                raise ValueError(
                    f"Date mapping not found: "
                    f"order_id={sale['order_id']}, "
                    f"full_date={full_date}"
                )

            sale["date_key"] = date_key

        mapped_count = sum(
            "date_key" in sale
            for sale in transformed_changed_sales
        )

        # ----------------------------------------------------
        # 15. INCREMENTAL UPSERT - FACT SALES
        # ----------------------------------------------------
        fact_data = []
        for sale in transformed_changed_sales:
            fact_data.append((
                sale["order_id"],
                sale["product_id"],
                sale["customer_key"],
                sale["product_key"],
                sale["date_key"],
                sale["quantity"],
                sale["unit_price"],
                sale["revenue"],
                sale["status"]
            ))

        cur.executemany("""
            INSERT INTO analytics.fact_sales (
                order_id, product_id, customer_key,
                product_key, date_key, quantity,
                unit_price, revenue, order_status
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)

            ON CONFLICT (order_id, product_id)
            DO UPDATE SET
                customer_key = EXCLUDED.customer_key,
                product_key = EXCLUDED.product_key,
                date_key = EXCLUDED.date_key,
                quantity = EXCLUDED.quantity,
                unit_price = EXCLUDED.unit_price,
                revenue = EXCLUDED.revenue,
                order_status = EXCLUDED.order_status
        """, fact_data)
        


        # ----------------------------------------------------
        # 16. UPDATE WATERMARK - LAST STEP BEFORE COMMIT
        # ----------------------------------------------------
        cur.execute("""
            UPDATE analytics.etl_watermark
            SET last_successful_at = %s
            WHERE pipeline_name = %s
            RETURNING last_successful_at
        """, (batch_end, "ecommerce_incremental"))

        result = cur.fetchone()

        if result is None:
            raise ValueError("Watermark not found")

# Exiting the connection context commits the entire transaction.
# If an exception occurred inside, psycopg rolls it all back.


# ============================================================
# FINAL SUMMARY - PRINT ONLY AFTER SUCCESSFUL COMMIT
# ============================================================
print("\n========== ETL SUMMARY ==========")
print("Previous Watermark:", watermark)
print("Batch End:", batch_end)

print("\n--- INCREMENTAL EXTRACT ---")
print("Customers:", len(changed_customers))
print("Products:", len(changed_products))
print("Sales:", len(changed_sales))

print("\n--- SCD TYPE 2 ---")
print("New Customers:", len(new_customers))
print("Modified Customers:", len(modified_customers))
print("New Products:", len(new_products))
print("Modified Products:", len(modified_products))

print("\n--- FACT SALES ---")
print("Rows processed:", len(fact_data))

print("\nSTATUS: SUCCESS")
print("=================================")


# ----------------------------------
# SAVE ETL SUMMARY TO LOG FILE
# ----------------------------------

logger.info(
    "SUCCESS | Watermark: %s -> %s | "
    "Customers: %d | Products: %d | Sales: %d | "
    "New Customers: %d | Modified Customers: %d | "
    "New Products: %d | Modified Products: %d | "
    "Fact Rows: %d",
    watermark,
    batch_end,
    len(changed_customers),
    len(changed_products),
    len(changed_sales),
    len(new_customers),
    len(modified_customers),
    len(new_products),
    len(modified_products),
    len(fact_data)
)
