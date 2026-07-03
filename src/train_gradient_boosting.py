"""Train a gradient-boosted trees win-probability model.

Uses sklearn's HistGradientBoostingClassifier (LightGBM-class performance, no
new dependency). Enters the same champion competition as every other model.

Run: python src/train_gradient_boosting.py
"""

from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import HistGradientBoostingClassifier

from ml_pipeline_utils import (
    TARGET_COLUMN,
    apply_terminal_state_overrides,
    compute_probability_metrics,
    load_shared_training_inputs,
)

MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")

MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODELS_DIR / "gradient_boosting_win_probability_model.joblib"


def train_model(train_data: pd.DataFrame, feature_columns: list[str]) -> HistGradientBoostingClassifier:
    X_train = train_data[feature_columns].astype(float)
    y_train = train_data[TARGET_COLUMN].astype(int)

    # Conservative settings: rows within a game are heavily correlated, so
    # row-level early stopping leaks and lets the model memorize trajectories.
    # A fixed, shallow ensemble generalizes to unseen games far better.
    model = HistGradientBoostingClassifier(
        loss="log_loss",
        max_iter=150,
        learning_rate=0.05,
        max_depth=None,
        max_leaf_nodes=31,
        min_samples_leaf=500,
        l2_regularization=10.0,
        early_stopping=False,
        random_state=42,
    )
    model.fit(X_train, y_train)
    return model


def evaluate_model(model, train_data: pd.DataFrame, test_data: pd.DataFrame, feature_columns: list[str]) -> dict:
    probabilities = model.predict_proba(test_data[feature_columns].astype(float))[:, 1]

    prediction_frame = test_data.copy()
    prediction_frame["home_win_prob"] = probabilities
    prediction_frame = apply_terminal_state_overrides(prediction_frame)

    return compute_probability_metrics(
        y_true=prediction_frame[TARGET_COLUMN],
        probabilities=prediction_frame["home_win_prob"],
        model_key="gradient_boosting",
        model_name="Gradient Boosting",
        feature_count=len(feature_columns),
        train_data=train_data,
        test_data=test_data,
    )


def main() -> None:
    train_data, test_data, feature_columns, train_game_ids, test_game_ids = load_shared_training_inputs()

    print("\nDataset summary:")
    print(f"Feature count: {len(feature_columns)}")
    print(f"Train rows: {len(train_data)} ({len(train_game_ids)} games)")
    print(f"Test rows: {len(test_data)} ({len(test_game_ids)} games)")

    model = train_model(train_data, feature_columns)
    print(f"Boosting iterations: {model.n_iter_}")

    metrics = evaluate_model(model, train_data, test_data, feature_columns)

    joblib.dump(model, MODEL_PATH)
    pd.DataFrame([metrics]).to_csv(REPORTS_DIR / "gradient_boosting_model_metrics.csv", index=False)

    print(f"\nSaved model to: {MODEL_PATH}")
    print("\nModel metrics:")
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
