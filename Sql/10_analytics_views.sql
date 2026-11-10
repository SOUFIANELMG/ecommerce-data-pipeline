--Création dyal Sales KPIs View:

CREATE OR REPLACE VIEW analytics.v_sales_kpis AS

SELECT
    SUM(revenue) AS total_revenue,
    COUNT(DISTINCT order_id) AS total_orders,
    SUM(quantity) AS units_sold,

    ROUND(
        SUM(revenue) /
        NULLIF(COUNT(DISTINCT order_id), 0),
        2
    ) AS average_order_value

FROM analytics.fact_sales;


--Création dyal Monthly Sales View:

CREATE OR REPLACE VIEW analytics.v_monthly_sales AS

SELECT
    d.year_number,
    d.month_number,
    d.month_name,

    SUM(fs.revenue) AS monthly_revenue,
    COUNT(DISTINCT fs.order_id) AS total_orders,
    SUM(fs.quantity) AS units_sold

FROM analytics.fact_sales fs

JOIN analytics.dim_date d
    ON fs.date_key = d.date_key

GROUP BY
    d.year_number,
    d.month_number,
    d.month_name;

-— Customer Analytics View:


CREATE OR REPLACE VIEW analytics.v_customer_sales AS

SELECT
    dc.customer_id,
    current_dc.customer_name,
    current_dc.city,
    SUM(fs.revenue) AS total_revenue,
    COUNT(DISTINCT fs.order_id) AS total_orders

FROM analytics.fact_sales fs

JOIN analytics.dim_customer dc
    ON fs.customer_key = dc.customer_key

JOIN analytics.dim_customer current_dc
    ON dc.customer_id = current_dc.customer_id
   AND current_dc.is_current = TRUE

GROUP BY
    dc.customer_id,
    current_dc.customer_name,
    current_dc.city;

-— Product Analytics View:


CREATE OR REPLACE VIEW analytics.v_product_sales AS

SELECT
    dp.product_id,
    dp.product_name,
    dp.category_name,

    SUM(fs.revenue) AS total_revenue,
    SUM(fs.quantity) AS units_sold,
    COUNT(DISTINCT fs.order_id) AS total_orders

FROM analytics.fact_sales fs

JOIN analytics.dim_product dp
    ON fs.product_id = dp.product_id
   AND dp.is_current = TRUE

GROUP BY
    dp.product_id,
    dp.product_name,
    dp.category_name;

-- For Power BI:

CREATE OR REPLACE VIEW analytics.v_dim_product_current AS
SELECT
    product_id,
    product_name,
    category_name
FROM analytics.dim_product
WHERE is_current = TRUE;



CREATE OR REPLACE VIEW analytics.v_dim_customer_current AS

SELECT
    hist.customer_key,
    hist.customer_id,
    curr.customer_name,
    curr.city AS current_city

FROM analytics.dim_customer hist

JOIN analytics.dim_customer curr
    ON hist.customer_id = curr.customer_id
   AND curr.is_current = TRUE;
