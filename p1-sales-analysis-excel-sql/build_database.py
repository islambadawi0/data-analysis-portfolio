from pathlib import Path
import sqlite3
import sys

import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
DB = ROOT / "sales.db"
TABLES = {
    "olist_orders_dataset.csv": "orders",
    "olist_order_items_dataset.csv": "order_items",
    "olist_order_payments_dataset.csv": "order_payments",
    "olist_customers_dataset.csv": "customers",
    "olist_products_dataset.csv": "products",
    "olist_sellers_dataset.csv": "sellers",
    "olist_order_reviews_dataset.csv": "order_reviews",
    "product_category_name_translation.csv": "category_translation",
}


def main() -> None:
    missing = [f for f in TABLES if not (RAW / f).is_file()]
    if missing:
        sys.exit("Source files missing. Run `python download_data.py` first. Missing: " + ", ".join(missing))
    if DB.exists():
        DB.unlink()
    with sqlite3.connect(DB) as conn:
        for filename, table in TABLES.items():
            frame = pd.read_csv(RAW / filename, low_memory=False)
            frame.to_sql(table, conn, index=False, if_exists="replace", chunksize=20_000)
            print(f"Loaded {table}: {len(frame):,} rows, {len(frame.columns)} columns")
        conn.executescript("""
        CREATE INDEX idx_orders_order_id ON orders(order_id);
        CREATE INDEX idx_orders_customer_id ON orders(customer_id);
        CREATE INDEX idx_orders_purchase_ts ON orders(order_purchase_timestamp);
        CREATE INDEX idx_order_items_order_id ON order_items(order_id);
        CREATE INDEX idx_order_items_product_id ON order_items(product_id);
        CREATE INDEX idx_order_payments_order_id ON order_payments(order_id);
        CREATE INDEX idx_customers_customer_id ON customers(customer_id);
        CREATE INDEX idx_customers_unique_id ON customers(customer_unique_id);
        CREATE INDEX idx_products_product_id ON products(product_id);
        CREATE INDEX idx_reviews_order_id ON order_reviews(order_id);
        CREATE INDEX idx_translation_category ON category_translation(product_category_name);
        PRAGMA optimize;
        """)
    print(f"Database created: {DB}")


if __name__ == "__main__":
    main()
