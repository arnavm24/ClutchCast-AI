from pathlib import Path
import argparse

import pandas as pd
import torch

from ml_pipeline_utils import apply_terminal_state_overrides
from model_features import build_model_features
from sequence_features import build_game_windows
from train_sequence_model import WinProbabilityGRU


PROCESSED_DIR = Path("data/processed")
MODELS_DIR = Path("models")
MODEL_PATH = MODELS_DIR / "sequence_gru_model.pt"


def load_model() -> WinProbabilityGRU:
    if not MODEL_PATH.exists():
        raise FileNotFoundError(
            "No sequence model found. Run:\n"
            "python src/train_sequence_model.py"
        )
    checkpoint = torch.load(MODEL_PATH, map_location="cpu")
    model = WinProbabilityGRU(
        input_size=checkpoint.get("input_size", 11),
        hidden_size=checkpoint.get("hidden_size", 64),
    )
    model.load_state_dict(checkpoint["model_state_dict"])
    model.eval()
    return model


def load_game_state(game_id: str | None = None) -> pd.DataFrame:
    if game_id:
        game_id = str(game_id).zfill(10)
        input_path = PROCESSED_DIR / f"game_state_{game_id}.csv"
        if not input_path.exists():
            raise FileNotFoundError(
                f"No game-state file found for game {game_id}. Run:\n"
                f"python src/game_state.py --game-id {game_id}"
            )
        return pd.read_csv(input_path, dtype={"game_id": str})
    files = sorted(PROCESSED_DIR.glob("game_state_*.csv"))
    if not files:
        raise FileNotFoundError("No game-state file found. Run: python src/game_state.py")
    return pd.read_csv(files[-1], dtype={"game_id": str})


def add_predictions(game_state: pd.DataFrame, model: WinProbabilityGRU) -> pd.DataFrame:
    output = game_state.copy()
    engineered = build_model_features(output)
    windows = torch.from_numpy(build_game_windows(engineered))
    with torch.no_grad():
        output["home_win_prob"] = model(windows).numpy()
    output = apply_terminal_state_overrides(output)
    output["prediction_source"] = "sequence_gru"
    return output


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate GRU sequence model win probability predictions.")
    parser.add_argument("--game-id", type=str, default=None, help="Specific NBA game ID to predict.")
    args = parser.parse_args()

    model = load_model()
    game_state = load_game_state(args.game_id)
    predictions = add_predictions(game_state, model)

    game_id = str(predictions["game_id"].iloc[0]).zfill(10)
    output_path = PROCESSED_DIR / f"seq_predictions_{game_id}.csv"
    predictions.to_csv(output_path, index=False)

    print("\nSuccess.")
    print(f"Saved sequence model predictions to: {output_path}")
    print(f"Rows: {len(predictions)}")


if __name__ == "__main__":
    main()
