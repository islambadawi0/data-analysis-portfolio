from pathlib import Path
import sqlite3
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]
DB = ROOT / "sales.db"


@pytest.fixture(scope="module")
def conn():
    if not DB.exists():
        pytest.skip("Run download_data.py and build_database.py before the integration tests.")
    connection = sqlite3.connect(DB)
    yield connection
    connection.close()


def test_order_ids_are_unique(conn):
    duplicates = conn.execute("SELECT COUNT(*) FROM (SELECT order_id FROM orders GROUP BY order_id HAVING COUNT(*) > 1)").fetchone()[0]
    assert duplicates == 0


def test_no_orphan_order_items(conn):
    orphans = conn.execute("SELECT COUNT(*) FROM order_items i LEFT JOIN orders o ON i.order_id=o.order_id WHERE o.order_id IS NULL").fetchone()[0]
    assert orphans == 0


def test_item_prices_are_nonnegative(conn):
    negatives = conn.execute("SELECT COUNT(*) FROM order_items WHERE price < 0").fetchone()[0]
    assert negatives == 0
