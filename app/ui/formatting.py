import html
import textwrap

import pandas as pd
import streamlit as st


def render_html(markup: str) -> None:
    st.markdown(textwrap.dedent(markup).strip(), unsafe_allow_html=True)


def esc(value) -> str:
    return html.escape(str(value), quote=True)


def format_nba_clock(clock_value) -> str:
    clock = str(clock_value)
    if not clock.startswith("PT"):
        return clock
    clock = clock.replace("PT", "")
    minutes = 0
    seconds = 0.0
    if "M" in clock:
        minutes_part, clock = clock.split("M")
        minutes = int(minutes_part)
    if "S" in clock:
        seconds = float(clock.replace("S", ""))
    if seconds.is_integer():
        return f"{minutes}:{int(seconds):02d}"
    return f"{minutes}:{seconds:04.1f}"


def format_period(period: int) -> str:
    return f"Q{period}" if period <= 4 else f"OT{period - 4}"


def format_game_moment(period, clock) -> str:
    return f"{format_period(int(period))} {format_nba_clock(clock)}"


def initials(name: str) -> str:
    parts = [part for part in str(name).replace(".", " ").split() if part]
    if not parts:
        return "--"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def as_float(value, default: float = 0.0) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def as_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def short_text(value: str, max_len: int = 130) -> str:
    value = str(value).strip()
    return value if len(value) <= max_len else value[: max_len - 1].rstrip() + "..."


def best_row_text(df: pd.DataFrame, columns: list[str], fallback: str) -> str:
    if df.empty:
        return fallback
    row = df.iloc[0]
    pieces = [str(row[column]) for column in columns if column in row and not pd.isna(row[column])]
    return " · ".join(pieces) if pieces else fallback


def add_game_time_columns(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    output["game_minutes_elapsed"] = ((48 * 60) - output["seconds_remaining"]) / 60
    output["Clock"] = output["clock"].apply(format_nba_clock)
    return output


def clean_table_columns(df: pd.DataFrame) -> pd.DataFrame:
    display = df.copy()
    if "clock" in display.columns:
        display["clock"] = display["clock"].apply(format_nba_clock)
    return display.rename(columns={
        "game_id": "Game ID", "period": "Quarter", "clock": "Clock", "home_score": "Home Score",
        "away_score": "Away Score", "score_margin_home": "Home Margin", "event_team": "Team",
        "event_player": "Player", "event_description": "Play Description", "home_win_prob_pct": "Home Win Probability",
        "away_win_prob_pct": "Away Win Probability", "wp_before_pct": "Win Prob. Before",
        "wp_after_pct": "Win Prob. After", "wp_swing_pct": "Win Prob. Swing", "clutch_pressure": "Clutch Pressure",
        "pressure_level": "Pressure Level", "trailing_team": "Trailing Team", "deficit": "Deficit",
        "comeback_probability_pct": "Comeback Probability", "comeback_status": "Comeback Status",
        "required_points_per_minute": "Required Points / Min", "hidden_momentum_score": "Hidden Momentum",
        "momentum_label": "Momentum Label", "recent_margin_change": "Recent Margin Change", "recent_wp_change_pct": "Recent WP Change",
        "event_value": "Event Value", "rank": "Rank", "model_key": "Model Key", "model_name": "Model",
        "brier_score": "Brier Score", "log_loss": "Log Loss", "roc_auc": "ROC-AUC", "accuracy": "Accuracy",
        "insight": "Insight", "value": "Value", "details": "Details", "total_raw_home_wp_swing_pct": "Total Home WP Swing",
        "total_absolute_swing_pct": "Total Swing Impact", "avg_absolute_swing_pct": "Avg Swing Impact", "event_count": "Events",
        "max_model_disagreement_pct": "Max Model Disagreement",
    })
