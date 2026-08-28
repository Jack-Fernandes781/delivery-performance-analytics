"""Create portfolio-ready delivery-performance visualizations from the clean extract."""

from __future__ import annotations

from pathlib import Path

import matplotlib.dates as mdates
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import numpy as np
import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PATH = PROJECT_ROOT / "data" / "processed" / "delivery_performance.csv"
OUTPUT_DIR = PROJECT_ROOT / "outputs"

NAVY = "#1f4e79"
BLUE = "#4c78a8"
SKY = "#72b7b2"
ORANGE = "#f58518"
RED = "#d4504c"
TEAL = "#2a9d8f"
SLATE = "#4f5b66"
GRID = "#d9e1e8"


plt.rcParams.update(
    {
        "figure.facecolor": "white",
        "axes.facecolor": "white",
        "axes.edgecolor": "#9aa7b2",
        "axes.labelcolor": "#23323d",
        "xtick.color": "#425563",
        "ytick.color": "#425563",
        "text.color": "#1f2d38",
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 13,
        "axes.titleweight": "bold",
    }
)


def load_data() -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load clean data and retain only delivered orders with valid timeliness dates."""
    frame = pd.read_csv(
        DATA_PATH,
        parse_dates=["purchase_timestamp", "delivered_timestamp", "estimated_delivery_timestamp", "purchase_month"],
    )
    delivered = frame.loc[(frame["is_delivered"] == 1) & frame["was_on_time"].notna()].copy()
    delivered["was_on_time"] = delivered["was_on_time"].astype(int)
    delivered["was_late"] = 1 - delivered["was_on_time"]
    return frame, delivered


def monthly_kpis(delivered: pd.DataFrame) -> pd.DataFrame:
    return (
        delivered.groupby("purchase_month", as_index=False)
        .agg(
            delivered_orders=("order_id", "size"),
            on_time_rate=("was_on_time", "mean"),
            median_delivery_days=("delivery_days", "median"),
        )
        .sort_values("purchase_month")
    )


def style_axis(axis: plt.Axes, *, y_grid: bool = True) -> None:
    axis.spines[["top", "right"]].set_visible(False)
    axis.grid(axis="y", color=GRID, linewidth=0.8, alpha=0.9) if y_grid else axis.grid(False)
    axis.set_axisbelow(True)


def save_figure(figure: plt.Figure, filename: str) -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    figure.savefig(OUTPUT_DIR / filename, dpi=220, bbox_inches="tight", facecolor="white")
    plt.close(figure)


def plot_monthly_on_time(axis: plt.Axes, monthly: pd.DataFrame, *, compact: bool = False) -> None:
    axis.plot(
        monthly["purchase_month"],
        100 * monthly["on_time_rate"],
        color=NAVY,
        linewidth=2.5,
        marker="o",
        markersize=4.5,
    )
    axis.axhline(100 * monthly["on_time_rate"].mean(), color=ORANGE, linewidth=1.5, linestyle="--")
    axis.set_ylim(70, 100)
    axis.yaxis.set_major_formatter(mtick.PercentFormatter())
    axis.set_ylabel("On-time delivery rate")
    axis.xaxis.set_major_locator(mdates.MonthLocator(interval=3 if compact else 2))
    axis.xaxis.set_major_formatter(mdates.DateFormatter("%b\n%Y"))
    style_axis(axis)


def plot_state_late_rate(axis: plt.Axes, delivered: pd.DataFrame, *, compact: bool = False) -> None:
    states = (
        delivered.groupby("customer_state", as_index=False)
        .agg(delivered_orders=("order_id", "size"), late_rate=("was_late", "mean"))
        .query("delivered_orders >= 500")
        .sort_values("late_rate")
    )
    colors = np.where(states["late_rate"] > delivered["was_late"].mean(), RED, SKY)
    axis.barh(states["customer_state"], 100 * states["late_rate"], color=colors, edgecolor="none")
    axis.axvline(100 * delivered["was_late"].mean(), color=ORANGE, linewidth=1.5, linestyle="--")
    axis.xaxis.set_major_formatter(mtick.PercentFormatter())
    axis.set_xlabel("Late-delivery rate")
    if not compact:
        axis.set_title("Late-delivery rate by customer state", loc="left")
        axis.text(
            0.995,
            0.02,
            "Dashed line = overall rate; states with 500+ delivered orders",
            transform=axis.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            color=SLATE,
        )
    style_axis(axis)


def plot_outcome_experience(axis_review: plt.Axes, axis_days: plt.Axes, delivered: pd.DataFrame) -> None:
    outcome = (
        delivered.assign(delivery_outcome=np.where(delivered["was_on_time"].eq(1), "On time", "Late"))
        .groupby("delivery_outcome", as_index=False)
        .agg(
            orders=("order_id", "size"),
            avg_review_score=("review_score", "mean"),
            median_delivery_days=("delivery_days", "median"),
        )
        .set_index("delivery_outcome")
        .loc[["On time", "Late"]]
        .reset_index()
    )
    colors = [TEAL, RED]

    review_bars = axis_review.bar(outcome["delivery_outcome"], outcome["avg_review_score"], color=colors, edgecolor="none")
    axis_review.set_ylim(0, 5)
    axis_review.set_ylabel("Average review score (1–5)")
    axis_review.set_title("Customer reviews by delivery outcome", loc="left")
    for bar, value, count in zip(review_bars, outcome["avg_review_score"], outcome["orders"]):
        axis_review.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.1,
            f"{value:.2f}\n(n={count:,.0f})",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#1f2d38",
        )
    style_axis(axis_review)

    day_bars = axis_days.bar(outcome["delivery_outcome"], outcome["median_delivery_days"], color=colors, edgecolor="none")
    axis_days.set_ylabel("Median days from purchase")
    axis_days.set_title("Delivery time by outcome", loc="left")
    for bar, value in zip(day_bars, outcome["median_delivery_days"]):
        axis_days.text(
            bar.get_x() + bar.get_width() / 2,
            value + 0.6,
            f"{value:.1f}",
            ha="center",
            va="bottom",
            fontsize=10,
            color="#1f2d38",
        )
    style_axis(axis_days)


def plot_category_opportunities(axis: plt.Axes, delivered: pd.DataFrame, *, compact: bool = False) -> None:
    categories = (
        delivered.groupby("primary_category", as_index=False)
        .agg(
            delivered_orders=("order_id", "size"),
            late_rate=("was_late", "mean"),
            revenue=("merchandise_and_freight_total", "sum"),
        )
        .query("delivered_orders >= 500")
    )
    sizes = 35 + 550 * categories["revenue"] / categories["revenue"].max()
    axis.scatter(
        categories["delivered_orders"],
        100 * categories["late_rate"],
        s=sizes,
        color=BLUE,
        alpha=0.72,
        edgecolors="white",
        linewidths=0.8,
    )
    axis.axhline(100 * delivered["was_late"].mean(), color=ORANGE, linewidth=1.5, linestyle="--")
    axis.axvline(categories["delivered_orders"].median(), color="#9aa7b2", linewidth=1, linestyle=":")
    axis.set_xscale("log")
    axis.xaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
    axis.yaxis.set_major_formatter(mtick.PercentFormatter())
    axis.set_xlabel("Delivered orders (log scale)")
    axis.set_ylabel("Late-delivery rate")
    if not compact:
        axis.set_title("Category opportunity matrix", loc="left")
        axis.text(
            0.995,
            0.02,
            "Bubble area = merchandise + freight value; dashed line = overall late rate",
            transform=axis.transAxes,
            ha="right",
            va="bottom",
            fontsize=9,
            color=SLATE,
        )

    label_count = 4 if compact else 5
    late_label_count = 2 if compact else 4
    priorities = categories.nlargest(label_count, "revenue").index.union(
        categories.nlargest(late_label_count, "late_rate").index
    )
    for _, row in categories.loc[priorities].iterrows():
        label = row["primary_category"].replace("_", " ")
        axis.annotate(
            label,
            (row["delivered_orders"], 100 * row["late_rate"]),
            xytext=(5, 5),
            textcoords="offset points",
            fontsize=8 if compact else 9,
            color="#263945",
        )
    style_axis(axis)


def create_monthly_trend(monthly: pd.DataFrame) -> None:
    figure, (axis_volume, axis_rate) = plt.subplots(2, 1, figsize=(13, 8), sharex=True, height_ratios=[1, 1.15])
    figure.suptitle("Delivery reliability changed sharply during high-volume periods", x=0.01, ha="left", fontsize=16, fontweight="bold")

    axis_volume.bar(monthly["purchase_month"], monthly["delivered_orders"], width=20, color=SKY, edgecolor="none")
    axis_volume.set_ylabel("Delivered orders")
    axis_volume.set_title("Monthly delivered-order volume", loc="left")
    axis_volume.yaxis.set_major_formatter(mtick.StrMethodFormatter("{x:,.0f}"))
    style_axis(axis_volume)

    plot_monthly_on_time(axis_rate, monthly)
    axis_rate.set_title("Monthly on-time delivery rate", loc="left")
    low_month = monthly.loc[monthly["on_time_rate"].idxmin()]
    axis_rate.annotate(
        f"Low: {low_month['on_time_rate']:.1%}\n{low_month['purchase_month']:%b %Y}",
        xy=(low_month["purchase_month"], 100 * low_month["on_time_rate"]),
        xytext=(20, -32),
        textcoords="offset points",
        arrowprops={"arrowstyle": "-", "color": SLATE},
        fontsize=9,
        color=SLATE,
    )
    figure.text(0.01, 0.01, "On-time rate uses delivered orders with both actual and promised delivery dates.", color=SLATE, fontsize=9)
    figure.tight_layout(rect=(0, 0.03, 1, 0.94))
    save_figure(figure, "01_monthly_delivery_trend.png")


def create_state_chart(delivered: pd.DataFrame) -> None:
    figure, axis = plt.subplots(figsize=(12, 9))
    plot_state_late_rate(axis, delivered)
    figure.tight_layout()
    save_figure(figure, "02_state_late_delivery_rate.png")


def create_customer_experience_chart(delivered: pd.DataFrame) -> None:
    figure, (axis_review, axis_days) = plt.subplots(1, 2, figsize=(13, 5.5))
    figure.suptitle("Late deliveries align with a much weaker customer experience", x=0.01, ha="left", fontsize=16, fontweight="bold")
    plot_outcome_experience(axis_review, axis_days, delivered)
    figure.tight_layout(rect=(0, 0, 1, 0.9))
    save_figure(figure, "03_delivery_outcome_customer_experience.png")


def create_category_chart(delivered: pd.DataFrame) -> None:
    figure, axis = plt.subplots(figsize=(13, 7.5))
    plot_category_opportunities(axis, delivered)
    figure.tight_layout()
    save_figure(figure, "04_category_opportunity_matrix.png")


def create_dashboard(frame: pd.DataFrame, delivered: pd.DataFrame, monthly: pd.DataFrame) -> None:
    figure = plt.figure(figsize=(18, 14), facecolor="white")
    grid = figure.add_gridspec(3, 6, height_ratios=[0.78, 2.4, 2.4], hspace=0.55, wspace=0.45)

    figure.suptitle("Delivery Performance & Customer Experience", x=0.03, y=0.98, ha="left", fontsize=21, fontweight="bold", color="#16324f")
    figure.text(0.03, 0.955, "Olist e-commerce orders | Delivered-order KPIs use complete actual and promised dates", color=SLATE, fontsize=10)

    total_delivered = len(delivered)
    on_time_rate = 100 * delivered["was_on_time"].mean()
    median_days = delivered["delivery_days"].median()
    review_score = delivered["review_score"].mean()
    metrics = [
        ("Delivered orders", f"{total_delivered:,.0f}"),
        ("On-time delivery rate", f"{on_time_rate:.1f}%"),
        ("Median delivery time", f"{median_days:.1f} days"),
        ("Average review score", f"{review_score:.2f} / 5"),
    ]
    kpi_grid = grid[0, :].subgridspec(1, 4, wspace=0.45)
    for position, (label, value) in enumerate(metrics):
        axis = figure.add_subplot(kpi_grid[0, position])
        axis.axis("off")
        axis.text(0, 0.78, label, fontsize=10, color=SLATE, transform=axis.transAxes)
        axis.text(0, 0.2, value, fontsize=19, fontweight="bold", color="#16324f", transform=axis.transAxes)
        axis.plot([0, 1], [0.05, 0.05], transform=axis.transAxes, color=SKY, linewidth=4, solid_capstyle="round")

    axis_trend = figure.add_subplot(grid[1, :3])
    plot_monthly_on_time(axis_trend, monthly, compact=True)
    axis_trend.set_title("On-time delivery rate by purchase month", loc="left")

    axis_state = figure.add_subplot(grid[1, 3:])
    plot_state_late_rate(axis_state, delivered, compact=True)
    axis_state.set_title("Late-delivery rate by customer state", loc="left")

    axis_reviews = figure.add_subplot(grid[2, :3])
    outcome = (
        delivered.assign(outcome=np.where(delivered["was_on_time"].eq(1), "On time", "Late"))
        .groupby("outcome", as_index=False)
        .agg(avg_review_score=("review_score", "mean"))
        .set_index("outcome")
        .loc[["On time", "Late"]]
        .reset_index()
    )
    bars = axis_reviews.bar(outcome["outcome"], outcome["avg_review_score"], color=[TEAL, RED], edgecolor="none")
    axis_reviews.set_ylim(0, 5)
    axis_reviews.set_ylabel("Average review score (1–5)")
    axis_reviews.set_title("Customer reviews by delivery outcome", loc="left")
    for bar, value in zip(bars, outcome["avg_review_score"]):
        axis_reviews.text(bar.get_x() + bar.get_width() / 2, value + 0.1, f"{value:.2f}", ha="center", fontsize=11, fontweight="bold")
    style_axis(axis_reviews)

    axis_category = figure.add_subplot(grid[2, 3:])
    plot_category_opportunities(axis_category, delivered, compact=True)
    axis_category.set_title("Category opportunity matrix", loc="left")

    figure.text(0.03, 0.015, "Interpretation: start with high-volume states/categories above the overall late-rate reference, then assess feasible carrier, inventory, and customer-communication interventions.", color=SLATE, fontsize=9)
    save_figure(figure, "00_delivery_performance_dashboard.png")


def main() -> None:
    frame, delivered = load_data()
    monthly = monthly_kpis(delivered)
    create_monthly_trend(monthly)
    create_state_chart(delivered)
    create_customer_experience_chart(delivered)
    create_category_chart(delivered)
    create_dashboard(frame, delivered, monthly)
    print(f"Created 5 visualization files in {OUTPUT_DIR}")


if __name__ == "__main__":
    main()