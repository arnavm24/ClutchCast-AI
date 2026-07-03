import pandas as pd
import streamlit as st

from ui.analytics import build_player_events, build_player_impact, summarize_player
from ui.charts import player_impact_timeline
from ui.components import render_player_card, render_summary_card, show_empty_report_card
from ui.config import DEFAULT_AWAY_COLOR, DEFAULT_HOME_COLOR, team_color
from ui.data_loaders import load_player_id_map, lookup_player_id
from ui.formatting import clean_table_columns, initials, render_html


def show_matchup_section(predictions: pd.DataFrame, impact: pd.DataFrame, game_id: str, home_team: str, away_team: str) -> None:
    st.markdown("### Player Matchup")
    render_html('<div class="tab-intro">Pick any two players and compare how they moved the win probability — total impact, clutch impact, and their signature plays.</div>')
    events = build_player_events(predictions, home_team)
    if events.empty:
        st.info("No rankable player events found for this game.")
        return
    options = [f"{row['event_player']} ({row['event_team']})" for _, row in impact.iterrows()]
    lookup = {f"{row['event_player']} ({row['event_team']})": (row["event_player"], row["event_team"]) for _, row in impact.iterrows()}

    home_options = [o for o in options if lookup[o][1] == str(home_team)]
    away_options = [o for o in options if lookup[o][1] == str(away_team)]
    default_a = away_options[0] if away_options else options[0]
    default_b = home_options[0] if home_options else (options[1] if len(options) > 1 else options[0])

    col_a, col_b = st.columns(2)
    with col_a:
        pick_a = st.selectbox("Player A", options, index=options.index(default_a), key="matchup_player_a")
    with col_b:
        pick_b = st.selectbox("Player B", options, index=options.index(default_b), key="matchup_player_b")

    player_map = load_player_id_map(game_id)
    cards = []
    picks = [lookup[pick_a], lookup[pick_b]]
    for index, (player, team) in enumerate(picks):
        stats = summarize_player(events, player, team)
        if not stats:
            continue
        person_id = lookup_player_id(player_map, player, team)
        accent = team_color(team, DEFAULT_AWAY_COLOR if index == 0 else DEFAULT_HOME_COLOR)
        cards.append(render_player_card(player, team, stats, person_id, accent))
    if cards:
        render_html('<div class="insight-grid">' + "".join(cards) + '</div>')
    st.markdown("#### Impact Timeline")
    render_html('<div class="tab-intro">Every tracked play by each player, positive when it helped their team, sized by how big the swing was.</div>')
    player_impact_timeline(events, picks, chart_key="matchup_timeline")


def render(predictions: pd.DataFrame, game_id: str, home_team: str, away_team: str) -> None:
    impact = build_player_impact(predictions)
    st.subheader("Player Impact")
    render_html('<div class="tab-intro">Player impact aggregates win-probability movement attached to tracked player events.</div>')
    if impact.empty:
        show_empty_report_card("Player impact", f"python src/player_impact.py --game-id {game_id}")
        return
    highest = impact.sort_values("total_absolute_swing_pct", ascending=False).iloc[0]
    volatile = impact.sort_values("avg_absolute_swing_pct", ascending=False).iloc[0]
    team_impact = impact.groupby("event_team", as_index=False)["total_absolute_swing_pct"].sum().sort_values("total_absolute_swing_pct", ascending=False).iloc[0]
    cards = [
        render_summary_card("Highest Impact Player", str(highest["event_player"]), f"{float(highest['total_absolute_swing_pct']):.1f} total swing pts · {highest['event_team']}", avatar=initials(str(highest["event_player"]))),
        render_summary_card("Most Volatile Player", str(volatile["event_player"]), f"{float(volatile['avg_absolute_swing_pct']):.2f} avg swing pts/event", avatar=initials(str(volatile["event_player"]))),
        render_summary_card("Top Team by Swing", str(team_impact["event_team"]), f"{float(team_impact['total_absolute_swing_pct']):.1f} total swing points."),
        render_summary_card("Tracked Player Events", str(int(impact["event_count"].sum())), "Events with player, team, and valid WP movement context."),
    ]
    render_html('<div class="summary-grid">' + "".join(cards) + '</div>')
    show_matchup_section(predictions, impact, game_id, home_team, away_team)
    with st.expander("Full player impact table"):
        st.dataframe(clean_table_columns(impact), width="stretch", hide_index=True)
