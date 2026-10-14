from pathlib import Path
import json
import sys

import matplotlib.pyplot as plt
import pandas as pd

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw" / "nyc_payroll_public.csv"
PROCESSED = ROOT / "data" / "processed" / "payroll_clean.csv"
OUT = ROOT / "outputs"

NUMERIC = ["base_salary", "regular_hours", "regular_gross_paid", "overtime_hours", "overtime_pay", "other_pay"]
RENAME = {
    "agency_name": "agency", "work_location_borough": "borough", "title_description": "job_title",
    "leave_status_as_of_june_30": "leave_status", "ot_hours": "overtime_hours", "total_ot_paid": "overtime_pay",
    "total_other_pay": "other_pay",
}


def clean_payroll(frame: pd.DataFrame) -> pd.DataFrame:
    frame = frame.rename(columns=RENAME).copy()
    for col in NUMERIC:
        if col in frame:
            frame[col] = pd.to_numeric(frame[col].astype(str).str.replace(r"[$,]", "", regex=True), errors="coerce")
    frame["fiscal_year"] = pd.to_numeric(frame["fiscal_year"], errors="coerce").astype("Int64")
    for col in ["agency", "borough", "job_title", "leave_status", "pay_basis"]:
        frame[col] = frame[col].fillna("Unknown").astype(str).str.strip()
        frame.loc[frame[col].eq(""), col] = "Unknown"
    if "agency_start_date" in frame:
        frame["agency_start_date"] = pd.to_datetime(frame["agency_start_date"], errors="coerce")
    return frame


def write_quality(raw: pd.DataFrame, clean: pd.DataFrame) -> None:
    numeric_negative = sum(int((clean[c] < 0).sum()) for c in NUMERIC if c in clean)
    exact_duplicates = int(raw.duplicated().sum())
    report = pd.DataFrame([
        {"check": "source_rows", "value": len(raw), "status": "info"},
        {"check": "rows_after_type_normalization", "value": len(clean), "status": "info"},
        {"check": "fiscal_year_count", "value": int(clean["fiscal_year"].nunique(dropna=True)), "status": "info"},
        {"check": "exact_duplicate_rows", "value": exact_duplicates, "status": "review" if exact_duplicates else "pass"},
        {"check": "negative_numeric_pay_or_hour_values", "value": numeric_negative, "status": "review" if numeric_negative else "pass"},
        {"check": "missing_fiscal_year", "value": int(clean["fiscal_year"].isna().sum()), "status": "review" if clean["fiscal_year"].isna().any() else "pass"},
    ])
    report.to_csv(OUT / "data_quality_report.csv", index=False)
    missing = clean.isna().sum().rename("missing_rows").reset_index().rename(columns={"index": "column"})
    missing["missing_pct"] = (missing["missing_rows"] / max(len(clean), 1) * 100).round(2)
    missing.to_csv(OUT / "missingness_by_column.csv", index=False)


def main() -> None:
    if not RAW.is_file():
        sys.exit("Raw payroll data is missing. Run `python download_data.py` first.")
    OUT.mkdir(exist_ok=True)
    raw = pd.read_csv(RAW, low_memory=False)
    clean = clean_payroll(raw)
    PROCESSED.parent.mkdir(parents=True, exist_ok=True)
    clean.to_csv(PROCESSED, index=False)
    write_quality(raw, clean)

    clean["gross_pay_total"] = clean[["regular_gross_paid", "overtime_pay", "other_pay"]].fillna(0).sum(axis=1)
    clean["overtime_share_pct"] = (100 * clean["overtime_pay"] / clean["gross_pay_total"].where(clean["gross_pay_total"].ne(0))).replace([float("inf"), -float("inf")], pd.NA)
    annual_basis = clean["pay_basis"].str.contains(r"annual|annum|year", case=False, regex=True, na=False)

    annual = clean.groupby("fiscal_year", dropna=True).agg(
        employee_records=("agency", "size"),
        agencies=("agency", "nunique"),
        regular_pay_total=("regular_gross_paid", "sum"),
        overtime_pay_total=("overtime_pay", "sum"),
        other_pay_total=("other_pay", "sum"),
        overtime_hours_total=("overtime_hours", "sum"),
    ).reset_index()
    annual["total_gross_pay"] = annual[["regular_pay_total", "overtime_pay_total", "other_pay_total"]].sum(axis=1, min_count=1)
    annual["overtime_share_pct"] = (100 * annual["overtime_pay_total"] / annual["total_gross_pay"].where(annual["total_gross_pay"].ne(0))).round(2)
    avg_salary = clean.loc[annual_basis].groupby("fiscal_year")["base_salary"].mean().rename("mean_annual_basis_base_salary")
    annual = annual.merge(avg_salary, on="fiscal_year", how="left").sort_values("fiscal_year")
    annual.to_csv(OUT / "annual_kpis.csv", index=False)

    by_agency = clean.groupby(["fiscal_year", "agency"], dropna=False).agg(
        employee_records=("agency", "size"),
        regular_pay_total=("regular_gross_paid", "sum"),
        overtime_pay_total=("overtime_pay", "sum"),
        other_pay_total=("other_pay", "sum"),
        overtime_hours_total=("overtime_hours", "sum"),
    ).reset_index()
    by_agency["total_gross_pay"] = by_agency[["regular_pay_total", "overtime_pay_total", "other_pay_total"]].sum(axis=1, min_count=1)
    by_agency["overtime_share_pct"] = (100 * by_agency["overtime_pay_total"] / by_agency["total_gross_pay"].where(by_agency["total_gross_pay"].ne(0))).round(2)
    by_agency.sort_values(["fiscal_year", "total_gross_pay"], ascending=[True, False]).to_csv(OUT / "agency_compensation.csv", index=False)

    by_title = clean.groupby(["fiscal_year", "job_title"], dropna=False).agg(
        employee_records=("job_title", "size"),
        median_base_salary=("base_salary", "median"),
        mean_regular_pay=("regular_gross_paid", "mean"),
        overtime_pay_total=("overtime_pay", "sum"),
    ).reset_index()
    by_title.sort_values(["fiscal_year", "employee_records"], ascending=[True, False]).to_csv(OUT / "job_title_compensation.csv", index=False)

    borough = clean.groupby(["fiscal_year", "borough"], dropna=False).agg(
        employee_records=("borough", "size"),
        regular_pay_total=("regular_gross_paid", "sum"),
        overtime_pay_total=("overtime_pay", "sum"),
    ).reset_index()
    borough.to_csv(OUT / "borough_compensation.csv", index=False)

    if not annual.empty:
        fig, ax = plt.subplots(figsize=(10, 5))
        ax.plot(annual["fiscal_year"].astype(str), annual["total_gross_pay"], marker="o", label="Total gross pay")
        ax.plot(annual["fiscal_year"].astype(str), annual["overtime_pay_total"], marker="o", label="Overtime pay")
        ax.set(title="NYC Payroll: Fiscal-Year Compensation", xlabel="Fiscal year", ylabel="Reported pay (USD)")
        ax.legend()
        ax.grid(alpha=0.25)
        fig.tight_layout()
        fig.savefig(OUT / "payroll_trend.png", dpi=160)
        plt.close(fig)
        latest = by_agency[by_agency["fiscal_year"] == by_agency["fiscal_year"].max()].nlargest(15, "overtime_share_pct").sort_values("overtime_share_pct")
        fig, ax = plt.subplots(figsize=(10, 7))
        ax.barh(latest["agency"], latest["overtime_share_pct"])
        ax.set(title="Agencies with Highest Overtime Share (Latest Extracted FY)", xlabel="Overtime pay / gross pay (%)", ylabel="Agency")
        fig.tight_layout()
        fig.savefig(OUT / "overtime_share_by_agency.png", dpi=160)
        plt.close(fig)

    metadata = {
        "source": "NYC Open Data — Citywide Payroll Data (Fiscal Year)",
        "source_url": "https://data.cityofnewyork.us/City-Government/Citywide-Payroll-Data-Fiscal-Year-/k397-673e",
        "source_rows": len(raw), "processed_rows": len(clean),
        "fiscal_years": sorted(int(x) for x in clean["fiscal_year"].dropna().unique()),
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
        "privacy_note": "Downloader does not request employee names or personal identifiers.",
        "limitation": "Payroll records are not an attrition dataset and do not identify individual employee transitions across years.",
    }
    (OUT / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(f"Processed {len(clean):,} payroll rows. Outputs: {OUT}")


if __name__ == "__main__":
    main()
