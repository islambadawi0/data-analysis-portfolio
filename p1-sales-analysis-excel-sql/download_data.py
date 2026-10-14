from pathlib import Path
import shutil
import subprocess
import sys

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
REQUIRED = {
    "olist_orders_dataset.csv",
    "olist_order_items_dataset.csv",
    "olist_order_payments_dataset.csv",
    "olist_customers_dataset.csv",
    "olist_products_dataset.csv",
    "olist_sellers_dataset.csv",
    "olist_order_reviews_dataset.csv",
    "product_category_name_translation.csv",
}


def main() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    missing = [name for name in REQUIRED if not (RAW / name).exists()]
    if missing:
        if shutil.which("kaggle") is None:
            sys.exit("Kaggle CLI is not installed. Run `pip install kaggle`, configure your Kaggle API token locally, then rerun this script.")
        subprocess.run(
            ["kaggle", "datasets", "download", "-d", "olistbr/brazilian-ecommerce", "-p", str(RAW), "--unzip"],
            check=True,
        )
    missing = [name for name in REQUIRED if not (RAW / name).is_file()]
    if missing:
        sys.exit("Dataset download is incomplete. Missing: " + ", ".join(sorted(missing)))
    print(f"Verified {len(REQUIRED)} Olist source files in {RAW}")
    print("Source: https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce")


if __name__ == "__main__":
    main()
