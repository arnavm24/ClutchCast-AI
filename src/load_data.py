from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import leaguegamefinder, playbyplayv3


RAW_DIR = Path("data/raw")
RAW_DIR.mkdir(parents=True, exist_ok=True)


def get_recent_game_id(season: str = "2023-24") -> str:
    """
    Gets a recent completed NBA game ID from a chosen season.

    We use LeagueGameFinder first because it gives us valid NBA game IDs.
    Then we use that game ID to fetch play-by-play data.
    """
    print(f"Fetching games from season {season}...")

    finder = leaguegamefinder.LeagueGameFinder(
        season_nullable=season,
        league_id_nullable="00",
        season_type_nullable="Regular Season",
        timeout=30,
    )

    games = finder.get_data_frames()[0]

    if games.empty:
        raise ValueError("No games found. Try another season like 2022-23 or 2024-25.")

    # Keep only one row per GAME_ID because each game can appear twice, once for each team.
    games = games.drop_duplicates(subset=["GAME_ID"])

    # Sort by date so we pick a recent game from that season.
    games = games.sort_values("GAME_DATE", ascending=False)

    selected_game = games.iloc[0]

    game_id = str(selected_game["GAME_ID"])
    matchup = selected_game["MATCHUP"]
    game_date = selected_game["GAME_DATE"]

    print(f"Selected game: {game_id} | {game_date} | {matchup}")

    return game_id


def fetch_play_by_play(game_id: str) -> pd.DataFrame:
    """
    Fetches play-by-play event logs for one NBA game.
    """
    print(f"Fetching play-by-play for game ID {game_id}...")

    pbp = playbyplayv3.PlayByPlayV3(
        game_id=game_id,
        timeout=30,
    )

    df = pbp.get_data_frames()[0]

    if df.empty:
        raise ValueError("Play-by-play data came back empty.")

    return df


def main() -> None:
    game_id = get_recent_game_id(season="2023-24")
    pbp_df = fetch_play_by_play(game_id)

    output_path = RAW_DIR / f"play_by_play_{game_id}.csv"
    pbp_df.to_csv(output_path, index=False)

    print("\nSuccess.")
    print(f"Saved play-by-play file to: {output_path}")
    print(f"Rows: {len(pbp_df)}")
    print(f"Columns: {list(pbp_df.columns)}")


if __name__ == "__main__":
    main()