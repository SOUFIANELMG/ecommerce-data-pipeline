#Total Revenue:

SELECT
    SUM(revenue) AS total_revenue
FROM analytics.fact_sales;

# Total orders:
SELECT
    count (distinct order_id) AS total_orders
FROM analytics.fact_sales;

#total units sold:

SELECT
    sum(quantity) AS units_sold
FROM analytics.fact_sales;

#average_order_value:

SELECT
    SUM(revenue) AS total_revenue,
    COUNT(DISTINCT order_id) AS total_orders,
    ROUND(
        SUM(revenue) / NULLIF(COUNT(DISTINCT order_id), 0),
        2
    ) AS average_order_value
FROM analytics.fact_sales;

#chiffre d affaires par customer:

SELECT
    dc.customer_id,
    SUM(fs.revenue) AS total_revenue
FROM analytics.fact_sales fs
JOIN analytics.dim_customer dc
    ON fs.customer_key = dc.customer_key
GROUP BY dc.customer_id
ORDER BY total_revenue DESC;