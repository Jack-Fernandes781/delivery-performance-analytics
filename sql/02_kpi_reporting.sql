-- Delivery-performance questions for an entry-level analyst portfolio.

-- 1. Monthly operational KPIs. The on-time denominator is delivered orders only.
WITH monthly AS (
    SELECT
        purchase_month,
        COUNT(*) AS total_orders,
        COUNT(*) FILTER (WHERE is_delivered = 1) AS delivered_orders,
        ROUND(100.0 * AVG(was_on_time) FILTER (WHERE is_delivered = 1), 1) AS on_time_rate_pct,
        ROUND(PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY delivery_days)
              FILTER (WHERE is_delivered = 1), 1) AS median_delivery_days,
        ROUND(AVG(review_score) FILTER (WHERE is_delivered = 1), 2) AS avg_review_score
    FROM portfolio.delivery_performance
    GROUP BY purchase_month
)
SELECT *
FROM monthly
ORDER BY purchase_month;

-- 2. States worth prioritizing. A volume threshold avoids overreacting to small samples.
WITH state_kpis AS (
    SELECT
        customer_state,
        COUNT(*) FILTER (WHERE is_delivered = 1) AS delivered_orders,
        ROUND(100.0 * AVG(was_on_time) FILTER (WHERE is_delivered = 1), 1) AS on_time_rate_pct,
        ROUND(AVG(delivery_days) FILTER (WHERE is_delivered = 1), 1) AS avg_delivery_days,
        ROUND(AVG(freight_value), 2) AS avg_freight_value,
        ROUND(AVG(review_score) FILTER (WHERE is_delivered = 1), 2) AS avg_review_score
    FROM portfolio.delivery_performance
    GROUP BY customer_state
)
SELECT *
FROM state_kpis
WHERE delivered_orders >= 100
ORDER BY on_time_rate_pct, delivered_orders DESC;

-- 3. Category opportunities: rank high-volume categories by late-delivery rate.
WITH category_kpis AS (
    SELECT
        COALESCE(primary_category, 'Unknown') AS primary_category,
        COUNT(*) FILTER (WHERE is_delivered = 1) AS delivered_orders,
        ROUND(100.0 * (1 - AVG(was_on_time) FILTER (WHERE is_delivered = 1)), 1) AS late_rate_pct,
        ROUND(SUM(merchandise_and_freight_total), 2) AS merchandise_and_freight_revenue,
        ROUND(AVG(review_score) FILTER (WHERE is_delivered = 1), 2) AS avg_review_score
    FROM portfolio.delivery_performance
    GROUP BY COALESCE(primary_category, 'Unknown')
)
SELECT *
FROM category_kpis
WHERE delivered_orders >= 100
ORDER BY late_rate_pct DESC, delivered_orders DESC;

-- 4. Does late delivery coincide with worse reviews?
SELECT
    CASE
        WHEN is_delivered = 0 THEN 'Not delivered'
        WHEN was_on_time = 1 THEN 'On time'
        ELSE 'Late'
    END AS delivery_outcome,
    COUNT(*) AS orders,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    ROUND(AVG(merchandise_and_freight_total), 2) AS avg_order_value
FROM portfolio.delivery_performance
GROUP BY 1
ORDER BY CASE delivery_outcome
    WHEN 'On time' THEN 1
    WHEN 'Late' THEN 2
    ELSE 3
END;
