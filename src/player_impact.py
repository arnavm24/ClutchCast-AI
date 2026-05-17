import argparse
from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build player win-probability swing report.")
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


def load_predictions(game_id: str | None = None) -> pd.DataFrame:
    input_path = get_prediction_path(game_id)
    print(f"Loading predictions from: {input_path}")
    return pd.read_csv(input_path, dtype={"game_id": str})


def calculate_player_swing_impact(df: pd.DataFrame) -> pd.DataFrame:
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
    data = data[data["event_player"].notna()]
    data = data[data["event_player"].astype(str).str.strip() != ""]

    if data.empty:
        raise ValueError("No player events found in prediction data.")

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
    args = parse_args()
    predictions = load_predictions(args.game_id)
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
