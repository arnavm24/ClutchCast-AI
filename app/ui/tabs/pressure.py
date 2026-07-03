import pandas as pd
import streamlit as st

from ui.analytics import build_comeback_report, calculate_clutch_pressure
from ui.components import render_summary_card, show_empty_report_card
from ui.formatting import clean_table_columns, format_nba_clock, format_period, render_html, short_text


def render(predictions: pd.DataFrame, game_id: str) -> None:
    pressure = calculate_clutch_pressure(predictions).sort_values("clutch_pressure", ascending=False).head(15)
    comeback = build_comeback_report(predictions)
    st.subheader("Pressure & Comebacks")
    render_html('<div class="tab-intro">Pressure combines score closeness, game time, and win-probability uncertainty.</div>')
    if pressure.empty:
        show_empty_report_card("Pressure and comeback data", f"python src/features.py --game-id {game_id}")
        return
    peak = pressure.iloc[0]
    highest = None if comeback.empty else comeback.sort_values("comeback_probability_pct", ascending=False).iloc[0]
    biggest = None if comeback.empty else comeback.sort_values("deficit", ascending=False).iloc[0]
    cards = [
        render_summary_card("Peak Clutch Pressure", f"{float(peak['clutch_pressure']):.1f}", f"{format_period(int(peak['period']))} · {format_nba_clock(peak['clock'])} · {short_text(str(peak['event_description']), 80)}", big=True),
        render_summary_card("Highest Comeback Probability", "N/A" if highest is None else f"{float(highest['comeback_probability_pct']):.1f}%", "No comeback window found." if highest is None else f"{highest['trailing_team']} trailing by {int(highest['deficit'])}."),
        render_summary_card("Biggest Deficit With Chance", "N/A" if biggest is None else str(int(biggest["deficit"])), "No eligible comeback deficit found." if biggest is None else f"{biggest['comeback_status']} comeback window."),
        render_summary_card("Most Pressurized Moment", f"{format_period(int(peak['period']))}, {format_nba_clock(peak['clock'])}", short_text(str(peak["event_description"]), 100)),
    ]
    render_html('<div class="summary-grid">' + "".join(cards) + '</div>')
    col1, col2 = st.columns(2)
    with col1:
        st.markdown("### Clutch Pressure Detail")
        st.dataframe(clean_table_columns(pressure), width="stretch", hide_index=True)
    with col2:
        st.markdown("### Comeback Reality Detail")
        st.dataframe(clean_table_columns(comeback), width="stretch", hide_index=True)
