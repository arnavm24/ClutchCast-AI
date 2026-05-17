from pathlib import Path

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.model_selection import train_test_split


PROCESSED_DIR = Path("data/processed")
MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")

MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


FEATURE_COLUMNS = [
    "period",
    "seconds_remaining",
    "home_score",
    "away_score",
    "score_margin_home",
    "abs_score_margin",
    "total_score",
    "is_4th_quarter",
    "is_clutch_time",
]

TARGET_COLUMN = "home_won"


def load_training_data() -> pd.DataFrame:
    input_path = PROCESSED_DIR / "training_dataset.csv"

    if not input_path.exists():
        raise FileNotFoundError(
            "No training dataset found. Run:\n"
            'python src/build_training_dataset.py --season 2023-24 --season-type "Regular Season" --max-games 100'
        )

    print(f"Loading training data from: {input_path}")

    data = pd.read_csv(input_path, dtype={"game_id": str})

    if data.empty:
        raise ValueError("Training dataset is empty.")

    return data


def validate_training_data(data: pd.DataFrame) -> None:
    required_columns = FEATURE_COLUMNS + [TARGET_COLUMN, "game_id"]
    missing = [col for col in required_columns if col not in data.columns]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    if data[TARGET_COLUMN].nunique() < 2:
        raise ValueError(
            "Training data only has one target class. "
            "Build a bigger dataset with both home wins and home losses."
        )


def split_by_game(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    unique_games = sorted(data["game_id"].unique())

    if len(unique_games) < 5:
        raise ValueError(
            "Need at least 5 games for a useful train/test split. "
            "Build a larger training dataset first."
        )

    train_games, test_games = train_test_split(
        unique_games,
        test_size=0.2,
        random_state=42,
    )

    train_data = data[data["game_id"].isin(train_games)].copy()
    test_data = data[data["game_id"].isin(test_games)].copy()

    return train_data, test_data


def train_advanced_model(train_data: pd.DataFrame) -> RandomForestClassifier:
    X_train = train_data[FEATURE_COLUMNS]
    y_train = train_data[TARGET_COLUMN]

    model = RandomForestClassifier(
        n_estimators=300,
        max_depth=12,
        min_samples_leaf=20,
        random_state=42,
        n_jobs=-1,
        class_weight="balanced",
    )

    model.fit(X_train, y_train)

    return model


def evaluate_model(model: RandomForestClassifier, test_data: pd.DataFrame) -> dict:
    X_test = test_data[FEATURE_COLUMNS]
    y_test = test_data[TARGET_COLUMN]

    predicted_labels = model.predict(X_test)
    predicted_probabilities = model.predict_proba(X_test)[:, 1]

    metrics = {
        "model_type": "RandomForestClassifier",
        "test_rows": len(test_data),
        "test_games": test_data["game_id"].nunique(),
        "accuracy": round(accuracy_score(y_test, predicted_labels), 4),
        "brier_score": round(brier_score_loss(y_test, predicted_probabilities), 4),
        "log_loss": round(log_loss(y_test, predicted_probabilities), 4),
    }

    if y_test.nunique() == 2:
        metrics["roc_auc"] = round(roc_auc_score(y_test, predicted_probabilities), 4)
    else:
        metrics["roc_auc"] = None

    return metrics


def save_model(model: RandomForestClassifier) -> None:
    output_path = MODELS_DIR / "advanced_win_probability_model.joblib"
    joblib.dump(model, output_path)

    print(f"Saved advanced model to: {output_path}")


def save_metrics(metrics: dict) -> None:
    output_path = REPORTS_DIR / "advanced_model_metrics.csv"
    metrics_df = pd.DataFrame([metrics])
    metrics_df.to_csv(output_path, index=False)

    print(f"Saved advanced model metrics to: {output_path}")
    print("\nAdvanced model metrics:")
    for key, value in metrics.items():
        print(f"{key}: {value}")


def save_feature_importance(model: RandomForestClassifier) -> None:
    importance = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "importance": model.feature_importances_,
        }
    ).sort_values("importance", ascending=False)

    output_path = REPORTS_DIR / "advanced_model_feature_importance.csv"
    importance.to_csv(output_path, index=False)

    print(f"Saved advanced model feature importance to: {output_path}")
    print("\nAdvanced model feature importance:")
    print(importance)


def main() -> None:
    data = load_training_data()
    validate_training_data(data)

    train_data, test_data = split_by_game(data)

    print("\nDataset summary:")
    print(f"Total rows: {len(data)}")
    print(f"Total games: {data['game_id'].nunique()}")
    print(f"Train rows: {len(train_data)}")
    print(f"Train games: {train_data['game_id'].nunique()}")
    print(f"Test rows: {len(test_data)}")
    print(f"Test games: {test_data['game_id'].nunique()}")

    model = train_advanced_model(train_data)
    metrics = evaluate_model(model, test_data)

    save_model(model)
    save_metrics(metrics)
    save_feature_importance(model)

    print("\nSuccess.")
    print("Trained advanced ML win-probability model.")


if __name__ == "__main__":
    main()