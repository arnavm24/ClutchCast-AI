"""Shared feature/window definitions for the GRU sequence model.

The sequence model sees the trailing WINDOW_SIZE events of a game as a
time-series instead of hand-rolled rolling aggregates. Windows never cross
game boundaries and only look backwards, so there is no leakage.
"""

import numpy as np
import pandas as pd

WINDOW_SIZE = 24

# (column, scale) — values are divided by scale to keep inputs in a sane range.
SEQUENCE_FEATURES = [
    ("score_margin_home", 30.0),
    ("time_remaining_fraction", 1.0),
    ("period", 5.0),
    ("event_value", 5.0),
    ("signed_event_value_home_perspective", 5.0),
    ("home_score_delta", 3.0),
    ("away_score_delta", 3.0),
    ("is_clutch_time", 1.0),
    ("home_has_possession", 1.0),
    ("away_has_possession", 1.0),
    ("team_strength_diff_home", 0.5),
]

FEATURE_COUNT = len(SEQUENCE_FEATURES)


def game_feature_matrix(game_frame: pd.DataFrame) -> np.ndarray:
    """Normalized (n_events, FEATURE_COUNT) matrix for one game, in event order."""
    columns = []
    for column, scale in SEQUENCE_FEATURES:
        if column in game_frame.columns:
            values = pd.to_numeric(game_frame[column], errors="coerce").fillna(0.0).to_numpy(dtype=np.float32)
        else:
            values = np.zeros(len(game_frame), dtype=np.float32)
        columns.append(values / np.float32(scale))
    return np.stack(columns, axis=1)


def build_game_windows(game_frame: pd.DataFrame) -> np.ndarray:
    """(n_events, WINDOW_SIZE, FEATURE_COUNT) trailing windows, zero-padded at the start."""
    matrix = game_feature_matrix(game_frame)
    n_events = len(matrix)
    windows = np.zeros((n_events, WINDOW_SIZE, FEATURE_COUNT), dtype=np.float32)
    for index in range(n_events):
        start = max(0, index - WINDOW_SIZE + 1)
        chunk = matrix[start:index + 1]
        windows[index, WINDOW_SIZE - len(chunk):] = chunk
    return windows


def build_dataset_windows(data: pd.DataFrame, sort: bool = True) -> np.ndarray:
    """Trailing windows for a multi-game frame; row order of `data` is preserved."""
    frame = data
    if sort:
        frame = data.sort_values(["game_id", "event_num"])
    pieces = []
    for _, game_frame in frame.groupby("game_id", sort=False):
        pieces.append(build_game_windows(game_frame))
    windows = np.concatenate(pieces, axis=0)
    if sort:
        # Map back to the caller's original row order.
        sorted_positions = {index: position for position, index in enumerate(frame.index)}
        reorder = np.array([sorted_positions[index] for index in data.index], dtype=np.int64)
        windows = windows[reorder]
    return windows
