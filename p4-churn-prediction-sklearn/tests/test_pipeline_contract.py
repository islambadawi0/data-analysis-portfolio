from pathlib import Path
import sys
import pandas as pd
import pytest

ROOT = Path(__file__).resolve().parents[1]
PROCESSED = ROOT / "data" / "processed"


def test_training_script_excludes_identifier_and_target():
    script = (ROOT / "train.py").read_text(encoding="utf-8")
    assert 'METADATA = {"msno", "cohort", "snapshot_date", TARGET}' in script
    assert 'TARGET = "is_churn"' in script


def test_temporal_cohorts_use_different_feature_cutoffs():
    builder = (ROOT / "build_features.py").read_text(encoding="utf-8")
    assert '"cutoff": "20170131"' in builder
    assert '"cutoff": "20170228"' in builder


def test_feature_tables_match_when_created():
    train_file = PROCESSED / "train_v1_features.csv"
    test_file = PROCESSED / "test_v2_features.csv"
    if not train_file.exists() or not test_file.exists():
        pytest.skip("Run the Kaggle download and feature-building pipeline first.")
    train = pd.read_csv(train_file, nrows=10)
    test = pd.read_csv(test_file, nrows=10)
    assert set(train.columns) == set(test.columns)
    assert {"msno", "is_churn", "cohort", "snapshot_date"}.issubset(train.columns)
