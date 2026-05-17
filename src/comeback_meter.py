import argparse
from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build comeback metrics from feature data.")
    parser.add_argument("--game-id", type=str, default=None)
    return parser.parse_args()


def get_feature_path(game_id: str | None) -> Path:
    if game_id:
        normalized_game_id = str(game_id).zfill(10)
        input_path = PROCESSED_DIR / f"features_{normalized_game_id}.csv"

        if not input_path.exists():
            raise FileNotFoundError(
                f"Missing feature file for game {normalized_game_id}: {input_path}\n"
                f"Run: python src/features.py --game-id {normalized_game_id}"
            )

        return input_path

    files = sorted(PROCESSED_DIR.glob("features_*.csv"))

    if not files:
        raise FileNotFoundError("No feature files found. Run src/features.py first.")

    input_path = files[-1]
    print(f"No --game-id provided. Using latest feature file: {input_path}")
    return input_path


def load_feature_file(game_id: str | None = None) -> pd.DataFrame:
    """
    Loads the feature file created by src/features.py.
    """
    input_path = get_feature_path(game_id)
    print(f"Loading feature file from: {input_path}")
    return pd.read_csv(input_path, dtype={"game_id": str})


def classify_comeback_status(comeback_probability: float) -> str:
    if comeback_probability >= 0.40:
        return "Very realistic"
    if comeback_probability >= 0.25:
        return "Possible"
    if comeback_probability >= 0.10:
        return "Difficult"
    if comeback_probability >= 0.03:
        return "Very unlikely"
    return "Nearly impossible"


def calculate_required_scoring_rate(deficit: int, seconds_remaining: int) -> float:
    if deficit <= 0:
        return 0.0

    minutes_remaining = max(seconds_remaining / 60, 0.01)
    return round(deficit / minutes_remaining, 2)


def add_comeback_metrics(df: pd.DataFrame) -> pd.DataFrame:
    required_columns = [
        "game_id",
        "period",
        "clock",
        "seconds_remaining",
        "home_score",
        "away_score",
        "score_margin_home",
        "home_win_prob",
        "away_win_prob",
        "home_win_prob_pct",
        "away_win_prob_pct",
        "clutch_pressure",
        "pressure_level",
        "event_description",
    ]

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    output = df.copy()

    output["trailing_team"] = "Tie"
    output.loc[output["score_margin_home"] < 0, "trailing_team"] = "Home"
    output.loc[output["score_margin_home"] > 0, "trailing_team"] = "Away"

    output["deficit"] = output["score_margin_home"].abs()
    output["comeback_probability"] = 0.0

    home_trailing = output["score_margin_home"] < 0
    output.loc[home_trailing, "comeback_probability"] = output.loc[
        home_trailing, "home_win_prob"
    ]

    away_trailing = output["score_margin_home"] > 0
    output.loc[away_trailing, "comeback_probability"] = output.loc[
        away_trailing, "away_win_prob"
    ]

    tied = output["score_margin_home"] == 0
    output.loc[tied, "comeback_probability"] = 0.5

    output["comeback_probability_pct"] = (
        output["comeback_probability"] * 100
    ).round(1)

    output["comeback_status"] = output["comeback_probability"].apply(
        classify_comeback_status
    )

    output["required_points_per_minute"] = output.apply(
        lambda row: calculate_required_scoring_rate(
            int(row["deficit"]),
            int(row["seconds_remaining"]),
        ),
        axis=1,
    )

    return output


def get_most_interesting_comeback_windows(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    comeback_rows = df[
        (df["trailing_team"] != "Tie")
        & (df["seconds_remaining"] > 0)
        & (df["deficit"] >= 5)
    ].copy()

    if comeback_rows.empty:
        return pd.DataFrame()

    comeback_rows["interest_score"] = (
        comeback_rows["deficit"] * 0.45
        + comeback_rows["clutch_pressure"] * 0.35
        + comeback_rows["comeback_probability_pct"] * 0.20
    )

    columns = [
        "period",
        "clock",
        "home_score",
        "away_score",
        "trailing_team",
        "deficit",
        "comeback_probability_pct",
        "comeback_status",
        "required_points_per_minute",
        "clutch_pressure",
        "pressure_level",
        "event_description",
    ]

    return (
        comeback_rows.sort_values("interest_score", ascending=False)
        [columns]
        .head(top_n)
        .reset_index(drop=True)
    )


def main() -> None:
    args = parse_args()
    features = load_feature_file(args.game_id)
    game_id = str(features["game_id"].iloc[0]).zfill(10)

    output = add_comeback_metrics(features)

    output_path = PROCESSED_DIR / f"comeback_metrics_{game_id}.csv"
    output.to_csv(output_path, index=False)

    report = get_most_interesting_comeback_windows(output, top_n=10)
    report_path = REPORTS_DIR / f"comeback_report_{game_id}.csv"
    report.to_csv(report_path, index=False)

    print("\nSuccess.")
    print(f"Saved comeback metrics to: {output_path}")
    print(f"Saved comeback report to: {report_path}")

    print("\nMost interesting comeback windows:")
    print(report)


if __name__ == "__main__":
    main()
