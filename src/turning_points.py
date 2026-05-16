from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_predictions() -> pd.DataFrame:
    """
    Loads the baseline win probability predictions file.
    """
    files = list(PROCESSED_DIR.glob("baseline_predictions_*.csv"))

    if not files:
        raise FileNotFoundError(
            "No baseline prediction files found. Run src/train_baseline.py first."
        )

    input_path = files[0]
    print(f"Loading predictions from: {input_path}")

    return pd.read_csv(input_path, dtype={"game_id": str})


def find_turning_points(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """
    Finds the biggest win-probability swings in a game.

    A turning point is defined as a play/event where the home team's
    win probability changed the most compared to the previous event.
    """
    required_columns = [
        "game_id",
        "period",
        "clock",
        "home_score",
        "away_score",
        "score_margin_home",
        "event_team",
        "event_player",
        "event_description",
        "home_win_prob",
        "home_win_prob_pct",
        "wp_change",
        "abs_wp_change",
    ]

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    turning_points = df.copy()

    turning_points["wp_before_pct"] = (
        turning_points["home_win_prob"].shift(1).fillna(turning_points["home_win_prob"])
        * 100
    ).round(1)

    turning_points["wp_after_pct"] = turning_points["home_win_prob_pct"]

    turning_points["wp_swing_pct"] = (
        turning_points["wp_after_pct"] - turning_points["wp_before_pct"]
    ).round(1)

    # Ignore events with no real win probability movement.
    turning_points = turning_points[turning_points["abs_wp_change"] > 0]

    turning_points = turning_points.sort_values(
        "abs_wp_change",
        ascending=False,
    ).head(top_n)

    output_columns = [
        "period",
        "clock",
        "home_score",
        "away_score",
        "score_margin_home",
        "event_team",
        "event_player",
        "event_description",
        "wp_before_pct",
        "wp_after_pct",
        "wp_swing_pct",
    ]

    return turning_points[output_columns].reset_index(drop=True)


def main() -> None:
    predictions = load_predictions()
    game_id = str(predictions["game_id"].iloc[0]).zfill(10)

    turning_points = find_turning_points(predictions, top_n=10)

    output_path = REPORTS_DIR / f"turning_points_{game_id}.csv"
    turning_points.to_csv(output_path, index=False)

    print("\nSuccess.")
    print(f"Saved turning points to: {output_path}")
    print("\nTop turning points:")
    print(turning_points)


if __name__ == "__main__":
    main()