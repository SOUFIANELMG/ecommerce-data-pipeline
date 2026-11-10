--Revenue by  Category:

SELECT
    dp.category_name,
    SUM(fs.revenue) AS total_revenue,
    SUM(fs.quantity) AS units_sold,
    COUNT(DISTINCT fs.order_id) AS total_orders

FROM analytics.fact_sales fs

JOIN analytics.dim_product dp
    ON fs.product_key = dp.product_key

GROUP BY dp.category_name

ORDER BY total_revenue DESC;


--Revenue by Current Category:



SELECT
    current_dp.category_name,
    SUM(fs.revenue) AS total_revenue,
    SUM(fs.quantity) AS units_sold,
    COUNT(DISTINCT fs.order_id) AS total_orders

FROM analytics.fact_sales fs

JOIN analytics.dim_product current_dp
    ON fs.product_id = current_dp.product_id
   AND current_dp.is_current = TRUE

GROUP BY current_dp.category_name

ORDER BY total_revenue DESC;

--Category Revenue Contribution (%):


WITH category_sales AS (
    SELECT
        dp.category_name,
        SUM(fs.revenue) AS total_revenue

    FROM analytics.fact_sales fs

    JOIN analytics.dim_product dp
        ON fs.product_id = dp.product_id
       AND dp.is_current = TRUE

    GROUP BY dp.category_name
)

SELECT
    category_name,
    total_revenue,

    ROUND(
        total_revenue * 100.0 /
        NULLIF(SUM(total_revenue) OVER (), 0),
        2
    ) AS contribution_percentage

FROM category_sales

ORDER BY contribution_percentage DESC;

--Product Revenue Contribution by Category:


WITH product_sales AS (
    SELECT
        dp.product_id,
        dp.product_name,
        dp.category_name,
        SUM(fs.revenue) AS total_revenue

    FROM analytics.fact_sales fs

    JOIN analytics.dim_product dp
        ON fs.product_id = dp.product_id
       AND dp.is_current = TRUE

    GROUP BY
        dp.product_id,
        dp.product_name,
        dp.category_name
)

SELECT
    product_id,
    product_name,
    category_name,
    total_revenue,

    ROUND(
        total_revenue * 100.0 /
        NULLIF(
            SUM(total_revenue) OVER (
                PARTITION BY category_name
            ), 0
        ),
        2
    ) AS product_contribution_pct

FROM product_sales

ORDER BY category_name, product_contribution_pct DESC;
