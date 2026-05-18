"""Print live scoreboard structures for debugging ClutchCast live mode.

Run this during an actual NBA game:

    python src/debug_live_scoreboard.py

The point is to inspect the exact JSON shape returned by your local nba_api
install and network path, then compare it with the older stats ScoreboardV2.
"""

from __future__ import annotations

import json
from datetime import date
from pprint import pprint

import requests
from nba_api.live.nba.endpoints import scoreboard as live_scoreboard
from nba_api.stats.endpoints import scoreboardv2

NBA_LIVE_SCOREBOARD_CDN_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json"
NBA_LIVE_SCOREBOARD_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/126.0.0.0 Safari/537.36"
    ),
    "Accept": "application/json,text/plain,*/*",
    "Referer": "https://www.nba.com/",
    "Origin": "https://www.nba.com",
}


def print_section(title: str) -> None:
    print("\n" + "=" * 88)
    print(title)
    print("=" * 88)


def coerce_live_games(payload):
    if isinstance(payload, list):
        return payload
    if not isinstance(payload, dict):
        return []
    scoreboard_payload = payload.get("scoreboard", payload)
    games = scoreboard_payload.get("games") if isinstance(scoreboard_payload, dict) else []
    if isinstance(games, list):
        return games
    if isinstance(games, dict):
        nested = games.get("games", [])
        return nested if isinstance(nested, list) else []
    return []


def print_direct_cdn_request(label: str, headers: dict | None = None) -> None:
    print_section(label)
    print(f"URL: {NBA_LIVE_SCOREBOARD_CDN_URL}")
    try:
        response = requests.get(NBA_LIVE_SCOREBOARD_CDN_URL, headers=headers, timeout=10)
        print(f"HTTP status code: {response.status_code}")
        print(f"response content-type: {response.headers.get('content-type', '')}")
        raw_text = response.text or ""
        print("first 500 characters of raw response text:")
        print(raw_text[:500])
        try:
            payload = response.json()
        except ValueError as error:
            print(f"parses as JSON: no ({type(error).__name__}: {error})")
            print("NBA live scoreboard endpoint is not returning JSON from this environment.")
            return

        print("parses as JSON: yes")
        print(f"top-level type: {type(payload).__name__}")
        if isinstance(payload, dict):
            print(f"top-level keys: {list(payload.keys())}")
            scoreboard_payload = payload.get("scoreboard", payload)
            if isinstance(scoreboard_payload, dict):
                print(f"scoreboard keys: {list(scoreboard_payload.keys())}")
        games = coerce_live_games(payload)
        print(f"number of games found: {len(games)}")
        if games:
            print("first direct-CDN game summary:")
            first = games[0]
            for key in ["gameId", "gameCode", "gameStatus", "gameStatusText", "gameState", "period", "gameClock"]:
                print(f"{key}: {first.get(key)}")
            print("homeTeam:")
            pprint(first.get("homeTeam"))
            print("awayTeam:")
            pprint(first.get("awayTeam"))
    except Exception as error:
        print(f"direct CDN request error: {type(error).__name__}: {error}")


def print_live_scoreboard() -> None:
    print_section("NBA Live ScoreBoard")
    try:
        try:
            response = live_scoreboard.ScoreBoard(timeout=10)
        except TypeError:
            response = live_scoreboard.ScoreBoard()
        if hasattr(response, "get_dict"):
            payload = response.get_dict()
            print("response method: ScoreBoard().get_dict()")
        elif hasattr(response, "games"):
            payload = {"scoreboard": {"games": response.games.get_dict()}}
            print("response method: ScoreBoard().games.get_dict()")
        else:
            payload = {}
            print("response method: unknown")

        print(f"top-level type: {type(payload).__name__}")
        if isinstance(payload, dict):
            print(f"top-level keys: {list(payload.keys())}")
            scoreboard_payload = payload.get("scoreboard")
            if isinstance(scoreboard_payload, dict):
                print(f"scoreboard keys: {list(scoreboard_payload.keys())}")

        games = coerce_live_games(payload)
        print(f"number of games found: {len(games)}")

        for index, game in enumerate(games):
            print_section(f"Live Game #{index + 1}")
            print(f"all game keys: {list(game.keys()) if isinstance(game, dict) else 'not a dict'}")
            if not isinstance(game, dict):
                pprint(game)
                continue

            for key in ["gameId", "game_id", "GAME_ID", "gameCode", "GAMECODE"]:
                print(f"{key}: {game.get(key)}")
            for key in ["gameStatus", "gameStatusText", "gameState", "period", "gameClock"]:
                print(f"{key}: {game.get(key)}")

            home = game.get("homeTeam")
            away = game.get("awayTeam")
            print("homeTeam keys:", list(home.keys()) if isinstance(home, dict) else type(home).__name__)
            pprint(home)
            print("awayTeam keys:", list(away.keys()) if isinstance(away, dict) else type(away).__name__)
            pprint(away)

        print_section("First Full Live Game JSON")
        if games:
            print(json.dumps(games[0], indent=2, sort_keys=True))
        else:
            print("No live games returned.")
    except Exception as error:
        print(f"Live ScoreBoard error: {type(error).__name__}: {error}")


def print_stats_scoreboard() -> None:
    print_section("Stats ScoreboardV2 Comparison")
    try:
        response = scoreboardv2.ScoreboardV2(
            game_date=date.today().strftime("%m/%d/%Y"),
            league_id="00",
            day_offset=0,
            timeout=10,
        )
        frames = response.get_data_frames()
        print(f"number of data frames: {len(frames)}")
        for index, frame in enumerate(frames[:2]):
            print_section(f"ScoreboardV2 frame #{index}")
            print(f"shape: {frame.shape}")
            print(f"columns: {list(frame.columns)}")
            if not frame.empty:
                print(frame.head(10).to_string(index=False))
            else:
                print("empty frame")
    except Exception as error:
        print(f"ScoreboardV2 error: {type(error).__name__}: {error}")


def main() -> None:
    print_direct_cdn_request("Direct NBA CDN Live Scoreboard - No Custom Headers")
    print_direct_cdn_request("Direct NBA CDN Live Scoreboard - Browser Headers", NBA_LIVE_SCOREBOARD_HEADERS)
    print_live_scoreboard()
    print_stats_scoreboard()


if __name__ == "__main__":
    main()
