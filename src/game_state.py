import argparse
from pathlib import Path
import re

import pandas as pd


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build a game-state table from raw NBA play-by-play.")
    parser.add_argument(
        "--game-id",
        type=str,
        default=None,
        help="Specific NBA game ID to process, example: 0042300312.",
    )
    return parser.parse_args()


def get_input_path(game_id: str | None) -> Path:
    if game_id:
        normalized_game_id = str(game_id).zfill(10)
        input_path = RAW_DIR / f"play_by_play_{normalized_game_id}.csv"

        if not input_path.exists():
            raise FileNotFoundError(
                f"Missing raw play-by-play file for game {normalized_game_id}: {input_path}\n"
                f"Run: python src/load_data.py --game-id {normalized_game_id}"
            )

        return input_path

    files = sorted(RAW_DIR.glob("play_by_play_*.csv"))

    if not files:
        raise FileNotFoundError("No raw play-by-play files found in data/raw.")

    input_path = files[-1]
    print(f"No --game-id provided. Using latest raw play-by-play file: {input_path}")
    return input_path


def parse_clock_to_seconds(clock: str) -> int:
    """
    Converts an NBA clock string into seconds remaining in the current period.

    Example:
    PT11M45.00S -> 705 seconds
    PT05M32.00S -> 332 seconds
    """
    if pd.isna(clock):
        return 0

    clock = str(clock)

    minutes_match = re.search(r"(\d+)M", clock)
    seconds_match = re.search(r"(\d+(?:\.\d+)?)S", clock)

    minutes = int(minutes_match.group(1)) if minutes_match else 0
    seconds = float(seconds_match.group(1)) if seconds_match else 0

    return int(minutes * 60 + seconds)


def calculate_game_seconds_remaining(period: int, clock: str) -> int:
    """
    Calculates total seconds remaining in the game.

    NBA regulation has 4 periods of 12 minutes.
    Overtime periods are 5 minutes.

    For V1, overtime just uses the seconds remaining in that overtime period.
    """
    seconds_in_current_period = parse_clock_to_seconds(clock)

    if period <= 4:
        future_regulation_periods = 4 - period
        return seconds_in_current_period + future_regulation_periods * 12 * 60

    return seconds_in_current_period


def build_game_state(input_path: Path) -> pd.DataFrame:
    """
    Converts raw NBA play-by-play rows into model-ready game-state rows.

    Important:
    NBA play-by-play rows do not always repeat the score on every event.
    Some non-scoring events have blank scoreHome/scoreAway values.

    Correct approach:
    - Convert scoreHome/scoreAway to numeric.
    - Forward-fill the last known score.
    - Fill early missing values as 0.
    """
    df = pd.read_csv(input_path, dtype={"gameId": str})

    required_columns = [
        "gameId",
        "actionNumber",
        "clock",
        "period",
        "teamTricode",
        "playerName",
        "description",
        "actionType",
        "scoreHome",
        "scoreAway",
    ]

    missing = [col for col in required_columns if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    game_state = pd.DataFrame()

    game_state["game_id"] = df["gameId"].astype(str).str.zfill(10)
    game_state["event_num"] = df["actionNumber"]
    game_state["period"] = df["period"].astype(int)
    game_state["clock"] = df["clock"]

    game_state["seconds_remaining"] = df.apply(
        lambda row: calculate_game_seconds_remaining(
            int(row["period"]),
            row["clock"],
        ),
        axis=1,
    )

    score_home = (
        pd.to_numeric(df["scoreHome"], errors="coerce")
        .ffill()
        .fillna(0)
        .astype(int)
    )

    score_away = (
        pd.to_numeric(df["scoreAway"], errors="coerce")
        .ffill()
        .fillna(0)
        .astype(int)
    )

    game_state["home_score"] = score_home
    game_state["away_score"] = score_away

    game_state["score_margin_home"] = (
        game_state["home_score"] - game_state["away_score"]
    )
    game_state["abs_score_margin"] = game_state["score_margin_home"].abs()
    game_state["total_score"] = game_state["home_score"] + game_state["away_score"]

    game_state["event_team"] = df["teamTricode"].fillna("")
    game_state["event_player"] = df["playerName"].fillna("")
    game_state["event_description"] = df["description"].fillna("")
    game_state["event_type"] = df["actionType"].fillna("")

    game_state["is_4th_quarter"] = (game_state["period"] == 4).astype(int)

    game_state["is_clutch_time"] = (
        (game_state["period"] >= 4)
        & (game_state["seconds_remaining"] <= 5 * 60)
        & (game_state["abs_score_margin"] <= 5)
    ).astype(int)

    final_home_score = game_state["home_score"].iloc[-1]
    final_away_score = game_state["away_score"].iloc[-1]
    home_won = int(final_home_score > final_away_score)

    game_state["home_won"] = home_won

    return game_state


def main() -> None:
    args = parse_args()
    input_path = get_input_path(args.game_id)
    print(f"Building game-state table from: {input_path}")

    game_state = build_game_state(input_path)

    game_id = str(game_state["game_id"].iloc[0]).zfill(10)
    output_path = PROCESSED_DIR / f"game_state_{game_id}.csv"

    game_state.to_csv(output_path, index=False)

    print("\nSuccess.")
    print(f"Saved processed game-state file to: {output_path}")
    print(f"Rows: {len(game_state)}")
    print(f"Columns: {list(game_state.columns)}")

    print("\nFirst 5 rows:")
    print(game_state.head())

    print("\nFinal score:")
    print(
        game_state[
            [
                "home_score",
                "away_score",
                "score_margin_home",
                "home_won",
            ]
        ].tail(1)
    )


if __name__ == "__main__":
    main()
