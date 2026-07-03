"""Build leak-free pregame team-strength priors.

For games played in season S, strength = the team's final regular-season win
percentage from season S-1. Prior-season results cannot leak information about
the games being predicted.

Output: data/processed/team_strength.csv with columns team, season, strength —
where `season` is the season the strength applies TO (not the season it was
measured in). model_features.add_team_strength_features maps (team, season).

Run: python src/team_strength.py --apply-to-seasons 2022-23 2023-24
"""

import argparse
import time
from pathlib import Path

import pandas as pd
from nba_api.stats.endpoints import leaguestandingsv3
from nba_api.stats.static import teams as static_teams

PROCESSED_DIR = Path("data/processed")
OUTPUT_PATH = PROCESSED_DIR / "team_strength.csv"


def previous_season(season: str) -> str:
    start_year = int(season[:4]) - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def team_id_to_abbrev() -> dict[int, str]:
    return {team["id"]: team["abbreviation"] for team in static_teams.get_teams()}


def fetch_season_win_pct(season: str) -> pd.DataFrame:
    print(f"Fetching {season} final standings...")
    standings = leaguestandingsv3.LeagueStandingsV3(season=season, season_type="Regular Season", timeout=30)
    frame = standings.get_data_frames()[0]
    id_column = next(column for column in frame.columns if column.lower() == "teamid")
    pct_column = next(column for column in frame.columns if column.lower() in {"winpct", "win_pct", "w_pct"})
    abbrevs = team_id_to_abbrev()
    output = pd.DataFrame({
        "team": frame[id_column].astype(int).map(abbrevs),
        "strength": frame[pct_column].astype(float),
    })
    return output.dropna(subset=["team"])


def main() -> None:
    parser = argparse.ArgumentParser(description="Build prior-season team strength priors.")
    parser.add_argument(
        "--apply-to-seasons",
        nargs="+",
        default=["2022-23", "2023-24"],
        help="Seasons the priors will be used in; strength comes from each season's predecessor.",
    )
    args = parser.parse_args()

    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    frames = []
    for season in args.apply_to_seasons:
        source_season = previous_season(season)
        strengths = fetch_season_win_pct(source_season)
        strengths.insert(1, "season", season)
        frames.append(strengths)
        time.sleep(0.7)

    output = pd.concat(frames, ignore_index=True)
    output.to_csv(OUTPUT_PATH, index=False)
    print(f"\nSaved team strength priors to: {OUTPUT_PATH}")
    print(f"Rows: {len(output)} ({output['season'].nunique()} seasons x {output['team'].nunique()} teams)")
    print(output.groupby('season')['strength'].describe()[['min', 'mean', 'max']].to_string())


if __name__ == "__main__":
    main()
