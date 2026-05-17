import argparse
from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add clutch pressure features to predictions.")
    parser.add_argument("--game-id", type=str, default=None)
    return parser.parse_args()


def get_prediction_path(game_id: str | None) -> Path:
    if game_id:
        normalized_game_id = str(game_id).zfill(10)
        input_path = PROCESSED_DIR / f"baseline_predictions_{normalized_game_id}.csv"

        if not input_path.exists():
            raise FileNotFoundError(
                f"Missing baseline predictions for game {normalized_game_id}: {input_path}\n"
                f"Run: python src/train_baseline.py --game-id {normalized_game_id}"
            )

        return input_path

    files = sorted(PROCESSED_DIR.glob("baseline_predictions_*.csv"))

    if not files:
        raise FileNotFoundError(
            "No baseline prediction files found. Run src/train_baseline.py first."
        )

    input_path = files[-1]
    print(f"No --game-id provided. Using latest baseline predictions file: {input_path}")
    return input_path


def calculate_closeness_score(abs_score_margin: float) -> float:
    """
    Returns a 0 to 1 score for how close the game is.

    0-point margin = 1.0
    5-point margin = still high pressure
    20+ point margin = low pressure
    """
    return max(0.0, 1.0 - (abs_score_margin / 20.0))


def calculate_time_pressure(seconds_remaining: float) -> float:
    """
    Returns a 0 to 1 score for how much time pressure exists.

    Early game = low pressure
    Late game = high pressure
    """
    total_game_seconds = 48 * 60
    elapsed_ratio = 1.0 - (seconds_remaining / total_game_seconds)
    return max(0.0, min(1.0, elapsed_ratio))


def calculate_uncertainty_score(home_win_prob: float) -> float:
    """
    Returns a 0 to 1 score for how uncertain the game outcome is.

    Win probability near 50% = highest uncertainty.
    Win probability near 0% or 100% = lowest uncertainty.
    """
    return 1.0 - min(1.0, abs(home_win_prob - 0.5) / 0.5)


def calculate_clutch_pressure(row: pd.Series) -> float:
    """
    Calculates a 0 to 100 clutch pressure score for one play/event.

    Pressure is high when:
    - score is close
    - game is late
    - win probability is uncertain
    """
    closeness = calculate_closeness_score(row["abs_score_margin"])
    time_pressure = calculate_time_pressure(row["seconds_remaining"])
    uncertainty = calculate_uncertainty_score(row["home_win_prob"])

    pressure = (
        0.40 * closeness
        + 0.35 * time_pressure
        + 0.25 * uncertainty
    )

    return round(pressure * 100, 1)


def add_clutch_pressure(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds clutch pressure columns to a prediction dataframe.
    """
    output = df.copy()

    required_columns = [
        "abs_score_margin",
        "seconds_remaining",
        "home_win_prob",
    ]

    missing = [col for col in required_columns if col not in output.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    output["clutch_pressure"] = output.apply(calculate_clutch_pressure, axis=1)

    output["pressure_level"] = pd.cut(
        output["clutch_pressure"],
        bins=[-1, 25, 50, 75, 100],
        labels=["Low", "Medium", "High", "Extreme"],
    )

    return output


def main() -> None:
    args = parse_args()
    input_path = get_prediction_path(args.game_id)
    print(f"Loading predictions from: {input_path}")

    predictions = pd.read_csv(input_path, dtype={"game_id": str})
    output = add_clutch_pressure(predictions)

    game_id = str(output["game_id"].iloc[0]).zfill(10)
    output_path = PROCESSED_DIR / f"features_{game_id}.csv"
    output.to_csv(output_path, index=False)

    print("\nSuccess.")
    print(f"Saved feature file to: {output_path}")

    print("\nHighest-pressure moments:")
    print(
        output.sort_values("clutch_pressure", ascending=False)[
            [
                "period",
                "clock",
                "home_score",
                "away_score",
                "score_margin_home",
                "home_win_prob_pct",
                "clutch_pressure",
                "pressure_level",
                "event_description",
            ]
        ].head(10)
    )


if __name__ == "__main__":
    main()
