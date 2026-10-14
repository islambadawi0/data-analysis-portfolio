from pathlib import Path
import json
import sys

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    average_precision_score, classification_report, confusion_matrix, f1_score,
    log_loss, precision_recall_curve, precision_score, recall_score, roc_auc_score, roc_curve,
)
from sklearn.model_selection import GridSearchCV, StratifiedKFold, train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler

ROOT = Path(__file__).resolve().parent
PROCESSED = ROOT / "data" / "processed"
OUT = ROOT / "outputs"
CHARTS = ROOT / "charts"
MODELS = ROOT / "models"
TARGET = "is_churn"
METADATA = {"msno", "cohort", "snapshot_date", TARGET}
CATEGORICAL_CANDIDATES = [
    "city_code", "registration_channel", "last_payment_method_id", "last_is_auto_renew", "last_is_cancel",
]
MAX_TUNING_ROWS = 100_000


def load_cohort(path: Path) -> pd.DataFrame:
    if not path.is_file():
        sys.exit(f"Missing feature table: {path}. Run `python download_data.py` and `python build_features.py` first.")
    frame = pd.read_csv(path, dtype={"msno": "string", "city_code": "string", "registration_channel": "string"})
    frame["snapshot_date"] = pd.to_datetime(frame["snapshot_date"], errors="coerce")
    frame[TARGET] = pd.to_numeric(frame[TARGET], errors="raise").astype(int)
    if frame["msno"].duplicated().any():
        raise ValueError(f"Duplicate member rows in {path.name}")
    if frame[TARGET].nunique() != 2:
        raise ValueError(f"Both churn classes must be present in {path.name}")
    return frame


def make_pipeline(numeric: list[str], categorical: list[str], estimator) -> Pipeline:
    numeric_pipe = Pipeline([("imputer", SimpleImputer(strategy="median", add_indicator=True)), ("scaler", StandardScaler())])
    categorical_pipe = Pipeline([("imputer", SimpleImputer(strategy="most_frequent")), ("onehot", OneHotEncoder(handle_unknown="ignore", min_frequency=50))])
    prep = ColumnTransformer([
        ("numeric", numeric_pipe, numeric),
        ("categorical", categorical_pipe, categorical),
    ], remainder="drop")
    return Pipeline([("preprocess", prep), ("model", estimator)])


def metrics_for(name: str, y_true, probability) -> dict:
    probability = np.clip(np.asarray(probability, dtype=float), 1e-7, 1 - 1e-7)
    prediction = (probability >= 0.5).astype(int)
    return {
        "model": name,
        "roc_auc": roc_auc_score(y_true, probability),
        "average_precision_pr_auc": average_precision_score(y_true, probability),
        "log_loss": log_loss(y_true, probability, labels=[0, 1]),
        "precision_at_0_5": precision_score(y_true, prediction, zero_division=0),
        "recall_at_0_5": recall_score(y_true, prediction, zero_division=0),
        "f1_at_0_5": f1_score(y_true, prediction, zero_division=0),
    }


def main() -> None:
    OUT.mkdir(exist_ok=True)
    CHARTS.mkdir(exist_ok=True)
    MODELS.mkdir(exist_ok=True)
    train = load_cohort(PROCESSED / "train_v1_features.csv")
    test = load_cohort(PROCESSED / "test_v2_features.csv")

    feature_columns = [c for c in train.columns if c not in METADATA]
    absent = set(feature_columns) - set(test.columns)
    if absent:
        raise ValueError(f"Temporal test cohort lacks feature columns: {sorted(absent)}")
    categorical = [c for c in CATEGORICAL_CANDIDATES if c in feature_columns]
    numeric = [c for c in feature_columns if c not in categorical]
    for frame in (train, test):
        for col in categorical:
            frame[col] = frame[col].astype("string").fillna("Unknown").astype(str)
        for col in numeric:
            frame[col] = pd.to_numeric(frame[col], errors="coerce")

    X_train, y_train = train[feature_columns], train[TARGET]
    X_test, y_test = test[feature_columns], test[TARGET]

    baseline = make_pipeline(numeric, categorical, DummyClassifier(strategy="prior"))
    baseline.fit(X_train, y_train)
    baseline_prob = baseline.predict_proba(X_test)[:, 1]

    logistic = make_pipeline(numeric, categorical, LogisticRegression(
        max_iter=500, class_weight="balanced", solver="saga", random_state=42, n_jobs=-1,
    ))
    logistic.fit(X_train, y_train)
    logistic_prob = logistic.predict_proba(X_test)[:, 1]

    if len(train) > MAX_TUNING_ROWS:
        tune_train, _ = train_test_split(
            train, train_size=MAX_TUNING_ROWS, stratify=train[TARGET], random_state=42,
        )
        tune_X, tune_y = tune_train[feature_columns], tune_train[TARGET]
    else:
        tune_X, tune_y = X_train, y_train
    cv = StratifiedKFold(n_splits=3, shuffle=True, random_state=42)
    rf = make_pipeline(numeric, categorical, RandomForestClassifier(
        random_state=42, class_weight="balanced_subsample", n_jobs=1,
    ))
    search = GridSearchCV(
        rf,
        param_grid={
            "model__n_estimators": [100, 200],
            "model__max_depth": [10, 18],
            "model__min_samples_leaf": [5, 25],
            "model__max_features": ["sqrt"],
        },
        scoring="average_precision",
        cv=cv,
        n_jobs=-1,
        refit=True,
        error_score="raise",
        return_train_score=True,
    )
    search.fit(tune_X, tune_y)
    tuned_params = {key.removeprefix("model__"): value for key, value in search.best_params_.items()}
    final_model = make_pipeline(numeric, categorical, RandomForestClassifier(
        random_state=42, class_weight="balanced_subsample", n_jobs=-1, **tuned_params,
    ))
    final_model.fit(X_train, y_train)
    rf_prob = final_model.predict_proba(X_test)[:, 1]

    metrics = pd.DataFrame([
        metrics_for("Prior baseline", y_test, baseline_prob),
        metrics_for("Balanced logistic regression", y_test, logistic_prob),
        metrics_for("Tuned random forest", y_test, rf_prob),
    ])
    metrics.to_csv(OUT / "metrics_temporal_holdout.csv", index=False)
    rf_pred = (rf_prob >= 0.5).astype(int)
    (OUT / "classification_report.txt").write_text(classification_report(y_test, rf_pred, zero_division=0), encoding="utf-8")
    pd.DataFrame(confusion_matrix(y_test, rf_pred), index=["actual_0", "actual_1"], columns=["predicted_0", "predicted_1"]).to_csv(OUT / "confusion_matrix.csv")
    pd.DataFrame(search.cv_results_).sort_values("rank_test_score").to_csv(OUT / "grid_search_results.csv", index=False)

    fpr, tpr, _ = roc_curve(y_test, rf_prob)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(fpr, tpr, label=f"Tuned Random Forest (AUC={roc_auc_score(y_test, rf_prob):.3f})")
    ax.plot([0, 1], [0, 1], linestyle="--", label="Chance")
    ax.set(title="Temporal Holdout ROC Curve: March Cohort", xlabel="False Positive Rate", ylabel="True Positive Rate")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHARTS / "roc_curve.png", dpi=160)
    plt.close(fig)

    precision, recall, _ = precision_recall_curve(y_test, rf_prob)
    fig, ax = plt.subplots(figsize=(7, 6))
    ax.plot(recall, precision, label=f"AP={average_precision_score(y_test, rf_prob):.3f}")
    ax.axhline(y_test.mean(), linestyle="--", label=f"Positive prevalence={y_test.mean():.3f}")
    ax.set(title="Temporal Holdout Precision–Recall Curve: March Cohort", xlabel="Recall", ylabel="Precision")
    ax.legend()
    ax.grid(alpha=0.25)
    fig.tight_layout()
    fig.savefig(CHARTS / "precision_recall_curve.png", dpi=160)
    plt.close(fig)

    if len(X_test) > 100_000:
        importance_idx, _ = train_test_split(np.arange(len(X_test)), train_size=50_000, stratify=y_test, random_state=42)
        X_imp, y_imp = X_test.iloc[importance_idx], y_test.iloc[importance_idx]
    else:
        X_imp, y_imp = X_test, y_test
    importance = permutation_importance(final_model, X_imp, y_imp, scoring="average_precision", n_repeats=3, random_state=42, n_jobs=1)
    imp = pd.DataFrame({"feature": feature_columns, "importance_mean": importance.importances_mean, "importance_std": importance.importances_std}).sort_values("importance_mean", ascending=False)
    imp.to_csv(OUT / "permutation_importance.csv", index=False)
    top = imp.head(15).sort_values("importance_mean")
    fig, ax = plt.subplots(figsize=(9, 6))
    ax.barh(top["feature"], top["importance_mean"], xerr=top["importance_std"])
    ax.set(title="Permutation Importance on Temporal Holdout", xlabel="Decrease in average precision", ylabel="Input feature")
    fig.tight_layout()
    fig.savefig(CHARTS / "feature_importance.png", dpi=160)
    plt.close(fig)

    model_path = MODELS / "tuned_random_forest.joblib"
    joblib.dump(final_model, model_path)
    metadata = {
        "source": "KKBox's Churn Prediction Challenge",
        "source_url": "https://www.kaggle.com/competitions/kkbox-churn-prediction-challenge/data",
        "training_cohort": "train.csv labels, feature snapshot cutoff 2017-01-31",
        "temporal_test_cohort": "train_v2.csv labels, feature snapshot cutoff 2017-02-28",
        "target_definition": "Official competition is_churn target: member did not continue a valid subscription within 30 days after the relevant membership expiry.",
        "train_rows": len(train), "test_rows": len(test),
        "train_positive_rate": float(y_train.mean()), "test_positive_rate": float(y_test.mean()),
        "tuning_rows": len(tune_X), "best_params": search.best_params_,
        "best_cv_average_precision": float(search.best_score_),
        "test_metrics": metrics.to_dict(orient="records"),
        "feature_columns": feature_columns,
        "excluded_inputs": ["msno", "cohort", "snapshot_date", "is_churn"],
        "leakage_controls": [
            "February cohort features use transactions dated on/before 2017-01-31.",
            "March cohort features use transactions dated on/before 2017-02-28.",
            "The later labeled cohort is held out for temporal evaluation.",
            "Transaction records after each cohort's feature cutoff are not used to build its features.",
        ],
        "generated_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
    }
    (OUT / "run_metadata.json").write_text(json.dumps(metadata, indent=2), encoding="utf-8")
    print(metrics.to_string(index=False))
    print(f"Best parameters: {search.best_params_}")
    print(f"Temporal test cohort rows: {len(test):,}; model saved to {model_path}")


if __name__ == "__main__":
    main()
