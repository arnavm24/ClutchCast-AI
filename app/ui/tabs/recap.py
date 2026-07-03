import re

import streamlit as st

from ui.components import render_info_card, show_empty_report_card
from ui.formatting import render_html, short_text


def extract_recap_section(recap: str, heading: str) -> str:
    pattern = rf"^##\s+{re.escape(heading)}\s*$"
    lines = recap.splitlines()
    start = None
    for index, line in enumerate(lines):
        if re.match(pattern, line.strip(), flags=re.IGNORECASE):
            start = index + 1
            break
    if start is None:
        return ""
    end = len(lines)
    for index in range(start, len(lines)):
        if lines[index].startswith("## "):
            end = index
            break
    return " ".join(line.strip(" -*") for line in lines[start:end] if line.strip()).strip()


def render(data: dict, game_id: str) -> None:
    st.subheader("Game Recap")
    recap = data["recap"]
    if recap.startswith("No recap file"):
        show_empty_report_card("Game Recap", f"python src/recap.py --game-id {game_id}")
        return
    sections = {name: extract_recap_section(recap, name) for name in ["Final Result", "Biggest Turning Point", "Player Impact", "Comeback Reality", "Hidden Momentum", "Model Note"]}
    if not any(sections.values()):
        sections["Final Result"] = short_text(recap.replace("#", ""), 360)
    cards = [
        render_info_card("Final Result", "Game Result", short_text(sections.get("Final Result") or "Final result summary not found.", 220), "🏀"),
        render_info_card("Biggest Turning Point", "Key Swing", short_text(sections.get("Biggest Turning Point") or "Turning point summary not found.", 220), "📈"),
        render_info_card("Player Impact", "Top Contributor", short_text(sections.get("Player Impact") or "Player impact summary not found.", 220), "🔥"),
        render_info_card("Comeback Reality", "Pressure Read", short_text(sections.get("Comeback Reality") or "Comeback summary not found.", 220), "⏱"),
        render_info_card("Hidden Momentum", "Flow Signal", short_text(sections.get("Hidden Momentum") or "Momentum summary not found.", 220), "↔"),
        render_info_card("Model Note", "Champion Context", short_text(sections.get("Model Note") or "Model note not found.", 220), "CC"),
    ]
    render_html('<div class="recap-grid">' + "".join(cards) + '</div>')
    with st.expander("Full recap text"):
        st.markdown(recap)
