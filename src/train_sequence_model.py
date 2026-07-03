"""Train a GRU sequence model over trailing event windows.

Benchmark competitor: instead of hand-rolled rolling aggregates, a small GRU
reads the last WINDOW_SIZE events directly. Champion selection still happens
in compare_models.py on probability metrics — this is not assumed to win.

Run: python src/train_sequence_model.py [--epochs 12]
"""

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset

from ml_pipeline_utils import (
    TARGET_COLUMN,
    apply_terminal_state_overrides,
    compute_probability_metrics,
    load_shared_training_inputs,
)
from sequence_features import FEATURE_COUNT, WINDOW_SIZE, build_dataset_windows

MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")
MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_PATH = MODELS_DIR / "sequence_gru_model.pt"

VALIDATION_GAME_FRACTION = 0.15
RANDOM_STATE = 42


class WinProbabilityGRU(nn.Module):
    def __init__(self, input_size: int = FEATURE_COUNT, hidden_size: int = 64):
        super().__init__()
        self.gru = nn.GRU(input_size=input_size, hidden_size=hidden_size, num_layers=1, batch_first=True)
        self.head = nn.Sequential(
            nn.Linear(hidden_size, 32),
            nn.ReLU(),
            nn.Linear(32, 1),
        )

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        _, hidden = self.gru(x)
        return torch.sigmoid(self.head(hidden[-1])).squeeze(-1)


def split_validation_games(train_data: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    games = sorted(train_data["game_id"].unique())
    rng = np.random.RandomState(RANDOM_STATE)
    rng.shuffle(games)
    n_val = max(int(len(games) * VALIDATION_GAME_FRACTION), 1)
    val_games = set(games[:n_val])
    return train_data[~train_data["game_id"].isin(val_games)], train_data[train_data["game_id"].isin(val_games)]


def to_tensors(frame: pd.DataFrame) -> tuple[torch.Tensor, torch.Tensor]:
    windows = build_dataset_windows(frame)
    X = torch.from_numpy(windows)
    y = torch.from_numpy(frame[TARGET_COLUMN].to_numpy(dtype=np.float32))
    return X, y


def main() -> None:
    parser = argparse.ArgumentParser(description="Train the GRU sequence win-probability model.")
    parser.add_argument("--epochs", type=int, default=12)
    parser.add_argument("--batch-size", type=int, default=1024)
    parser.add_argument("--hidden-size", type=int, default=64)
    parser.add_argument("--lr", type=float, default=1e-3)
    args = parser.parse_args()

    torch.manual_seed(RANDOM_STATE)

    train_data, test_data, _feature_columns, train_game_ids, test_game_ids = load_shared_training_inputs()
    fit_data, val_data = split_validation_games(train_data)

    print(f"Fit rows: {len(fit_data)} · Val rows: {len(val_data)} · Test rows: {len(test_data)}")
    print(f"Window: {WINDOW_SIZE} events x {FEATURE_COUNT} features")

    print("Building training windows...")
    X_fit, y_fit = to_tensors(fit_data)
    X_val, y_val = to_tensors(val_data)

    loader = DataLoader(TensorDataset(X_fit, y_fit), batch_size=args.batch_size, shuffle=True)
    model = WinProbabilityGRU(hidden_size=args.hidden_size)
    optimizer = torch.optim.Adam(model.parameters(), lr=args.lr)
    loss_fn = nn.BCELoss()

    best_val_loss = float("inf")
    best_state = None
    patience, bad_epochs = 3, 0

    for epoch in range(1, args.epochs + 1):
        model.train()
        total_loss = 0.0
        for X_batch, y_batch in loader:
            optimizer.zero_grad()
            loss = loss_fn(model(X_batch), y_batch)
            loss.backward()
            optimizer.step()
            total_loss += loss.item() * len(y_batch)
        model.eval()
        with torch.no_grad():
            val_loss = loss_fn(model(X_val), y_val).item()
        print(f"Epoch {epoch}: train loss {total_loss / len(y_fit):.4f} · val loss {val_loss:.4f}")
        if val_loss < best_val_loss - 1e-4:
            best_val_loss = val_loss
            best_state = {key: value.clone() for key, value in model.state_dict().items()}
            bad_epochs = 0
        else:
            bad_epochs += 1
            if bad_epochs >= patience:
                print("Early stopping.")
                break

    if best_state is not None:
        model.load_state_dict(best_state)

    print("Evaluating on held-out test games...")
    model.eval()
    X_test, _ = to_tensors(test_data)
    with torch.no_grad():
        probabilities = model(X_test).numpy()

    prediction_frame = test_data.copy()
    prediction_frame["home_win_prob"] = probabilities
    prediction_frame = apply_terminal_state_overrides(prediction_frame)

    metrics = compute_probability_metrics(
        y_true=prediction_frame[TARGET_COLUMN],
        probabilities=prediction_frame["home_win_prob"],
        model_key="sequence_gru",
        model_name="GRU Sequence Model",
        feature_count=FEATURE_COUNT,
        train_data=train_data,
        test_data=test_data,
    )

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "hidden_size": args.hidden_size,
            "input_size": FEATURE_COUNT,
            "window_size": WINDOW_SIZE,
            "best_val_loss": best_val_loss,
        },
        MODEL_PATH,
    )
    pd.DataFrame([metrics]).to_csv(REPORTS_DIR / "sequence_model_metrics.csv", index=False)

    print(f"\nSaved model to: {MODEL_PATH}")
    print("\nModel metrics:")
    for key, value in metrics.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
