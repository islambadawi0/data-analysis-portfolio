from pathlib import Path
import sys
import time

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

ROOT = Path(__file__).resolve().parent
RAW = ROOT / "data" / "raw" / "nyc_payroll_public.csv"
BASE = "https://data.cityofnewyork.us/resource/k397-673e.json"
FIELDS = [
    "fiscal_year", "agency_name", "agency_start_date", "work_location_borough",
    "title_description", "leave_status_as_of_june_30", "base_salary", "pay_basis",
    "regular_hours", "regular_gross_paid", "ot_hours", "total_ot_paid", "total_other_pay",
]


def make_session() -> requests.Session:
    session = requests.Session()
    retry = Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504], allowed_methods=["GET"])
    session.mount("https://", HTTPAdapter(max_retries=retry))
    session.headers.update({"User-Agent": "public-workforce-analytics-portfolio/1.0"})
    return session


def get_json(session: requests.Session, params: dict) -> list[dict]:
    response = session.get(BASE, params=params, timeout=90)
    response.raise_for_status()
    return response.json()


def main() -> None:
    RAW.parent.mkdir(parents=True, exist_ok=True)
    temp_raw = RAW.with_suffix(RAW.suffix + ".tmp")
    temp_raw.unlink(missing_ok=True)
    session = make_session()
    try:
        latest_record = get_json(session, {"$select": "max(fiscal_year) as latest_year"})
        latest_year = int(float(latest_record[0]["latest_year"]))
        first_year = latest_year - 2
        offset, limit, row_count = 0, 50_000, 0
        while True:
            page = get_json(session, {
                "$select": ",".join(FIELDS),
                "$where": f"fiscal_year >= {first_year} AND fiscal_year <= {latest_year}",
                "$order": ":id",
                "$limit": limit,
                "$offset": offset,
            })
            if not page:
                break
            missing = set(FIELDS) - set(page[0])
            if missing:
                sys.exit("The API schema changed; missing expected fields: " + ", ".join(sorted(missing)))
            pd.DataFrame(page, columns=FIELDS).to_csv(temp_raw, index=False, mode="w" if offset == 0 else "a", header=(offset == 0))
            row_count += len(page)
            print(f"Fetched {row_count:,} rows across FY{first_year}–FY{latest_year}", end="\r")
            if len(page) < limit:
                break
            offset += limit
            time.sleep(0.1)
    except (requests.RequestException, KeyError, ValueError, IndexError) as exc:
        temp_raw.unlink(missing_ok=True)
        sys.exit(f"NYC Open Data download failed: {exc}. Check network access and dataset API status, then retry.")
    if row_count == 0:
        temp_raw.unlink(missing_ok=True)
        sys.exit("The API returned no payroll records for the selected fiscal years.")
    temp_raw.replace(RAW)
    print(f"\nSaved {row_count:,} public payroll records to {RAW}")
    print(f"Fiscal years: {first_year}–{latest_year}; employee names and personal identifiers were not requested.")
    print("Source: https://data.cityofnewyork.us/City-Government/Citywide-Payroll-Data-Fiscal-Year-/k397-673e")


if __name__ == "__main__":
    main()
