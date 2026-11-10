
import psycopg
from psycopg.rows import dict_row
from getpass import getpass


# 1. Database configuration
db_config = {
    "host": "localhost",
    "port": 5432,
    "dbname": "ecommerce_pipeline_db",
    "user": "postgres",
    "password": getpass("PostgreSQL password: ")
}

# 2. SQL Extraction Query
sql_sales = """
    SELECT
        o.order_id,
        o.customer_id,
        o.order_date,
        (o.order_date AT TIME ZONE 'Africa/Casablanca')::date AS full_date,
        o.status,
        oi.product_id,
        oi.quantity,
        oi.unit_price
    FROM public.orders AS o
    JOIN public.order_items AS oi
        ON o.order_id = oi.order_id
    ORDER BY o.order_id, oi.product_id
"""


# 3. Extract OLTP data

with psycopg.connect(**db_config, row_factory=dict_row) as conn:
    with conn.cursor() as cur:

        # Extract Sales
        cur.execute(sql_sales)
        sales_rows = cur.fetchall()

        # Extract Customers
        cur.execute("""
            SELECT
                customer_id,
                customer_name,
                city,
                created_at,
                updated_at
            FROM public.customers
            ORDER BY customer_id
        """)
        customer_rows = cur.fetchall()

        # Extract Products with Categories
        cur.execute("""
            SELECT
                p.product_id,
                p.product_name,
                c.category_name,
                p.created_at,
                p.updated_at
            FROM public.products AS p
            JOIN public.categories AS c
                ON p.category_id = c.category_id
            ORDER BY p.product_id
        """)
        product_rows = cur.fetchall()
        
        # ----------------------------------
        # INITIAL LOAD - DIM CUSTOMER
        # ----------------------------------

        initial_valid_from = min(
            row["order_date"] for row in sales_rows
        )

        customer_data = []

        for c in customer_rows:
            customer_data.append((
                c["customer_id"],
                c["customer_name"],
                c["city"],
                initial_valid_from
            ))

        cur.executemany(
            """
            INSERT INTO analytics.dim_customer
                (customer_id, customer_name, city,
                 valid_from, valid_to, is_current)
            VALUES (%s, %s, %s, %s, NULL, TRUE)

            ON CONFLICT (customer_id)
            WHERE is_current = TRUE
            DO NOTHING
            """,
            customer_data
        )
        
        # ----------------------------------
        # INITIAL LOAD - DIM PRODUCT
        # ----------------------------------

        product_data = []

        for p in product_rows:
            product_data.append((
                p["product_id"],
                p["product_name"],
                p["category_name"],
                initial_valid_from
            ))

        cur.executemany(
            """
            INSERT INTO analytics.dim_product
                (product_id, product_name, category_name,
                 valid_from, valid_to, is_current)
            VALUES (%s, %s, %s, %s, NULL, TRUE)

            ON CONFLICT (product_id)
            WHERE is_current = TRUE
            DO NOTHING
            """,
            product_data
        )
        
        # ----------------------------------
        # INITIAL LOAD - DIM DATE
        # ----------------------------------

        # Extract unique order dates
        cur.execute("""
            SELECT DISTINCT
                (order_date AT TIME ZONE 'Africa/Casablanca')::date
                    AS full_date
            FROM public.orders
            ORDER BY full_date
        """)

        date_rows = cur.fetchall()

        # English month names
        month_names = [
            "January", "February", "March", "April",
            "May", "June", "July", "August",
            "September", "October", "November", "December"
        ]

        # Prepare dimension data
        date_data = []

        for row in date_rows:
            d = row["full_date"]

            date_data.append((
                d,
                d.day,
                d.month,
                month_names[d.month - 1],
                (d.month - 1) // 3 + 1,
                d.year
            ))

        # Load dimension
        cur.executemany(
            """
            INSERT INTO analytics.dim_date
                (full_date, day_number, month_number,
                 month_name, quarter_number, year_number)
            VALUES (%s, %s, %s, %s, %s, %s)

            ON CONFLICT (full_date) DO NOTHING
            """,
            date_data
        )
        
        # ----------------------------------
        # TRANSFORM SALES - STEP 1
        # ----------------------------------

        transformed_sales = []

        for row in sales_rows:

         quantity = row["quantity"]
         unit_price = row["unit_price"]

         revenue = quantity * unit_price

         transformed_sales.append({
          **row,
          "revenue": revenue
        })


         # Verification
        print("Transformed Sales:", len(transformed_sales))

        for row in transformed_sales[:3]:
         print(
        "Order:", row["order_id"],
        "| Product:", row["product_id"],
        "| Date:", row["full_date"],
        "| Revenue:", row["revenue"]
        )
         
        # ----------------------------------
        # MAPPING - CUSTOMER KEY
        # ----------------------------------

        # 1. Read customer dimension versions
        with psycopg.connect(**db_config, row_factory=dict_row) as conn:
         with conn.cursor() as cur:
            cur.execute("""
             SELECT
                customer_key,
                customer_id,
                valid_from,
                valid_to
             FROM analytics.dim_customer
            """)

            customer_versions_rows = cur.fetchall()


            # 2. Group versions by customer_id
            customer_versions = {}

            for version in customer_versions_rows:
              customer_id = version["customer_id"]

              customer_versions.setdefault(customer_id, []).append(version)
              
            # 3. Find the correct historical customer version

            for sale in transformed_sales:

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


            # Verification
            print("Customer keys mapped:", len(transformed_sales))

            for sale in transformed_sales[:3]:
             print(
              "Order:", sale["order_id"],
              "| Customer ID:", sale["customer_id"],
              "| Customer Key:", sale["customer_key"]
            )
             
        # ----------------------------------
        # MAPPING - PRODUCT KEY
        # ----------------------------------

        # 1. Read product dimension versions
        with psycopg.connect(**db_config, row_factory=dict_row) as conn:
          with conn.cursor() as cur:
            cur.execute("""
             SELECT
                product_key,
                product_id,
                valid_from,
                valid_to
             FROM analytics.dim_product
            """)

            product_versions_rows = cur.fetchall()


        # 2. Group versions by product_id
        product_versions = {}

        for version in product_versions_rows:
         product_id = version["product_id"]

         product_versions.setdefault(product_id, []).append(version)


        # 3. Find the correct historical product version
        for sale in transformed_sales:

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


        # 4. Verification
        print("Product keys mapped:", len(transformed_sales))

        for sale in transformed_sales[:3]:
          print(
          "Order:", sale["order_id"],
          "| Product ID:", sale["product_id"],
          "| Product Key:", sale["product_key"]
        )


         
# ----------------------------------
# MAPPING - DATE KEY
# ----------------------------------

# 1. Read Date Dimension
with psycopg.connect(**db_config, row_factory=dict_row) as conn:
    with conn.cursor() as cur:
        cur.execute("""
            SELECT date_key, full_date
            FROM analytics.dim_date
        """)

        date_rows_dw = cur.fetchall()


# 2. Create lookup dictionary
date_map = {}

for row in date_rows_dw:
    date_map[row["full_date"]] = row["date_key"]


# 3. Map date_key for each sale
for sale in transformed_sales:

    full_date = sale["full_date"]

    date_key = date_map.get(full_date)

    if date_key is None:
        raise ValueError(
            f"Date mapping not found: "
            f"order_id={sale['order_id']}, "
            f"full_date={full_date}"
        )

    sale["date_key"] = date_key


# 4. Verification
print("Date keys mapped:", len(transformed_sales))

for sale in transformed_sales[:3]:
    print(
        "Order:", sale["order_id"],
        "| Full Date:", sale["full_date"],
        "| Date Key:", sale["date_key"]
    )
 

# ----------------------------------
# PHASE 5.4 - DATA QUALITY
# ----------------------------------

required_cols = [
    "order_id",
    "product_id",
    "customer_key",
    "product_key",
    "date_key",
    "quantity",
    "unit_price",
    "revenue",
    "status"
]

valid_statuses = {
    "PENDING", "PAID", "SHIPPED", "CANCELLED"
}

seen_keys = set()

for sale in transformed_sales:

    # 1. Check missing values
    for col in required_cols:
        if sale.get(col) is None:
            raise ValueError(
                f"Missing value: {col}, "
                f"order_id={sale['order_id']}"
            )

    # 2. Check duplicate composite keys
    key = (sale["order_id"], sale["product_id"])

    if key in seen_keys:
        raise ValueError(
            f"Duplicate order item: {key}"
        )

    seen_keys.add(key)

    # 3. Check quantity and price
    if sale["quantity"] <= 0 or sale["unit_price"] <= 0:
        raise ValueError(
            f"Invalid quantity or price: {key}"
        )

    # 4. Check revenue
    expected_revenue = (
        sale["quantity"] * sale["unit_price"]
    )

    if sale["revenue"] != expected_revenue:
        raise ValueError(
            f"Invalid revenue: {key}"
        )

    # 5. Check order status
    if sale["status"] not in valid_statuses:
        raise ValueError(
            f"Invalid status: {key}"
        )


print("Data Quality PASSED")
print("Validated rows:", len(seen_keys))

 

# ----------------------------------
# PHASE 5.5 - LOAD FACT SALES
# ----------------------------------

# 1. Prepare data for INSERT
fact_data = []

for sale in transformed_sales:
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


# 2. Load into Data Warehouse
with psycopg.connect(**db_config) as conn:
    with conn.cursor() as cur:

        cur.executemany(
            """
            INSERT INTO analytics.fact_sales (
                order_id,
                product_id,
                customer_key,
                product_key,
                date_key,
                quantity,
                unit_price,
                revenue,
                order_status
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
            """,
            fact_data
        )

print("Fact Sales loading completed!")
print("Rows processed:", len(fact_data))



        

