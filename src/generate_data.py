
import csv
import random
from pathlib import Path
from faker import Faker
from datetime import datetime, timedelta, timezone
from decimal import Decimal

fake = Faker("fr_FR")
Faker.seed(42)
random.seed(42)

CITIES = [
    "Rabat", "Casablanca", "Marrakech",
    "Fes", "Tanger", "Agadir",
    "Meknes", "Oujda"
]

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "data"
DATA_DIR.mkdir(exist_ok=True)

file_path = DATA_DIR / "customers.csv"

with open(file_path, "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)

    writer.writerow(["customer_name", "email", "city"])

    for i in range(1, 201):
        name = fake.name()
        email = f"customer{i:03d}@example.com"
        city = random.choice(CITIES)

        writer.writerow([name, email, city])

print("200 Customers generated successfully!")

# ----------------------------------
# GENERATE CATEGORIES
# ----------------------------------

CATEGORIES = {
    "Electronics": (["Laptop", "Monitor", "Mouse", "Keyboard"], 150, 9000),
    "Furniture": (["Desk", "Office Chair", "Bookshelf"], 200, 5000),
    "Clothing": (["T-Shirt", "Jeans", "Jacket"], 70, 900),
    "Home & Kitchen": (["Blender", "Toaster", "Coffee Maker"], 60, 2000),
    "Beauty": (["Shampoo", "Perfume", "Face Cream"], 30, 500),
    "Sports": (["Yoga Mat", "Dumbbells", "Football"], 50, 1600),
    "Books": (["Python Guide", "SQL Handbook", "Novel"], 40, 400),
    "Accessories": (["Backpack", "Wallet", "Watch"], 40, 800)
}

with open(DATA_DIR / "categories.csv", "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)

    writer.writerow(["category_name"])

    for category_name in CATEGORIES:
        writer.writerow([category_name])

print("8 Categories generated successfully!")


# ----------------------------------
# GENERATE PRODUCTS
# ----------------------------------

category_names = list(CATEGORIES.keys())

with open(DATA_DIR / "products.csv", "w", newline="", encoding="utf-8") as file:
    writer = csv.writer(file)

    writer.writerow([
        "product_name", "price", "stock", "category_name"
    ])

    for i in range(60):
        category_name = category_names[i % len(category_names)]

        product_types, min_price, max_price = CATEGORIES[category_name]

        product_type = random.choice(product_types)
        product_name = f"{product_type} - REF{i+1:03d}"

        price = f"{random.randint(min_price, max_price)}.99"
        stock = random.randint(0, 120)

        writer.writerow([
            product_name, price, stock, category_name
        ])

print("60 Products generated successfully!")

# ----------------------------------
# GENERATE ORDERS & ORDER ITEMS
# ----------------------------------

# Read generated customers and products
with open(DATA_DIR / "customers.csv", newline="", encoding="utf-8") as f:
    customers = list(csv.DictReader(f))

with open(DATA_DIR / "products.csv", newline="", encoding="utf-8") as f:
    products = list(csv.DictReader(f))


# 1000 orders with exactly 2500 order items
items_per_order = (
    [1] * 250 +
    [2] * 250 +
    [3] * 250 +
    [4] * 250
)

random.shuffle(items_per_order)

start_date = datetime(2025, 1, 1, tzinfo=timezone.utc)
end_date = datetime(2026, 10, 31, 23, 59, tzinfo=timezone.utc)
date_range = int((end_date - start_date).total_seconds())


with open(DATA_DIR / "orders.csv", "w", newline="", encoding="utf-8") as orders_file, \
     open(DATA_DIR / "order_items.csv", "w", newline="", encoding="utf-8") as items_file:

    orders_writer = csv.writer(orders_file)
    items_writer = csv.writer(items_file)

    orders_writer.writerow([
        "order_ref", "customer_email",
        "order_date", "status", "total_amount"
    ])

    items_writer.writerow([
        "order_ref", "product_name", "quantity", "unit_price"
    ])

    for i, number_of_items in enumerate(items_per_order, start=1):

        order_ref = f"ORD-{i:05d}"
        customer = random.choice(customers)

        order_date = start_date + timedelta(
            seconds=random.randint(0, date_range)
        )

        status = random.choices(
            ["PENDING", "PAID", "SHIPPED", "CANCELLED"],
            weights=[20, 30, 40, 10],
            k=1
        )[0]

        selected_products = random.sample(
            products, k=number_of_items
        )

        total_amount = Decimal("0.00")

        for product in selected_products:

            quantity = random.randint(1, 4)
            unit_price = Decimal(product["price"])

            total_amount += quantity * unit_price

            items_writer.writerow([
                order_ref,
                product["product_name"],
                quantity,
                f"{unit_price:.2f}"
            ])

        orders_writer.writerow([
            order_ref,
            customer["email"],
            order_date.isoformat(timespec="seconds"),
            status,
            f"{total_amount:.2f}"
        ])

print("1000 Orders generated successfully!")
print("2500 Order Items generated successfully!")
