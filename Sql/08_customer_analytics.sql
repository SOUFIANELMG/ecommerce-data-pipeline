-- Revenue by City:

SELECT
    dc.city,
    SUM(fs.revenue) AS total_revenue,
    COUNT(DISTINCT fs.order_id) AS total_orders

FROM analytics.fact_sales fs

JOIN analytics.dim_customer dc
    ON fs.customer_key = dc.customer_key

GROUP BY dc.city

ORDER BY total_revenue DESC;


--Revenue by Current City:

SELECT
    current_dc.city,
    SUM(fs.revenue) AS total_revenue,
    COUNT(DISTINCT fs.order_id) AS total_orders

FROM analytics.fact_sales fs

JOIN analytics.dim_customer dc
    ON fs.customer_key = dc.customer_key

JOIN analytics.dim_customer current_dc
    ON dc.customer_id = current_dc.customer_id
   AND current_dc.is_current = TRUE

GROUP BY current_dc.city

ORDER BY total_revenue DESC;

--Active Customers & Purchase Frequency:


SELECT
    COUNT(DISTINCT dc.customer_id) AS active_customers,

    COUNT(DISTINCT fs.order_id) AS total_orders,

    ROUND(
        COUNT(DISTINCT fs.order_id)::NUMERIC
        / NULLIF(COUNT(DISTINCT dc.customer_id), 0),
        2
    ) AS avg_orders_per_customer

FROM analytics.fact_sales fs

JOIN analytics.dim_customer dc
    ON fs.customer_key = dc.customer_key;

--Customer Segmentation:


WITH customer_revenue AS (
    SELECT
        dc.customer_id,
        COUNT(DISTINCT fs.order_id) AS total_orders,
        SUM(fs.revenue) AS total_revenue

    FROM analytics.fact_sales fs

    JOIN analytics.dim_customer dc
        ON fs.customer_key = dc.customer_key

    GROUP BY dc.customer_id
),

customer_ranking AS (
    SELECT
        *,
        NTILE(3) OVER (
            ORDER BY total_revenue DESC
        ) AS revenue_group
    FROM customer_revenue
)

SELECT
    customer_id,
    total_orders,
    total_revenue,

    CASE
        WHEN revenue_group = 1 THEN 'High Value'
        WHEN revenue_group = 2 THEN 'Medium Value'
        ELSE 'Low Value'
    END AS customer_segment

FROM customer_ranking
ORDER BY total_revenue DESC;
