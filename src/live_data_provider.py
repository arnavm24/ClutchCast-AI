"""Live NBA data provider helpers for ClutchCast AI.

The live backend should feel responsive even when nba_api play-by-play is
not ready yet. This module tries play-by-play first, then falls back to the
NBA scoreboard so the UI can still show score, clock, teams, and a simple
probability estimate.

Paid provider placeholders are intentionally key-free. Future integrations
should read credentials from environment variables only:
- SPORTSDATA_IO_API_KEY
- API_SPORTS_API_KEY
"""

from __future__ import annotations

import os
from datetime import date
from typing import Any

import pandas as pd
from nba_api.live.nba.endpoints import scoreboard as live_scoreboard
from nba_api.stats.endpoints import playbyplayv3, scoreboardv2

SPORTSDATA_IO_API_KEY_ENV = "SPORTSDATA_IO_API_KEY"
API_SPORTS_API_KEY_ENV = "API_SPORTS_API_KEY"


def _clean_game_id(game_id: str) -> str:
    return str(game_id).strip().zfill(10)


def _safe_int(value: Any, default: int = 0) -> int:
    try:
        if pd.isna(value):
            return default
        return int(value)
    except (TypeError, ValueError):
        return default


def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        if pd.isna(value):
            return default
        return float(value)
    except (TypeError, ValueError):
        return default


def _safe_str(value: Any, default: str = "") -> str:
    if value is None:
        return default
    try:
        if pd.isna(value):
            return default
    except TypeError:
        pass
    text = str(value).strip()
    return text if text else default


def _first_existing(row: pd.Series, names: list[str], default: Any = None) -> Any:
    for name in names:
        if name in row.index:
            value = row.get(name)
            if _safe_str(value):
                return value
    return default


def _latest_score(play_by_play: pd.DataFrame, column: str) -> int:
    if column not in play_by_play.columns:
        return 0
    scores = pd.to_numeric(play_by_play[column], errors="coerce").ffill().dropna()
    if scores.empty:
        return 0
    return int(scores.iloc[-1])


def _latest_text(play_by_play: pd.DataFrame, column: str) -> str:
    if column not in play_by_play.columns:
        return ""
    values = play_by_play[column].dropna().astype(str).str.strip()
    values = values[values != ""]
    return values.iloc[-1] if not values.empty else ""


def _fetch_play_by_play(game_id: str) -> pd.DataFrame:
    response = playbyplayv3.PlayByPlayV3(game_id=game_id, timeout=10)
    frames = response.get_data_frames()
    if not frames:
        return pd.DataFrame()
    return frames[0]


def _fetch_scoreboard_frames(game_date: str | None = None) -> tuple[pd.DataFrame, pd.DataFrame]:
    game_date = game_date or date.today().strftime("%m/%d/%Y")
    response = scoreboardv2.ScoreboardV2(
        game_date=game_date,
        league_id="00",
        day_offset=0,
        timeout=10,
    )
    frames = response.get_data_frames()
    games = frames[0] if len(frames) > 0 else pd.DataFrame()
    line_score = frames[1] if len(frames) > 1 else pd.DataFrame()
    return games, line_score


def _fetch_live_scoreboard_games() -> list[dict[str, Any]]:
    response = live_scoreboard.ScoreBoard(timeout=10)
    if hasattr(response, "get_dict"):
        payload = response.get_dict()
    elif hasattr(response, "games"):
        games = response.games.get_dict()
        if isinstance(games, list):
            return games
        if isinstance(games, dict):
            nested_games = games.get("games", [])
            return nested_games if isinstance(nested_games, list) else []
        return []
    else:
        return []
    scoreboard_payload = payload.get("scoreboard", payload)
    games = scoreboard_payload.get("games", [])
    return games if isinstance(games, list) else []


def _live_team_abbreviation(team: dict[str, Any], fallback: str) -> str:
    return (
        _safe_str(team.get("teamTricode"))
        or _safe_str(team.get("teamAbbreviation"))
        or _safe_str(team.get("teamName"))
        or fallback
    )


def _live_team_name(team: dict[str, Any], fallback: str) -> str:
    city = _safe_str(team.get("teamCity"))
    name = _safe_str(team.get("teamName"))
    if city and name:
        return f"{city} {name}"
    return name or _live_team_abbreviation(team, fallback)


def _live_last_play(game: dict[str, Any], status: str) -> str:
    for key in ["lastPlay", "lastPlayDescription", "lastAction"]:
        value = game.get(key)
        if isinstance(value, dict):
            text = _safe_str(value.get("description")) or _safe_str(value.get("actionType"))
            if text:
                return text
        text = _safe_str(value)
        if text:
            return text
    actions = game.get("actions")
    if isinstance(actions, list) and actions:
        latest = actions[-1]
        if isinstance(latest, dict):
            text = _safe_str(latest.get("description")) or _safe_str(latest.get("actionType"))
            if text:
                return text
    return status


def _live_scoreboard_snapshot(game_id: str) -> dict[str, Any] | None:
    for game in _fetch_live_scoreboard_games():
        current_id = _clean_game_id(game.get("gameId") or game.get("game_id") or game.get("GAME_ID"))
        if current_id != game_id:
            continue

        home = game.get("homeTeam") or {}
        away = game.get("awayTeam") or {}
        status = _safe_str(game.get("gameStatusText"), "Live scoreboard available")
        clock = _safe_str(game.get("gameClock"), status)
        game_state = _safe_str(game.get("gameState")) or _safe_str(game.get("gameStatus"))

        return {
            "game_id": game_id,
            "status": status,
            "game_status": game_state,
            "game_state": game_state,
            "period": _safe_int(game.get("period")),
            "clock": clock,
            "game_clock": clock,
            "home_score": _safe_int(home.get("score")),
            "away_score": _safe_int(away.get("score")),
            "home_team": _live_team_abbreviation(home, "Home"),
            "away_team": _live_team_abbreviation(away, "Away"),
            "home_team_name": _live_team_name(home, "Home"),
            "away_team_name": _live_team_name(away, "Away"),
            "home_team_id": _safe_int(home.get("teamId")),
            "away_team_id": _safe_int(away.get("teamId")),
            "last_play": _live_last_play(game, status),
            "data_source": "nba_api_live_scoreboard",
            "has_play_by_play": False,
        }
    return None


def _stats_scoreboard_snapshot(game_id: str) -> dict[str, Any] | None:
    games, line_score = _fetch_scoreboard_frames()
    if games.empty or "GAME_ID" not in games.columns:
        return None

    matches = games[games["GAME_ID"].astype(str).str.zfill(10) == game_id]
    if matches.empty:
        return None

    game = matches.iloc[0]
    home_team_id = _safe_int(game.get("HOME_TEAM_ID"))
    away_team_id = _safe_int(game.get("VISITOR_TEAM_ID"))

    home_team = str(home_team_id) if home_team_id else "Home"
    away_team = str(away_team_id) if away_team_id else "Away"
    home_score = 0
    away_score = 0

    if not line_score.empty and "GAME_ID" in line_score.columns:
        lines = line_score[line_score["GAME_ID"].astype(str).str.zfill(10) == game_id]
        if not lines.empty and "TEAM_ID" in lines.columns:
            home_rows = lines[lines["TEAM_ID"].astype(str) == str(home_team_id)]
            away_rows = lines[lines["TEAM_ID"].astype(str) == str(away_team_id)]
            if not home_rows.empty:
                home_row = home_rows.iloc[0]
                home_team = _safe_str(home_row.get("TEAM_ABBREVIATION"), home_team)
                home_score = _safe_int(home_row.get("PTS"))
            if not away_rows.empty:
                away_row = away_rows.iloc[0]
                away_team = _safe_str(away_row.get("TEAM_ABBREVIATION"), away_team)
                away_score = _safe_int(away_row.get("PTS"))

    status = _safe_str(game.get("GAME_STATUS_TEXT"), "Scoreboard available")
    clock = _safe_str(_first_existing(game, ["LIVE_PC_TIME", "LIVE_PERIOD_TIME_BCAST"]), status)

    return {
        "game_id": game_id,
        "status": status,
        "period": _safe_int(game.get("PERIOD")),
        "clock": clock,
        "home_score": home_score,
        "away_score": away_score,
        "home_team": home_team,
        "away_team": away_team,
        "last_play": status,
        "data_source": "nba_api_stats_scoreboardv2",
        "has_play_by_play": False,
    }


def _scoreboard_snapshot(game_id: str) -> dict[str, Any] | None:
    try:
        snapshot = _live_scoreboard_snapshot(game_id)
        if snapshot is not None:
            return snapshot
    except Exception:
        pass

    return _stats_scoreboard_snapshot(game_id)


def _paid_provider_placeholders(game_id: str) -> None:
    """Document future provider hooks without implementing paid calls.

    The environment variable reads are intentionally unused today. They make the
    expected configuration names explicit without hardcoding credentials.
    """

    _ = game_id
    _sportsdata_key = os.getenv(SPORTSDATA_IO_API_KEY_ENV)
    _api_sports_key = os.getenv(API_SPORTS_API_KEY_ENV)
    return None


def get_live_game_snapshot(game_id: str) -> dict[str, Any]:
    """Return the best available live snapshot for an NBA game.

    Priority:
    1. nba_api play-by-play, when rows are available.
    2. nba_api live scoreboard fallback.
    3. nba_api stats scoreboardv2 fallback.
    4. Clean empty fallback payload.
    """

    clean_id = _clean_game_id(game_id)
    play_by_play_error: str | None = None

    try:
        play_by_play = _fetch_play_by_play(clean_id)
        if not play_by_play.empty:
            latest = play_by_play.iloc[-1]
            try:
                scoreboard_snapshot = _scoreboard_snapshot(clean_id)
            except Exception:
                scoreboard_snapshot = None
            snapshot = dict(scoreboard_snapshot or {})
            snapshot.update(
                {
                    "game_id": clean_id,
                    "status": snapshot.get("status") or "Play-by-play available",
                    "period": _safe_int(latest.get("period"), _safe_int(snapshot.get("period"))),
                    "clock": _safe_str(latest.get("clock"), _safe_str(snapshot.get("clock"))),
                    "home_score": _latest_score(play_by_play, "scoreHome") or _safe_int(snapshot.get("home_score")),
                    "away_score": _latest_score(play_by_play, "scoreAway") or _safe_int(snapshot.get("away_score")),
                    "home_team": _safe_str(snapshot.get("home_team"), "Home"),
                    "away_team": _safe_str(snapshot.get("away_team"), "Away"),
                    "last_play": _latest_text(play_by_play, "description") or _safe_str(snapshot.get("last_play")),
                    "data_source": "nba_api_play_by_play",
                    "has_play_by_play": True,
                    "_play_by_play_df": play_by_play,
                }
            )
            return snapshot
    except Exception as error:
        play_by_play_error = str(error)

    try:
        scoreboard_snapshot = _scoreboard_snapshot(clean_id)
    except Exception:
        scoreboard_snapshot = None

    if scoreboard_snapshot is not None:
        if play_by_play_error:
            scoreboard_snapshot["play_by_play_error"] = play_by_play_error
        return scoreboard_snapshot

    _paid_provider_placeholders(clean_id)
    return {
        "game_id": clean_id,
        "status": "No live data available",
        "period": 0,
        "clock": "",
        "home_score": 0,
        "away_score": 0,
        "home_team": "Home",
        "away_team": "Away",
        "last_play": "No play-by-play or scoreboard data is available yet.",
        "data_source": "fallback_empty",
        "has_play_by_play": False,
    }


def get_today_games() -> list[dict[str, Any]]:
    """Return today's games from live scoreboard first, then stats scoreboardv2."""

    try:
        live_games = []
        for game in _fetch_live_scoreboard_games():
            game_id = _clean_game_id(game.get("gameId") or game.get("game_id") or game.get("GAME_ID"))
            home = game.get("homeTeam") or {}
            away = game.get("awayTeam") or {}
            status = _safe_str(game.get("gameStatusText"), "Scheduled")
            clock = _safe_str(game.get("gameClock"), status)
            live_games.append(
                {
                    "GAME_ID": game_id,
                    "GAMECODE": _safe_str(game.get("gameCode")),
                    "status": status,
                    "game_status": _safe_str(game.get("gameState")) or _safe_str(game.get("gameStatus")),
                    "period": _safe_int(game.get("period")),
                    "clock": clock,
                    "home_score": _safe_int(home.get("score")),
                    "away_score": _safe_int(away.get("score")),
                    "home_team_id": _safe_int(home.get("teamId")),
                    "away_team_id": _safe_int(away.get("teamId")),
                    "home_team": _live_team_abbreviation(home, ""),
                    "away_team": _live_team_abbreviation(away, ""),
                    "home_team_name": _live_team_name(home, ""),
                    "away_team_name": _live_team_name(away, ""),
                    "data_source": "nba_api_live_scoreboard",
                }
            )
        if live_games:
            return live_games
    except Exception:
        pass

    games, line_score = _fetch_scoreboard_frames()
    if games.empty:
        return []

    output: list[dict[str, Any]] = []
    for _, game in games.iterrows():
        game_id = _clean_game_id(game.get("GAME_ID"))
        home_team_id = _safe_int(game.get("HOME_TEAM_ID"))
        away_team_id = _safe_int(game.get("VISITOR_TEAM_ID"))
        home_team = str(home_team_id) if home_team_id else ""
        away_team = str(away_team_id) if away_team_id else ""

        if not line_score.empty and "GAME_ID" in line_score.columns:
            lines = line_score[line_score["GAME_ID"].astype(str).str.zfill(10) == game_id]
            if not lines.empty and "TEAM_ID" in lines.columns:
                home_rows = lines[lines["TEAM_ID"].astype(str) == str(home_team_id)]
                away_rows = lines[lines["TEAM_ID"].astype(str) == str(away_team_id)]
                if not home_rows.empty:
                    home_team = _safe_str(home_rows.iloc[0].get("TEAM_ABBREVIATION"), home_team)
                if not away_rows.empty:
                    away_team = _safe_str(away_rows.iloc[0].get("TEAM_ABBREVIATION"), away_team)

        output.append(
            {
                "GAME_ID": game_id,
                "GAMECODE": _safe_str(game.get("GAMECODE")),
                "status": _safe_str(game.get("GAME_STATUS_TEXT"), "Scheduled"),
                "period": _safe_int(game.get("PERIOD")),
                "clock": _safe_str(_first_existing(game, ["LIVE_PC_TIME", "LIVE_PERIOD_TIME_BCAST"])),
                "home_team_id": home_team_id,
                "away_team_id": away_team_id,
                "home_team": home_team,
                "away_team": away_team,
            }
        )
    return output
