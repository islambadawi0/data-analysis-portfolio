from pathlib import Path
import json
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw"
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
TXN_COLUMNS = [
    "msno", "payment_method_id", "payment_plan_days", "plan_list_price", "actual_amount_paid",
    "is_auto_renew", "transaction_date", "membership_expire_date", "is_cancel",
]
MEMBER_COLUMNS = ["msno", "city", "registered_via", "registration_init_time"]
COHORTS = [
    {"name": "train_v1", "labels": "train.csv", "transactions": "transactions.csv", "cutoff": "20170131"},
    {"name": "test_v2", "labels": "train_v2.csv", "transactions": "transactions.csv", "cutoff": "20170228"},
]
CHUNK_SIZE = 500_000


def require_file(name: str) -> Path:
    path = RAW / name
    if not path.is_file():
        sys.exit(f"Missing {path}. Run `python download_data.py` first.")
    return path


def read_labels(filename: str) -> pd.DataFrame:
    frame = pd.read_csv(require_file(filename), dtype={"msno": "string"})
    missing = {"msno", "is_churn"} - set(frame.columns)
    if missing:
        raise ValueError(f"Unexpected label schema in {filename}; missing columns: {sorted(missing)}")
    frame = frame[["msno", "is_churn"]].dropna(subset=["msno", "is_churn"]).copy()
    frame["msno"] = frame["msno"].astype(str)
    frame["is_churn"] = pd.to_numeric(frame["is_churn"], errors="raise").astype(int)
    if frame["msno"].duplicated().any():
        raise ValueError(f"Duplicate member labels found in {filename}")
    if not set(frame["is_churn"].unique()).issubset({0, 1}):
        raise ValueError(f"Unexpected target values in {filename}")
    return frame


def aggregate_transactions(filename: str, member_ids: set[str], cutoff_text: str) -> pd.DataFrame:
    path = require_file(filename)
    cutoff = pd.to_datetime(cutoff_text, format="%Y%m%d")
    cutoff_int = int(cutoff_text)
    chunk_aggregates = []
    latest_transactions = []

    for chunk in pd.read_csv(path, usecols=TXN_COLUMNS, dtype={"msno": "string"}, chunksize=CHUNK_SIZE, low_memory=False):
        chunk = chunk.loc[chunk["msno"].astype(str).isin(member_ids)].copy()
        if chunk.empty:
            continue
        chunk["transaction_date_num"] = pd.to_numeric(chunk["transaction_date"], errors="coerce")
        chunk = chunk.loc[chunk["transaction_date_num"].le(cutoff_int)].copy()
        if chunk.empty:
            continue
        chunk["transaction_dt"] = pd.to_datetime(chunk["transaction_date_num"].astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
        chunk["expire_dt"] = pd.to_datetime(pd.to_numeric(chunk["membership_expire_date"], errors="coerce").astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
        for col in ["payment_method_id", "payment_plan_days", "plan_list_price", "actual_amount_paid", "is_auto_renew", "is_cancel"]:
            chunk[col] = pd.to_numeric(chunk[col], errors="coerce")
        chunk["discount_ratio"] = np.where(
            chunk["plan_list_price"].gt(0),
            (chunk["plan_list_price"] - chunk["actual_amount_paid"]) / chunk["plan_list_price"],
            np.nan,
        )
        reference_time = cutoff + pd.Timedelta(days=1)
        chunk["days_from_cutoff"] = (reference_time - chunk["transaction_dt"]).dt.days
        chunk["transaction_in_last_30d"] = chunk["days_from_cutoff"].between(0, 29).astype(int)
        chunk["transaction_in_last_90d"] = chunk["days_from_cutoff"].between(0, 89).astype(int)
        grouped = chunk.groupby("msno", dropna=False).agg(
            txn_count=("msno", "size"),
            paid_sum=("actual_amount_paid", "sum"), paid_count=("actual_amount_paid", "count"),
            plan_days_sum=("payment_plan_days", "sum"), plan_days_count=("payment_plan_days", "count"),
            listed_price_sum=("plan_list_price", "sum"), listed_price_count=("plan_list_price", "count"),
            auto_renew_sum=("is_auto_renew", "sum"), auto_renew_count=("is_auto_renew", "count"),
            cancel_sum=("is_cancel", "sum"), cancel_count=("is_cancel", "count"),
            discount_ratio_sum=("discount_ratio", "sum"), discount_ratio_count=("discount_ratio", "count"),
            txn_count_30d=("transaction_in_last_30d", "sum"), txn_count_90d=("transaction_in_last_90d", "sum"),
        ).reset_index()
        chunk_aggregates.append(grouped)
        latest_transactions.append(chunk.sort_values("transaction_dt").drop_duplicates("msno", keep="last")[
            ["msno", "transaction_dt", "expire_dt", "payment_method_id", "payment_plan_days", "plan_list_price", "actual_amount_paid", "is_auto_renew", "is_cancel"]
        ])

    if not chunk_aggregates:
        return pd.DataFrame({"msno": sorted(member_ids)})

    sums = pd.concat(chunk_aggregates, ignore_index=True).groupby("msno", as_index=False).sum(numeric_only=True)
    sums["mean_amount_paid"] = sums["paid_sum"] / sums["paid_count"].replace(0, np.nan)
    sums["mean_plan_days"] = sums["plan_days_sum"] / sums["plan_days_count"].replace(0, np.nan)
    sums["mean_plan_list_price"] = sums["listed_price_sum"] / sums["listed_price_count"].replace(0, np.nan)
    sums["auto_renew_rate"] = sums["auto_renew_sum"] / sums["auto_renew_count"].replace(0, np.nan)
    sums["cancel_rate"] = sums["cancel_sum"] / sums["cancel_count"].replace(0, np.nan)
    sums["mean_discount_ratio"] = sums["discount_ratio_sum"] / sums["discount_ratio_count"].replace(0, np.nan)

    latest = pd.concat(latest_transactions, ignore_index=True).sort_values("transaction_dt").drop_duplicates("msno", keep="last")
    reference_time = cutoff + pd.Timedelta(days=1)
    latest["days_since_last_transaction"] = (reference_time - latest["transaction_dt"]).dt.days
    latest["days_until_latest_expiry"] = (latest["expire_dt"] - reference_time).dt.days
    latest = latest.rename(columns={
        "payment_method_id": "last_payment_method_id", "payment_plan_days": "last_payment_plan_days",
        "plan_list_price": "last_plan_list_price", "actual_amount_paid": "last_amount_paid",
        "is_auto_renew": "last_is_auto_renew", "is_cancel": "last_is_cancel",
    })
    latest = latest[[
        "msno", "days_since_last_transaction", "days_until_latest_expiry", "last_payment_method_id",
        "last_payment_plan_days", "last_plan_list_price", "last_amount_paid", "last_is_auto_renew", "last_is_cancel",
    ]]
    sums = sums.merge(latest, on="msno", how="left")
    sums = sums.drop(columns=[c for c in ["paid_sum", "paid_count", "plan_days_sum", "plan_days_count", "listed_price_sum", "listed_price_count", "auto_renew_sum", "auto_renew_count", "cancel_sum", "cancel_count", "discount_ratio_sum", "discount_ratio_count"] if c in sums])
    return sums


def load_member_features(member_ids: set[str], cutoff_text: str) -> pd.DataFrame:
    path = require_file("members_v3.csv")
    parts = []
    for chunk in pd.read_csv(path, usecols=MEMBER_COLUMNS, dtype={"msno": "string"}, chunksize=CHUNK_SIZE, low_memory=False):
        matches = chunk.loc[chunk["msno"].astype(str).isin(member_ids)].copy()
        if not matches.empty:
            parts.append(matches)
    if not parts:
        return pd.DataFrame({"msno": sorted(member_ids)})
    members = pd.concat(parts, ignore_index=True).drop_duplicates("msno", keep="last")
    members["city"] = members["city"].astype("string")
    members["registered_via"] = members["registered_via"].astype("string")
    members["registration_dt"] = pd.to_datetime(pd.to_numeric(members["registration_init_time"], errors="coerce").astype("Int64").astype(str), format="%Y%m%d", errors="coerce")
    reference = pd.to_datetime(cutoff_text, format="%Y%m%d") + pd.Timedelta(days=1)
    members["membership_tenure_days"] = (reference - members["registration_dt"]).dt.days
    members = members.rename(columns={"city": "city_code", "registered_via": "registration_channel"})
    return members[["msno", "city_code", "registration_channel", "membership_tenure_days"]]


def build_cohort(config: dict, member_cache: pd.DataFrame | None = None) -> tuple[pd.DataFrame, dict]:
    labels = read_labels(config["labels"])
    ids = set(labels["msno"])
    txn = aggregate_transactions(config["transactions"], ids, config["cutoff"])
    if member_cache is None:
        member_cache = load_member_features(ids, config["cutoff"])
    features = labels.merge(txn, on="msno", how="left").merge(member_cache, on="msno", how="left")
    features["cohort"] = config["name"]
    features["snapshot_date"] = pd.to_datetime(config["cutoff"], format="%Y%m%d")
    stats = {
        "cohort": config["name"], "label_rows": len(labels),
        "unique_members": int(labels["msno"].nunique()),
        "churn_rate": float(labels["is_churn"].mean()),
        "snapshot_date": config["cutoff"],
        "members_without_transaction_features": int(features["txn_count"].isna().sum()) if "txn_count" in features else len(features),
        "features_with_member_profile": int(features["membership_tenure_days"].notna().sum()),
    }
    return features, stats


def main() -> None:
    PROCESSED.mkdir(parents=True, exist_ok=True)
    OUT.mkdir(parents=True, exist_ok=True)
    for filename in ["train.csv", "train_v2.csv", "transactions.csv", "transactions_v2.csv", "members_v3.csv"]:
        require_file(filename)

    frames, cohort_stats = [], []
    for config in COHORTS:
        features, stats = build_cohort(config)
        frames.append(features)
        cohort_stats.append(stats)
        out_file = PROCESSED / f"{config['name']}_features.csv"
        features.to_csv(out_file, index=False)
        print(f"{config['name']}: {len(features):,} member rows, churn rate {stats['churn_rate']:.3%}; saved {out_file}")

    report = {
        "source": "KKBox's Churn Prediction Challenge (Kaggle)",
        "source_url": "https://www.kaggle.com/competitions/kkbox-churn-prediction-challenge/data",
        "cohorts": cohort_stats,
        "feature_cutoffs": {"train_v1": "2017-01-31; transaction records on/before this date only", "test_v2": "2017-02-28; transaction records on/before this date only"},
        "target_definition": "Use source-provided is_churn labels: 1 indicates a member did not continue the subscription within 30 days after the relevant membership expiry; 0 indicates renewal.",
        "excluded_feature_groups": ["User listening logs are not downloaded in this portfolio release to control data volume; membership and transaction history are used."],
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    (OUT / "data_quality_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    pd.DataFrame(cohort_stats).to_csv(OUT / "cohort_summary.csv", index=False)
    pd.DataFrame([{
        "cohort": c["cohort"], "feature": col,
        "missing_rows": int(f[col].isna().sum()), "missing_pct": round(100 * f[col].isna().mean(), 2),
    } for c, f in zip(cohort_stats, frames) for col in frames[0].columns if col not in {"msno", "is_churn", "cohort", "snapshot_date"}]).to_csv(OUT / "feature_missingness.csv", index=False)


if __name__ == "__main__":
    main()
