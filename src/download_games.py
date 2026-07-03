"""Download raw play-by-play files only — no training-dataset rebuild.

Used to pull playoff games (or any season slice) into data/raw so they can be
indexed and analyzed without touching the training data the models were fit on.

Run: python src/download_games.py --season 2025-26 --season-type Playoffs
"""

import argparse
import time
from pathlib import Path

from build_training_dataset import fetch_play_by_play, get_game_ids

RAW_DIR = Path("data/raw")


def main() -> None:
    parser = argparse.ArgumentParser(description="Download raw NBA play-by-play files.")
    parser.add_argument("--season", required=True, type=str, help="Season, example: 2025-26.")
    parser.add_argument("--season-type", default="Playoffs", choices=["Regular Season", "Playoffs", "Pre Season", "All Star"])
    parser.add_argument("--max-games", type=int, default=120)
    parser.add_argument("--sleep-seconds", type=float, default=0.7)
    args = parser.parse_args()

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    game_ids = get_game_ids(season=args.season, season_type=args.season_type, max_games=args.max_games)

    downloaded, skipped, failed = 0, 0, []
    for index, game_id in enumerate(game_ids, start=1):
        raw_path = RAW_DIR / f"play_by_play_{game_id}.csv"
        if raw_path.exists():
            skipped += 1
            continue
        try:
            frame = fetch_play_by_play(game_id)
            frame.to_csv(raw_path, index=False)
            downloaded += 1
            print(f"[{index}/{len(game_ids)}] saved {game_id}")
        except Exception as error:
            failed.append(game_id)
            print(f"[{index}/{len(game_ids)}] FAILED {game_id}: {error}")
        time.sleep(args.sleep_seconds)

    print(f"\nDone: {downloaded} downloaded, {skipped} already present, {len(failed)} failed.")
    if failed:
        print("Failed: " + ", ".join(failed))


if __name__ == "__main__":
    main()
