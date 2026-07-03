import pandas as pd
import streamlit as st

from ui.analytics import build_win_probability_story
from ui.charts import show_win_probability_chart
from ui.components import render_info_card, render_metric_card
from ui.formatting import esc, format_game_moment, render_html


def show_win_probability_story(data: dict, predictions: pd.DataFrame, home_team: str, away_team: str) -> None:
    story = build_win_probability_story(data, predictions, home_team, away_team)
    cards = [
        render_info_card("Current State", story["state"], story["favorite"], "⏱"),
        render_info_card("Biggest Swing", story["biggest_swing"], story["biggest_detail"], "📈"),
        render_info_card("Key Play", "Game Intelligence", story["key_play"], "🔥"),
    ]
    render_html(f'<div class="story-shell"><div class="story-title">Win Probability Story</div><div class="story-lede">{esc(story["lede"])}</div><div class="story-grid">' + "".join(cards) + '</div></div>')


def show_why_panel(predictions: pd.DataFrame, game_id: str, model_key: str, model_label: str, home_team: str, away_team: str) -> float | None:
    """Moment slider + Why This Probability panel. Returns selected moment in game minutes for the chart marker."""
    from ui.explain import build_moment_explanation, get_engineered_features

    st.markdown("### Why This Probability?")
    render_html('<div class="tab-intro">Scrub to any moment and see the game state and the signals pushing the model up or down.</div>')
    last_index = len(predictions) - 1
    row_index = st.slider(
        "Game moment",
        min_value=0,
        max_value=last_index,
        value=last_index,
        format="",
        key="why_moment_slider",
        help="Slide through every tracked play of the game.",
    )
    try:
        features = get_engineered_features(game_id, model_key)
        explanation = build_moment_explanation(features, predictions, row_index, model_label)
    except Exception as error:
        st.info(f"Explanation unavailable for this game: {error}")
        return None

    left, right = st.columns([1, 1], gap="large")
    with left:
        cards = [
            render_metric_card("Moment", explanation["moment"], explanation["score_line"]),
            render_metric_card("Score Margin", explanation["margin_text"], explanation["leader_text"]),
            render_metric_card("Win Probability", explanation["probability_text"], f"{explanation['model_label']} estimate at this moment."),
            render_metric_card("Game Context", explanation["context_text"], explanation["momentum_text"]),
        ]
        render_html('<div class="insight-grid">' + "".join(cards) + '</div>')
    with right:
        render_html('<div class="section-card"><div class="eyebrow">Top Probability Drivers</div>' + "".join(
            f'<div class="driver-row"><span class="driver-arrow {"driver-up" if d["direction"] > 0 else "driver-down"}">{"▲" if d["direction"] > 0 else "▼"}</span>'
            f'<span class="driver-name">{esc(d["label"])}</span><span class="driver-value">{esc(d["display_value"])}</span></div>'
            for d in explanation["drivers"][:5]
        ) + f'<div class="intel-body" style="font-size:.78rem; opacity:.75; margin-top:10px;">{esc(explanation["caveat"])}</div></div>')
    return explanation["game_minutes"]


def show_what_if_simulator(predictions: pd.DataFrame, moment_index: int, home_team: str, away_team: str) -> None:
    from ui.explain import predict_what_if

    with st.expander("🧪 What-If Simulator — ask the champion model hypotheticals"):
        render_html('<div class="tab-intro">Change the game state and the champion model re-scores it live. This is the model itself answering, not a lookup table.</div>')
        col1, col2, col3 = st.columns(3)
        with col1:
            margin = st.slider(f"{home_team} margin (negative = trailing)", -30, 30, 0, key="whatif_margin")
        with col2:
            period = st.selectbox("Quarter", [1, 2, 3, 4, 5], format_func=lambda p: f"Q{p}" if p <= 4 else "OT", index=3, key="whatif_period")
        with col3:
            minutes = st.slider("Minutes remaining in quarter", 0.0, 12.0, 2.0, step=0.5, key="whatif_minutes")
        try:
            with st.spinner("Scoring hypothetical state with the champion model..."):
                result = predict_what_if(margin, int(period), float(minutes), predictions, moment_index)
        except Exception as error:
            st.info(f"What-if unavailable: {error}")
            return
        prob = result["home_win_prob"] * 100
        actual = result.get("actual_prob_pct")
        delta = f"{prob - actual:+.1f} pts vs the actual moment" if actual is not None else ""
        cards = [
            render_metric_card(f"{home_team} Win Probability", f"{prob:.1f}%", delta),
            render_metric_card(f"{away_team} Win Probability", f"{100 - prob:.1f}%", "Champion model on the hypothetical state."),
            render_metric_card("Hypothetical State", result["state_text"], result["context_note"]),
        ]
        render_html('<div class="story-grid">' + "".join(cards) + '</div>')


def render(data: dict, predictions: pd.DataFrame, game_id: str, home_team: str, away_team: str, champion_view: bool, model_key: str, model_label: str) -> None:
    moment_minutes = None
    moment_index = len(predictions) - 1
    if "why_moment_slider" in st.session_state:
        moment_index = min(int(st.session_state["why_moment_slider"]), len(predictions) - 1)
        moment_minutes = float(((48 * 60) - predictions.iloc[moment_index]["seconds_remaining"]) / 60)
    show_win_probability_chart(predictions, home_team, away_team, champion_view, chart_key="full_win_probability_chart", marker_minutes=moment_minutes)
    show_win_probability_story(data, predictions, home_team, away_team)
    st.divider()
    show_why_panel(predictions, game_id, model_key, model_label, home_team, away_team)
    show_what_if_simulator(predictions, moment_index, home_team, away_team)
