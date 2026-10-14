from pathlib import Path
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "raw" / "nyc_payroll_public.csv"


def test_processed_payroll_has_no_name_columns():
    path = ROOT / "data" / "processed" / "payroll_clean.csv"
    if not path.exists():
        pytest.skip("Run download_data.py and analysis.py first.")
    columns = {c.lower() for c in pd.read_csv(path, nrows=1).columns}
    assert "first_name" not in columns
    assert "last_name" not in columns
    assert "employee_id" not in columns


def test_gross_pay_components_are_documented():
    assert "gross_pay_total" in (ROOT / "analysis.py").read_text(encoding="utf-8")
    assert "Reported Gross Pay" in (ROOT / "powerbi" / "measures.dax").read_text(encoding="utf-8")
