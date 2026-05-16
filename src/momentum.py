from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_comeback_metrics() -> pd.DataFrame:
    """
    Loads the comeback metrics file.

    This file should already include:
    - baseline win probability
    - clutch pressure
    - comeback metrics
    """
    files = list(PROCESSED_DIR.glob("comeback_metrics_*.csv"))

    if not files:
        raise FileNotFoundError(
            "No comeback metrics files found. Run src/comeback_meter.py first."
        )

    input_path = files[0]
    print(f"Loading comeback metrics from: {input_path}")

    return pd.read_csv(input_path, dtype={"game_id": str})


def classify_event_value(description: str) -> int:
    """
    Gives a simple event value based on the play description.

    Positive values generally indicate successful offensive/defensive events.
    Negative values generally indicate empty possessions or mistakes.

    This is a V1 heuristic, not a perfect basketball model.
    """
    desc = str(description).lower()

    if "turnover" in desc:
        return -3

    if "miss" in desc:
        return -1

    if "3pt" in desc and "miss" not in desc:
        return 4

    if "free throw" in desc and "miss" not in desc:
        return 1

    if any(word in desc for word in ["layup", "dunk", "jump shot", "hook shot"]):
        if "miss" not in desc:
            return 2

    if "steal" in desc:
        return 3

    if "block" in desc:
        return 2

    if "rebound" in desc and "off:" in desc:
        return 2

    return 0


def add_event_value(df: pd.DataFrame) -> pd.DataFrame:
    """
    Adds a simple event_value column from the play description.
    """
    output = df.copy()
    output["event_value"] = output["event_description"].apply(classify_event_value)
    return output


def add_recent_score_margin_change(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """
    Calculates how much the home team's score margin changed over the last N events.
    """
    output = df.copy()

    output["recent_margin_change"] = (
        output["score_margin_home"] - output["score_margin_home"].shift(window)
    ).fillna(0)

    return output


def add_recent_wp_momentum(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """
    Calculates recent home-team win probability momentum over the last N events.
    """
    output = df.copy()

    output["recent_wp_change_pct"] = (
        (output["home_win_prob"] - output["home_win_prob"].shift(window)) * 100
    ).fillna(0).round(2)

    return output


def add_recent_event_value(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """
    Calculates rolling recent event value.
    """
    output = df.copy()

    output["recent_event_value"] = (
        output["event_value"].rolling(window=window, min_periods=1).sum()
    )

    return output


def calculate_hidden_momentum(row: pd.Series) -> float:
    """
    Calculates a hidden momentum score from -100 to +100.

    Positive = home team momentum.
    Negative = away team momentum.

    Inputs:
    - recent score margin change
    - recent win probability change
    - recent event value
    """
    margin_component = row["recent_margin_change"] * 5
    wp_component = row["recent_wp_change_pct"] * 2
    event_component = row["recent_event_value"] * 2

    raw_score = margin_component + wp_component + event_component

    return round(max(-100, min(100, raw_score)), 1)


def classify_momentum(score: float) -> str:
    """
    Converts hidden momentum score into a readable label.
    """
    if score >= 50:
        return "Strong home momentum"
    if score >= 20:
        return "Home momentum"
    if score > -20:
        return "Neutral"
    if score > -50:
        return "Away momentum"
    return "Strong away momentum"


def add_hidden_momentum(df: pd.DataFrame, window: int = 10) -> pd.DataFrame:
    """
    Adds hidden momentum metrics to the dataframe.
    """
    required_columns = [
        "score_margin_home",
        "home_win_prob",
        "event_description",
    ]

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    output = df.copy()

    output = add_event_value(output)
    output = add_recent_score_margin_change(output, window=window)
    output = add_recent_wp_momentum(output, window=window)
    output = add_recent_event_value(output, window=window)

    output["hidden_momentum_score"] = output.apply(calculate_hidden_momentum, axis=1)
    output["momentum_label"] = output["hidden_momentum_score"].apply(classify_momentum)

    return output


def get_biggest_momentum_swings(df: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    """
    Finds moments where hidden momentum is strongest.
    """
    output = df.copy()
    output["abs_hidden_momentum"] = output["hidden_momentum_score"].abs()

    columns = [
        "period",
        "clock",
        "home_score",
        "away_score",
        "score_margin_home",
        "home_win_prob_pct",
        "recent_margin_change",
        "recent_wp_change_pct",
        "recent_event_value",
        "hidden_momentum_score",
        "momentum_label",
        "event_description",
    ]

    return (
        output.sort_values("abs_hidden_momentum", ascending=False)
        [columns]
        .head(top_n)
        .reset_index(drop=True)
    )


def main() -> None:
    data = load_comeback_metrics()
    game_id = str(data["game_id"].iloc[0]).zfill(10)

    output = add_hidden_momentum(data, window=10)

    output_path = PROCESSED_DIR / f"momentum_{game_id}.csv"
    output.to_csv(output_path, index=False)

    report = get_biggest_momentum_swings(output, top_n=10)
    report_path = REPORTS_DIR / f"momentum_report_{game_id}.csv"
    report.to_csv(report_path, index=False)

    print("\nSuccess.")
    print(f"Saved momentum data to: {output_path}")
    print(f"Saved momentum report to: {report_path}")

    print("\nBiggest hidden momentum moments:")
    print(report)


if __name__ == "__main__":
    main()