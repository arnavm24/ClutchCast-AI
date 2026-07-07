"""End-to-end refresh: pull new games, retrain, refresh the site, push to deploy.

Designed to run unattended on a schedule (see scripts/register_refresh_task.ps1).
If no new games exist since the last run, it exits early without retraining.

Steps:
    1. Download the current season's regular-season + playoff play-by-play.
    2. If nothing new arrived, stop.
    3. Refresh team-strength priors, rebuild the dataset over the three most
       recent seasons, re-split, retrain all six competitors, re-select the
       champion, re-run calibration.
    4. Rebuild the game index, analyze the newest completed games, refresh
       demo picks, export web data.
    5. Build the web app, run the model parity check, commit, and push —
       Vercel auto-deploys from main.

Run manually: python src/refresh_all.py [--force] [--skip-push]
"""

import argparse
import subprocess
import sys
from datetime import datetime
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
LOG_DIR = PROJECT_ROOT / "reports" / "refresh_logs"


def current_season(now: datetime | None = None) -> str:
    now = now or datetime.now()
    start_year = now.year if now.month >= 10 else now.year - 1
    return f"{start_year}-{str(start_year + 1)[-2:]}"


def recent_seasons(count: int = 3) -> list[str]:
    latest = current_season()
    start = int(latest[:4])
    return [f"{year}-{str(year + 1)[-2:]}" for year in range(start - count + 1, start + 1)]


def run(step: str, command: list[str], log, cwd: Path = PROJECT_ROOT) -> None:
    print(f"\n=== {step} ===")
    log.write(f"\n=== {step} === {datetime.now().isoformat()}\n")
    log.flush()
    result = subprocess.run(command, cwd=cwd, text=True, stdout=log, stderr=subprocess.STDOUT, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        raise RuntimeError(f"Refresh failed at step: {step} (see log)")


def main() -> None:
    parser = argparse.ArgumentParser(description="Full ClutchCast refresh: data, models, site.")
    parser.add_argument("--force", action="store_true", help="Retrain even if no new games were downloaded.")
    parser.add_argument("--skip-push", action="store_true", help="Do everything except git commit/push.")
    parser.add_argument("--analyze-limit", type=int, default=15, help="Newest completed games to analyze for the site.")
    parser.add_argument(
        "--max-games", type=int, default=300,
        help="Regular-season games per season to keep in training (most recent first). Raise to scale up the dataset — expect much longer training.",
    )
    args = parser.parse_args()

    LOG_DIR.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M")
    log_path = LOG_DIR / f"refresh_{stamp}.log"
    python = sys.executable
    season = current_season()
    seasons = recent_seasons(3)

    with open(log_path, "w", encoding="utf-8") as log:
        print(f"Refresh started · season {season} · log: {log_path}")

        before = len(list(RAW_DIR.glob("play_by_play_*.csv")))
        run("Download regular season", [python, "src/download_games.py", "--season", season, "--season-type", "Regular Season", "--max-games", str(args.max_games)], log)
        run("Download playoffs", [python, "src/download_games.py", "--season", season, "--season-type", "Playoffs", "--max-games", "120"], log)
        after = len(list(RAW_DIR.glob("play_by_play_*.csv")))
        new_games = after - before
        print(f"New games downloaded: {new_games}")

        if new_games == 0 and not args.force:
            print("Nothing new — skipping retrain. (Use --force to retrain anyway.)")
            return

        run("Team strength priors", [python, "src/team_strength.py", "--apply-to-seasons", *seasons], log)
        run("Rebuild training dataset", [python, "src/build_training_dataset.py", "--seasons", *seasons, "--max-games", str(args.max_games)], log)

        for split_file in ("train_game_ids.txt", "test_game_ids.txt"):
            path = PROJECT_ROOT / "data" / "processed" / split_file
            if path.exists():
                path.unlink()

        run("Feature engineering", [python, "src/model_features.py"], log)
        run("Train logistic regression", [python, "src/train_model.py"], log)
        run("Train gradient boosting", [python, "src/train_gradient_boosting.py"], log)
        run("Train random forest", [python, "src/train_advanced_model.py"], log)
        run("Train neural network", [python, "src/train_neural_network.py"], log)
        run("Train sequence model", [python, "src/train_sequence_model.py"], log)
        run("Select champion", [python, "src/compare_models.py", "--leaderboard"], log)
        run("Calibration decision", [python, "src/calibrate_champion.py"], log)
        run("Calibration report", [python, "src/calibration_report.py"], log)

        run("Game index", [python, "src/game_index.py"], log)

        # Analyze the newest completed games so the site always has fresh content.
        import pandas as pd

        index = pd.read_csv(PROJECT_ROOT / "reports" / "game_index.csv", dtype={"game_id": str})
        fresh = (
            index[(index["season"] == season) & (index["looks_complete"] == True)]  # noqa: E712
            .sort_values("game_id", ascending=False)
            .head(args.analyze_limit)["game_id"]
            .tolist()
        )
        targets = PROJECT_ROOT / "data" / "processed" / "_refresh_targets.txt"
        targets.write_text("\n".join(fresh), encoding="utf-8")
        run("Analyze newest games", [python, "src/batch_analyze.py", "--from-file", str(targets), "--skip-existing"], log)

        run("Demo games", [python, "src/demo_games.py"], log)
        run("Export web data", [python, "src/export_web_data.py"], log)

        web = PROJECT_ROOT / "web"
        run("Web build", ["npm.cmd" if sys.platform == "win32" else "npm", "run", "build"], log, cwd=web)
        run("Model parity check", ["node", "scripts/parity.ts"], log, cwd=web)

        if args.skip_push:
            print("Done (push skipped).")
            return

        run("Git stage", ["git", "add", "-A"], log)
        commit = subprocess.run(
            ["git", "commit", "-m", f"Automated refresh {stamp}: new games, retrained models, updated site data"],
            cwd=PROJECT_ROOT, text=True, capture_output=True,
        )
        if commit.returncode != 0:
            print("Nothing to commit.")
            return
        run("Git push (triggers Vercel deploy)", ["git", "push", "origin", "main"], log)
        print("Refresh complete — pushed to main, Vercel will deploy automatically.")


if __name__ == "__main__":
    main()
