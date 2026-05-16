import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


PIPELINE_STEPS = [
    ("Load NBA play-by-play data", "src/load_data.py"),
    ("Build game-state table", "src/game_state.py"),
    ("Generate baseline win probability", "src/train_baseline.py"),
    ("Create win probability chart", "src/predict_game.py"),
    ("Add clutch pressure features", "src/features.py"),
    ("Build comeback reality meter", "src/comeback_meter.py"),
    ("Calculate hidden momentum", "src/momentum.py"),
    ("Calculate player swing impact", "src/player_impact.py"),
    ("Find turning points", "src/turning_points.py"),
    ("Generate post-game recap", "src/recap.py"),
]


def run_step(step_name: str, script_path: str) -> None:
    print("\n" + "=" * 80)
    print(f"Running: {step_name}")
    print(f"Script: {script_path}")
    print("=" * 80)

    result = subprocess.run(
        [sys.executable, script_path],
        cwd=PROJECT_ROOT,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Pipeline failed at step: {step_name}")

    print(f"Completed: {step_name}")


def main() -> None:
    print("\nStarting ClutchCast AI full pipeline...")

    for step_name, script_path in PIPELINE_STEPS:
        run_step(step_name, script_path)

    print("\n" + "=" * 80)
    print("Pipeline complete.")
    print("You can now run the dashboard with:")
    print("streamlit run app/streamlit_app.py")
    print("=" * 80)


if __name__ == "__main__":
    main()