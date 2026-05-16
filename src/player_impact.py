from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_predictions() -> pd.DataFrame:
    """
    Loads baseline prediction data.
    """
    files = list(PROCESSED_DIR.glob("baseline_predictions_*.csv"))

    if not files:
        raise FileNotFoundError(
            "No baseline prediction files found. Run src/train_baseline.py first."
        )

    input_path = files[0]
    print(f"Loading predictions from: {input_path}")

    return pd.read_csv(input_path, dtype={"game_id": str})


def calculate_player_swing_impact(df: pd.DataFrame) -> pd.DataFrame:
    """
    Calculates each player's win-probability swing impact.

    Positive impact means the player's events increased their team's chance
    of winning or created a favorable swing.

    For V1:
    - If the event team is the home team, positive home WP change helps them.
    - If the event team is the away team, negative home WP change helps them.
    """

    required_columns = [
        "event_team",
        "event_player",
        "wp_change",
        "abs_wp_change",
        "home_score",
        "away_score",
        "event_description",
    ]

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    data = df.copy()

    # Remove rows without a player name.
    data = data[data["event_player"].notna()]
    data = data[data["event_player"].astype(str).str.strip() != ""]

    if data.empty:
        raise ValueError("No player events found in prediction data.")

    # Infer home team as the team attached to home-scoring events is not always direct,
    # so for this V1 we rank raw WP swings tied to player events.
    # Later, we can improve by mapping home/away team IDs exactly.
    data["positive_swing_pct"] = (data["wp_change"] * 100).round(2)
    data["absolute_swing_pct"] = (data["abs_wp_change"] * 100).round(2)

    grouped = (
        data.groupby(["event_player", "event_team"], as_index=False)
        .agg(
            total_raw_home_wp_swing_pct=("positive_swing_pct", "sum"),
            total_absolute_swing_pct=("absolute_swing_pct", "sum"),
            avg_absolute_swing_pct=("absolute_swing_pct", "mean"),
            event_count=("event_player", "count"),
        )
    )

    grouped["total_raw_home_wp_swing_pct"] = grouped[
        "total_raw_home_wp_swing_pct"
    ].round(2)
    grouped["total_absolute_swing_pct"] = grouped[
        "total_absolute_swing_pct"
    ].round(2)
    grouped["avg_absolute_swing_pct"] = grouped[
        "avg_absolute_swing_pct"
    ].round(2)

    grouped = grouped.sort_values(
        "total_absolute_swing_pct",
        ascending=False,
    ).reset_index(drop=True)

    grouped.insert(0, "rank", range(1, len(grouped) + 1))

    return grouped


def get_top_player_events(df: pd.DataFrame, player_name: str, top_n: int = 5) -> pd.DataFrame:
    """
    Shows the player's biggest individual swing events.
    """
    player_events = df[
        df["event_player"].astype(str).str.lower() == player_name.lower()
    ].copy()

    if player_events.empty:
        return pd.DataFrame()

    player_events["swing_pct"] = (player_events["wp_change"] * 100).round(2)
    player_events["absolute_swing_pct"] = (player_events["abs_wp_change"] * 100).round(2)

    columns = [
        "period",
        "clock",
        "home_score",
        "away_score",
        "event_team",
        "event_player",
        "event_description",
        "home_win_prob_pct",
        "swing_pct",
        "absolute_swing_pct",
    ]

    return (
        player_events.sort_values("absolute_swing_pct", ascending=False)
        [columns]
        .head(top_n)
        .reset_index(drop=True)
    )


def main() -> None:
    predictions = load_predictions()
    game_id = str(predictions["game_id"].iloc[0]).zfill(10)

    player_impact = calculate_player_swing_impact(predictions)

    output_path = REPORTS_DIR / f"player_impact_{game_id}.csv"
    player_impact.to_csv(output_path, index=False)

    print("\nSuccess.")
    print(f"Saved player impact report to: {output_path}")

    print("\nTop player swing impact:")
    print(player_impact.head(10))

    top_player = player_impact.iloc[0]["event_player"]
    top_events = get_top_player_events(predictions, top_player, top_n=5)

    print(f"\nBiggest individual events for {top_player}:")
    print(top_events)


if __name__ == "__main__":
    main()