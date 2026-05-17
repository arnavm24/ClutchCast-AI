from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

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


def train_advanced_model(
    train_data: pd.DataFrame,
    feature_columns: list[str],
) -> RandomForestClassifier:
    X_train = train_data[feature_columns]
    y_train = train_data[TARGET_COLUMN]

    model = RandomForestClassifier(
        n_estimators=500,
        max_depth=14,
        min_samples_leaf=15,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
    )

    model.fit(X_train, y_train)
    return model


def evaluate_model(
    model: RandomForestClassifier,
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
    feature_columns: list[str],
) -> dict:
    X_test = test_data[feature_columns]
    probabilities = model.predict_proba(X_test)[:, 1]

    prediction_frame = test_data.copy()
    prediction_frame["home_win_prob"] = probabilities
    prediction_frame = apply_terminal_state_overrides(prediction_frame)

    return compute_probability_metrics(
        y_true=prediction_frame[TARGET_COLUMN],
        probabilities=prediction_frame["home_win_prob"],
        model_key="random_forest",
        model_name="Random Forest",
        feature_count=len(feature_columns),
        train_data=train_data,
        test_data=test_data,
    )


def save_model(model: RandomForestClassifier, feature_columns: list[str]) -> None:
    output_path = MODELS_DIR / "advanced_win_probability_model.joblib"
    metadata_path = MODELS_DIR / "advanced_win_probability_model_features.txt"

    joblib.dump(model, output_path)
    metadata_path.write_text("\n".join(feature_columns), encoding="utf-8")

    print(f"Saved advanced model to: {output_path}")
    print(f"Saved advanced model feature list to: {metadata_path}")


def save_metrics(metrics: dict) -> None:
    output_path = REPORTS_DIR / "advanced_model_metrics.csv"

    metrics_df = pd.DataFrame([metrics])
    metrics_df.to_csv(output_path, index=False)

    print(f"Saved advanced model metrics to: {output_path}")
    print("\nAdvanced model metrics:")
    for key, value in metrics.items():
        print(f"{key}: {value}")


def save_feature_importance(
    model: RandomForestClassifier,
    feature_columns: list[str],
) -> None:
    importance = pd.DataFrame(
        {
            "feature": feature_columns,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)

    output_path = REPORTS_DIR / "advanced_model_feature_importance.csv"
    importance.to_csv(output_path, index=False)

    print(f"Saved advanced model feature importance to: {output_path}")
    print("\nTop advanced model feature importance:")
    print(importance.head(15).to_string(index=False))


def main() -> None:
    train_data, test_data, feature_columns, train_game_ids, test_game_ids = (
        load_shared_training_inputs()
    )

    print("\nDataset summary:")
    print(f"Feature count: {len(feature_columns)}")
    print(f"Train rows: {len(train_data)}")
    print(f"Train games: {len(train_game_ids)}")
    print(f"Test rows: {len(test_data)}")
    print(f"Test games: {len(test_game_ids)}")

    model = train_advanced_model(train_data, feature_columns)
    metrics = evaluate_model(model, train_data, test_data, feature_columns)

    save_model(model, feature_columns)
    save_metrics(metrics)
    save_feature_importance(model, feature_columns)

    print("\nSuccess.")
    print("Retrained random forest model using the shared game-level split.")


if __name__ == "__main__":
    main()
