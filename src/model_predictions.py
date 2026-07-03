"""Shared test-set probability generation.

Single code path used by both compare_models.py (leaderboard) and
calibration_report.py so their metrics can never drift apart.
"""

from pathlib import Path

import joblib
import pandas as pd
import torch

from ml_pipeline_utils import apply_terminal_state_overrides
from train_baseline import baseline_home_win_probability
from train_neural_network import WinProbabilityNeuralNetwork

MODELS_DIR = Path("models")

MODEL_LABELS = {
    "baseline": "Baseline Rule Model",
    "logistic_regression": "Logistic Regression",
    "random_forest": "Random Forest",
    "gradient_boosting": "Gradient Boosting",
    "pytorch_neural_network": "PyTorch Neural Network",
    "sequence_gru": "GRU Sequence Model",
    "scoreboard_fallback": "Scoreboard Fallback (Live)",
}

COMPETITOR_MODEL_KEYS = [
    "baseline",
    "logistic_regression",
    "random_forest",
    "gradient_boosting",
    "pytorch_neural_network",
    "sequence_gru",
]

SKLEARN_MODEL_PATHS = {
    "logistic_regression": MODELS_DIR / "win_probability_model.joblib",
    "random_forest": MODELS_DIR / "advanced_win_probability_model.joblib",
    "gradient_boosting": MODELS_DIR / "gradient_boosting_win_probability_model.joblib",
}


def scoreboard_fallback_home_probability(row: pd.Series) -> float:
    """Mirror of backend.app.scoreboard_baseline_home_probability's in-game branch,
    so the live scoreboard fallback's probability quality can be evaluated."""
    margin = float(row["home_score"]) - float(row["away_score"])
    period = int(row["period"])
    leverage = 0.025
    if period >= 4:
        leverage = 0.04
    elif period >= 2:
        leverage = 0.03
    return max(0.02, min(0.98, 0.5 + margin * leverage))


def predict_test_probabilities(model_key: str, test_data: pd.DataFrame, feature_columns: list[str]) -> pd.DataFrame:
    """Returns test_data with home_win_prob (+ derived cols) after terminal overrides."""
    prediction_frame = test_data.copy()

    if model_key == "baseline":
        prediction_frame["home_win_prob"] = prediction_frame.apply(baseline_home_win_probability, axis=1)
    elif model_key == "scoreboard_fallback":
        prediction_frame["home_win_prob"] = prediction_frame.apply(scoreboard_fallback_home_probability, axis=1)
    elif model_key in SKLEARN_MODEL_PATHS:
        model_path = SKLEARN_MODEL_PATHS[model_key]
        if not model_path.exists():
            raise FileNotFoundError(
                f"Missing {MODEL_LABELS[model_key]} model artifact: {model_path}. "
                "Train models before generating the leaderboard."
            )
        model = joblib.load(model_path)
        prediction_frame["home_win_prob"] = model.predict_proba(test_data[feature_columns])[:, 1]
    elif model_key == "pytorch_neural_network":
        model_path = MODELS_DIR / "pytorch_win_probability_model.pt"
        scaler_path = MODELS_DIR / "pytorch_scaler.joblib"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Missing PyTorch model artifact: {model_path}. "
                "Train models before generating the leaderboard."
            )
        if not scaler_path.exists():
            raise FileNotFoundError(
                f"Missing PyTorch scaler artifact: {scaler_path}. "
                "Train models before generating the leaderboard."
            )
        checkpoint = torch.load(model_path, map_location="cpu")
        input_size = checkpoint.get("input_size", len(feature_columns))
        model = WinProbabilityNeuralNetwork(input_size=input_size)
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        scaler = joblib.load(scaler_path)
        X_test = test_data[feature_columns].astype(float)
        X_test_scaled = scaler.transform(X_test)
        X_test_tensor = torch.tensor(X_test_scaled, dtype=torch.float32)
        with torch.no_grad():
            prediction_frame["home_win_prob"] = model(X_test_tensor).numpy().flatten()
    elif model_key == "sequence_gru":
        from sequence_features import build_dataset_windows
        from train_sequence_model import WinProbabilityGRU

        model_path = MODELS_DIR / "sequence_gru_model.pt"
        if not model_path.exists():
            raise FileNotFoundError(
                f"Missing sequence model artifact: {model_path}. "
                "Run: python src/train_sequence_model.py"
            )
        checkpoint = torch.load(model_path, map_location="cpu")
        model = WinProbabilityGRU(
            input_size=checkpoint.get("input_size", 11),
            hidden_size=checkpoint.get("hidden_size", 64),
        )
        model.load_state_dict(checkpoint["model_state_dict"])
        model.eval()
        windows = torch.from_numpy(build_dataset_windows(test_data))
        with torch.no_grad():
            prediction_frame["home_win_prob"] = model(windows).numpy()
    else:
        raise ValueError(f"Unknown model key: {model_key}")

    return apply_terminal_state_overrides(prediction_frame)


def generate_all_test_probabilities(test_data: pd.DataFrame, feature_columns: list[str], include_fallback: bool = True) -> pd.DataFrame:
    """One column of home-win probabilities per model, plus evaluation context columns."""
    output = test_data[["game_id", "period", "seconds_remaining", "home_score", "away_score", "home_won"]].copy().reset_index(drop=True)
    model_keys = list(COMPETITOR_MODEL_KEYS)
    if include_fallback:
        model_keys.append("scoreboard_fallback")
    for model_key in model_keys:
        predicted = predict_test_probabilities(model_key, test_data, feature_columns)
        output[model_key] = predicted["home_win_prob"].to_numpy()
    return output
