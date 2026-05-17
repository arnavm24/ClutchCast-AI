from pathlib import Path

import joblib
import pandas as pd
import torch
import torch.nn as nn
from sklearn.preprocessing import StandardScaler
from torch.utils.data import DataLoader, TensorDataset

from ml_pipeline_utils import (
    TARGET_COLUMN,
    apply_terminal_state_overrides,
    compute_probability_metrics,
    load_shared_training_inputs,
)


MODELS_DIR = Path("models")
REPORTS_DIR = Path("reports")

MODELS_DIR.mkdir(parents=True, exist_ok=True)
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


class WinProbabilityNeuralNetwork(nn.Module):
    def __init__(self, input_size: int):
        super().__init__()

        self.network = nn.Sequential(
            nn.Linear(input_size, 64),
            nn.ReLU(),
            nn.Dropout(0.20),
            nn.Linear(64, 32),
            nn.ReLU(),
            nn.Dropout(0.15),
            nn.Linear(32, 16),
            nn.ReLU(),
            nn.Dropout(0.10),
            nn.Linear(16, 1),
            nn.Sigmoid(),
        )

    def forward(self, x):
        return self.network(x)


def prepare_tensors(
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
    feature_columns: list[str],
) -> tuple[TensorDataset, torch.Tensor, torch.Tensor, StandardScaler]:
    X_train = train_data[feature_columns].astype(float)
    y_train = train_data[TARGET_COLUMN].astype(float)

    X_test = test_data[feature_columns].astype(float)
    y_test = test_data[TARGET_COLUMN].astype(float)

    scaler = StandardScaler()
    X_train_scaled = scaler.fit_transform(X_train)
    X_test_scaled = scaler.transform(X_test)

    X_train_tensor = torch.tensor(X_train_scaled, dtype=torch.float32)
    y_train_tensor = torch.tensor(y_train.values, dtype=torch.float32).view(-1, 1)

    X_test_tensor = torch.tensor(X_test_scaled, dtype=torch.float32)
    y_test_tensor = torch.tensor(y_test.values, dtype=torch.float32).view(-1, 1)

    train_dataset = TensorDataset(X_train_tensor, y_train_tensor)

    return train_dataset, X_test_tensor, y_test_tensor, scaler


def train_neural_network(
    train_dataset: TensorDataset,
    input_size: int,
    epochs: int = 100,
    batch_size: int = 128,
    learning_rate: float = 0.001,
) -> WinProbabilityNeuralNetwork:
    model = WinProbabilityNeuralNetwork(input_size=input_size)

    loss_function = nn.BCELoss()
    optimizer = torch.optim.Adam(
        model.parameters(),
        lr=learning_rate,
        weight_decay=0.0001,
    )

    train_loader = DataLoader(
        train_dataset,
        batch_size=batch_size,
        shuffle=True,
    )

    print("\nTraining neural network...")

    for epoch in range(1, epochs + 1):
        model.train()
        total_loss = 0.0

        for X_batch, y_batch in train_loader:
            optimizer.zero_grad()
            predictions = model(X_batch)
            loss = loss_function(predictions, y_batch)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()

        if epoch == 1 or epoch % 10 == 0 or epoch == epochs:
            avg_loss = total_loss / len(train_loader)
            print(f"Epoch {epoch:03d}/{epochs} | Loss: {avg_loss:.4f}")

    return model


def evaluate_model(
    model: WinProbabilityNeuralNetwork,
    X_test: torch.Tensor,
    train_data: pd.DataFrame,
    test_data: pd.DataFrame,
    feature_columns: list[str],
) -> dict:
    model.eval()

    with torch.no_grad():
        probabilities = model(X_test).numpy().flatten()

    prediction_frame = test_data.copy()
    prediction_frame["home_win_prob"] = probabilities
    prediction_frame = apply_terminal_state_overrides(prediction_frame)

    return compute_probability_metrics(
        y_true=prediction_frame[TARGET_COLUMN],
        probabilities=prediction_frame["home_win_prob"],
        model_key="pytorch_neural_network",
        model_name="PyTorch Neural Network",
        feature_count=len(feature_columns),
        train_data=train_data,
        test_data=test_data,
    )


def save_model_and_scaler(
    model: WinProbabilityNeuralNetwork,
    scaler: StandardScaler,
    feature_columns: list[str],
) -> None:
    model_path = MODELS_DIR / "pytorch_win_probability_model.pt"
    scaler_path = MODELS_DIR / "pytorch_scaler.joblib"
    feature_path = MODELS_DIR / "pytorch_model_features.txt"

    torch.save(
        {
            "model_state_dict": model.state_dict(),
            "input_size": len(feature_columns),
            "feature_columns": feature_columns,
        },
        model_path,
    )

    joblib.dump(scaler, scaler_path)
    feature_path.write_text("\n".join(feature_columns), encoding="utf-8")

    print(f"Saved PyTorch model to: {model_path}")
    print(f"Saved PyTorch scaler to: {scaler_path}")
    print(f"Saved PyTorch feature list to: {feature_path}")


def save_metrics(metrics: dict) -> None:
    output_path = REPORTS_DIR / "pytorch_model_metrics.csv"

    metrics_df = pd.DataFrame([metrics])
    metrics_df.to_csv(output_path, index=False)

    print(f"Saved PyTorch model metrics to: {output_path}")
    print("\nPyTorch model metrics:")
    for key, value in metrics.items():
        print(f"{key}: {value}")


def main() -> None:
    torch.manual_seed(42)

    train_data, test_data, feature_columns, train_game_ids, test_game_ids = (
        load_shared_training_inputs()
    )

    print("\nDataset summary:")
    print(f"Feature count: {len(feature_columns)}")
    print(f"Train rows: {len(train_data)}")
    print(f"Train games: {len(train_game_ids)}")
    print(f"Test rows: {len(test_data)}")
    print(f"Test games: {len(test_game_ids)}")

    train_dataset, X_test, _y_test, scaler = prepare_tensors(
        train_data=train_data,
        test_data=test_data,
        feature_columns=feature_columns,
    )

    model = train_neural_network(
        train_dataset=train_dataset,
        input_size=len(feature_columns),
        epochs=100,
        batch_size=128,
        learning_rate=0.001,
    )

    metrics = evaluate_model(
        model=model,
        X_test=X_test,
        train_data=train_data,
        test_data=test_data,
        feature_columns=feature_columns,
    )

    save_model_and_scaler(
        model=model,
        scaler=scaler,
        feature_columns=feature_columns,
    )

    save_metrics(metrics)

    print("\nSuccess.")
    print("Retrained PyTorch neural network using the shared game-level split.")


if __name__ == "__main__":
    main()
