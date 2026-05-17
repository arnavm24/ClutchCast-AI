from pathlib import Path
import argparse
import time

import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder, playbyplayv3

from game_state import build_game_state


RAW_DIR = Path("data/raw")
PROCESSED_DIR = Path("data/processed")
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)


def get_game_ids(
    season: str,
    season_type: str,
    max_games: int,
) -> list[str]:
    """
    Gets unique NBA game IDs for a given season.

    Each NBA game usually appears twice in LeagueGameFinder,
    once from each team's perspective, so we drop duplicates.
    """
    print(f"Fetching game list for {season} {season_type}...")

    finder = leaguegamefinder.LeagueGameFinder(
        season_nullable=season,
        league_id_nullable="00",
        season_type_nullable=season_type,
        timeout=30,
    )

    games = finder.get_data_frames()[0]

    if games.empty:
        raise ValueError("No games found.")

    games["GAME_ID"] = games["GAME_ID"].astype(str).str.zfill(10)
    games = games.drop_duplicates(subset=["GAME_ID"])
    games = games.sort_values("GAME_DATE", ascending=False)

    game_ids = games["GAME_ID"].head(max_games).tolist()

    print(f"Found {len(game_ids)} games to process.")

    return game_ids


def fetch_play_by_play(game_id: str) -> pd.DataFrame:
    """
    Downloads play-by-play data for one game.
    """
    game_id = str(game_id).zfill(10)

    pbp = playbyplayv3.PlayByPlayV3(
        game_id=game_id,
        timeout=30,
    )

    df = pbp.get_data_frames()[0]

    if df.empty:
        raise ValueError(f"Play-by-play data was empty for game {game_id}.")

    return df


def process_game(game_id: str) -> pd.DataFrame:
    """
    Downloads one game, saves the raw file, builds the game-state table,
    and returns the processed dataframe.
    """
    game_id = str(game_id).zfill(10)

    print("\n" + "-" * 80)
    print(f"Processing game {game_id}")
    print("-" * 80)

    raw_path = RAW_DIR / f"play_by_play_{game_id}.csv"

    if raw_path.exists():
        print(f"Raw file already exists. Loading: {raw_path}")
        pbp_df = pd.read_csv(raw_path, dtype={"gameId": str})
    else:
        print(f"Downloading play-by-play for {game_id}...")
        pbp_df = fetch_play_by_play(game_id)
        pbp_df.to_csv(raw_path, index=False)
        print(f"Saved raw file to: {raw_path}")

    game_state = build_game_state(raw_path)

    game_state["game_id"] = game_state["game_id"].astype(str).str.zfill(10)

    print(f"Processed rows: {len(game_state)}")
    print(
        "Final score:",
        int(game_state["home_score"].iloc[-1]),
        "-",
        int(game_state["away_score"].iloc[-1]),
    )

    return game_state


def build_training_dataset(
    season: str,
    season_type: str,
    max_games: int,
    sleep_seconds: float,
) -> pd.DataFrame:
    """
    Builds one combined training dataset from many games.
    """
    game_ids = get_game_ids(
        season=season,
        season_type=season_type,
        max_games=max_games,
    )

    all_games = []

    failed_games = []

    for index, game_id in enumerate(game_ids, start=1):
        print(f"\nGame {index}/{len(game_ids)}")

        try:
            game_state = process_game(game_id)
            all_games.append(game_state)
        except Exception as error:
            print(f"Failed to process game {game_id}: {error}")
            failed_games.append(game_id)

        # Be polite to the NBA API so we do not spam requests.
        time.sleep(sleep_seconds)

    if not all_games:
        raise RuntimeError("No games were processed successfully.")

    training_data = pd.concat(all_games, ignore_index=True)

    print("\n" + "=" * 80)
    print("Training dataset complete.")
    print(f"Successful games: {len(all_games)}")
    print(f"Failed games: {len(failed_games)}")
    print(f"Total rows: {len(training_data)}")
    print("=" * 80)

    if failed_games:
        print("Failed game IDs:")
        for game_id in failed_games:
            print(game_id)

    return training_data


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build a ClutchCast AI training dataset from many NBA games."
    )

    parser.add_argument(
        "--season",
        type=str,
        default="2023-24",
        help="NBA season, example: 2023-24.",
    )

    parser.add_argument(
        "--season-type",
        type=str,
        default="Regular Season",
        choices=["Regular Season", "Playoffs", "Pre Season", "All Star"],
        help="Season type.",
    )

    parser.add_argument(
        "--max-games",
        type=int,
        default=25,
        help="Maximum number of games to process.",
    )

    parser.add_argument(
        "--sleep-seconds",
        type=float,
        default=0.7,
        help="Pause between NBA API requests.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    training_data = build_training_dataset(
        season=args.season,
        season_type=args.season_type,
        max_games=args.max_games,
        sleep_seconds=args.sleep_seconds,
    )

    output_path = PROCESSED_DIR / "training_dataset.csv"
    training_data.to_csv(output_path, index=False)

    print(f"\nSaved training dataset to: {output_path}")
    print(f"Rows: {len(training_data)}")
    print(f"Columns: {list(training_data.columns)}")


if __name__ == "__main__":
    main()