import argparse
import subprocess
import sys
from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parents[1]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run the full ClutchCast AI pipeline."
    )

    parser.add_argument(
        "--game-id",
        type=str,
        default=None,
        help="Specific NBA game ID to analyze, example: 0022301188.",
    )

    parser.add_argument(
        "--season",
        type=str,
        default="2023-24",
        help="NBA season to search if no game ID is provided, example: 2023-24.",
    )

    parser.add_argument(
        "--season-type",
        type=str,
        default="Regular Season",
        choices=["Regular Season", "Playoffs", "Pre Season", "All Star"],
        help="Season type to search if no game ID is provided.",
    )

    parser.add_argument(
        "--model",
        type=str,
        default="baseline",
        choices=["baseline", "ml", "advanced"],
        help="Prediction model to use: baseline, ml, or advanced.",
    )

    return parser.parse_args()


def build_prediction_step(model_name: str) -> tuple[str, list[str]]:
    if model_name == "ml":
        return ("Generate logistic regression ML win probability", ["src/predict_with_model.py"])

    if model_name == "advanced":
        return (
            "Generate advanced ML win probability",
            ["src/predict_with_advanced_model.py"],
        )

    return ("Generate baseline win probability", ["src/train_baseline.py"])


def build_pipeline_steps(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    load_command = ["src/load_data.py"]

    if args.game_id:
        load_command.extend(["--game-id", args.game_id])
    else:
        load_command.extend(["--season", args.season])
        load_command.extend(["--season-type", args.season_type])

    prediction_step = build_prediction_step(args.model)

    return [
        ("Load NBA play-by-play data", load_command),
        ("Build game-state table", ["src/game_state.py"]),
        prediction_step,
        ("Create win probability chart", ["src/predict_game.py"]),
        ("Add clutch pressure features", ["src/features.py"]),
        ("Build comeback reality meter", ["src/comeback_meter.py"]),
        ("Calculate hidden momentum", ["src/momentum.py"]),
        ("Calculate player swing impact", ["src/player_impact.py"]),
        ("Find turning points", ["src/turning_points.py"]),
        ("Generate post-game recap", ["src/recap.py"]),
    ]


def run_step(step_name: str, command_parts: list[str]) -> None:
    command = [sys.executable] + command_parts

    print("\n" + "=" * 80)
    print(f"Running: {step_name}")
    print(f"Command: {' '.join(command_parts)}")
    print("=" * 80)

    result = subprocess.run(
        command,
        cwd=PROJECT_ROOT,
        text=True,
    )

    if result.returncode != 0:
        raise RuntimeError(f"Pipeline failed at step: {step_name}")

    print(f"Completed: {step_name}")


def main() -> None:
    args = parse_args()
    pipeline_steps = build_pipeline_steps(args)

    print("\nStarting ClutchCast AI full pipeline...")
    print(f"Prediction mode: {args.model}")

    for step_name, command_parts in pipeline_steps:
        run_step(step_name, command_parts)

    print("\n" + "=" * 80)
    print("Pipeline complete.")
    print("You can now run the dashboard with:")
    print("streamlit run app/streamlit_app.py")
    print("=" * 80)


if __name__ == "__main__":
    main()