import pandas as pd
import streamlit as st

from ui.analytics import build_comeback_report, build_player_impact, get_insight
from ui.charts import show_win_probability_chart
from ui.components import render_metric_card, show_scoreboard
from ui.formatting import best_row_text, clean_table_columns, esc, render_html, short_text


def show_metric_cards(data: dict, champion_label: str) -> None:
    drama = get_insight(data, "Game Drama Score", field="value", default="Pending")
    cards = [
        render_metric_card("Game Drama", f"{drama}/100" if str(drama).isdigit() else drama, short_text(get_insight(data, "Game Drama Score"), 120)),
        render_metric_card("Biggest Swing", "Most Valuable Play", short_text(get_insight(data, "Most Valuable Play"), 120)),
        render_metric_card("Damaging Play", "Loser WP Swing", short_text(get_insight(data, "Most Damaging Play"), 120)),
        render_metric_card("Champion Model", champion_label, "Selected by Brier score, log loss, ROC-AUC, then accuracy."),
    ]
    render_html('<div class="metric-grid">' + "".join(cards) + '</div>')


def show_game_intelligence_panel(data: dict, predictions: pd.DataFrame) -> None:
    comeback = data["comeback_report"] if not data["comeback_report"].empty else build_comeback_report(predictions)
    player = data["player_impact"] if not data["player_impact"].empty else build_player_impact(predictions)
    momentum = data["momentum_report"]
    blocks = [
        ("Comeback Reality", best_row_text(clean_table_columns(comeback), ["Quarter", "Clock", "Trailing Team", "Deficit", "Comeback Probability", "Comeback Status"], "No comeback report found.")),
        ("Hidden Momentum", best_row_text(clean_table_columns(momentum), ["Quarter", "Clock", "Hidden Momentum", "Momentum Label", "Play Description"], "No hidden momentum report found.")),
        ("Top Player Impact", best_row_text(clean_table_columns(player), ["Player", "Team", "Total Swing Impact", "Events"], "No player impact report found.")),
        ("Key Play", get_insight(data, "Most Valuable Play")),
    ]
    render_html('<div class="section-card"><div class="eyebrow">Game Intelligence</div>' + "".join(f'<div class="intel-card"><div class="intel-title">{esc(title)}</div><div class="intel-body">{esc(short_text(text, 220))}</div></div>' for title, text in blocks) + '</div>')


def show_live_mode_panel(game_id: str) -> None:
    render_html(f'<div class="live-card"><div class="eyebrow">Live Backend MVP</div><div class="intel-body">Historical dashboard uses saved reports and CSV files. Live prediction runs through the Flask/SocketIO backend.<br><br><strong>Run:</strong> <code>python backend/app.py</code><br><strong>Endpoint:</strong> <code>/predict/{esc(game_id)}?mode=live</code></div></div>')


def show_why_card(predictions: pd.DataFrame, game_id: str, model_key: str, model_label: str) -> None:
    try:
        from ui.explain import build_moment_explanation, get_engineered_features

        features = get_engineered_features(game_id, model_key)
        explanation = build_moment_explanation(features, predictions, len(predictions) - 1, model_label)
    except Exception:
        return
    drivers = explanation.get("drivers", [])[:3]
    driver_rows = "".join(
        f'<div class="driver-row"><span class="driver-arrow {"driver-up" if d["direction"] > 0 else "driver-down"}">{"▲" if d["direction"] > 0 else "▼"}</span>'
        f'<span class="driver-name">{esc(d["label"])}</span><span class="driver-value">{esc(d["display_value"])}</span></div>'
        for d in drivers
    )
    render_html(
        f'<div class="section-card" style="margin-top:14px;"><div class="eyebrow">Why This Probability?</div>'
        f'<div class="intel-card"><div class="intel-title">{esc(explanation["headline"])}</div>'
        f'<div class="intel-body">{esc(explanation["summary"])}</div>{driver_rows}'
        f'<div class="intel-body" style="font-size:.76rem; opacity:.75;">{esc(explanation["caveat"])}</div></div></div>'
    )


def render(data: dict, predictions: pd.DataFrame, game_id: str, home_team: str, away_team: str, model_label: str, champion_label: str, champion_view: bool, model_key: str) -> None:
    show_scoreboard(predictions, home_team, away_team, model_label, champion_label)
    show_metric_cards(data, champion_label)
    left, right = st.columns([2.15, 1], gap="large")
    with left:
        show_win_probability_chart(predictions, home_team, away_team, champion_view, chart_key="overview_win_probability_chart", top_spacing_px=22)
    with right:
        render_html('<div class="right-rail-spacer"></div>')
        show_game_intelligence_panel(data, predictions)
        show_why_card(predictions, game_id, model_key, model_label)
        show_live_mode_panel(game_id)
