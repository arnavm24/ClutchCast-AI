"""Batch-run the per-game analysis pipeline over games whose raw play-by-play is already on disk.

Skips the network download step entirely — everything runs offline from data/raw.

Examples:
    python src/batch_analyze.py --test-games --limit 20 --skip-existing
    python src/batch_analyze.py --game-ids 0022300589 0022300761
    python src/batch_analyze.py --from-file my_game_ids.txt
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RAW_DIR = PROJECT_ROOT / "data" / "raw"

CHAMPION_PREDICT_SCRIPTS = {
    "logistic_regression": "src/predict_with_model.py",
    "random_forest": "src/predict_with_advanced_model.py",
    "gradient_boosting": "src/predict_with_gradient_boosting.py",
    "pytorch_neural_network": "src/predict_with_neural_network.py",
    "sequence_gru": "src/predict_with_sequence_model.py",
}


def champion_predict_step() -> tuple[str, str]:
    """Predict with whichever model is the current champion (baseline already runs)."""
    import json

    champion_path = PROJECT_ROOT / "reports" / "champion_model.json"
    champion_key = "pytorch_neural_network"
    if champion_path.exists():
        try:
            champion_key = str(json.loads(champion_path.read_text(encoding="utf-8")).get("model_key", champion_key))
        except (json.JSONDecodeError, OSError):
            pass
    script = CHAMPION_PREDICT_SCRIPTS.get(champion_key, "src/predict_with_neural_network.py")
    return (f"Champion win probability ({champion_key})", script)


def build_per_game_steps() -> list[tuple[str, str]]:
    return [
        ("Build game-state table", "src/game_state.py"),
        ("Baseline win probability", "src/train_baseline.py"),
        champion_predict_step(),
        ("Clutch pressure features", "src/features.py"),
        ("Comeback reality meter", "src/comeback_meter.py"),
        ("Hidden momentum", "src/momentum.py"),
        ("Player swing impact", "src/player_impact.py"),
        ("Turning points", "src/turning_points.py"),
        ("Game insights", "src/game_insights.py"),
        ("Post-game recap", "src/recap.py"),
    ]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Batch-analyze games offline from data/raw.")
    parser.add_argument("--game-ids", nargs="*", default=None, help="Explicit game IDs to analyze.")
    parser.add_argument("--from-file", type=str, default=None, help="File with one game ID per line.")
    parser.add_argument("--test-games", action="store_true", help="Use the held-out test split game IDs.")
    parser.add_argument("--limit", type=int, default=None, help="Analyze at most N games.")
    parser.add_argument("--skip-existing", action="store_true", help="Skip games that already have neural predictions.")
    parser.add_argument("--continue-on-error", action="store_true", default=True, help="Log failures and keep going (default).")
    return parser.parse_args()


def collect_game_ids(args: argparse.Namespace) -> list[str]:
    game_ids: list[str] = []
    if args.game_ids:
        game_ids.extend(args.game_ids)
    if args.from_file:
        game_ids.extend(line.strip() for line in Path(args.from_file).read_text(encoding="utf-8").splitlines() if line.strip())
    if args.test_games:
        test_path = PROCESSED_DIR / "test_game_ids.txt"
        if not test_path.exists():
            raise FileNotFoundError(f"Missing {test_path}.")
        game_ids.extend(line.strip() for line in test_path.read_text(encoding="utf-8").splitlines() if line.strip())
    if not game_ids:
        raise SystemExit("No games selected. Use --game-ids, --from-file, or --test-games.")
    return [str(game_id).zfill(10) for game_id in dict.fromkeys(game_ids)]


def run_game(game_id: str) -> bool:
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    for step_name, script in build_per_game_steps():
        command = [sys.executable, script, "--game-id", game_id]
        result = subprocess.run(command, cwd=PROJECT_ROOT, text=True, capture_output=True, encoding="utf-8", errors="replace", env=env)
        if result.returncode != 0:
            tail = (result.stderr or result.stdout or "").strip().splitlines()
            detail = tail[-1] if tail else "no output"
            print(f"  FAILED at '{step_name}': {detail}")
            return False
    return True


def main() -> None:
    args = parse_args()
    game_ids = collect_game_ids(args)

    selected = []
    for game_id in game_ids:
        raw_path = RAW_DIR / f"play_by_play_{game_id}.csv"
        if not raw_path.exists():
            print(f"Skipping {game_id}: no raw play-by-play at {raw_path.name} (run load_data.py for it first).")
            continue
        if args.skip_existing and (PROJECT_ROOT / "reports" / f"post_game_recap_{game_id}.md").exists():
            print(f"Skipping {game_id}: already analyzed.")
            continue
        selected.append(game_id)
        if args.limit and len(selected) >= args.limit:
            break

    print(f"\nAnalyzing {len(selected)} game(s) offline...\n")
    succeeded, failed = [], []
    for position, game_id in enumerate(selected, start=1):
        print(f"[{position}/{len(selected)}] Game {game_id}")
        if run_game(game_id):
            succeeded.append(game_id)
            print("  done.")
        else:
            failed.append(game_id)
            if not args.continue_on_error:
                break

    print(f"\nBatch complete: {len(succeeded)} succeeded, {len(failed)} failed.")
    if failed:
        print("Failed games: " + ", ".join(failed))
    if succeeded:
        print("\nNext steps:")
        print("  python src/demo_games.py")
        print("  streamlit run app/streamlit_app.py")


if __name__ == "__main__":
    main()
