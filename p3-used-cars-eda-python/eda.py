from pathlib import Path
import json
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns

ROOT = Path(__file__).resolve().parent
RAW_FILE = ROOT / "data" / "raw" / "vehicles.csv"
CLEAN_FILE = ROOT / "data" / "processed" / "vehicles_clean.csv"
OUT = ROOT / "outputs"
CHARTS = ROOT / "charts"
USECOLS = {
    "id", "price", "year", "manufacturer", "model", "condition", "cylinders", "fuel",
    "odometer", "title_status", "transmission", "drive", "type", "paint_color", "state", "posting_date",
}


def read_source() -> pd.DataFrame:
    if not RAW_FILE.is_file():
        sys.exit("Real dataset is missing. Run `python download_data.py` first.")
    frame = pd.read_csv(RAW_FILE, usecols=lambda c: c in USECOLS, low_memory=False)
    required = {"price", "year", "odometer", "posting_date"}
    if not required.issubset(frame.columns):
        raise ValueError(f"Unexpected source schema; missing required columns: {sorted(required - set(frame.columns))}")
    return frame


def clean_data(raw: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    frame = raw.copy()
    initial_rows = len(frame)
    reports = [{"stage": "source_loaded", "rows_before": initial_rows, "rows_after": initial_rows, "rows_removed": 0, "rule": "Source row count before cleaning"}]
    duplicates_before = len(frame)
    if "posting_date" in frame:
        frame["posting_date"] = pd.to_datetime(frame["posting_date"], errors="coerce", utc=True)
    for col in ["price", "year", "odometer"]:
        frame[col] = pd.to_numeric(frame[col], errors="coerce")
    if "id" in frame:
        frame = frame.sort_values("posting_date", na_position="first").drop_duplicates(subset=["id"], keep="last")
    else:
        frame = frame.drop_duplicates()
    reports.append({"stage": "deduplicated", "rows_before": duplicates_before, "rows_after": len(frame), "rows_removed": duplicates_before - len(frame), "rule": "Keep the latest posting per source listing ID"})

    if "posting_date" in frame:
        frame["listing_year"] = frame["posting_date"].dt.year
        fallback_listing_year = int(frame["listing_year"].dropna().max()) if frame["listing_year"].notna().any() else int(frame["year"].dropna().max())
        frame["listing_year"] = frame["listing_year"].fillna(fallback_listing_year)
    else:
        frame["listing_year"] = int(frame["year"].dropna().max())
    price_valid = frame["price"].between(500, 250_000, inclusive="both")
    year_valid = frame["year"].between(1980, frame["listing_year"] + 1, inclusive="both")
    keep = price_valid & year_valid
    before = len(frame)
    frame = frame.loc[keep].copy()
    reports.append({"stage": "scope_valid_price_year", "rows_before": before, "rows_after": len(frame), "rows_removed": before - len(frame), "rule": "Keep listed price $500–$250,000 and vehicle year 1980 through listing year + 1; chosen business scope, review sensitivity before conclusions"})

    before = len(frame)
    bad_odometer = frame["odometer"].notna() & ~frame["odometer"].between(0, 1_000_000, inclusive="both")
    frame.loc[bad_odometer, "odometer"] = np.nan
    reports.append({"stage": "odometer_domain_review", "rows_before": before, "rows_after": len(frame), "rows_removed": 0, "rule": f"{int(bad_odometer.sum())} values outside 0–1,000,000 miles set to missing, records retained"})

    for col in ["manufacturer", "model", "condition", "cylinders", "fuel", "title_status", "transmission", "drive", "type", "paint_color", "state"]:
        if col in frame:
            frame[col] = frame[col].fillna("Unknown").astype(str).str.strip().replace("", "Unknown")
    frame["vehicle_age_at_listing"] = (frame["listing_year"] - frame["year"]).clip(lower=0)
    frame["miles_per_year"] = frame["odometer"] / frame["vehicle_age_at_listing"].replace(0, np.nan)
    frame["log_price"] = np.log1p(frame["price"])
    if "manufacturer" in frame:
        frame["price_iqr_outlier_by_manufacturer"] = False
        for manufacturer, idx in frame.groupby("manufacturer").groups.items():
            vals = frame.loc[idx, "price"].dropna()
            if len(vals) >= 50:
                q1, q3 = vals.quantile([0.25, 0.75])
                spread = q3 - q1
                frame.loc[idx, "price_iqr_outlier_by_manufacturer"] = (frame.loc[idx, "price"] < q1 - 1.5 * spread) | (frame.loc[idx, "price"] > q3 + 1.5 * spread)
    reports.append({"stage": "features_created", "rows_before": len(frame), "rows_after": len(frame), "rows_removed": 0, "rule": "Added vehicle age at listing, miles/year, log price, and an IQR outlier flag; flagged outliers are retained"})

    missing = raw.isna().sum().rename("missing_rows").reset_index().rename(columns={"index": "column"})
    missing["missing_pct"] = (missing["missing_rows"] / max(len(raw), 1) * 100).round(2)
    return frame, pd.DataFrame(reports), missing


def create_charts(frame: pd.DataFrame) -> None:
    sns.set_theme(context="notebook", style="whitegrid")
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.histplot(data=frame, x="price", bins=70, ax=ax)
    ax.set_xscale("log")
    ax.set(title="Used Vehicle Listing Prices (Log X-Axis)", xlabel="Asking price (USD, log scale)", ylabel="Listings")
    fig.tight_layout()
    fig.savefig(CHARTS / "price_distribution.png", dpi=160)
    plt.close(fig)

    age_summary = frame.groupby("vehicle_age_at_listing").agg(median_price=("price", "median"), listings=("price", "size")).query("listings >= 30").reset_index()
    fig, ax = plt.subplots(figsize=(10, 5))
    sns.lineplot(data=age_summary, x="vehicle_age_at_listing", y="median_price", ax=ax)
    ax.set(title="Median Asking Price by Vehicle Age at Listing", xlabel="Vehicle age (years)", ylabel="Median asking price (USD)")
    fig.tight_layout()
    fig.savefig(CHARTS / "price_by_age.png", dpi=160)
    plt.close(fig)

    if "manufacturer" in frame:
        makes = frame.groupby("manufacturer").agg(median_price=("price", "median"), listings=("price", "size")).query("listings >= 100").nlargest(15, "median_price").sort_values("median_price")
        fig, ax = plt.subplots(figsize=(10, 7))
        ax.barh(makes.index, makes["median_price"])
        ax.set(title="Highest Median Asking Prices by Manufacturer (n ≥ 100)", xlabel="Median asking price (USD)", ylabel="Manufacturer")
        fig.tight_layout()
        fig.savefig(CHARTS / "price_by_manufacturer.png", dpi=160)
        plt.close(fig)

    scatter = frame[["odometer", "price"]].dropna()
    if len(scatter) > 20_000:
        scatter = scatter.sample(20_000, random_state=42)
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.scatter(scatter["odometer"], scatter["price"], alpha=0.2, s=8)
    ax.set(title="Asking Price vs Odometer", xlabel="Odometer (miles)", ylabel="Asking price (USD)")
    fig.tight_layout()
    fig.savefig(CHARTS / "price_vs_odometer.png", dpi=160)
    plt.close(fig)


def main() -> None:
    OUT.mkdir(exist_ok=True)
    CHARTS.mkdir(exist_ok=True)
    PROCESSED = CLEAN_FILE.parent
    PROCESSED.mkdir(parents=True, exist_ok=True)
    raw = read_source()
    clean, ledger, missingness = clean_data(raw)
    clean.to_csv(CLEAN_FILE, index=False)
    ledger.to_csv(OUT / "cleaning_ledger.csv", index=False)
    missingness.to_csv(OUT / "raw_missingness.csv", index=False)
    quality = pd.DataFrame([
        {"metric": "raw_rows", "value": len(raw)},
        {"metric": "clean_rows", "value": len(clean)},
        {"metric": "rows_removed", "value": len(raw) - len(clean)},
        {"metric": "distinct_manufacturers", "value": int(clean["manufacturer"].nunique()) if "manufacturer" in clean else None},
        {"metric": "price_iqr_outlier_flagged", "value": int(clean["price_iqr_outlier_by_manufacturer"].sum()) if "price_iqr_outlier_by_manufacturer" in clean else None},
        {"metric": "missing_odometer_after_domain_checks", "value": int(clean["odometer"].isna().sum())},
    ])
    quality.to_csv(OUT / "quality_summary.csv", index=False)
    create_charts(clean)
    metadata = {
        "source": "Craigslist Cars & Trucks public dataset on Kaggle",
        "source_url": "https://www.kaggle.com/datasets/austinreese/craigslist-carstrucks-data",
        "raw_rows_loaded": len(raw), "clean_rows": len(clean),
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "price_scope_usd": [500, 250000], "vehicle_year_min": 1980,
        "outlier_policy": "Statistical outliers are flagged, not automatically removed.",
        "interpretation": "Asking prices are listing values, not confirmed transaction prices.",
    }
    (OUT / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Loaded {len(raw):,} real source rows; retained {len(clean):,} after documented scope rules.")
    print(f"Processed data: {CLEAN_FILE}; output reports: {OUT}; charts: {CHARTS}")


if __name__ == "__main__":
    main()
