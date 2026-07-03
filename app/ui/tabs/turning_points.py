import pandas as pd
import streamlit as st

from ui.analytics import build_turning_points
from ui.components import render_summary_card, show_empty_report_card
from ui.formatting import clean_table_columns, format_period, initials, render_html, short_text


def render(predictions: pd.DataFrame, game_id: str) -> None:
    turning = build_turning_points(predictions)
    st.subheader("Turning Points")
    render_html('<div class="tab-intro">The biggest win-probability swings reveal where the game actually bent.</div>')
    if turning.empty:
        show_empty_report_card("Turning points", f"python src/turning_points.py --game-id {game_id}")
        return
    data = turning.copy()
    data["abs_swing"] = data["wp_swing_pct"].abs()
    biggest = data.sort_values("abs_swing", ascending=False).iloc[0]
    quarter_summary = data.groupby("period")["abs_swing"].sum().sort_values(ascending=False)
    volatile_period = int(quarter_summary.index[0])
    cards = [
        render_summary_card("Biggest Swing", f"{float(biggest['wp_swing_pct']):+.1f} pts", short_text(str(biggest["event_description"]), 110), big=True),
        render_summary_card("Total Major Swings", str(int((data["abs_swing"] >= 10).sum())), "Swings of at least 10 win-probability points."),
        render_summary_card("Most Volatile Quarter", format_period(volatile_period), f"{quarter_summary.iloc[0]:.1f} combined swing points."),
        render_summary_card("Key Play", str(biggest["event_player"]), short_text(str(biggest["event_description"]), 110), avatar=initials(str(biggest["event_player"]))),
    ]
    render_html('<div class="summary-grid">' + "".join(cards) + '</div>')
    st.dataframe(clean_table_columns(turning), width="stretch", hide_index=True)
