"""Why-This-Probability panel and What-If simulator engine.

Driver rankings come from the logistic-regression twin model (coefficient x scaled
feature value), which is honest to label as an approximation of the champion.
The What-If simulator runs the champion model itself on modified game states.
"""

import numpy as np
import pandas as pd
import streamlit as st

from ui.config import PROJECT_ROOT
from ui.data_loaders import get_prediction_path
from ui.formatting import as_float, as_int, format_nba_clock, format_period

FRIENDLY_FEATURE_NAMES = {
    "score_margin_home": "Score margin (home)",
    "score_margin_time_weighted": "Margin weighted by game time",
    "abs_margin_time_weighted": "Lead size x time elapsed",
    "margin_squared": "Margin squared (blowout signal)",
    "seconds_remaining": "Seconds remaining",
    "time_remaining_fraction": "Fraction of game remaining",
    "time_elapsed_fraction": "Fraction of game elapsed",
    "home_lead": "Home team leading",
    "away_lead": "Away team leading",
    "tied_game": "Game tied",
    "one_possession_game": "One-possession game",
    "two_possession_game": "Two-possession game",
    "three_possession_game": "Three-possession game",
    "blowout_margin": "Blowout margin (20+)",
    "is_clutch_time": "Clutch time",
    "is_final_5_minutes": "Final 5 minutes",
    "is_final_2_minutes": "Final 2 minutes",
    "is_final_1_minute": "Final minute",
    "is_second_half": "Second half",
    "is_overtime": "Overtime",
    "is_4th_quarter": "4th quarter",
    "home_has_possession": "Home possession (est.)",
    "away_has_possession": "Away possession (est.)",
    "possession_value_home_perspective": "Possession edge (est.)",
    "home_run_last_10_events": "Home scoring run (last 10 events)",
    "away_run_last_10_events": "Away scoring run (last 10 events)",
    "recent_margin_change_5": "Margin change (last 5 events)",
    "recent_margin_change_10": "Margin change (last 10 events)",
    "recent_home_perspective_event_value_5": "Recent event momentum (5)",
    "recent_home_perspective_event_value_10": "Recent event momentum (10)",
    "team_strength_diff_home": "Team strength edge",
    "home_team_strength": "Home team strength",
    "away_team_strength": "Away team strength",
    "total_score": "Total points scored",
    "event_value": "Last event value",
}


def _friendly(feature: str) -> str:
    return FRIENDLY_FEATURE_NAMES.get(feature, feature.replace("_", " ").capitalize())


def _prepare_game_state_frame(predictions: pd.DataFrame) -> pd.DataFrame:
    frame = predictions.copy()
    if "home_won" not in frame.columns:
        frame["home_won"] = 0
    return frame


@st.cache_data(show_spinner=False)
def get_engineered_features(game_id: str, model_key: str) -> pd.DataFrame:
    from model_features import build_model_features

    predictions = pd.read_csv(get_prediction_path(game_id, model_key), dtype={"game_id": str})
    return build_model_features(_prepare_game_state_frame(predictions))


@st.cache_resource(show_spinner=False)
def _load_lr_explainer() -> dict | None:
    """Scaler + coefficients from the logistic-regression pipeline, aligned to feature columns."""
    import joblib
    from sklearn.linear_model import LogisticRegression
    from sklearn.preprocessing import StandardScaler

    from ml_pipeline_utils import load_feature_columns

    model_path = PROJECT_ROOT / "models" / "win_probability_model.joblib"
    if not model_path.exists():
        return None
    pipeline = joblib.load(model_path)
    scaler = None
    logistic = None
    steps = getattr(pipeline, "named_steps", {})
    for step in steps.values() if steps else [pipeline]:
        if isinstance(step, StandardScaler):
            scaler = step
        if isinstance(step, LogisticRegression):
            logistic = step
    if logistic is None:
        return None
    return {
        "scaler": scaler,
        "coefficients": np.asarray(logistic.coef_).flatten(),
        "feature_columns": load_feature_columns(),
    }


@st.cache_resource(show_spinner=False)
def _champion_bundle():
    from champion_inference import load_model_bundle

    return load_model_bundle()


def compute_drivers(feature_row: pd.Series, top_n: int = 6) -> list[dict]:
    explainer = _load_lr_explainer()
    if explainer is None:
        return []
    columns = explainer["feature_columns"]
    values = np.array([[as_float(feature_row.get(column, 0.0)) for column in columns]])
    if explainer["scaler"] is not None:
        scaled = explainer["scaler"].transform(values)[0]
    else:
        scaled = values[0]
    contributions = scaled * explainer["coefficients"]
    order = np.argsort(-np.abs(contributions))
    drivers = []
    for position in order[:top_n]:
        feature = columns[position]
        raw_value = as_float(feature_row.get(feature, 0.0))
        contribution = float(contributions[position])
        if abs(contribution) < 1e-6:
            continue
        if feature.startswith(("is_", "home_lead", "away_lead", "tied_game")) or feature.endswith("_game"):
            display_value = "Yes" if raw_value >= 0.5 else "No"
        elif abs(raw_value) >= 100:
            display_value = f"{raw_value:,.0f}"
        else:
            display_value = f"{raw_value:.2f}".rstrip("0").rstrip(".")
        drivers.append({
            "feature": feature,
            "label": _friendly(feature),
            "value": raw_value,
            "display_value": display_value,
            "contribution": contribution,
            "direction": 1 if contribution > 0 else -1,
        })
    return drivers


def build_moment_explanation(features: pd.DataFrame, predictions: pd.DataFrame, row_index: int, model_label: str) -> dict:
    row_index = max(0, min(int(row_index), len(predictions) - 1))
    pred_row = predictions.iloc[row_index]
    feature_row = features.iloc[row_index]

    period = as_int(pred_row.get("period"), 1)
    clock = format_nba_clock(pred_row.get("clock", ""))
    home_score = as_int(pred_row.get("home_score"))
    away_score = as_int(pred_row.get("away_score"))
    margin = home_score - away_score
    home_prob = as_float(pred_row.get("home_win_prob_pct"), 50.0)
    seconds_remaining = as_float(pred_row.get("seconds_remaining"), 0)
    is_clutch = as_int(feature_row.get("is_clutch_time", 0)) == 1
    run = as_float(feature_row.get("home_run_last_10_events", 0))

    if margin > 0:
        leader_text = f"Home leads by {margin}"
    elif margin < 0:
        leader_text = f"Away leads by {abs(margin)}"
    else:
        leader_text = "Game is tied"

    if run > 0:
        momentum_text = f"Home on a +{run:.0f} run over the last 10 events."
    elif run < 0:
        momentum_text = f"Away on a +{abs(run):.0f} run over the last 10 events."
    else:
        momentum_text = "No recent scoring run either way."

    context_bits = [format_period(period)]
    if is_clutch:
        context_bits.append("Clutch time")
    if seconds_remaining <= 0:
        context_bits = ["Final"]

    moment = f"{format_period(period)} {clock}" if seconds_remaining > 0 else "Final"
    drivers = compute_drivers(feature_row)
    driver_summary = drivers[0]["label"] if drivers else "score margin and time remaining"

    return {
        "moment": moment,
        "score_line": f"Away {away_score} - Home {home_score}",
        "margin_text": f"{margin:+d}",
        "leader_text": leader_text,
        "probability_text": f"{home_prob:.1f}% home",
        "model_label": model_label,
        "context_text": " · ".join(context_bits),
        "momentum_text": momentum_text,
        "game_minutes": float(((48 * 60) - seconds_remaining) / 60),
        "headline": f"{home_prob:.1f}% home win probability at {moment}",
        "summary": f"{leader_text} with {format_nba_clock(pred_row.get('clock', ''))} left in {format_period(period)}. Biggest signal right now: {driver_summary.lower()}.",
        "drivers": drivers,
        "caveat": "Driver estimates come from the logistic twin model trained on the same features; the champion neural network weighs these signals non-linearly.",
    }


def predict_what_if(margin: int, period: int, minutes_remaining: float, predictions: pd.DataFrame | None = None, moment_index: int | None = None) -> dict:
    """Score a hypothetical game state with the champion model.

    Uses the trailing rows of the selected game as rolling-feature context when
    available, otherwise builds a neutral single-row state.
    """
    from champion_inference import predict_game_state

    if period <= 4:
        seconds_remaining = (4 - period) * 12 * 60 + minutes_remaining * 60
    else:
        seconds_remaining = minutes_remaining * 60
    seconds_remaining = max(seconds_remaining, 1.0)

    context_note = "Neutral context (no recent-play history)."
    if predictions is not None and len(predictions) > 0:
        index = len(predictions) - 1 if moment_index is None else max(0, min(int(moment_index), len(predictions) - 1))
        start = max(0, index - 10)
        frame = _prepare_game_state_frame(predictions.iloc[start:index + 1])
        actual_prob_pct = as_float(predictions.iloc[index].get("home_win_prob_pct"), None)
        context_note = "Rolling features taken from the selected game moment."
    else:
        frame = _prepare_game_state_frame(pd.DataFrame([{
            "game_id": "whatif", "event_num": 1, "clock": "", "event_description": "",
            "event_team": "", "event_player": "",
            "period": period, "seconds_remaining": seconds_remaining,
            "home_score": 100, "away_score": 100 - margin,
            "score_margin_home": margin, "abs_score_margin": abs(margin),
            "total_score": 200 - margin, "is_4th_quarter": int(period == 4),
            "is_clutch_time": int(period >= 4 and seconds_remaining <= 300),
        }]))
        actual_prob_pct = None

    frame = frame.copy()
    last = frame.index[-1]
    base_total = as_int(frame.loc[last, "home_score"]) + as_int(frame.loc[last, "away_score"])
    home_score = max((base_total + margin) // 2, abs(margin))
    away_score = home_score - margin
    frame.loc[last, "home_score"] = home_score
    frame.loc[last, "away_score"] = away_score
    frame.loc[last, "score_margin_home"] = margin
    frame.loc[last, "abs_score_margin"] = abs(margin)
    frame.loc[last, "total_score"] = home_score + away_score
    frame.loc[last, "period"] = period
    frame.loc[last, "seconds_remaining"] = seconds_remaining
    frame.loc[last, "is_4th_quarter"] = int(period == 4)
    frame.loc[last, "is_clutch_time"] = int(period >= 4 and seconds_remaining <= 300)

    _champion_bundle()  # warm the cached model artifacts
    result = predict_game_state(frame)
    prob = float(result.iloc[-1]["home_win_prob"])
    period_label = format_period(period)
    state_text = f"{'Home' if margin >= 0 else 'Away'} {'+' + str(abs(margin)) if margin != 0 else 'tied'} · {period_label} {minutes_remaining:.1f} min left"
    return {
        "home_win_prob": prob,
        "state_text": state_text,
        "context_note": context_note,
        "actual_prob_pct": actual_prob_pct,
    }
