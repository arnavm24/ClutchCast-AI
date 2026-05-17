from pathlib import Path

import joblib
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss, roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


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
            "python src/build_training_dataset.py --season 2023-24 --season-type \"Regular Season\" --max-games 50"
        )

    print(f"Loading training data from: {input_path}")

    data = pd.read_csv(input_path, dtype={"game_id": str})

    if data.empty:
        raise ValueError("Training dataset is empty.")

    return data


def validate_training_data(data: pd.DataFrame) -> None:
    missing = [col for col in FEATURE_COLUMNS + [TARGET_COLUMN, "game_id"] if col not in data.columns]

    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    unique_targets = data[TARGET_COLUMN].nunique()

    if unique_targets < 2:
        raise ValueError(
            "The training dataset only has one result class. "
            "The model needs both home wins and home losses to train properly. "
            "Build a larger dataset, for example:\n"
            "python src/build_training_dataset.py --season 2023-24 --season-type \"Regular Season\" --max-games 100"
        )


def split_by_game(data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """
    Splits by game_id, not random rows.

    This is important because rows from the same game are highly related.
    A row-level random split would leak game information into the test set.
    """
    unique_games = sorted(data["game_id"].unique())

    if len(unique_games) < 3:
        raise ValueError(
            "Need at least 3 games for a meaningful train/test split. "
            "Build a larger dataset first."
        )

    split_index = int(len(unique_games) * 0.8)

    train_games = set(unique_games[:split_index])
    test_games = set(unique_games[split_index:])

    train_data = data[data["game_id"].isin(train_games)].copy()
    test_data = data[data["game_id"].isin(test_games)].copy()

    return train_data, test_data


def train_model(train_data: pd.DataFrame) -> Pipeline:
    X_train = train_data[FEATURE_COLUMNS]
    y_train = train_data[TARGET_COLUMN]

    model = Pipeline(
        steps=[
            ("scaler", StandardScaler()),
            (
                "classifier",
                LogisticRegression(
                    max_iter=1000,
                    random_state=42,
                ),
            ),
        ]
    )

    model.fit(X_train, y_train)

    return model


def evaluate_model(model: Pipeline, test_data: pd.DataFrame) -> dict:
    X_test = test_data[FEATURE_COLUMNS]
    y_test = test_data[TARGET_COLUMN]

    predicted_labels = model.predict(X_test)
    predicted_probabilities = model.predict_proba(X_test)[:, 1]

    metrics = {
        "test_rows": len(test_data),
        "test_games": test_data["game_id"].nunique(),
        "accuracy": accuracy_score(y_test, predicted_labels),
        "brier_score": brier_score_loss(y_test, predicted_probabilities),
        "log_loss": log_loss(y_test, predicted_probabilities),
    }

    if y_test.nunique() == 2:
        metrics["roc_auc"] = roc_auc_score(y_test, predicted_probabilities)
    else:
        metrics["roc_auc"] = None

    return metrics


def save_feature_importance(model: Pipeline) -> None:
    classifier = model.named_steps["classifier"]

    importance = pd.DataFrame(
        {
            "feature": FEATURE_COLUMNS,
            "coefficient": classifier.coef_[0],
            "absolute_importance": abs(classifier.coef_[0]),
        }
    ).sort_values("absolute_importance", ascending=False)

    output_path = REPORTS_DIR / "model_feature_importance.csv"
    importance.to_csv(output_path, index=False)

    print(f"Saved feature importance to: {output_path}")
    print("\nFeature importance:")
    print(importance)


def save_metrics(metrics: dict) -> None:
    output_path = REPORTS_DIR / "model_metrics.csv"

    metrics_df = pd.DataFrame([metrics])
    metrics_df.to_csv(output_path, index=False)

    print(f"Saved model metrics to: {output_path}")
    print("\nModel metrics:")
    for key, value in metrics.items():
        print(f"{key}: {value}")


def save_model(model: Pipeline) -> None:
    output_path = MODELS_DIR / "win_probability_model.joblib"
    joblib.dump(model, output_path)

    print(f"Saved trained model to: {output_path}")


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

    model = train_model(train_data)
    metrics = evaluate_model(model, test_data)

    save_model(model)
    save_metrics(metrics)
    save_feature_importance(model)

    print("\nSuccess.")
    print("Trained first ML win-probability model.")


if __name__ == "__main__":
    main()