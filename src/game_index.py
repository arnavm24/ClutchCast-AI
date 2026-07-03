"""Build reports/game_index.csv — offline metadata for every game in the training dataset.

Used by the dashboard sidebar for game search, demo games, and offline team labels.

Run: python src/game_index.py
"""

from pathlib import Path

import numpy as np
import pandas as pd

PROCESSED_DIR = Path("data/processed")
RAW_DIR = Path("data/raw")
REPORTS_DIR = Path("reports")

SEASON_TYPE_BY_DIGIT = {"1": "Preseason", "2": "Regular Season", "3": "All-Star", "4": "Playoffs", "5": "Play-In"}

INDEX_COLUMNS = [
    "game_id", "season", "season_type", "home_team", "away_team",
    "final_home_score", "final_away_score", "final_margin", "home_won",
    "max_period", "went_overtime", "n_overtimes", "lead_changes", "tied_states",
    "winner_max_deficit", "playoff_round", "looks_complete", "is_test_game",
]


def season_from_game_id(game_id: str) -> str:
    digits = str(game_id).zfill(10)
    try:
        start_year = 2000 + int(digits[3:5])
    except ValueError:
        return ""
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def season_type_from_game_id(game_id: str) -> str:
    return SEASON_TYPE_BY_DIGIT.get(str(game_id).zfill(10)[2], "Unknown")


def playoff_round_from_game_id(game_id: str) -> int:
    """Playoff ids encode the round at position 7: 004YY00RSG (4 = Finals)."""
    digits = str(game_id).zfill(10)
    if digits[2] != "4":
        return 0
    try:
        return int(digits[7])
    except ValueError:
        return 0


def count_lead_changes(margins: pd.Series) -> int:
    signs = np.sign(margins.to_numpy())
    signs = signs[signs != 0]
    if len(signs) < 2:
        return 0
    return int((np.diff(signs) != 0).sum())


def count_tied_states(margins: pd.Series) -> int:
    values = margins.to_numpy()
    tied = values == 0
    if len(values) < 2:
        return int(tied[0])
    entered_tie = tied[1:] & ~tied[:-1]
    return int(tied[0]) + int(entered_tie.sum())


def teams_from_raw_play_by_play(game_id: str) -> tuple[str, str]:
    """Infer (home, away) tricodes from the raw feed: the team that scores when
    scoreHome increases is the home team. Uses the modal team to absorb noise."""
    path = RAW_DIR / f"play_by_play_{game_id}.csv"
    if not path.exists():
        return "", ""
    try:
        raw = pd.read_csv(path, usecols=["teamTricode", "scoreHome", "scoreAway"], low_memory=False)
    except (ValueError, OSError):
        return "", ""
    raw["teamTricode"] = raw["teamTricode"].fillna("").astype(str).str.strip()
    for column in ("scoreHome", "scoreAway"):
        raw[column] = pd.to_numeric(raw[column], errors="coerce").ffill().fillna(0)
    home_delta = raw["scoreHome"].diff().fillna(0)
    away_delta = raw["scoreAway"].diff().fillna(0)
    home_scorers = raw.loc[(home_delta > 0) & (raw["teamTricode"] != ""), "teamTricode"]
    away_scorers = raw.loc[(away_delta > 0) & (raw["teamTricode"] != ""), "teamTricode"]
    if home_scorers.empty or away_scorers.empty:
        return "", ""
    home = home_scorers.mode().iloc[0]
    away = away_scorers.mode().iloc[0]
    if home == away:
        return "", ""
    return home, away


def load_test_game_ids() -> set[str]:
    path = PROCESSED_DIR / "test_game_ids.txt"
    if not path.exists():
        return set()
    return {line.strip().zfill(10) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()}


def build_game_index() -> pd.DataFrame:
    # Raw play-by-play is the ground truth the per-game pipeline analyzes,
    # so the index is built from the same source to keep finals consistent.
    raw_paths = sorted(RAW_DIR.glob("play_by_play_*.csv"))
    if not raw_paths:
        raise FileNotFoundError(f"No raw play-by-play files in {RAW_DIR}.")
    test_ids = load_test_game_ids()

    rows = []
    for path in raw_paths:
        game_id = path.stem.replace("play_by_play_", "").zfill(10)
        try:
            raw = pd.read_csv(path, usecols=["period", "scoreHome", "scoreAway"], low_memory=False)
        except (ValueError, OSError):
            continue
        if raw.empty:
            continue
        for column in ("scoreHome", "scoreAway"):
            raw[column] = pd.to_numeric(raw[column], errors="coerce").ffill().fillna(0)
        raw["period"] = pd.to_numeric(raw["period"], errors="coerce").ffill().fillna(1)
        margins = raw["scoreHome"] - raw["scoreAway"]
        max_period = int(raw["period"].max())
        home_team, away_team = teams_from_raw_play_by_play(game_id)
        final_home = int(raw["scoreHome"].iloc[-1])
        final_away = int(raw["scoreAway"].iloc[-1])
        home_won = int(final_home > final_away)
        winner_max_deficit = int(max(-margins.min(), 0)) if home_won else int(max(margins.max(), 0))
        rows.append({
            "game_id": game_id,
            "season": season_from_game_id(game_id),
            "season_type": season_type_from_game_id(game_id),
            "home_team": home_team if home_team.lower() != "nan" else "",
            "away_team": away_team if away_team.lower() != "nan" else "",
            "final_home_score": final_home,
            "final_away_score": final_away,
            "final_margin": final_home - final_away,
            "home_won": home_won,
            "max_period": max_period,
            "went_overtime": max_period > 4,
            "n_overtimes": max(max_period - 4, 0),
            "lead_changes": count_lead_changes(margins),
            "tied_states": count_tied_states(margins),
            "winner_max_deficit": winner_max_deficit,
            "playoff_round": playoff_round_from_game_id(game_id),
            # Truncated play-by-play shows up as implausibly low final scores.
            "looks_complete": max_period >= 4 and min(final_home, final_away) >= 70,
            "is_test_game": game_id in test_ids,
        })

    return pd.DataFrame(rows, columns=INDEX_COLUMNS)


def main() -> None:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    index = build_game_index()
    output_path = REPORTS_DIR / "game_index.csv"
    index.to_csv(output_path, index=False)
    labeled = int((index["home_team"] != "").sum())
    print(f"Saved game index to: {output_path}")
    print(f"Games indexed: {len(index)} · with team labels: {labeled} · test games: {int(index['is_test_game'].sum())}")


if __name__ == "__main__":
    main()
