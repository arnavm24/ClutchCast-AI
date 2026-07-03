"""Pick curated demo games from already-analyzed games and write app/demo_games.json.

Run after batch_analyze.py:
    python src/demo_games.py
"""

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(errors="replace")

REPORTS_DIR = Path("reports")
PROCESSED_DIR = Path("data/processed")
APP_DIR = Path("app")


def load_analyzed_game_ids() -> list[str]:
    game_ids = set()
    for pattern in ["baseline_predictions_*.csv", "ml_predictions_*.csv", "advanced_predictions_*.csv", "neural_predictions_*.csv"]:
        prefix = pattern.split("*")[0]
        for file in PROCESSED_DIR.glob(pattern):
            game_ids.add(file.name.replace(prefix, "").replace(".csv", ""))
    return sorted(game_ids)


def load_drama_scores() -> dict[str, float]:
    scores = {}
    for path in REPORTS_DIR.glob("game_insights_*.csv"):
        try:
            insights = pd.read_csv(path, dtype={"game_id": str})
        except Exception:
            continue
        if "insight" not in insights.columns:
            continue
        drama = insights[insights["insight"] == "Game Drama Score"]
        if drama.empty:
            continue
        game_id = str(drama.iloc[0].get("game_id") or path.stem.replace("game_insights_", "")).zfill(10)
        try:
            scores[game_id] = float(drama.iloc[0]["value"])
        except (TypeError, ValueError):
            continue
    return scores


def matchup_text(row: pd.Series) -> str:
    home = str(row.get("home_team") or "Home")
    away = str(row.get("away_team") or "Away")
    return f"{away} {int(row['final_away_score'])}-{int(row['final_home_score'])} {home}"


def build_demos() -> list[dict]:
    index_path = REPORTS_DIR / "game_index.csv"
    if not index_path.exists():
        raise FileNotFoundError("Missing reports/game_index.csv. Run: python src/game_index.py")
    index = pd.read_csv(index_path, dtype={"game_id": str})
    index["game_id"] = index["game_id"].str.zfill(10)

    analyzed = set(load_analyzed_game_ids())
    drama_scores = load_drama_scores()
    candidates = index[index["game_id"].isin(analyzed)].copy()
    if "looks_complete" in candidates.columns:
        candidates = candidates[candidates["looks_complete"] == True]  # noqa: E712
    if candidates.empty:
        raise SystemExit("No analyzed games found. Run: python src/batch_analyze.py --test-games --limit 20")
    candidates["drama"] = candidates["game_id"].map(drama_scores).fillna(0.0)
    candidates["abs_margin"] = candidates["final_margin"].abs()
    candidates["deficit_overcome"] = candidates.get("winner_max_deficit", pd.Series(0, index=candidates.index)).fillna(0)

    demos, used = [], set()

    def add_demo(key: str, label: str, frame: pd.DataFrame, tagline_fn) -> None:
        frame = frame[~frame["game_id"].isin(used)]
        if frame.empty:
            return
        row = frame.iloc[0]
        used.add(row["game_id"])
        demos.append({
            "key": key,
            "label": label,
            "game_id": row["game_id"],
            "tagline": tagline_fn(row),
        })

    add_demo(
        "close_finish", "🔥 Close Finish",
        candidates.sort_values(["abs_margin", "drama"], ascending=[True, False]),
        lambda row: f"{matchup_text(row)} · decided by {int(row['abs_margin'])}",
    )
    add_demo(
        "overtime", "⏰ Overtime Thriller",
        candidates[candidates["went_overtime"] == True].sort_values("drama", ascending=False),  # noqa: E712
        lambda row: f"{matchup_text(row)} · {int(row['n_overtimes'])}OT",
    )
    add_demo(
        "comeback", "⛰️ Big Comeback",
        candidates.sort_values(["deficit_overcome", "drama"], ascending=[False, False]),
        lambda row: f"{matchup_text(row)} · won after trailing by {int(row['deficit_overcome'])}",
    )
    add_demo(
        "blowout", "🧹 Blowout",
        candidates.sort_values("abs_margin", ascending=False),
        lambda row: f"{matchup_text(row)} · won by {int(row['abs_margin'])}",
    )
    add_demo(
        "most_dramatic", "🎭 Highest Drama",
        candidates.sort_values("drama", ascending=False),
        lambda row: f"{matchup_text(row)} · drama {row['drama']:.0f}/100",
    )
    return demos


def main() -> None:
    demos = build_demos()
    payload = {"generated": datetime.now(timezone.utc).isoformat(), "demos": demos}
    output_path = APP_DIR / "demo_games.json"
    output_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Saved {len(demos)} demo games to: {output_path}")
    for demo in demos:
        print(f"  {demo['label']}: {demo['game_id']} · {demo['tagline']}")


if __name__ == "__main__":
    main()
