-- PostgreSQL table for the clean, one-row-per-order extract.
-- First run this file, then import data/processed/delivery_performance.csv.

CREATE SCHEMA IF NOT EXISTS portfolio;

DROP TABLE IF EXISTS portfolio.delivery_performance;

CREATE TABLE portfolio.delivery_performance (
    order_id                    TEXT PRIMARY KEY,
    customer_id                 TEXT,
    customer_unique_id          TEXT,
    customer_state              TEXT,
    order_status                TEXT,
    purchase_timestamp          TIMESTAMP,
    approved_timestamp          TIMESTAMP,
    carrier_handoff_timestamp   TIMESTAMP,
    delivered_timestamp         TIMESTAMP,
    estimated_delivery_timestamp TIMESTAMP,
    purchase_month              DATE,
    item_count                  INTEGER,
    seller_count                INTEGER,
    distinct_product_count      INTEGER,
    primary_category            TEXT,
    item_value                  NUMERIC(12,2),
    freight_value               NUMERIC(12,2),
    merchandise_and_freight_total NUMERIC(12,2),
    payment_value_total         NUMERIC(12,2),
    review_count                INTEGER,
    review_score                NUMERIC(4,2),
    delivery_days               NUMERIC(10,2),
    days_vs_estimate            NUMERIC(10,2),
    is_delivered                SMALLINT,
    was_on_time                 SMALLINT
);

-- Example psql import (replace the file path with your local absolute path):
-- \copy portfolio.delivery_performance FROM 'C:/Users/jjfst/delivery-performance-analytics/data/processed/delivery_performance.csv' WITH (FORMAT csv, HEADER true)
