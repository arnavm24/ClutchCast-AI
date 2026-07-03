import json
from pathlib import Path

import pandas as pd
import streamlit as st

from ui.config import DEMO_GAMES_PATH, MODE_FILES, PROCESSED_DIR, RAW_DIR, REPORTS_DIR


def get_available_game_ids() -> list[str]:
    game_ids = set()
    for pattern in MODE_FILES.values():
        prefix, suffix = pattern.split("{game_id}")
        for file in PROCESSED_DIR.glob(pattern.format(game_id="*")):
            game_ids.add(file.name.replace(prefix, "").replace(suffix, ""))
    return sorted(game_ids)


def get_available_modes(game_id: str) -> list[str]:
    return [mode for mode, pattern in MODE_FILES.items() if (PROCESSED_DIR / pattern.format(game_id=game_id)).exists()]


def load_csv_if_exists(path: Path) -> pd.DataFrame:
    if path.exists():
        return pd.read_csv(path, dtype={"game_id": str})
    return pd.DataFrame()


def get_prediction_path(game_id: str, model_key: str) -> Path:
    return PROCESSED_DIR / MODE_FILES[model_key].format(game_id=game_id)


@st.cache_data(show_spinner=False, ttl=60)
def load_game_index() -> pd.DataFrame:
    return load_csv_if_exists(REPORTS_DIR / "game_index.csv")


@st.cache_data(show_spinner=False)
def get_team_labels(game_id: str) -> tuple[str, str]:
    index = load_game_index()
    if not index.empty and {"game_id", "home_team", "away_team"}.issubset(index.columns):
        rows = index[index["game_id"].astype(str) == str(game_id)]
        if not rows.empty:
            home = str(rows.iloc[0]["home_team"]).strip()
            away = str(rows.iloc[0]["away_team"]).strip()
            if home and away and home.lower() != "nan" and away.lower() != "nan":
                return home, away
    try:
        from nba_api.stats.endpoints import boxscoresummaryv2

        summary = boxscoresummaryv2.BoxScoreSummaryV2(game_id=game_id, timeout=30)
        try:
            line_score = summary.line_score.get_data_frame()
        except AttributeError:
            line_score = summary.get_data_frames()[5]
        if len(line_score) >= 2:
            away_team = str(line_score.iloc[0]["TEAM_ABBREVIATION"])
            home_team = str(line_score.iloc[1]["TEAM_ABBREVIATION"])
            return home_team, away_team
    except Exception:
        pass
    return "Home", "Away"


def load_dashboard_data(game_id: str, model_key: str) -> dict:
    insights_md_path = REPORTS_DIR / f"game_insights_{game_id}.md"
    recap_path = REPORTS_DIR / f"post_game_recap_{game_id}.md"
    return {
        "predictions": pd.read_csv(get_prediction_path(game_id, model_key), dtype={"game_id": str}),
        "comparison_summary": load_csv_if_exists(REPORTS_DIR / f"model_comparison_summary_{game_id}.csv"),
        "model_disagreements": load_csv_if_exists(REPORTS_DIR / f"model_disagreements_{game_id}.csv"),
        "leaderboard": load_csv_if_exists(REPORTS_DIR / "model_leaderboard.csv"),
        "game_insights": load_csv_if_exists(REPORTS_DIR / f"game_insights_{game_id}.csv"),
        "turning_points": load_csv_if_exists(REPORTS_DIR / f"turning_points_{game_id}.csv"),
        "player_impact": load_csv_if_exists(REPORTS_DIR / f"player_impact_{game_id}.csv"),
        "comeback_report": load_csv_if_exists(REPORTS_DIR / f"comeback_report_{game_id}.csv"),
        "momentum_report": load_csv_if_exists(REPORTS_DIR / f"momentum_report_{game_id}.csv"),
        "game_insights_md": insights_md_path.read_text(encoding="utf-8") if insights_md_path.exists() else "",
        "recap": recap_path.read_text(encoding="utf-8") if recap_path.exists() else "No recap file found.",
    }


@st.cache_data(show_spinner=False, ttl=60)
def load_demo_games() -> list[dict]:
    if not DEMO_GAMES_PATH.exists():
        return []
    try:
        payload = json.loads(DEMO_GAMES_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []
    return payload.get("demos", [])


@st.cache_data(show_spinner=False, ttl=60)
def load_drama_leaderboard() -> pd.DataFrame:
    rows = []
    for path in REPORTS_DIR.glob("game_insights_*.csv"):
        insights = load_csv_if_exists(path)
        if insights.empty or "insight" not in insights.columns:
            continue
        drama = insights[insights["insight"] == "Game Drama Score"]
        if drama.empty:
            continue
        game_id = str(drama.iloc[0].get("game_id", path.stem.replace("game_insights_", "")))
        try:
            score = float(drama.iloc[0]["value"])
        except (TypeError, ValueError):
            continue
        rows.append({"game_id": game_id, "drama_score": score})
    if not rows:
        return pd.DataFrame()
    board = pd.DataFrame(rows)
    index = load_game_index()
    if not index.empty and "game_id" in index.columns:
        index = index.copy()
        index["game_id"] = index["game_id"].astype(str)
        board = board.merge(index, on="game_id", how="left")
    return board.sort_values("drama_score", ascending=False).reset_index(drop=True)


@st.cache_data(show_spinner=False)
def load_player_id_map(game_id: str) -> dict:
    """Map (last-name-style event_player, team tricode) -> NBA personId from the raw play-by-play."""
    path = RAW_DIR / f"play_by_play_{game_id}.csv"
    if not path.exists():
        return {}
    try:
        raw = pd.read_csv(path, usecols=["personId", "playerName", "teamTricode"])
    except (ValueError, OSError):
        return {}
    raw = raw[(raw["personId"].fillna(0) > 0) & raw["playerName"].notna()]
    if raw.empty:
        return {}
    raw["playerName"] = raw["playerName"].astype(str).str.strip()
    raw["teamTricode"] = raw["teamTricode"].fillna("").astype(str).str.strip()
    mapping = {}
    grouped = raw.groupby(["playerName", "teamTricode"])["personId"]
    for (name, team), ids in grouped:
        mapping[(name, team)] = int(ids.mode().iloc[0])
    return mapping


def lookup_player_id(player_map: dict, player_name: str, team: str) -> int | None:
    if not player_map:
        return None
    key = (str(player_name).strip(), str(team).strip())
    if key in player_map:
        return player_map[key]
    # event_player may be a shortened name; fall back to a name-only match on this team.
    matches = [pid for (name, tri), pid in player_map.items() if name == key[0]]
    if len(matches) == 1:
        return matches[0]
    return None
