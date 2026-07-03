import streamlit as st

from ui.analytics import get_insight
from ui.components import render_info_card, show_empty_report_card
from ui.formatting import clean_table_columns, render_html, short_text


def render(data: dict, game_id: str) -> None:
    st.subheader("Game Insights")
    render_html('<div class="tab-intro">Game-specific intelligence turns the probability feed into a quick broadcast-style read.</div>')
    insights = data["game_insights"]
    if insights.empty:
        show_empty_report_card("Game Insights", f"python src/game_insights.py --game-id {game_id}")
        return
    cards = [
        render_info_card("Game Drama Score", get_insight(data, "Game Drama Score", "value", "Pending"), short_text(get_insight(data, "Game Drama Score"), 180), "🏀"),
        render_info_card("Most Valuable Play", short_text(get_insight(data, "Most Valuable Play", "value", "Most Valuable Play"), 42), short_text(get_insight(data, "Most Valuable Play"), 180), "📈"),
        render_info_card("Most Damaging Play", short_text(get_insight(data, "Most Damaging Play", "value", "Most Damaging Play"), 42), short_text(get_insight(data, "Most Damaging Play"), 180), "🔥"),
        render_info_card("Clutch-Time Scoring", short_text(get_insight(data, "Clutch-Time Scoring Summary", "value", "Clutch scoring"), 42), short_text(get_insight(data, "Clutch-Time Scoring Summary"), 180), "⏱"),
    ]
    render_html('<div class="insight-grid">' + "".join(cards) + '</div>')
    with st.expander("Detailed game insights table"):
        st.dataframe(clean_table_columns(insights), width="stretch", hide_index=True)
