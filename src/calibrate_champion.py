"""Fit an isotonic calibration layer for the current champion model.

The calibrator is fitted on validation games carved out of the TRAIN split
(never the test games), so reported test-set improvements are honest. It is a
monotonic map over probabilities: it cannot change which team is favored, only
make the numbers mean what they say. champion_inference applies it
automatically when models/champion_calibrator.joblib matches the champion.

Run: python src/calibrate_champion.py
"""

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.isotonic import IsotonicRegression
from sklearn.metrics import brier_score_loss, log_loss

from ml_pipeline_utils import load_shared_training_inputs
from model_predictions import MODEL_LABELS, predict_test_probabilities

MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")
CALIBRATOR_PATH = MODELS_DIR / "champion_calibrator.joblib"

VALIDATION_GAME_FRACTION = 0.2
RANDOM_STATE = 7


def load_champion_key() -> str:
    champion_path = REPORTS_DIR / "champion_model.json"
    if not champion_path.exists():
        raise FileNotFoundError("Missing reports/champion_model.json. Run: python src/compare_models.py --leaderboard")
    return str(json.loads(champion_path.read_text(encoding="utf-8"))["model_key"])


def metric_row(label: str, y_true: np.ndarray, probs: np.ndarray) -> dict:
    probs = np.clip(probs, 1e-6, 1 - 1e-6)
    return {
        "stage": label,
        "brier_score": round(brier_score_loss(y_true, probs), 4),
        "log_loss": round(log_loss(y_true, probs, labels=[0, 1]), 4),
    }


def main() -> None:
    champion_key = load_champion_key()
    print(f"Champion model: {MODEL_LABELS.get(champion_key, champion_key)} ({champion_key})")

    train_data, test_data, feature_columns, _train_ids, _test_ids = load_shared_training_inputs()

    games = sorted(train_data["game_id"].unique())
    rng = np.random.RandomState(RANDOM_STATE)
    rng.shuffle(games)
    n_val = max(int(len(games) * VALIDATION_GAME_FRACTION), 1)
    val_games = set(games[:n_val])
    val_data = train_data[train_data["game_id"].isin(val_games)].copy()
    print(f"Fitting isotonic calibrator on {len(val_games)} validation games ({len(val_data)} rows) from the train split.")

    val_predictions = predict_test_probabilities(champion_key, val_data, feature_columns)
    # Terminal rows are hard-overridden to 0/1 at inference; excluding them
    # keeps the calibrator focused on live in-game probabilities.
    in_game = val_predictions["seconds_remaining"] > 0
    y_val = val_predictions.loc[in_game, "home_won"].astype(int).to_numpy()
    p_val = val_predictions.loc[in_game, "home_win_prob"].to_numpy(dtype=float)

    calibrator = IsotonicRegression(y_min=0.0, y_max=1.0, out_of_bounds="clip")
    calibrator.fit(p_val, y_val)

    test_predictions = predict_test_probabilities(champion_key, test_data, feature_columns)
    test_in_game = test_predictions["seconds_remaining"] > 0
    y_test = test_predictions.loc[test_in_game, "home_won"].astype(int).to_numpy()
    p_test_raw = test_predictions.loc[test_in_game, "home_win_prob"].to_numpy(dtype=float)
    p_test_cal = calibrator.predict(np.clip(p_test_raw, 0, 1))

    raw_metrics = metric_row("test_raw", y_test, p_test_raw)
    calibrated_metrics = metric_row("test_calibrated", y_test, p_test_cal)
    improved = calibrated_metrics["brier_score"] < raw_metrics["brier_score"]

    report = pd.DataFrame([raw_metrics, calibrated_metrics])
    report.insert(0, "champion_key", champion_key)
    report["applied"] = improved
    report.to_csv(REPORTS_DIR / "champion_calibration_effect.csv", index=False)

    print(f"Saved before/after report to: {REPORTS_DIR / 'champion_calibration_effect.csv'}")
    print("\nHeld-out test games (in-game rows, terminal rows excluded):")
    print(report.to_string(index=False))

    # A calibrator only ships if it actually improves held-out probability
    # quality; a well-calibrated champion doesn't need one.
    if improved:
        joblib.dump({"champion_key": champion_key, "calibrator": calibrator}, CALIBRATOR_PATH)
        print(f"\nCalibration improves the champion — saved calibrator to: {CALIBRATOR_PATH}")
    else:
        if CALIBRATOR_PATH.exists():
            CALIBRATOR_PATH.unlink()
        print("\nCalibration did not improve held-out Brier — champion is already well calibrated; no calibrator applied.")


if __name__ == "__main__":
    main()
