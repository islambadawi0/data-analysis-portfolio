from pathlib import Path
import json
import re
import sqlite3
import sys

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
DB = ROOT / "sales.db"
SQL_FILE = ROOT / "sql" / "queries.sql"
OUT = ROOT / "outputs"
CHARTS = ROOT / "charts"


def load_queries() -> dict[str, str]:
    text = SQL_FILE.read_text(encoding="utf-8")
    parts = re.split(r"^-- name: ([a-zA-Z0-9_]+)\s*$", text, flags=re.MULTILINE)
    queries = {}
    for i in range(1, len(parts), 2):
        queries[parts[i]] = parts[i + 1].strip()
    if not queries:
        raise RuntimeError("No named SQL queries found in sql/queries.sql")
    return queries


def quality_checks(conn: sqlite3.Connection) -> pd.DataFrame:
    sql_checks = {
        "orders_rows": "SELECT COUNT(*) FROM orders",
        "duplicate_order_ids": "SELECT COUNT(*) FROM (SELECT order_id FROM orders GROUP BY order_id HAVING COUNT(*) > 1)",
        "null_order_ids": "SELECT COUNT(*) FROM orders WHERE order_id IS NULL OR TRIM(order_id) = ''",
        "orphan_order_items": "SELECT COUNT(*) FROM order_items i LEFT JOIN orders o ON i.order_id=o.order_id WHERE o.order_id IS NULL",
        "orphan_order_payments": "SELECT COUNT(*) FROM order_payments p LEFT JOIN orders o ON p.order_id=o.order_id WHERE o.order_id IS NULL",
        "negative_item_prices": "SELECT COUNT(*) FROM order_items WHERE price < 0",
        "negative_freight_values": "SELECT COUNT(*) FROM order_items WHERE freight_value < 0",
        "orders_without_items": "SELECT COUNT(*) FROM orders o LEFT JOIN order_items i ON o.order_id=i.order_id WHERE i.order_id IS NULL",
        "delivered_missing_delivery_timestamp": "SELECT COUNT(*) FROM orders WHERE order_status='delivered' AND order_delivered_customer_date IS NULL",
    }
    records = []
    for check, query in sql_checks.items():
        value = conn.execute(query).fetchone()[0]
        records.append({"check": check, "value": int(value), "status": "review" if value else "pass"})
    result = pd.DataFrame(records)
    result.to_csv(OUT / "data_quality_report.csv", index=False)
    return result


def make_charts(results: dict[str, pd.DataFrame]) -> None:
    monthly = results.get("monthly_sales")
    if monthly is not None and not monthly.empty:
        fig, ax = plt.subplots(figsize=(11, 5))
        ax.plot(monthly["purchase_month"], monthly["product_sales_brl"], marker="o", linewidth=2)
        ax.set(title="Delivered Product Sales by Purchase Month", xlabel="Purchase month", ylabel="Product sales (BRL)")
        ax.tick_params(axis="x", rotation=60)
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(CHARTS / "monthly_product_sales.png", dpi=160)
        plt.close(fig)
    category = results.get("category_performance")
    if category is not None and not category.empty:
        top = category.head(15).sort_values("product_sales_brl")
        fig, ax = plt.subplots(figsize=(10, 7))
        ax.barh(top["category"], top["product_sales_brl"])
        ax.set(title="Top Product Categories by Delivered Product Sales", xlabel="Product sales (BRL)", ylabel="Category")
        fig.tight_layout()
        fig.savefig(CHARTS / "category_sales.png", dpi=160)
        plt.close(fig)


def main() -> None:
    if not DB.is_file():
        sys.exit("Database is missing. Run `python download_data.py` and `python build_database.py` first.")
    OUT.mkdir(exist_ok=True)
    CHARTS.mkdir(exist_ok=True)
    results = {}
    with sqlite3.connect(DB) as conn:
        for name, query in load_queries().items():
            frame = pd.read_sql_query(query, conn)
            frame.to_csv(OUT / f"{name}.csv", index=False)
            results[name] = frame
            print(f"{name}: {len(frame):,} result rows")
        quality = quality_checks(conn)
    make_charts(results)
    metadata = {
        "source": "Olist Brazilian E-Commerce Public Dataset",
        "source_url": "https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce",
        "query_count": len(results),
        "quality_checks": quality.to_dict(orient="records"),
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "scope_note": "Sales figures use delivered orders. Product sales sum order-item prices; freight is reported separately. These are not profit figures.",
    }
    (OUT / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Outputs written to {OUT}")


if __name__ == "__main__":
    main()
