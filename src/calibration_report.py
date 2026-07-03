"""Calibration report over the held-out test games.

Answers: when the model says 70%, does the home team actually win ~70% of the time?

Outputs (reports/):
    calibration_curves.csv   per-model reliability bins
    calibration_summary.csv  ECE, max bin error, Brier, log loss, overconfidence flag
    brier_by_quarter.csv     Brier score per game segment per model

Run: python src/calibration_report.py [--bins 10] [--exclude-terminal]
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import brier_score_loss, log_loss

import json

from ml_pipeline_utils import load_shared_training_inputs
from model_predictions import COMPETITOR_MODEL_KEYS, MODEL_LABELS, generate_all_test_probabilities

REPORTS_DIR = Path("reports")

EVALUATED_MODELS = COMPETITOR_MODEL_KEYS + ["scoreboard_fallback"]


def champion_model_key() -> str:
    champion_path = REPORTS_DIR / "champion_model.json"
    if champion_path.exists():
        try:
            return str(json.loads(champion_path.read_text(encoding="utf-8")).get("model_key", ""))
        except (json.JSONDecodeError, OSError):
            pass
    return "pytorch_neural_network"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate calibration reports over the test split.")
    parser.add_argument("--bins", type=int, default=10, help="Number of uniform probability bins.")
    parser.add_argument(
        "--exclude-terminal",
        action="store_true",
        help="Exclude final-buzzer rows (which are overridden to 0/1) as a sensitivity check.",
    )
    return parser.parse_args()


def reliability_bins(y_true: np.ndarray, probabilities: np.ndarray, n_bins: int) -> pd.DataFrame:
    edges = np.linspace(0.0, 1.0, n_bins + 1)
    bin_index = np.clip(np.digitize(probabilities, edges[1:-1]), 0, n_bins - 1)
    rows = []
    for index in range(n_bins):
        mask = bin_index == index
        count = int(mask.sum())
        if count == 0:
            continue
        rows.append({
            "bin_index": index,
            "bin_lower": edges[index],
            "bin_upper": edges[index + 1],
            "mean_predicted": float(probabilities[mask].mean()),
            "observed_rate": float(y_true[mask].mean()),
            "count": count,
        })
    return pd.DataFrame(rows)


def expected_calibration_error(bins: pd.DataFrame) -> float:
    total = bins["count"].sum()
    return float((bins["count"] / total * (bins["mean_predicted"] - bins["observed_rate"]).abs()).sum())


def is_overconfident(bins: pd.DataFrame, ece: float, champion_ece: float) -> bool:
    confident = bins[(bins["count"] >= 200) & (bins["mean_predicted"] > 0.8)]
    inflated = ((confident["mean_predicted"] - confident["observed_rate"]) > 0.05).any() if not confident.empty else False
    return bool(inflated or (champion_ece > 0 and ece > 1.5 * champion_ece))


def period_bucket(period: int) -> str:
    return f"Q{period}" if period <= 4 else "OT"


def main() -> None:
    args = parse_args()
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    _train, test_data, feature_columns, _train_ids, _test_ids = load_shared_training_inputs()
    probabilities = generate_all_test_probabilities(test_data, feature_columns)

    if args.exclude_terminal:
        probabilities = probabilities[probabilities["seconds_remaining"] > 0].reset_index(drop=True)
        print("Terminal (final-buzzer) rows excluded.")

    y_true = probabilities["home_won"].astype(int).to_numpy()
    curves, summaries, quarter_rows = [], [], []

    for model_key in EVALUATED_MODELS:
        probs = np.clip(probabilities[model_key].to_numpy(dtype=float), 1e-6, 1 - 1e-6)
        bins = reliability_bins(y_true, probs, args.bins)
        bins.insert(0, "model_key", model_key)
        bins.insert(1, "model_name", MODEL_LABELS[model_key])
        curves.append(bins)
        summaries.append({
            "model_key": model_key,
            "model_name": MODEL_LABELS[model_key],
            "ece": round(expected_calibration_error(bins), 4),
            "max_calibration_error": round(float((bins["mean_predicted"] - bins["observed_rate"]).abs().max()), 4),
            "brier_score": round(brier_score_loss(y_true, probs), 4),
            "log_loss": round(log_loss(y_true, probs, labels=[0, 1]), 4),
            "rows": len(probs),
            "terminal_excluded": args.exclude_terminal,
        })
        segments = probabilities["period"].astype(int).map(period_bucket)
        for bucket in ["Q1", "Q2", "Q3", "Q4", "OT"]:
            mask = (segments == bucket).to_numpy()
            if mask.sum() == 0:
                continue
            quarter_rows.append({
                "model_key": model_key,
                "model_name": MODEL_LABELS[model_key],
                "period_bucket": bucket,
                "brier_score": round(brier_score_loss(y_true[mask], probs[mask]), 4),
                "rows": int(mask.sum()),
            })

    summary = pd.DataFrame(summaries)
    champion_key = champion_model_key()
    champion_ece = float(summary.loc[summary["model_key"] == champion_key, "ece"].min()) if (summary["model_key"] == champion_key).any() else float(summary["ece"].min())
    summary["overconfident"] = [
        is_overconfident(curve.drop(columns=["model_key", "model_name"]), row["ece"], champion_ece)
        for curve, (_, row) in zip(curves, summary.iterrows())
    ]
    summary["notes"] = summary.apply(
        lambda row: "Overconfident at high probabilities on held-out games." if row["overconfident"] else "", axis=1
    )

    curves_frame = pd.concat(curves, ignore_index=True)
    quarters_frame = pd.DataFrame(quarter_rows)

    curves_path = REPORTS_DIR / "calibration_curves.csv"
    summary_path = REPORTS_DIR / "calibration_summary.csv"
    quarters_path = REPORTS_DIR / "brier_by_quarter.csv"
    curves_frame.to_csv(curves_path, index=False)
    summary.to_csv(summary_path, index=False)
    quarters_frame.to_csv(quarters_path, index=False)

    print("\nSuccess.")
    print(f"Saved calibration curves to: {curves_path}")
    print(f"Saved calibration summary to: {summary_path}")
    print(f"Saved Brier-by-quarter to: {quarters_path}")
    print("\nCalibration summary:")
    print(summary.to_string(index=False))


if __name__ == "__main__":
    main()
