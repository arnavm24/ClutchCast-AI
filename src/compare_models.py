from pathlib import Path
import argparse

import pandas as pd


PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


MODEL_FILES = {
    "baseline": "baseline_predictions_{game_id}.csv",
    "logistic_ml": "ml_predictions_{game_id}.csv",
    "advanced_ml": "advanced_predictions_{game_id}.csv",
}


MODEL_LABELS = {
    "baseline": "Baseline",
    "logistic_ml": "Logistic ML",
    "advanced_ml": "Advanced ML",
}


def get_available_game_ids() -> list[str]:
    baseline_ids = {
        file.stem.replace("baseline_predictions_", "")
        for file in PROCESSED_DIR.glob("baseline_predictions_*.csv")
    }

    ml_ids = {
        file.stem.replace("ml_predictions_", "")
        for file in PROCESSED_DIR.glob("ml_predictions_*.csv")
    }

    advanced_ids = {
        file.stem.replace("advanced_predictions_", "")
        for file in PROCESSED_DIR.glob("advanced_predictions_*.csv")
    }

    return sorted(baseline_ids.intersection(ml_ids).intersection(advanced_ids))


def load_prediction_file(game_id: str, model_key: str) -> pd.DataFrame:
    filename = MODEL_FILES[model_key].format(game_id=game_id)
    path = PROCESSED_DIR / filename

    if not path.exists():
        raise FileNotFoundError(f"Missing prediction file: {path}")

    return pd.read_csv(path, dtype={"game_id": str})


def load_predictions(game_id: str) -> dict[str, pd.DataFrame]:
    return {
        model_key: load_prediction_file(game_id, model_key)
        for model_key in MODEL_FILES
    }


def validate_prediction_lengths(predictions: dict[str, pd.DataFrame]) -> None:
    lengths = {
        model_key: len(df)
        for model_key, df in predictions.items()
    }

    if len(set(lengths.values())) != 1:
        raise ValueError(f"Prediction files have different lengths: {lengths}")


def compare_predictions(predictions: dict[str, pd.DataFrame]) -> pd.DataFrame:
    validate_prediction_lengths(predictions)

    baseline = predictions["baseline"]
    logistic_ml = predictions["logistic_ml"]
    advanced_ml = predictions["advanced_ml"]

    comparison = pd.DataFrame()

    comparison["game_id"] = baseline["game_id"]
    comparison["period"] = baseline["period"]
    comparison["clock"] = baseline["clock"]
    comparison["home_score"] = baseline["home_score"]
    comparison["away_score"] = baseline["away_score"]
    comparison["score_margin_home"] = baseline["score_margin_home"]
    comparison["event_team"] = baseline["event_team"]
    comparison["event_player"] = baseline["event_player"]
    comparison["event_description"] = baseline["event_description"]

    comparison["baseline_home_win_prob_pct"] = baseline["home_win_prob_pct"]
    comparison["logistic_ml_home_win_prob_pct"] = logistic_ml["home_win_prob_pct"]
    comparison["advanced_ml_home_win_prob_pct"] = advanced_ml["home_win_prob_pct"]

    comparison["logistic_minus_baseline_pct"] = (
        comparison["logistic_ml_home_win_prob_pct"]
        - comparison["baseline_home_win_prob_pct"]
    ).round(2)

    comparison["advanced_minus_baseline_pct"] = (
        comparison["advanced_ml_home_win_prob_pct"]
        - comparison["baseline_home_win_prob_pct"]
    ).round(2)

    comparison["advanced_minus_logistic_pct"] = (
        comparison["advanced_ml_home_win_prob_pct"]
        - comparison["logistic_ml_home_win_prob_pct"]
    ).round(2)

    comparison["abs_logistic_minus_baseline_pct"] = (
        comparison["logistic_minus_baseline_pct"].abs()
    ).round(2)

    comparison["abs_advanced_minus_baseline_pct"] = (
        comparison["advanced_minus_baseline_pct"].abs()
    ).round(2)

    comparison["abs_advanced_minus_logistic_pct"] = (
        comparison["advanced_minus_logistic_pct"].abs()
    ).round(2)

    comparison["max_model_disagreement_pct"] = comparison[
        [
            "abs_logistic_minus_baseline_pct",
            "abs_advanced_minus_baseline_pct",
            "abs_advanced_minus_logistic_pct",
        ]
    ].max(axis=1)

    return comparison


def build_summary(comparison: pd.DataFrame) -> pd.DataFrame:
    final_row = comparison.iloc[-1]

    summary = {
        "game_id": str(final_row["game_id"]).zfill(10),
        "rows_compared": len(comparison),
        "avg_logistic_vs_baseline_diff_pct": round(
            comparison["abs_logistic_minus_baseline_pct"].mean(), 2
        ),
        "avg_advanced_vs_baseline_diff_pct": round(
            comparison["abs_advanced_minus_baseline_pct"].mean(), 2
        ),
        "avg_advanced_vs_logistic_diff_pct": round(
            comparison["abs_advanced_minus_logistic_pct"].mean(), 2
        ),
        "max_model_disagreement_pct": round(
            comparison["max_model_disagreement_pct"].max(), 2
        ),
        "baseline_final_home_win_prob_pct": final_row[
            "baseline_home_win_prob_pct"
        ],
        "logistic_ml_final_home_win_prob_pct": final_row[
            "logistic_ml_home_win_prob_pct"
        ],
        "advanced_ml_final_home_win_prob_pct": final_row[
            "advanced_ml_home_win_prob_pct"
        ],
        "final_home_score": int(final_row["home_score"]),
        "final_away_score": int(final_row["away_score"]),
        "final_home_margin": int(final_row["score_margin_home"]),
    }

    return pd.DataFrame([summary])


def get_biggest_disagreements(
    comparison: pd.DataFrame,
    top_n: int = 10,
) -> pd.DataFrame:
    columns = [
        "period",
        "clock",
        "home_score",
        "away_score",
        "score_margin_home",
        "event_team",
        "event_player",
        "event_description",
        "baseline_home_win_prob_pct",
        "logistic_ml_home_win_prob_pct",
        "advanced_ml_home_win_prob_pct",
        "logistic_minus_baseline_pct",
        "advanced_minus_baseline_pct",
        "advanced_minus_logistic_pct",
        "max_model_disagreement_pct",
    ]

    return (
        comparison.sort_values("max_model_disagreement_pct", ascending=False)
        [columns]
        .head(top_n)
        .reset_index(drop=True)
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Compare baseline, logistic ML, and advanced ML predictions."
    )

    parser.add_argument(
        "--game-id",
        type=str,
        default=None,
        help="Specific game ID to compare. If omitted, uses the latest available shared game.",
    )

    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of biggest disagreement moments to show.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    available_game_ids = get_available_game_ids()

    if not available_game_ids:
        raise FileNotFoundError(
            "No games found with baseline, logistic ML, and advanced ML predictions. Run:\n"
            "python src/run_pipeline.py --game-id YOUR_GAME_ID --model baseline\n"
            "python src/run_pipeline.py --game-id YOUR_GAME_ID --model ml\n"
            "python src/run_pipeline.py --game-id YOUR_GAME_ID --model advanced"
        )

    if args.game_id:
        game_id = str(args.game_id).zfill(10)
    else:
        game_id = available_game_ids[-1]

    if game_id not in available_game_ids:
        raise ValueError(
            f"Game {game_id} does not have all three prediction files.\n"
            f"Available game IDs: {available_game_ids}"
        )

    print(f"Comparing models for game: {game_id}")

    predictions = load_predictions(game_id)
    comparison = compare_predictions(predictions)

    summary = build_summary(comparison)
    disagreements = get_biggest_disagreements(comparison, top_n=args.top_n)

    comparison_path = REPORTS_DIR / f"model_comparison_{game_id}.csv"
    summary_path = REPORTS_DIR / f"model_comparison_summary_{game_id}.csv"
    disagreements_path = REPORTS_DIR / f"model_disagreements_{game_id}.csv"

    comparison.to_csv(comparison_path, index=False)
    summary.to_csv(summary_path, index=False)
    disagreements.to_csv(disagreements_path, index=False)

    print("\nSuccess.")
    print(f"Saved full comparison to: {comparison_path}")
    print(f"Saved summary to: {summary_path}")
    print(f"Saved biggest disagreements to: {disagreements_path}")

    print("\nModel comparison summary:")
    print(summary.to_string(index=False))

    print("\nBiggest disagreement moments:")
    print(disagreements.to_string(index=False))


if __name__ == "__main__":
    main()