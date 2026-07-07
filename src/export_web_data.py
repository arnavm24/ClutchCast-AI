"""Export precomputed analysis + champion model to static JSON for the web app.

Everything the Next.js app needs lives in web/public/data — no Python at runtime.

Outputs:
    web/public/data/games.json          browse index + featured demos
    web/public/data/games/{id}.json     per-game timeline, players, insights, recap
    web/public/data/models.json         leaderboard + calibration
    web/public/data/model.json          champion NN weights, scaler, feature order, team strengths
    web/public/data/test_vectors.json   Python-computed vectors for TS parity checks

Run from project root: python src/export_web_data.py
"""

import json
import re
from pathlib import Path

import joblib
import pandas as pd
import torch

PROCESSED_DIR = Path("data/processed")
RAW_DIR = Path("data/raw")
REPORTS_DIR = Path("reports")
APP_DIR = Path("app")
WEB_DATA_DIR = Path("web/public/data")
GAME_DATES_PATH = REPORTS_DIR / "game_dates.csv"

CHAMPION_PREFIXES = {
    "pytorch_neural_network": "neural_predictions",
    "gradient_boosting": "gbm_predictions",
    "sequence_gru": "seq_predictions",
    "random_forest": "advanced_predictions",
    "logistic_regression": "ml_predictions",
    "baseline": "baseline_predictions",
}

RECAP_SECTIONS = ["Final Result", "Biggest Turning Point", "Player Impact", "Comeback Reality", "Hidden Momentum", "Model Note"]


def load_champion() -> dict:
    return json.loads((REPORTS_DIR / "champion_model.json").read_text(encoding="utf-8"))


def fetch_game_dates(seasons: list[str]) -> pd.DataFrame:
    """Game dates via LeagueGameFinder (regular season + playoffs), cached."""
    wanted = [(season, season_type) for season in seasons for season_type in ("Regular Season", "Playoffs")]
    cached = pd.read_csv(GAME_DATES_PATH, dtype={"game_id": str}) if GAME_DATES_PATH.exists() else pd.DataFrame()
    if not cached.empty and "season_type" in cached.columns:
        have = set(zip(cached["season"], cached["season_type"]))
        if all(pair in have for pair in wanted):
            return cached
    import time

    from nba_api.stats.endpoints import leaguegamefinder

    frames = []
    for season, season_type in wanted:
        print(f"Fetching game dates for {season} {season_type}...")
        try:
            finder = leaguegamefinder.LeagueGameFinder(
                season_nullable=season, league_id_nullable="00",
                season_type_nullable=season_type, timeout=30,
            )
            games = finder.get_data_frames()[0]
        except Exception as error:
            print(f"  skipped ({error})")
            continue
        if games.empty:
            continue
        games["GAME_ID"] = games["GAME_ID"].astype(str).str.zfill(10)
        games = games.drop_duplicates(subset=["GAME_ID"])
        frames.append(pd.DataFrame({
            "game_id": games["GAME_ID"],
            "date": games["GAME_DATE"].astype(str),
            "season": season,
            "season_type": season_type,
        }))
        time.sleep(0.7)
    dates = pd.concat(frames, ignore_index=True)
    dates.to_csv(GAME_DATES_PATH, index=False)
    return dates


def elapsed_minutes(period: int, seconds_remaining: float) -> float:
    """Game time on a continuous axis. In overtime, seconds_remaining only
    counts time left in the current 5-minute OT period, so OT maps to 48+."""
    if period <= 4:
        return (48 * 60 - seconds_remaining) / 60
    completed_overtimes = period - 5
    return 48 + completed_overtimes * 5 + (300 - seconds_remaining) / 60


def format_clock(value) -> str:
    clock = str(value)
    if not clock.startswith("PT"):
        return clock
    clock = clock.replace("PT", "")
    minutes, seconds = 0, 0.0
    if "M" in clock:
        part, clock = clock.split("M")
        minutes = int(part)
    if "S" in clock:
        seconds = float(clock.replace("S", ""))
    return f"{minutes}:{int(seconds):02d}"


def drama_scores() -> dict[str, dict]:
    scores = {}
    for path in REPORTS_DIR.glob("game_insights_*.csv"):
        try:
            insights = pd.read_csv(path, dtype={"game_id": str})
        except Exception:
            continue
        if "insight" not in insights.columns:
            continue
        game_id = path.stem.replace("game_insights_", "").zfill(10)
        row = insights[insights["insight"] == "Game Drama Score"]
        if not row.empty:
            try:
                scores[game_id] = float(row.iloc[0]["value"])
            except (TypeError, ValueError):
                pass
    return scores


def player_id_map(game_id: str) -> dict[tuple[str, str], int]:
    path = RAW_DIR / f"play_by_play_{game_id}.csv"
    if not path.exists():
        return {}
    raw = pd.read_csv(path, usecols=["personId", "playerName", "teamTricode"], low_memory=False)
    raw = raw[(raw["personId"].fillna(0) > 0) & raw["playerName"].notna()]
    raw["playerName"] = raw["playerName"].astype(str).str.strip()
    raw["teamTricode"] = raw["teamTricode"].fillna("").astype(str).str.strip()
    return {
        (name, team): int(ids.mode().iloc[0])
        for (name, team), ids in raw.groupby(["playerName", "teamTricode"])["personId"]
    }


def strip_markdown(text: str) -> str:
    return re.sub(r"\*\*|__|`", "", text)


def extract_recap_sections(recap_path: Path) -> dict:
    if not recap_path.exists():
        return {}
    text = recap_path.read_text(encoding="utf-8")
    sections = {}
    for name in RECAP_SECTIONS:
        match = re.search(rf"^##\s+{re.escape(name)}\s*$(.*?)(?=^##\s|\Z)", text, re.MULTILINE | re.DOTALL | re.IGNORECASE)
        if match:
            body = " ".join(line.strip(" -*") for line in match.group(1).splitlines() if line.strip())
            sections[name] = strip_markdown(body).strip()
    return sections


def export_game(game_id: str, index_row: pd.Series, champion: dict, date: str | None) -> dict | None:
    prefix = CHAMPION_PREFIXES.get(champion.get("model_key", ""), "neural_predictions")
    pred_path = PROCESSED_DIR / f"{prefix}_{game_id}.csv"
    if not pred_path.exists():
        return None
    predictions = pd.read_csv(pred_path, dtype={"game_id": str})
    home, away = str(index_row["home_team"]), str(index_row["away_team"])

    timeline = [
        {
            "t": round(elapsed_minutes(int(row["period"]), float(row["seconds_remaining"])), 2),
            "wp": round(float(row["home_win_prob_pct"]), 1),
            "hs": int(row["home_score"]),
            "as": int(row["away_score"]),
            "per": int(row["period"]),
            "clock": format_clock(row["clock"]),
            "play": str(row.get("event_description") or "")[:140],
        }
        for _, row in predictions.iterrows()
    ]

    turning = []
    tp_path = REPORTS_DIR / f"turning_points_{game_id}.csv"
    if tp_path.exists():
        for _, row in pd.read_csv(tp_path).head(6).iterrows():
            turning.append({
                "per": int(row["period"]), "clock": format_clock(row["clock"]),
                "player": str(row.get("event_player") or ""), "team": str(row.get("event_team") or ""),
                "play": str(row.get("event_description") or "")[:140],
                "before": float(row["wp_before_pct"]), "after": float(row["wp_after_pct"]),
                "swing": float(row["wp_swing_pct"]),
            })

    players = []
    pi_path = REPORTS_DIR / f"player_impact_{game_id}.csv"
    if pi_path.exists():
        ids = player_id_map(game_id)
        for _, row in pd.read_csv(pi_path).head(12).iterrows():
            name, team = str(row["event_player"]), str(row["event_team"])
            players.append({
                "name": name, "team": team,
                "personId": ids.get((name, team)),
                "impact": float(row["total_absolute_swing_pct"]),
                "net": float(row["total_raw_home_wp_swing_pct"]),
                "events": int(row["event_count"]),
            })

    insights = {}
    gi_path = REPORTS_DIR / f"game_insights_{game_id}.csv"
    if gi_path.exists():
        for _, row in pd.read_csv(gi_path, dtype={"game_id": str}).iterrows():
            insights[str(row["insight"])] = {"value": str(row["value"]), "details": str(row["details"])}

    payload = {
        "id": game_id,
        "date": date,
        "home": home, "away": away,
        "finalHome": int(index_row["final_home_score"]), "finalAway": int(index_row["final_away_score"]),
        "overtime": bool(index_row["went_overtime"]), "nOvertimes": int(index_row["n_overtimes"]),
        "model": champion.get("model_name", ""),
        "timeline": timeline,
        "turningPoints": turning,
        "players": players,
        "insights": insights,
        "recap": extract_recap_sections(REPORTS_DIR / f"post_game_recap_{game_id}.md"),
    }
    (WEB_DATA_DIR / "games" / f"{game_id}.json").write_text(json.dumps(payload), encoding="utf-8")
    return payload


def export_model_bundle(champion: dict) -> None:
    feature_columns = [
        line.strip() for line in (PROCESSED_DIR / "model_feature_columns.txt").read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    checkpoint = torch.load(Path("models/pytorch_win_probability_model.pt"), map_location="cpu")
    state = checkpoint["model_state_dict"]
    scaler = joblib.load(Path("models/pytorch_scaler.joblib"))
    strengths = pd.read_csv(PROCESSED_DIR / "team_strength.csv")

    bundle = {
        "championKey": champion.get("model_key", ""),
        "championName": champion.get("model_name", ""),
        "featureColumns": feature_columns,
        "scalerMean": [float(x) for x in scaler.mean_],
        "scalerScale": [float(x) for x in scaler.scale_],
        "layers": [
            {
                "weights": state[f"network.{i}.weight"].numpy().tolist(),
                "bias": state[f"network.{i}.bias"].numpy().tolist(),
            }
            for i in (0, 3, 6)
        ],
        "teamStrength": {
            f"{row['team']}|{row['season']}": float(row["strength"]) for _, row in strengths.iterrows()
        },
    }
    (WEB_DATA_DIR / "model.json").write_text(json.dumps(bundle), encoding="utf-8")
    print(f"Exported model bundle: {len(feature_columns)} features, {len(bundle['layers'])} layers")


def export_test_vectors(analyzed_ids: list[str], champion: dict) -> None:
    """A handful of (raw feature vector -> expected probability) pairs for TS parity."""
    import sys

    sys.path.insert(0, "src")
    from model_features import build_model_features

    feature_columns = [
        line.strip() for line in (PROCESSED_DIR / "model_feature_columns.txt").read_text(encoding="utf-8").splitlines() if line.strip()
    ]
    checkpoint = torch.load(Path("models/pytorch_win_probability_model.pt"), map_location="cpu")
    from train_neural_network import WinProbabilityNeuralNetwork

    model = WinProbabilityNeuralNetwork(input_size=checkpoint.get("input_size", len(feature_columns)))
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    scaler = joblib.load(Path("models/pytorch_scaler.joblib"))

    game_id = analyzed_ids[0]
    prefix = CHAMPION_PREFIXES.get(champion.get("model_key", ""), "neural_predictions")
    frame = pd.read_csv(PROCESSED_DIR / f"{prefix}_{game_id}.csv", dtype={"game_id": str})
    if "home_won" not in frame.columns:
        frame["home_won"] = 0
    engineered = build_model_features(frame)
    sample_indices = [10, 100, 250, len(engineered) - 20]
    vectors = []
    for index in sample_indices:
        raw = engineered.iloc[index][feature_columns].astype(float).tolist()
        scaled = scaler.transform([raw])
        with torch.no_grad():
            prob = float(model(torch.tensor(scaled, dtype=torch.float32)).item())
        vectors.append({"features": raw, "expected": prob})
    (WEB_DATA_DIR / "test_vectors.json").write_text(json.dumps({"gameId": game_id, "vectors": vectors}), encoding="utf-8")
    print(f"Exported {len(vectors)} test vectors from game {game_id}")


def main() -> None:
    WEB_DATA_DIR.mkdir(parents=True, exist_ok=True)
    (WEB_DATA_DIR / "games").mkdir(exist_ok=True)

    champion = load_champion()
    index = pd.read_csv(REPORTS_DIR / "game_index.csv", dtype={"game_id": str})
    index["game_id"] = index["game_id"].str.zfill(10)
    seasons = sorted(index["season"].dropna().unique().tolist())
    dates = fetch_game_dates(seasons)
    date_map = dict(zip(dates["game_id"], dates["date"]))
    drama = drama_scores()

    prefix = CHAMPION_PREFIXES.get(champion.get("model_key", ""), "neural_predictions")
    analyzed = {p.stem.replace(f"{prefix}_", "").zfill(10) for p in PROCESSED_DIR.glob(f"{prefix}_*.csv")}

    exported = []
    games_index = []
    for _, row in index.iterrows():
        game_id = row["game_id"]
        is_analyzed = game_id in analyzed
        # Only analyzed games are browsable, so shipping the rest is dead weight.
        if not is_analyzed:
            continue
        playoff_round = int(row.get("playoff_round", 0) or 0)
        games_index.append({
            "id": game_id,
            "date": date_map.get(game_id),
            "season": row["season"],
            "home": str(row["home_team"]), "away": str(row["away_team"]),
            "finalHome": int(row["final_home_score"]), "finalAway": int(row["final_away_score"]),
            "margin": int(row["final_margin"]),
            "overtime": bool(row["went_overtime"]),
            "leadChanges": int(row["lead_changes"]),
            "drama": drama.get(game_id),
            "playoffRound": playoff_round,
            "analyzed": is_analyzed,
        })
        if is_analyzed:
            result = export_game(game_id, row, champion, date_map.get(game_id))
            if result:
                exported.append(game_id)

    featured = []
    demo_path = APP_DIR / "demo_games.json"
    if demo_path.exists():
        featured = json.loads(demo_path.read_text(encoding="utf-8")).get("demos", [])

    leaderboard = pd.read_csv(REPORTS_DIR / "model_leaderboard.csv")
    curves = pd.read_csv(REPORTS_DIR / "calibration_curves.csv")
    summary = pd.read_csv(REPORTS_DIR / "calibration_summary.csv")
    by_quarter = pd.read_csv(REPORTS_DIR / "brier_by_quarter.csv")
    calibration_effect_path = REPORTS_DIR / "champion_calibration_effect.csv"
    effect = pd.read_csv(calibration_effect_path).to_dict("records") if calibration_effect_path.exists() else []

    (WEB_DATA_DIR / "models.json").write_text(json.dumps({
        "champion": {k: v for k, v in champion.items() if not isinstance(v, (list, dict))},
        "leaderboard": leaderboard.to_dict("records"),
        "calibrationCurves": curves.to_dict("records"),
        "calibrationSummary": summary.to_dict("records"),
        "brierByQuarter": by_quarter.to_dict("records"),
        "calibrationEffect": effect,
    }), encoding="utf-8")

    (WEB_DATA_DIR / "games.json").write_text(json.dumps({
        "generatedFor": champion.get("model_name", ""),
        "featured": featured,
        "games": games_index,
    }), encoding="utf-8")

    export_model_bundle(champion)
    export_test_vectors(sorted(exported), champion)

    print(f"\nExported {len(exported)} analyzed games, {len(games_index)} games in index.")
    print(f"Web data written to: {WEB_DATA_DIR}")


if __name__ == "__main__":
    main()
