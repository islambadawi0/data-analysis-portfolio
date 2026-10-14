import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import pandas as pd
from eda import clean_data


def test_cleaning_flags_outliers_without_removing_them():
    raw = pd.DataFrame({
        "id": [1, 2, 3, 4],
        "price": [5000, 6000, 7000, 200000],
        "year": [2018, 2019, 2020, 2018],
        "odometer": [10000, 20000, 30000, 40000],
        "manufacturer": ["x", "x", "x", "x"],
        "posting_date": ["2021-01-01T00:00:00Z"] * 4,
    })
    clean, ledger, missing = clean_data(raw)
    assert len(clean) == 4
    assert "price_iqr_outlier_by_manufacturer" in clean
    assert ledger.iloc[0]["rows_before"] == 4
