-- Run these checks after importing the processed CSV and before publishing findings.

-- The one-row-per-order output must remain unique.
SELECT
    COUNT(*) AS rows_loaded,
    COUNT(DISTINCT order_id) AS distinct_order_ids,
    COUNT(*) - COUNT(DISTINCT order_id) AS duplicate_order_rows
FROM portfolio.delivery_performance;

-- Timing fields should be present for delivered orders, and no negative durations should exist.
SELECT
    COUNT(*) FILTER (WHERE is_delivered = 1) AS delivered_orders,
    COUNT(*) FILTER (WHERE is_delivered = 1 AND delivered_timestamp IS NULL) AS delivered_missing_timestamp,
    COUNT(*) FILTER (WHERE is_delivered = 1 AND estimated_delivery_timestamp IS NULL) AS delivered_missing_estimate,
    COUNT(*) FILTER (WHERE delivery_days < 0) AS negative_delivery_days,
    COUNT(*) FILTER (WHERE days_vs_estimate IS NULL AND is_delivered = 1) AS delivered_missing_variance
FROM portfolio.delivery_performance;

-- Confirm the displayed on-time KPI exposes its denominator.
SELECT
    COUNT(*) FILTER (WHERE is_delivered = 1) AS on_time_denominator,
    COUNT(*) FILTER (WHERE was_on_time = 1) AS on_time_orders,
    ROUND(100.0 * AVG(was_on_time) FILTER (WHERE is_delivered = 1), 1) AS on_time_rate_pct
FROM portfolio.delivery_performance;

-- Missingness inventory for fields used in dashboard filters and KPIs.
SELECT
    COUNT(*) FILTER (WHERE customer_state IS NULL) AS missing_state,
    COUNT(*) FILTER (WHERE primary_category IS NULL) AS missing_primary_category,
    COUNT(*) FILTER (WHERE review_score IS NULL) AS missing_review_score,
    COUNT(*) FILTER (WHERE freight_value IS NULL) AS missing_freight_value
FROM portfolio.delivery_performance;
