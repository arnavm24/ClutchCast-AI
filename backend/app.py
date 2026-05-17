from pathlib import Path
import sys
import time

from flask import Flask, jsonify, request
from flask_socketio import SocketIO, emit
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))

from champion_inference import latest_prediction_payload, load_champion_metadata, predict_game_state
from game_state import build_game_state
from load_data import fetch_play_by_play


RAW_DIR = PROJECT_ROOT / "data/raw"
PROCESSED_DIR = PROJECT_ROOT / "data/processed"
RAW_DIR.mkdir(parents=True, exist_ok=True)
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

app = Flask(__name__)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode="threading")


def load_or_fetch_game_state(game_id: str, force_fetch: bool = False) -> pd.DataFrame:
    game_id = str(game_id).zfill(10)
    game_state_path = PROCESSED_DIR / f"game_state_{game_id}.csv"
    raw_path = RAW_DIR / f"play_by_play_{game_id}.csv"

    if game_state_path.exists() and not force_fetch:
        return pd.read_csv(game_state_path, dtype={"game_id": str})

    pbp_df = fetch_play_by_play(game_id)
    pbp_df.to_csv(raw_path, index=False)

    game_state = build_game_state(raw_path)
    game_state.to_csv(game_state_path, index=False)
    return game_state


def predict_payload(game_id: str, mode: str) -> dict:
    force_fetch = mode == "live"
    game_state = load_or_fetch_game_state(game_id, force_fetch=force_fetch)
    predictions = predict_game_state(game_state)
    payload = latest_prediction_payload(predictions)
    payload["mode"] = mode
    payload["champion"] = load_champion_metadata()
    return payload


@app.get("/health")
def health():
    return jsonify({"status": "ok", "service": "clutchcast-ai-backend"})


@app.get("/predict/<game_id>")
def predict(game_id: str):
    mode = request.args.get("mode", "historical").lower()

    if mode not in {"historical", "live"}:
        return jsonify({"error": "mode must be 'historical' or 'live'"}), 400

    try:
        return jsonify(predict_payload(game_id, mode))
    except Exception as error:
        return jsonify({"error": str(error), "game_id": str(game_id).zfill(10), "mode": mode}), 502


@socketio.on("subscribe_game")
def subscribe_game(message):
    game_id = str(message.get("game_id", "")).zfill(10)
    mode = str(message.get("mode", "live")).lower()
    updates = int(message.get("updates", 60))

    if not game_id or game_id == "0000000000":
        emit("prediction_error", {"error": "Missing game_id"})
        return

    if mode not in {"historical", "live"}:
        emit("prediction_error", {"error": "mode must be 'historical' or 'live'"})
        return

    for _ in range(max(1, updates)):
        try:
            emit("prediction_update", predict_payload(game_id, mode))
        except Exception as error:
            emit("prediction_error", {"error": str(error), "game_id": game_id, "mode": mode})

        if mode == "historical":
            break

        time.sleep(10)


if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=5000, debug=True)
