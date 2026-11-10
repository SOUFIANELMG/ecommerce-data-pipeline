
-- Create Data Warehouse schema

CREATE SCHEMA IF NOT EXISTS analytics;




CREATE TABLE analytics.dim_customer (
    customer_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    customer_id INTEGER NOT NULL,
    customer_name VARCHAR(100) NOT NULL,
    city VARCHAR(100) NOT NULL,

    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ
        CHECK (valid_to IS NULL OR valid_to > valid_from),

    is_current BOOLEAN NOT NULL DEFAULT TRUE
        CHECK (is_current = (valid_to IS NULL)),

    UNIQUE (customer_id, valid_from)
);



CREATE TABLE analytics.dim_product (
    product_key BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    product_id INTEGER NOT NULL,
    product_name VARCHAR(150) NOT NULL,
    category_name VARCHAR(100) NOT NULL,

    valid_from TIMESTAMPTZ NOT NULL,
    valid_to TIMESTAMPTZ
        CHECK (valid_to IS NULL OR valid_to > valid_from),

    is_current BOOLEAN NOT NULL DEFAULT TRUE
        CHECK (is_current = (valid_to IS NULL)),

    UNIQUE (product_id, valid_from)
);



CREATE TABLE analytics.dim_date (
    date_key INTEGER GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    full_date DATE NOT NULL UNIQUE,
    day_number INTEGER NOT NULL CHECK (day_number BETWEEN 1 AND 31),
    month_number INTEGER NOT NULL CHECK (month_number BETWEEN 1 AND 12),
    month_name VARCHAR(20) NOT NULL,
    quarter_number INTEGER NOT NULL CHECK (quarter_number BETWEEN 1 AND 4),
    year_number INTEGER NOT NULL
);



CREATE TABLE analytics.fact_sales (
    order_id INTEGER NOT NULL,
    product_id INTEGER NOT NULL,

    customer_key BIGINT NOT NULL
        REFERENCES analytics.dim_customer(customer_key),

    product_key BIGINT NOT NULL
        REFERENCES analytics.dim_product(product_key),

    date_key INTEGER NOT NULL
        REFERENCES analytics.dim_date(date_key),

    quantity INTEGER NOT NULL CHECK (quantity > 0),
    unit_price NUMERIC(12,2) NOT NULL CHECK (unit_price > 0),
    revenue NUMERIC(18,2) NOT NULL
        CHECK (revenue = quantity * unit_price),

    order_status VARCHAR(20) NOT NULL
        CHECK (order_status IN (
            'PENDING', 'PAID', 'SHIPPED', 'CANCELLED'
        )),

    PRIMARY KEY (order_id, product_id)
);



-- Only one current version per customer

CREATE UNIQUE INDEX idx_dim_customer_current
ON analytics.dim_customer (customer_id)
WHERE is_current = TRUE;


-- Only one current version per product

CREATE UNIQUE INDEX idx_dim_product_current
ON analytics.dim_product (product_id)
WHERE is_current = TRUE;

