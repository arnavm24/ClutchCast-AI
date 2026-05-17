from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st
from nba_api.stats.endpoints import boxscoresummaryv2


PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")

HOME_COLOR = "#3B82F6"
AWAY_COLOR = "#EF4444"


st.set_page_config(
    page_title="ClutchCast AI",
    page_icon="🏀",
    layout="wide",
)


def apply_custom_css() -> None:
    st.markdown(
        """
        <style>
        .stApp {
            background: radial-gradient(circle at top left, #111827 0%, #080B12 40%, #05070D 100%);
            color: #F9FAFB;
        }

        [data-testid="stSidebar"] {
            background-color: #070A12;
            border-right: 1px solid #1F2937;
        }

        .main-title {
            font-size: 2.6rem;
            font-weight: 800;
            letter-spacing: -0.04em;
            margin-bottom: 0.2rem;
        }

        .subtitle {
            color: #9CA3AF;
            font-size: 1rem;
            margin-bottom: 1.5rem;
        }

        .premium-card {
            background: rgba(17, 24, 39, 0.92);
            border: 1px solid #1F2937;
            border-radius: 18px;
            padding: 1.2rem 1.3rem;
            box-shadow: 0 20px 45px rgba(0, 0, 0, 0.25);
            margin-bottom: 1rem;
        }

        .team-pill-home {
            display: inline-block;
            background: rgba(59, 130, 246, 0.15);
            color: #93C5FD;
            border: 1px solid rgba(59, 130, 246, 0.35);
            padding: 0.25rem 0.7rem;
            border-radius: 999px;
            font-weight: 700;
        }

        .team-pill-away {
            display: inline-block;
            background: rgba(239, 68, 68, 0.15);
            color: #FCA5A5;
            border: 1px solid rgba(239, 68, 68, 0.35);
            padding: 0.25rem 0.7rem;
            border-radius: 999px;
            font-weight: 700;
        }

        div[data-testid="stMetric"] {
            background: rgba(17, 24, 39, 0.9);
            border: 1px solid #1F2937;
            padding: 1rem;
            border-radius: 16px;
            box-shadow: 0 12px 30px rgba(0, 0, 0, 0.22);
        }

        div[data-testid="stMetricLabel"] {
            color: #9CA3AF;
        }

        div[data-testid="stMetricValue"] {
            color: #F9FAFB;
        }

        .stTabs [data-baseweb="tab-list"] {
            gap: 0.5rem;
        }

        .stTabs [data-baseweb="tab"] {
            background: rgba(17, 24, 39, 0.8);
            border: 1px solid #1F2937;
            border-radius: 999px;
            padding: 0.5rem 1rem;
            color: #D1D5DB;
        }

        .stTabs [aria-selected="true"] {
            background: linear-gradient(90deg, #2563EB, #7C3AED);
            color: white;
            border: 1px solid transparent;
        }

        h1, h2, h3 {
            letter-spacing: -0.03em;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


def format_nba_clock(clock_value) -> str:
    clock = str(clock_value)

    if not clock.startswith("PT"):
        return clock

    clock = clock.replace("PT", "")

    minutes = 0
    seconds = 0

    if "M" in clock:
        minutes_part, clock = clock.split("M")
        minutes = int(minutes_part)

    if "S" in clock:
        seconds_part = clock.replace("S", "")
        seconds = int(float(seconds_part))

    return f"{minutes}:{seconds:02d}"


def load_csv(path: Path) -> pd.DataFrame:
    if not path.exists():
        st.error(f"Missing required file: `{path}`")
        st.info("Run the project pipeline for this game and prediction mode first.")
        st.stop()

    return pd.read_csv(path, dtype={"game_id": str})


def get_available_game_ids() -> list[str]:
    game_ids = set()

    for file in PROCESSED_DIR.glob("baseline_predictions_*.csv"):
        game_ids.add(file.stem.replace("baseline_predictions_", ""))

    for file in PROCESSED_DIR.glob("ml_predictions_*.csv"):
        game_ids.add(file.stem.replace("ml_predictions_", ""))

    for file in PROCESSED_DIR.glob("advanced_predictions_*.csv"):
        game_ids.add(file.stem.replace("advanced_predictions_", ""))

    return sorted(game_ids)


def get_prediction_file(game_id: str, prediction_mode: str) -> Path:
    if prediction_mode == "Advanced ML Model":
        return PROCESSED_DIR / f"advanced_predictions_{game_id}.csv"

    if prediction_mode == "ML Model":
        return PROCESSED_DIR / f"ml_predictions_{game_id}.csv"

    return PROCESSED_DIR / f"baseline_predictions_{game_id}.csv"


@st.cache_data(show_spinner=False)
def get_team_labels(game_id: str) -> tuple[str, str]:
    try:
        summary = boxscoresummaryv2.BoxScoreSummaryV2(
            game_id=game_id,
            timeout=30,
        )

        try:
            line_score = summary.line_score.get_data_frame()
        except AttributeError:
            line_score = summary.get_data_frames()[5]

        if len(line_score) >= 2:
            away_team = str(line_score.iloc[0]["TEAM_ABBREVIATION"])
            home_team = str(line_score.iloc[1]["TEAM_ABBREVIATION"])
            return home_team, away_team

    except Exception:
        pass

    return "Home", "Away"


@st.cache_data
def load_dashboard_data(game_id: str, prediction_mode: str) -> dict:
    prediction_path = get_prediction_file(game_id, prediction_mode)
    predictions = load_csv(prediction_path)

    recap_path = REPORTS_DIR / f"post_game_recap_{game_id}.md"
    recap = (
        recap_path.read_text(encoding="utf-8")
        if recap_path.exists()
        else "No recap file found. Run the full pipeline first."
    )

    summary_path = REPORTS_DIR / f"model_comparison_summary_{game_id}.csv"
    disagreements_path = REPORTS_DIR / f"model_disagreements_{game_id}.csv"

    comparison_summary = (
        pd.read_csv(summary_path, dtype={"game_id": str})
        if summary_path.exists()
        else pd.DataFrame()
    )

    model_disagreements = (
        pd.read_csv(disagreements_path, dtype={"game_id": str})
        if disagreements_path.exists()
        else pd.DataFrame()
    )

    return {
        "predictions": predictions,
        "recap": recap,
        "comparison_summary": comparison_summary,
        "model_disagreements": model_disagreements,
    }


def add_game_time_columns(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    total_game_seconds = 48 * 60
    output["game_seconds_elapsed"] = total_game_seconds - output["seconds_remaining"]
    output["game_minutes_elapsed"] = output["game_seconds_elapsed"] / 60
    output["Clock"] = output["clock"].apply(format_nba_clock)
    return output


def clean_table_columns(df: pd.DataFrame) -> pd.DataFrame:
    display = df.copy()

    if "clock" in display.columns:
        display["clock"] = display["clock"].apply(format_nba_clock)

    rename_map = {
        "period": "Quarter",
        "clock": "Clock",
        "home_score": "Home Score",
        "away_score": "Away Score",
        "score_margin_home": "Home Margin",
        "event_team": "Team",
        "event_player": "Player",
        "event_description": "Play Description",
        "wp_before_pct": "Win Prob. Before",
        "wp_after_pct": "Win Prob. After",
        "wp_swing_pct": "Win Prob. Swing",
        "rank": "Rank",
        "total_raw_home_wp_swing_pct": "Net Home Win Prob. Swing",
        "total_absolute_swing_pct": "Total Win Prob. Impact",
        "avg_absolute_swing_pct": "Average Impact Per Event",
        "event_count": "Events Tracked",
        "home_win_prob_pct": "Home Win Probability",
        "away_win_prob_pct": "Away Win Probability",
        "baseline_home_win_prob_pct": "Baseline Home Win Probability",
        "ml_home_win_prob_pct": "ML Home Win Probability",
        "probability_difference_pct": "ML - Baseline Difference",
        "absolute_difference_pct": "Absolute Difference",
        "baseline_wp_change_pct": "Baseline Win Prob. Change",
        "ml_wp_change_pct": "ML Win Prob. Change",
        "wp_change_difference_pct": "Change Difference",
        "rows_compared": "Rows Compared",
        "average_absolute_difference_pct": "Avg. Absolute Difference",
        "maximum_absolute_difference_pct": "Max Difference",
        "average_signed_difference_pct": "Avg. Signed Difference",
        "baseline_final_home_win_prob_pct": "Baseline Final Home Win Prob.",
        "ml_final_home_win_prob_pct": "ML Final Home Win Prob.",
        "final_probability_difference_pct": "Final Difference",
        "final_home_score": "Final Home Score",
        "final_away_score": "Final Away Score",
        "final_home_margin": "Final Home Margin",
        "clutch_pressure": "Clutch Pressure",
        "pressure_level": "Pressure Level",
        "trailing_team": "Trailing Team",
        "deficit": "Deficit",
        "comeback_probability_pct": "Comeback Probability",
        "comeback_status": "Comeback Status",
        "required_points_per_minute": "Required Points/Min",
    }

    return display.rename(columns=rename_map)


def show_header(home_team: str, away_team: str, prediction_mode: str) -> None:
    st.markdown(
        f"""
        <div class="main-title">ClutchCast AI</div>
        <div class="subtitle">
            Premium NBA win probability, turning-point, momentum, and game-story engine.
        </div>
        <div style="margin-bottom: 1rem;">
            <span class="team-pill-away">{away_team}</span>
            <span style="color:#6B7280; margin: 0 0.5rem;">at</span>
            <span class="team-pill-home">{home_team}</span>
            <span style="color:#9CA3AF; margin-left: 1rem;">Mode: {prediction_mode}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )


def show_game_summary(
    predictions: pd.DataFrame,
    home_team: str,
    away_team: str,
    prediction_mode: str,
) -> None:
    final_row = predictions.iloc[-1]

    game_id = str(final_row["game_id"]).zfill(10)
    home_score = int(final_row["home_score"])
    away_score = int(final_row["away_score"])
    margin = int(final_row["score_margin_home"])
    home_wp = float(final_row["home_win_prob_pct"])
    away_wp = float(final_row["away_win_prob_pct"])

    if margin > 0:
        result = f"{home_team} by {margin}"
    elif margin < 0:
        result = f"{away_team} by {abs(margin)}"
    else:
        result = "Tie"

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Final Score", f"{home_team} {home_score} - {away_team} {away_score}")
    col2.metric("Result", result)
    col3.metric(f"{home_team} Final Win Prob.", f"{home_wp:.1f}%")
    col4.metric("Prediction Mode", prediction_mode)

    st.caption(
        f"Game ID: {game_id} · Events tracked: {len(predictions)} · "
        f"{away_team} final win probability: {away_wp:.1f}%"
    )


def show_win_probability_chart(
    predictions: pd.DataFrame,
    home_team: str,
    away_team: str,
) -> None:
    st.subheader("Win Probability Timeline")

    chart_data = add_game_time_columns(predictions)

    chart_data_long = chart_data.melt(
        id_vars=[
            "game_minutes_elapsed",
            "period",
            "Clock",
            "home_score",
            "away_score",
            "score_margin_home",
            "event_description",
        ],
        value_vars=["home_win_prob_pct", "away_win_prob_pct"],
        var_name="team",
        value_name="win_probability_pct",
    )

    chart_data_long["team"] = chart_data_long["team"].replace(
        {
            "home_win_prob_pct": home_team,
            "away_win_prob_pct": away_team,
        }
    )

    fig = px.line(
        chart_data_long,
        x="game_minutes_elapsed",
        y="win_probability_pct",
        color="team",
        color_discrete_map={
            home_team: HOME_COLOR,
            away_team: AWAY_COLOR,
        },
        hover_data=[
            "period",
            "Clock",
            "home_score",
            "away_score",
            "score_margin_home",
            "event_description",
        ],
        labels={
            "game_minutes_elapsed": "Game Time",
            "win_probability_pct": "Win Probability (%)",
            "team": "Team",
            "period": "Quarter",
            "home_score": "Home Score",
            "away_score": "Away Score",
            "score_margin_home": "Home Margin",
            "event_description": "Play",
        },
        title=f"{away_team} at {home_team} · Win Probability",
    )

    fig.update_traces(line=dict(width=3))

    fig.update_yaxes(
        range=[0, 100],
        gridcolor="#1F2937",
        zeroline=False,
    )

    fig.update_xaxes(
        gridcolor="#1F2937",
        zeroline=False,
    )

    fig.add_hline(
        y=50,
        line_dash="dot",
        line_color="#9CA3AF",
        opacity=0.8,
        annotation_text="50%",
        annotation_position="right",
    )

    for minute, label in [(12, "End Q1"), (24, "Half"), (36, "End Q3"), (48, "Final")]:
        fig.add_vline(
            x=minute,
            line_dash="dash",
            line_color="#6B7280",
            opacity=0.45,
            annotation_text=label,
            annotation_position="top",
        )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0B1020",
        hovermode="x unified",
        legend_title_text="",
        margin=dict(l=20, r=20, t=60, b=20),
        height=430,
    )

    st.plotly_chart(fig, width="stretch")


def build_turning_points(predictions: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    data = predictions.copy()

    data["wp_before_pct"] = (
        data["home_win_prob"].shift(1).fillna(data["home_win_prob"]) * 100
    ).round(1)

    data["wp_after_pct"] = data["home_win_prob_pct"]
    data["wp_swing_pct"] = (data["wp_after_pct"] - data["wp_before_pct"]).round(1)

    data = data[data["abs_wp_change"] > 0]
    data = data.sort_values("abs_wp_change", ascending=False).head(top_n)

    columns = [
        "period",
        "clock",
        "home_score",
        "away_score",
        "score_margin_home",
        "event_team",
        "event_player",
        "event_description",
        "wp_before_pct",
        "wp_after_pct",
        "wp_swing_pct",
    ]

    return data[columns].reset_index(drop=True)


def build_player_impact(predictions: pd.DataFrame) -> pd.DataFrame:
    data = predictions.copy()

    data = data[data["event_player"].notna()]
    data = data[data["event_player"].astype(str).str.strip() != ""]

    data["positive_swing_pct"] = (data["wp_change"] * 100).round(2)
    data["absolute_swing_pct"] = (data["abs_wp_change"] * 100).round(2)

    grouped = (
        data.groupby(["event_player", "event_team"], as_index=False)
        .agg(
            total_raw_home_wp_swing_pct=("positive_swing_pct", "sum"),
            total_absolute_swing_pct=("absolute_swing_pct", "sum"),
            avg_absolute_swing_pct=("absolute_swing_pct", "mean"),
            event_count=("event_player", "count"),
        )
    )

    grouped["total_raw_home_wp_swing_pct"] = grouped[
        "total_raw_home_wp_swing_pct"
    ].round(2)
    grouped["total_absolute_swing_pct"] = grouped[
        "total_absolute_swing_pct"
    ].round(2)
    grouped["avg_absolute_swing_pct"] = grouped[
        "avg_absolute_swing_pct"
    ].round(2)

    grouped = grouped.sort_values("total_absolute_swing_pct", ascending=False)
    grouped.insert(0, "rank", range(1, len(grouped) + 1))

    return grouped.reset_index(drop=True)


def calculate_clutch_pressure(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()

    total_game_seconds = 48 * 60
    elapsed_ratio = 1 - (output["seconds_remaining"] / total_game_seconds)
    elapsed_ratio = elapsed_ratio.clip(0, 1)

    closeness = (1 - (output["abs_score_margin"] / 20)).clip(0, 1)
    uncertainty = 1 - ((output["home_win_prob"] - 0.5).abs() / 0.5).clip(0, 1)

    output["clutch_pressure"] = (
        (0.40 * closeness + 0.35 * elapsed_ratio + 0.25 * uncertainty) * 100
    ).round(1)

    output["pressure_level"] = pd.cut(
        output["clutch_pressure"],
        bins=[-1, 25, 50, 75, 100],
        labels=["Low", "Medium", "High", "Extreme"],
    )

    return output


def build_comeback_report(predictions: pd.DataFrame) -> pd.DataFrame:
    data = calculate_clutch_pressure(predictions)

    data["trailing_team"] = "Tie"
    data.loc[data["score_margin_home"] < 0, "trailing_team"] = "Home"
    data.loc[data["score_margin_home"] > 0, "trailing_team"] = "Away"

    data["deficit"] = data["score_margin_home"].abs()

    data["comeback_probability"] = 0.5
    data.loc[data["score_margin_home"] < 0, "comeback_probability"] = data["home_win_prob"]
    data.loc[data["score_margin_home"] > 0, "comeback_probability"] = data["away_win_prob"]

    data["comeback_probability_pct"] = (data["comeback_probability"] * 100).round(1)

    def status(probability: float) -> str:
        if probability >= 0.40:
            return "Very realistic"
        if probability >= 0.25:
            return "Possible"
        if probability >= 0.10:
            return "Difficult"
        if probability >= 0.03:
            return "Very unlikely"
        return "Nearly impossible"

    data["comeback_status"] = data["comeback_probability"].apply(status)

    data["required_points_per_minute"] = data.apply(
        lambda row: round(
            row["deficit"] / max(row["seconds_remaining"] / 60, 0.01), 2
        )
        if row["deficit"] > 0
        else 0.0,
        axis=1,
    )

    comeback_rows = data[
        (data["trailing_team"] != "Tie")
        & (data["seconds_remaining"] > 0)
        & (data["deficit"] >= 5)
    ].copy()

    if comeback_rows.empty:
        return pd.DataFrame()

    comeback_rows["interest_score"] = (
        comeback_rows["deficit"] * 0.45
        + comeback_rows["clutch_pressure"] * 0.35
        + comeback_rows["comeback_probability_pct"] * 0.20
    )

    columns = [
        "period",
        "clock",
        "home_score",
        "away_score",
        "trailing_team",
        "deficit",
        "comeback_probability_pct",
        "comeback_status",
        "required_points_per_minute",
        "clutch_pressure",
        "pressure_level",
        "event_description",
    ]

    return (
        comeback_rows.sort_values("interest_score", ascending=False)[columns]
        .head(10)
        .reset_index(drop=True)
    )


def show_turning_points(predictions: pd.DataFrame) -> None:
    st.subheader("Turning Points")
    st.caption("The plays that created the largest win-probability swings.")

    turning_points = build_turning_points(predictions)

    st.dataframe(
        clean_table_columns(turning_points),
        width="stretch",
        hide_index=True,
    )


def show_player_impact(
    predictions: pd.DataFrame,
    home_team: str,
    away_team: str,
) -> None:
    st.subheader("Player Impact")
    st.caption("Players ranked by how much their events moved win probability.")

    player_impact = build_player_impact(predictions)
    top_10 = player_impact.head(10)

    fig = px.bar(
        top_10,
        x="event_player",
        y="total_absolute_swing_pct",
        color="event_team",
        color_discrete_map={
            home_team: HOME_COLOR,
            away_team: AWAY_COLOR,
        },
        hover_data=["event_team", "event_count", "avg_absolute_swing_pct"],
        labels={
            "event_player": "Player",
            "total_absolute_swing_pct": "Total Win Probability Impact",
            "event_team": "Team",
            "event_count": "Events Tracked",
            "avg_absolute_swing_pct": "Average Impact Per Event",
        },
        title="Top Player Win Probability Impact",
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0B1020",
        margin=dict(l=20, r=20, t=60, b=20),
        height=420,
        legend_title_text="Team",
    )

    st.plotly_chart(fig, width="stretch")

    st.dataframe(
        clean_table_columns(player_impact),
        width="stretch",
        hide_index=True,
    )


def show_clutch_pressure(predictions: pd.DataFrame) -> None:
    st.subheader("Clutch Pressure")
    st.caption("High-pressure moments based on score closeness, time, and win-probability uncertainty.")

    features = calculate_clutch_pressure(predictions)
    features_with_time = add_game_time_columns(features)

    fig = px.scatter(
        features_with_time,
        x="game_minutes_elapsed",
        y="clutch_pressure",
        color="pressure_level",
        size="clutch_pressure",
        hover_data=[
            "period",
            "Clock",
            "home_score",
            "away_score",
            "score_margin_home",
            "home_win_prob_pct",
            "event_description",
        ],
        labels={
            "game_minutes_elapsed": "Game Time",
            "clutch_pressure": "Clutch Pressure",
            "pressure_level": "Pressure Level",
            "period": "Quarter",
            "home_score": "Home Score",
            "away_score": "Away Score",
            "score_margin_home": "Home Margin",
            "home_win_prob_pct": "Home Win Probability",
            "event_description": "Play",
        },
        title="Clutch Pressure Timeline",
    )

    fig.update_layout(
        template="plotly_dark",
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="#0B1020",
        margin=dict(l=20, r=20, t=60, b=20),
        height=430,
    )

    st.plotly_chart(fig, width="stretch")

    columns = [
        "period",
        "clock",
        "home_score",
        "away_score",
        "score_margin_home",
        "home_win_prob_pct",
        "clutch_pressure",
        "pressure_level",
        "event_description",
    ]

    display = features.sort_values("clutch_pressure", ascending=False)[columns].head(15)

    st.dataframe(
        clean_table_columns(display),
        width="stretch",
        hide_index=True,
    )


def show_comeback_meter(predictions: pd.DataFrame) -> None:
    st.subheader("Comeback Reality")
    st.caption("Moments where the trailing team had a comeback scenario worth analyzing.")

    comeback_report = build_comeback_report(predictions)

    st.dataframe(
        clean_table_columns(comeback_report),
        width="stretch",
        hide_index=True,
    )


def show_model_comparison(
    comparison_summary: pd.DataFrame,
    model_disagreements: pd.DataFrame,
) -> None:
    st.subheader("Model Comparison")
    st.caption("Compares the rule-based baseline against the trained logistic regression ML model.")

    if comparison_summary.empty or model_disagreements.empty:
        st.warning("Model comparison files were not found for this game.")
        st.info("Run: `python src/compare_models.py --game-id YOUR_GAME_ID`")
        return

    summary = comparison_summary.iloc[0]

    col1, col2, col3, col4 = st.columns(4)

    col1.metric(
        "Avg. Difference",
        f"{float(summary['average_absolute_difference_pct']):.1f}%",
    )
    col2.metric(
        "Max Difference",
        f"{float(summary['maximum_absolute_difference_pct']):.1f}%",
    )
    col3.metric(
        "Baseline Final WP",
        f"{float(summary['baseline_final_home_win_prob_pct']):.1f}%",
    )
    col4.metric(
        "ML Final WP",
        f"{float(summary['ml_final_home_win_prob_pct']):.1f}%",
    )

    st.markdown("### Biggest Baseline vs ML Disagreements")

    display = clean_table_columns(model_disagreements)

    st.dataframe(
        display,
        width="stretch",
        hide_index=True,
    )


def show_recap(
    recap: str,
    predictions: pd.DataFrame,
    home_team: str,
    away_team: str,
) -> None:
    st.subheader("Auto Game Recap")

    final_row = predictions.iloc[-1]
    home_score = int(final_row["home_score"])
    away_score = int(final_row["away_score"])

    col1, col2 = st.columns([1, 3])

    with col1:
        st.metric(home_team, home_score)
        st.metric(away_team, away_score)

    with col2:
        word_count = len(recap.split())
        read_time = max(1, round(word_count / 200))
        st.caption(f"{word_count} words · ~{read_time} min read")
        st.markdown(
            f"""
            <div class="premium-card">
            {recap}
            </div>
            """,
            unsafe_allow_html=True,
        )


def main() -> None:
    apply_custom_css()

    available_game_ids = get_available_game_ids()

    if not available_game_ids:
        st.error("No analyzed games found.")
        st.info("Run `python src/run_pipeline.py --game-id YOUR_GAME_ID` first.")
        st.stop()

    with st.sidebar:
        st.markdown("## 🏀 ClutchCast AI")
        st.caption("Premium NBA game intelligence engine")
        st.divider()

        selected_game_id = st.selectbox(
            "Select analyzed game",
            available_game_ids,
            index=len(available_game_ids) - 1,
        )

        available_modes = []

        if (PROCESSED_DIR / f"baseline_predictions_{selected_game_id}.csv").exists():
            available_modes.append("Baseline Model")

        if (PROCESSED_DIR / f"ml_predictions_{selected_game_id}.csv").exists():
            available_modes.append("ML Model")

        if (PROCESSED_DIR / f"advanced_predictions_{selected_game_id}.csv").exists():
            available_modes.append("Advanced ML Model")

        prediction_mode = st.selectbox(
            "Prediction mode",
            available_modes,
            index=len(available_modes) - 1,
        )

    data = load_dashboard_data(selected_game_id, prediction_mode)

    predictions = data["predictions"]
    recap = data["recap"]
    comparison_summary = data["comparison_summary"]
    model_disagreements = data["model_disagreements"]

    game_id = str(predictions["game_id"].iloc[0]).zfill(10)
    home_team, away_team = get_team_labels(game_id)

    with st.sidebar:
        st.divider()
        st.markdown(f"**Matchup:** {away_team} at {home_team}")
        st.markdown(f"**Game ID:** `{game_id}`")
        st.markdown(f"**Mode:** `{prediction_mode}`")
        st.divider()
        st.caption("Baseline = rule-based formula")
        st.caption("ML Model = logistic regression")
        st.caption("Advanced ML = random forest model")

    show_header(home_team, away_team, prediction_mode)
    show_game_summary(predictions, home_team, away_team, prediction_mode)
    show_win_probability_chart(predictions, home_team, away_team)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "Turning Points",
            "Player Impact",
            "Clutch Pressure",
            "Comeback Reality",
            "Model Comparison",
            "Game Recap",
        ]
    )

    with tab1:
        show_turning_points(predictions)

    with tab2:
        show_player_impact(predictions, home_team, away_team)

    with tab3:
        show_clutch_pressure(predictions)

    with tab4:
        show_comeback_meter(predictions)

    with tab5:
        show_model_comparison(comparison_summary, model_disagreements)

    with tab6:
        show_recap(recap, predictions, home_team, away_team)


if __name__ == "__main__":
    main()