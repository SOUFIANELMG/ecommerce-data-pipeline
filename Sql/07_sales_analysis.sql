#Monthly Revenue:

SELECT
    d.year_number,
    d.month_number,
    d.month_name,
    SUM(fs.revenue) AS monthly_revenue

FROM analytics.fact_sales fs

JOIN analytics.dim_date d
    ON fs.date_key = d.date_key

GROUP BY
    d.year_number,
    d.month_number,
    d.month_name

ORDER BY
    d.year_number,
    d.month_number;


# Monthly Revenue Growth (%):

WITH monthly_sales AS (
    SELECT
        d.year_number,
        d.month_number,
        SUM(fs.revenue) AS monthly_revenue
    FROM analytics.fact_sales fs
    JOIN analytics.dim_date d
        ON fs.date_key = d.date_key
    GROUP BY d.year_number, d.month_number
)

SELECT
    year_number,
    month_number,
    monthly_revenue,

    LAG(monthly_revenue) OVER (
        ORDER BY year_number, month_number
    ) AS previous_month_revenue,

    ROUND(
        (
            monthly_revenue
            - LAG(monthly_revenue) OVER (
                ORDER BY year_number, month_number
            )
        ) * 100.0
        / NULLIF(
            LAG(monthly_revenue) OVER (
                ORDER BY year_number, month_number
            ), 0
        ),
        2
    ) AS growth_percentage

FROM monthly_sales
ORDER BY year_number, month_number;


# Top 10 Best-Selling Products:

SELECT
    dp.product_id,
    current_dp.product_name,
    SUM(fs.quantity) AS units_sold,
    SUM(fs.revenue) AS total_revenue

FROM analytics.fact_sales fs

JOIN analytics.dim_product dp
    ON fs.product_key = dp.product_key

JOIN analytics.dim_product current_dp
    ON dp.product_id = current_dp.product_id
    AND current_dp.is_current = TRUE

GROUP BY
    dp.product_id,
    current_dp.product_name

ORDER BY units_sold DESC
LIMIT 10;


# Top 10 Customers by Revenue:

SELECT
    dc.customer_id,
    current_dc.customer_name,
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
    current_dc.customer_name

ORDER BY total_revenue DESC
LIMIT 10;
