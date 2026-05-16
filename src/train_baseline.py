from pathlib import Path
import math

import pandas as pd


PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
FIGURES_DIR = REPORTS_DIR / "figures"

REPORTS_DIR.mkdir(parents=True, exist_ok=True)
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def sigmoid(x: float) -> float:
    """
    Converts any number into a value between 0 and 1.
    This is useful for turning a score/time formula into a probability.
    """
    return 1 / (1 + math.exp(-x))


def baseline_home_win_probability(row: pd.Series) -> float:
    """
    Simple baseline win probability model.

    This is not machine learning yet.

    Logic:
    - Home team leading increases home win probability.
    - A lead matters more when less time is left.
    - Home team gets a small home-court advantage.
    """

    score_margin = row["score_margin_home"]
    seconds_remaining = row["seconds_remaining"]

    total_game_seconds = 48 * 60
    time_elapsed_ratio = 1 - (seconds_remaining / total_game_seconds)
    time_elapsed_ratio = max(0, min(1, time_elapsed_ratio))

    # Lead becomes more important later in the game.
    score_weight = 0.08 + 0.35 * time_elapsed_ratio

    # Small home advantage.
    home_advantage = 0.15

    raw_score = score_weight * score_margin + home_advantage

    probability = sigmoid(raw_score)

    return probability


def add_baseline_predictions(game_state: pd.DataFrame) -> pd.DataFrame:
    """
    Adds baseline home and away win probability columns.
    """
    output = game_state.copy()

    output["home_win_prob"] = output.apply(baseline_home_win_probability, axis=1)
    output["away_win_prob"] = 1 - output["home_win_prob"]

    output["home_win_prob_pct"] = (output["home_win_prob"] * 100).round(1)
    output["away_win_prob_pct"] = (output["away_win_prob"] * 100).round(1)

    output["wp_change"] = output["home_win_prob"].diff().fillna(0)
    output["abs_wp_change"] = output["wp_change"].abs()

    return output


def main() -> None:
    files = list(PROCESSED_DIR.glob("game_state_*.csv"))

    if not files:
        raise FileNotFoundError("No processed game-state files found in data/processed.")

    input_path = files[0]
    print(f"Loading game-state file: {input_path}")

    game_state = pd.read_csv(input_path, dtype={"game_id": str})

    predictions = add_baseline_predictions(game_state)

    game_id = str(predictions["game_id"].iloc[0]).zfill(10)
    output_path = PROCESSED_DIR / f"baseline_predictions_{game_id}.csv"

    predictions.to_csv(output_path, index=False)

    print("\nSuccess.")
    print(f"Saved baseline predictions to: {output_path}")
    print(f"Rows: {len(predictions)}")

    print("\nSample columns:")
    print(
        predictions[
            [
                "period",
                "clock",
                "home_score",
                "away_score",
                "score_margin_home",
                "home_win_prob_pct",
                "away_win_prob_pct",
                "wp_change",
            ]
        ].head(10)
    )

    print("\nFinal row:")
    print(
        predictions[
            [
                "period",
                "clock",
                "home_score",
                "away_score",
                "score_margin_home",
                "home_win_prob_pct",
                "away_win_prob_pct",
                "home_won",
            ]
        ].tail(1)
    )


if __name__ == "__main__":
    main()