-- name: kpi_overview
WITH item_order AS (
    SELECT order_id, SUM(price) AS product_sales_brl, SUM(freight_value) AS freight_value_brl,
           COUNT(*) AS item_lines
    FROM order_items GROUP BY order_id
), payment_order AS (
    SELECT order_id, SUM(payment_value) AS payment_value_brl
    FROM order_payments GROUP BY order_id
), customer_order AS (
    SELECT o.order_id, c.customer_unique_id
    FROM orders o LEFT JOIN customers c ON o.customer_id = c.customer_id
)
SELECT
    COUNT(*) AS delivered_orders,
    COUNT(DISTINCT co.customer_unique_id) AS identified_customers,
    ROUND(SUM(io.product_sales_brl), 2) AS product_sales_brl,
    ROUND(SUM(io.freight_value_brl), 2) AS freight_value_brl,
    ROUND(AVG(io.product_sales_brl), 2) AS avg_product_value_per_order_brl,
    ROUND(SUM(po.payment_value_brl), 2) AS payment_value_brl
FROM orders o
JOIN item_order io ON io.order_id = o.order_id
LEFT JOIN payment_order po ON po.order_id = o.order_id
LEFT JOIN customer_order co ON co.order_id = o.order_id
WHERE o.order_status = 'delivered';

-- name: monthly_sales
WITH item_order AS (
    SELECT order_id, SUM(price) AS product_sales_brl, SUM(freight_value) AS freight_value_brl
    FROM order_items GROUP BY order_id
)
SELECT substr(o.order_purchase_timestamp, 1, 7) AS purchase_month,
       COUNT(*) AS delivered_orders,
       ROUND(SUM(io.product_sales_brl), 2) AS product_sales_brl,
       ROUND(SUM(io.freight_value_brl), 2) AS freight_value_brl,
       ROUND(AVG(io.product_sales_brl), 2) AS avg_product_value_per_order_brl
FROM orders o JOIN item_order io ON io.order_id = o.order_id
WHERE o.order_status = 'delivered'
GROUP BY purchase_month ORDER BY purchase_month;

-- name: category_performance
SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
       COUNT(DISTINCT oi.order_id) AS orders,
       COUNT(*) AS order_item_lines,
       ROUND(SUM(oi.price), 2) AS product_sales_brl,
       ROUND(SUM(oi.freight_value), 2) AS freight_value_brl,
       ROUND(AVG(oi.price), 2) AS avg_item_price_brl
FROM order_items oi
JOIN orders o ON o.order_id = oi.order_id
LEFT JOIN products p ON p.product_id = oi.product_id
LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
WHERE o.order_status = 'delivered'
GROUP BY category
ORDER BY product_sales_brl DESC;

-- name: category_yoy_growth
WITH yearly AS (
    SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
           substr(o.order_purchase_timestamp, 1, 4) AS sales_year,
           SUM(oi.price) AS product_sales_brl
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    LEFT JOIN products p ON p.product_id = oi.product_id
    LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
    WHERE o.order_status = 'delivered'
    GROUP BY category, sales_year
), compared AS (
    SELECT category, sales_year, product_sales_brl,
           LAG(product_sales_brl) OVER (PARTITION BY category ORDER BY sales_year) AS prior_year_sales_brl
    FROM yearly
)
SELECT category, sales_year, ROUND(product_sales_brl, 2) AS product_sales_brl,
       ROUND(prior_year_sales_brl, 2) AS prior_year_sales_brl,
       ROUND(100.0 * (product_sales_brl - prior_year_sales_brl) / NULLIF(prior_year_sales_brl, 0), 2) AS yoy_growth_pct
FROM compared ORDER BY category, sales_year;

-- name: category_pareto
WITH category_sales AS (
    SELECT COALESCE(t.product_category_name_english, p.product_category_name, 'unknown') AS category,
           SUM(oi.price) AS product_sales_brl
    FROM order_items oi
    JOIN orders o ON o.order_id = oi.order_id
    LEFT JOIN products p ON p.product_id = oi.product_id
    LEFT JOIN category_translation t ON t.product_category_name = p.product_category_name
    WHERE o.order_status = 'delivered'
    GROUP BY category
), ranked AS (
    SELECT category, product_sales_brl,
           SUM(product_sales_brl) OVER (ORDER BY product_sales_brl DESC ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW) AS cumulative_sales_brl,
           SUM(product_sales_brl) OVER () AS all_sales_brl
    FROM category_sales
)
SELECT category, ROUND(product_sales_brl, 2) AS product_sales_brl,
       ROUND(100.0 * product_sales_brl / NULLIF(all_sales_brl, 0), 2) AS sales_share_pct,
       ROUND(100.0 * cumulative_sales_brl / NULLIF(all_sales_brl, 0), 2) AS cumulative_sales_share_pct
FROM ranked ORDER BY product_sales_brl DESC;

-- name: customer_rfm
WITH order_value AS (
    SELECT o.order_id, o.customer_id, o.order_purchase_timestamp,
           SUM(oi.price) AS product_sales_brl
    FROM orders o JOIN order_items oi ON oi.order_id = o.order_id
    WHERE o.order_status = 'delivered'
    GROUP BY o.order_id, o.customer_id, o.order_purchase_timestamp
), customer_value AS (
    SELECT c.customer_unique_id,
           COUNT(DISTINCT ov.order_id) AS delivered_orders,
           SUM(ov.product_sales_brl) AS lifetime_product_sales_brl,
           MAX(date(ov.order_purchase_timestamp)) AS last_purchase_date,
           MIN(date(ov.order_purchase_timestamp)) AS first_purchase_date
    FROM order_value ov
    JOIN customers c ON c.customer_id = ov.customer_id
    GROUP BY c.customer_unique_id
), dataset_clock AS (
    SELECT MAX(date(order_purchase_timestamp)) AS data_end_date FROM orders
)
SELECT cv.customer_unique_id, cv.delivered_orders,
       CAST(julianday(dc.data_end_date) - julianday(cv.last_purchase_date) AS INTEGER) AS recency_days,
       CAST(julianday(cv.last_purchase_date) - julianday(cv.first_purchase_date) AS INTEGER) AS observed_customer_lifespan_days,
       ROUND(cv.lifetime_product_sales_brl, 2) AS lifetime_product_sales_brl,
       ROUND(cv.lifetime_product_sales_brl / NULLIF(cv.delivered_orders, 0), 2) AS avg_product_sales_per_order_brl,
       dc.data_end_date AS analysis_reference_date
FROM customer_value cv CROSS JOIN dataset_clock dc
ORDER BY lifetime_product_sales_brl DESC;

-- name: delivery_performance
SELECT substr(order_purchase_timestamp, 1, 7) AS purchase_month,
       COUNT(*) AS delivered_orders,
       ROUND(AVG(julianday(order_delivered_customer_date) - julianday(order_purchase_timestamp)), 2) AS avg_delivery_days,
       ROUND(AVG(CASE WHEN date(order_delivered_customer_date) > date(order_estimated_delivery_date) THEN 1.0 ELSE 0.0 END) * 100, 2) AS delivered_late_pct,
       ROUND(AVG(CASE WHEN date(order_delivered_customer_date) <= date(order_estimated_delivery_date) THEN 1.0 ELSE 0.0 END) * 100, 2) AS delivered_on_time_or_early_pct
FROM orders
WHERE order_status = 'delivered' AND order_delivered_customer_date IS NOT NULL
GROUP BY purchase_month ORDER BY purchase_month;

-- name: payment_reconciliation
WITH item_order AS (
    SELECT order_id, SUM(price) AS product_sales_brl, SUM(freight_value) AS freight_value_brl
    FROM order_items GROUP BY order_id
), payment_order AS (
    SELECT order_id, SUM(payment_value) AS payment_value_brl
    FROM order_payments GROUP BY order_id
)
SELECT o.order_status, COUNT(*) AS orders,
       ROUND(SUM(io.product_sales_brl), 2) AS product_sales_brl,
       ROUND(SUM(io.freight_value_brl), 2) AS freight_value_brl,
       ROUND(SUM(COALESCE(po.payment_value_brl, 0)), 2) AS payment_value_brl,
       ROUND(SUM(COALESCE(po.payment_value_brl, 0) - io.product_sales_brl - io.freight_value_brl), 2) AS payments_minus_items_and_freight_brl
FROM orders o
JOIN item_order io ON io.order_id = o.order_id
LEFT JOIN payment_order po ON po.order_id = o.order_id
GROUP BY o.order_status ORDER BY orders DESC;
