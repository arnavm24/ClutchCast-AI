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
        choices=["baseline", "ml", "advanced", "neural"],
        help="Prediction model to use: baseline, ml, advanced, or neural.",
    )

    return parser.parse_args()


def get_game_id_args(args: argparse.Namespace) -> list[str]:
    if not args.game_id:
        return []

    return ["--game-id", args.game_id]


def build_prediction_step(args: argparse.Namespace) -> tuple[str, list[str]]:
    game_id_args = get_game_id_args(args)

    if args.model == "ml":
        return (
            "Generate logistic regression ML win probability",
            ["src/predict_with_model.py"] + game_id_args,
        )

    if args.model == "advanced":
        return (
            "Generate advanced ML win probability",
            ["src/predict_with_advanced_model.py"] + game_id_args,
        )

    if args.model == "neural":
        return (
            "Generate PyTorch neural network win probability",
            ["src/predict_with_neural_network.py"] + game_id_args,
        )

    return (
        "Generate baseline win probability",
        ["src/train_baseline.py"] + game_id_args,
    )


def build_pipeline_steps(args: argparse.Namespace) -> list[tuple[str, list[str]]]:
    game_id_args = get_game_id_args(args)
    load_command = ["src/load_data.py"]

    if args.game_id:
        load_command.extend(game_id_args)
    else:
        load_command.extend(["--season", args.season])
        load_command.extend(["--season-type", args.season_type])

    prediction_step = build_prediction_step(args)

    return [
        ("Load NBA play-by-play data", load_command),
        ("Build game-state table", ["src/game_state.py"] + game_id_args),
        prediction_step,
        ("Create win probability chart", ["src/predict_game.py"] + game_id_args),
        ("Add clutch pressure features", ["src/features.py"] + game_id_args),
        ("Build comeback reality meter", ["src/comeback_meter.py"] + game_id_args),
        ("Calculate hidden momentum", ["src/momentum.py"] + game_id_args),
        ("Calculate player swing impact", ["src/player_impact.py"] + game_id_args),
        ("Find turning points", ["src/turning_points.py"] + game_id_args),
        ("Generate game insights", ["src/game_insights.py"] + game_id_args),
        ("Generate post-game recap", ["src/recap.py"] + game_id_args),
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

    if args.game_id:
        print(f"Selected game ID: {args.game_id}")

    for step_name, command_parts in pipeline_steps:
        run_step(step_name, command_parts)

    print("\n" + "=" * 80)
    print("Pipeline complete.")
    print("You can now run the dashboard with:")
    print("streamlit run app/streamlit_app.py")
    print("=" * 80)


if __name__ == "__main__":
    main()
