import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

from ui.config import CHART_AWAY_COLOR, CHART_HOME_COLOR, DEFAULT_AWAY_COLOR, DEFAULT_HOME_COLOR, team_color
from ui.formatting import add_game_time_columns, format_period, render_html


def base_plotly_layout(fig, height: int = 430, right_margin: int = 132, legend: bool = True) -> None:
    layout = dict(
        template="plotly_dark",
        plot_bgcolor="#0B1020",
        paper_bgcolor="rgba(0,0,0,0)",
        height=height,
        margin=dict(l=20, r=right_margin, t=42, b=20),
    )
    if legend:
        layout["legend_title_text"] = ""
        layout["legend"] = dict(orientation="v", yanchor="top", y=.98, xanchor="left", x=1.02, bgcolor="rgba(15,23,42,.78)", bordercolor="#334155", borderwidth=1, font=dict(color="#E5E7EB", size=13))
    fig.update_layout(**layout)
    fig.update_yaxes(gridcolor="#1F2937")
    fig.update_xaxes(gridcolor="#1F2937")


def add_quarter_markers(fig, max_elapsed: float) -> None:
    for x_value, label in [(12, "Q1"), (24, "Q2 / Halftime"), (36, "Q3"), (48, "Q4 / End Reg.")]:
        if max_elapsed + 0.5 >= x_value:
            fig.add_vline(x=x_value, line_dash="dash", line_color="rgba(226,232,240,.42)", line_width=1, annotation_text=label, annotation_position="top left", annotation_font_size=11, annotation_font_color="#CBD5E1")
    overtime_end, overtime_number = 53, 1
    while max_elapsed > 48.5 and overtime_end <= max_elapsed + 0.5:
        label = "OT" if overtime_number == 1 else f"{overtime_number}OT"
        fig.add_vline(x=overtime_end, line_dash="dash", line_color="rgba(226,232,240,.34)", line_width=1, annotation_text=label, annotation_position="top left", annotation_font_size=11, annotation_font_color="#CBD5E1")
        overtime_end += 5
        overtime_number += 1


def show_win_probability_chart(predictions: pd.DataFrame, home_team: str, away_team: str, champion_view: bool, chart_key: str, top_spacing_px: int = 0, marker_minutes: float | None = None) -> None:
    if top_spacing_px > 0:
        render_html(f'<div style="height:{int(top_spacing_px)}px"></div>')
    st.subheader("Champion Win Probability Timeline" if champion_view else "Win Probability Timeline")
    chart_data = add_game_time_columns(predictions)
    chart_long = chart_data.melt(
        id_vars=["game_minutes_elapsed", "period", "Clock", "home_score", "away_score", "score_margin_home", "event_description"],
        value_vars=["home_win_prob_pct", "away_win_prob_pct"],
        var_name="team",
        value_name="win_probability_pct",
    )
    chart_long["team"] = chart_long["team"].replace({"home_win_prob_pct": home_team, "away_win_prob_pct": away_team})
    chart_long["Quarter"] = chart_long["period"].apply(lambda value: format_period(int(value)))
    chart_long["Score"] = chart_long.apply(lambda row: f"{away_team} {int(row['away_score'])} - {home_team} {int(row['home_score'])}", axis=1)
    chart_long["Play"] = chart_long["event_description"].fillna("No play description")
    fig = px.line(chart_long, x="game_minutes_elapsed", y="win_probability_pct", color="team", color_discrete_map={away_team: CHART_AWAY_COLOR, home_team: CHART_HOME_COLOR}, custom_data=["team", "Quarter", "Clock", "Score", "Play"], labels={"game_minutes_elapsed": "Game Time", "win_probability_pct": "Win Probability (%)"})
    fig.update_traces(line=dict(width=4), hovertemplate="<b>%{customdata[0]}</b><br>Win Probability: %{y:.1f}%<br>Quarter: %{customdata[1]}<br>Clock: %{customdata[2]}<br>Score: %{customdata[3]}<br>Play: %{customdata[4]}<extra></extra>")
    fig.update_yaxes(range=[0, 100])
    fig.add_hline(y=50, line_dash="dot", line_color="#CBD5E1", opacity=.72)
    add_quarter_markers(fig, float(chart_data["game_minutes_elapsed"].max()))
    if marker_minutes is not None:
        fig.add_vline(x=marker_minutes, line_color="#FDE68A", line_width=2, opacity=.9)
    base_plotly_layout(fig)
    fig.update_layout(hovermode="x unified")
    st.plotly_chart(fig, width="stretch", key=chart_key)


MODEL_TRACE_COLORS = {
    "pytorch_neural_network": "#F97316",
    "logistic_regression": "#38BDF8",
    "random_forest": "#4ADE80",
    "gradient_boosting": "#FDE047",
    "sequence_gru": "#C084FC",
    "baseline": "#CBD5E1",
    "scoreboard_fallback": "#F43F5E",
}


def reliability_diagram(curves: pd.DataFrame, champion_key: str, chart_key: str) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=[0, 1], y=[0, 1], mode="lines", name="Perfect calibration", line=dict(dash="dash", color="rgba(226,232,240,.5)", width=2), hoverinfo="skip"))
    for model_key, group in curves.groupby("model_key", sort=False):
        group = group.sort_values("mean_predicted")
        is_champion = model_key == champion_key
        fig.add_trace(go.Scatter(
            x=group["mean_predicted"], y=group["observed_rate"],
            mode="lines+markers",
            name=str(group["model_name"].iloc[0]) + (" 🏆" if is_champion else ""),
            line=dict(width=5 if is_champion else 2.5, color=MODEL_TRACE_COLORS.get(str(model_key), "#94A3B8")),
            marker=dict(size=9 if is_champion else 6),
            customdata=group[["count"]],
            hovertemplate="Predicted: %{x:.2f}<br>Observed: %{y:.2f}<br>States in bin: %{customdata[0]}<extra>" + str(group["model_name"].iloc[0]) + "</extra>",
        ))
    fig.update_xaxes(title="Predicted home win probability", range=[0, 1])
    fig.update_yaxes(title="Observed home win rate", range=[0, 1])
    base_plotly_layout(fig, height=460, right_margin=180)
    st.plotly_chart(fig, width="stretch", key=chart_key)


def brier_by_quarter_chart(by_quarter: pd.DataFrame, chart_key: str) -> None:
    fig = px.bar(
        by_quarter, x="period_bucket", y="brier_score", color="model_name", barmode="group",
        color_discrete_map={name: MODEL_TRACE_COLORS.get(key, "#94A3B8") for key, name in by_quarter.set_index("model_key")["model_name"].items()},
        labels={"period_bucket": "Game Segment", "brier_score": "Brier Score (lower is better)", "model_name": ""},
    )
    base_plotly_layout(fig, height=380, right_margin=180)
    st.plotly_chart(fig, width="stretch", key=chart_key)


def live_timeline_chart(history: list[dict], home_team: str, away_team: str, chart_key: str) -> None:
    frame = pd.DataFrame(history)
    frame["tick"] = range(1, len(frame) + 1)
    frame["away_win_prob_pct"] = 100 - frame["home_win_prob_pct"]
    frame["Moment"] = frame.apply(lambda row: f"Q{row['period']} {row['clock']}", axis=1)
    frame["Score"] = frame.apply(lambda row: f"{away_team} {int(row['away_score'])} - {home_team} {int(row['home_score'])}", axis=1)
    fig = go.Figure()
    for column, name, color in [("away_win_prob_pct", away_team, CHART_AWAY_COLOR), ("home_win_prob_pct", home_team, CHART_HOME_COLOR)]:
        fig.add_trace(go.Scatter(
            x=frame["tick"], y=frame[column], mode="lines+markers", name=name,
            line=dict(width=4, color=color), marker=dict(size=6),
            customdata=frame[["Moment", "Score", "last_play"]],
            hovertemplate="<b>" + name + "</b><br>Win Probability: %{y:.1f}%<br>%{customdata[0]}<br>%{customdata[1]}<br>%{customdata[2]}<extra></extra>",
        ))
    fig.add_hline(y=50, line_dash="dot", line_color="#CBD5E1", opacity=.72)
    fig.update_yaxes(range=[0, 100], title="Win Probability (%)")
    fig.update_xaxes(title="Live updates")
    base_plotly_layout(fig, height=360)
    st.plotly_chart(fig, width="stretch", key=chart_key)


def player_impact_timeline(events: pd.DataFrame, players: list[tuple[str, str]], chart_key: str) -> None:
    fig = go.Figure()
    for player, team in players:
        rows = events[(events["event_player"] == player) & (events["event_team"] == team)]
        if rows.empty:
            continue
        color = team_color(team, DEFAULT_HOME_COLOR if not fig.data else DEFAULT_AWAY_COLOR)
        fig.add_trace(go.Scatter(
            x=rows["game_minutes_elapsed"], y=rows["team_swing_pct"], mode="markers",
            name=f"{player} ({team})",
            marker=dict(size=(rows["abs_swing_pct"].clip(lower=1.2) * 2.4).clip(upper=26), color=color, opacity=.82, line=dict(width=1, color="rgba(255,255,255,.35)")),
            customdata=rows[["period", "clock", "event_description", "team_swing_pct"]],
            hovertemplate="<b>" + player + "</b><br>Q%{customdata[0]} %{customdata[1]}<br>Impact: %{customdata[3]:+.1f} WP<br>%{customdata[2]}<extra></extra>",
        ))
    fig.add_hline(y=0, line_dash="dot", line_color="#CBD5E1", opacity=.6)
    add_quarter_markers(fig, float(events["game_minutes_elapsed"].max()) if not events.empty else 48)
    fig.update_yaxes(title="Team-perspective WP impact (pts)")
    fig.update_xaxes(title="Game Time (minutes)")
    base_plotly_layout(fig, height=400)
    st.plotly_chart(fig, width="stretch", key=chart_key)
