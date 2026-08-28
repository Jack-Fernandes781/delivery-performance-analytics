"""Build a validated, one-row-per-order delivery-performance dataset.

Source: Brazilian E-Commerce Public Dataset by Olist. Raw source CSVs belong in
data/raw; generated outputs are intentionally not versioned.
"""

from __future__ import annotations

from pathlib import Path
import sys

import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"

REQUIRED_FILES = {
    "orders": "olist_orders_dataset.csv",
    "items": "olist_order_items_dataset.csv",
    "customers": "olist_customers_dataset.csv",
    "payments": "olist_order_payments_dataset.csv",
    "reviews": "olist_order_reviews_dataset.csv",
    "products": "olist_products_dataset.csv",
    "translation": "product_category_name_translation.csv",
}

REQUIRED_COLUMNS = {
    "orders": {
        "order_id",
        "customer_id",
        "order_status",
        "order_purchase_timestamp",
        "order_approved_at",
        "order_delivered_carrier_date",
        "order_delivered_customer_date",
        "order_estimated_delivery_date",
    },
    "items": {"order_id", "order_item_id", "product_id", "seller_id", "price", "freight_value"},
    "customers": {"customer_id", "customer_unique_id", "customer_state"},
    "payments": {"order_id", "payment_value"},
    "reviews": {"order_id", "review_score"},
    "products": {"product_id", "product_category_name"},
    "translation": {"product_category_name", "product_category_name_english"},
}


def load_source(name: str) -> pd.DataFrame:
    """Read one expected source file and fail with a useful validation message."""
    source_path = RAW_DIR / REQUIRED_FILES[name]
    if not source_path.exists():
        raise FileNotFoundError(
            f"Missing {source_path.name}. See {RAW_DIR / 'README.md'} for raw-data setup."
        )

    frame = pd.read_csv(source_path)
    missing_columns = REQUIRED_COLUMNS[name] - set(frame.columns)
    if missing_columns:
        missing = ", ".join(sorted(missing_columns))
        raise ValueError(f"{source_path.name} is missing required column(s): {missing}")
    return frame


def parse_datetimes(frame: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    frame = frame.copy()
    for column in columns:
        frame[column] = pd.to_datetime(frame[column], errors="coerce")
    return frame


def build_order_items(items: pd.DataFrame, products: pd.DataFrame, translation: pd.DataFrame) -> pd.DataFrame:
    """Aggregate item rows and select an explicit dashboard category per order."""
    product_lookup = products.merge(
        translation,
        on="product_category_name",
        how="left",
        validate="m:1",
    )
    line_items = items.merge(
        product_lookup[["product_id", "product_category_name_english"]],
        on="product_id",
        how="left",
        validate="m:1",
    ).rename(columns={"product_category_name_english": "category"})

    line_items["category"] = line_items["category"].fillna("Unknown")

    totals = (
        line_items.groupby("order_id", as_index=False)
        .agg(
            item_count=("order_item_id", "count"),
            seller_count=("seller_id", "nunique"),
            distinct_product_count=("product_id", "nunique"),
            item_value=("price", "sum"),
            freight_value=("freight_value", "sum"),
        )
        .assign(
            merchandise_and_freight_total=lambda frame: frame["item_value"]
            + frame["freight_value"]
        )
    )

    # An order can include several categories. Use the highest-priced item so every
    # order has one stable category for dashboard grouping; break ties predictably.
    primary_category = (
        line_items.sort_values(
            ["order_id", "price", "category", "product_id"],
            ascending=[True, False, True, True],
            kind="stable",
        )
        .drop_duplicates("order_id")
        [["order_id", "category"]]
        .rename(columns={"category": "primary_category"})
    )

    return totals.merge(primary_category, on="order_id", how="left", validate="1:1")


def build_delivery_dataset() -> pd.DataFrame:
    frames = {name: load_source(name) for name in REQUIRED_FILES}

    orders = parse_datetimes(
        frames["orders"],
        [
            "order_purchase_timestamp",
            "order_approved_at",
            "order_delivered_carrier_date",
            "order_delivered_customer_date",
            "order_estimated_delivery_date",
        ],
    )

    if orders["order_id"].duplicated().any():
        raise ValueError("The orders source contains duplicate order_id values; stop and investigate.")
    if frames["customers"]["customer_id"].duplicated().any():
        raise ValueError("The customers source contains duplicate customer_id values; stop and investigate.")

    order_items = build_order_items(frames["items"], frames["products"], frames["translation"])
    payments = (
        frames["payments"].groupby("order_id", as_index=False)
        .agg(payment_value_total=("payment_value", "sum"))
    )
    reviews = (
        frames["reviews"].groupby("order_id", as_index=False)
        .agg(review_count=("review_score", "size"), review_score=("review_score", "mean"))
    )

    dataset = (
        orders.merge(
            frames["customers"][["customer_id", "customer_unique_id", "customer_state"]],
            on="customer_id",
            how="left",
            validate="1:1",
        )
        .merge(order_items, on="order_id", how="left", validate="1:1")
        .merge(payments, on="order_id", how="left", validate="1:1")
        .merge(reviews, on="order_id", how="left", validate="1:1")
    )

    dataset = dataset.rename(
        columns={
            "order_purchase_timestamp": "purchase_timestamp",
            "order_approved_at": "approved_timestamp",
            "order_delivered_carrier_date": "carrier_handoff_timestamp",
            "order_delivered_customer_date": "delivered_timestamp",
            "order_estimated_delivery_date": "estimated_delivery_timestamp",
        }
    )

    dataset["purchase_month"] = dataset["purchase_timestamp"].dt.to_period("M").dt.to_timestamp()
    dataset["is_delivered"] = (dataset["order_status"] == "delivered").astype("int8")
    dataset["delivery_days"] = (
        (dataset["delivered_timestamp"] - dataset["purchase_timestamp"]).dt.total_seconds() / 86_400
    )
    dataset["days_vs_estimate"] = (
        (dataset["delivered_timestamp"] - dataset["estimated_delivery_timestamp"]).dt.total_seconds() / 86_400
    )

    # Timeliness is unknown for undelivered orders; retain a nullable value instead
    # of incorrectly labeling those orders as late.
    dataset["was_on_time"] = pd.Series(pd.NA, index=dataset.index, dtype="Int8")
    delivered_with_estimate = (
        dataset["is_delivered"].eq(1)
        & dataset["delivered_timestamp"].notna()
        & dataset["estimated_delivery_timestamp"].notna()
    )
    dataset.loc[delivered_with_estimate, "was_on_time"] = np.where(
        dataset.loc[delivered_with_estimate, "days_vs_estimate"] <= 0,
        1,
        0,
    )

    if dataset["order_id"].duplicated().any():
        raise ValueError("Transformation created duplicate order rows; stop and investigate joins.")

    output_columns = [
        "order_id",
        "customer_id",
        "customer_unique_id",
        "customer_state",
        "order_status",
        "purchase_timestamp",
        "approved_timestamp",
        "carrier_handoff_timestamp",
        "delivered_timestamp",
        "estimated_delivery_timestamp",
        "purchase_month",
        "item_count",
        "seller_count",
        "distinct_product_count",
        "primary_category",
        "item_value",
        "freight_value",
        "merchandise_and_freight_total",
        "payment_value_total",
        "review_count",
        "review_score",
        "delivery_days",
        "days_vs_estimate",
        "is_delivered",
        "was_on_time",
    ]
    return dataset[output_columns].sort_values("purchase_timestamp", kind="stable")


def write_outputs(dataset: pd.DataFrame) -> None:
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(PROCESSED_DIR / "delivery_performance.csv", index=False)

    delivered = dataset.loc[dataset["is_delivered"].eq(1)]
    summary = pd.DataFrame(
        {
            "metric": [
                "rows",
                "unique_orders",
                "delivered_orders",
                "delivered_orders_missing_delivery_timestamp",
                "delivered_orders_missing_estimated_timestamp",
                "negative_delivery_days",
                "on_time_rate_pct_among_delivered_with_complete_dates",
            ],
            "value": [
                len(dataset),
                dataset["order_id"].nunique(),
                len(delivered),
                int(delivered["delivered_timestamp"].isna().sum()),
                int(delivered["estimated_delivery_timestamp"].isna().sum()),
                int((dataset["delivery_days"] < 0).sum()),
                round(100 * delivered["was_on_time"].dropna().mean(), 2),
            ],
        }
    )
    summary.to_csv(PROCESSED_DIR / "data_quality_summary.csv", index=False)


def main() -> None:
    try:
        dataset = build_delivery_dataset()
        write_outputs(dataset)
    except (FileNotFoundError, ValueError) as error:
        print(f"Build failed: {error}", file=sys.stderr)
        raise SystemExit(1) from error

    print(f"Built {len(dataset):,} order rows.")
    print(f"Wrote {PROCESSED_DIR / 'delivery_performance.csv'}")
    print(f"Wrote {PROCESSED_DIR / 'data_quality_summary.csv'}")


if __name__ == "__main__":
    main()
