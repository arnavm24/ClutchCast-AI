from pathlib import Path

import pandas as pd
import plotly.express as px
import streamlit as st


PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")


st.set_page_config(
    page_title="ClutchCast AI",
    page_icon="🏀",
    layout="wide",
)


def load_latest_csv(folder: Path, pattern: str) -> pd.DataFrame:
    files = list(folder.glob(pattern))

    if not files:
        st.error(f"No file found for pattern: {folder / pattern}")
        st.stop()

    return pd.read_csv(files[0], dtype={"game_id": str})


def load_latest_text(folder: Path, pattern: str) -> str:
    files = list(folder.glob(pattern))

    if not files:
        return "No recap file found. Run `python src/recap.py` first."

    return files[0].read_text(encoding="utf-8")


@st.cache_data
def load_dashboard_data():
    predictions = load_latest_csv(PROCESSED_DIR, "baseline_predictions_*.csv")
    features = load_latest_csv(PROCESSED_DIR, "features_*.csv")
    momentum = load_latest_csv(PROCESSED_DIR, "momentum_*.csv")

    turning_points = load_latest_csv(REPORTS_DIR, "turning_points_*.csv")
    player_impact = load_latest_csv(REPORTS_DIR, "player_impact_*.csv")
    comeback_report = load_latest_csv(REPORTS_DIR, "comeback_report_*.csv")
    momentum_report = load_latest_csv(REPORTS_DIR, "momentum_report_*.csv")

    recap = load_latest_text(REPORTS_DIR, "post_game_recap_*.md")

    return {
        "predictions": predictions,
        "features": features,
        "momentum": momentum,
        "turning_points": turning_points,
        "player_impact": player_impact,
        "comeback_report": comeback_report,
        "momentum_report": momentum_report,
        "recap": recap,
    }


def add_game_time_columns(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()

    total_game_seconds = 48 * 60
    output["game_seconds_elapsed"] = total_game_seconds - output["seconds_remaining"]
    output["game_minutes_elapsed"] = output["game_seconds_elapsed"] / 60

    return output


def show_game_summary(predictions: pd.DataFrame) -> None:
    final_row = predictions.iloc[-1]

    game_id = str(final_row["game_id"]).zfill(10)
    home_score = int(final_row["home_score"])
    away_score = int(final_row["away_score"])
    margin = int(final_row["score_margin_home"])

    if margin > 0:
        result = f"Home team won by {margin}"
    elif margin < 0:
        result = f"Away team won by {abs(margin)}"
    else:
        result = "Tie / data issue"

    st.subheader("Game Summary")

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Game ID", game_id)
    col2.metric("Final Score", f"Home {home_score} - Away {away_score}")
    col3.metric("Result", result)
    col4.metric("Events Tracked", len(predictions))


def show_win_probability_chart(predictions: pd.DataFrame) -> None:
    st.subheader("Live Win Probability Curve")

    chart_data = add_game_time_columns(predictions)

    chart_data_long = chart_data.melt(
        id_vars=[
            "game_minutes_elapsed",
            "period",
            "clock",
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
            "home_win_prob_pct": "Home Team",
            "away_win_prob_pct": "Away Team",
        }
    )

    fig = px.line(
        chart_data_long,
        x="game_minutes_elapsed",
        y="win_probability_pct",
        color="team",
        hover_data=[
            "period",
            "clock",
            "home_score",
            "away_score",
            "score_margin_home",
            "event_description",
        ],
        labels={
            "game_minutes_elapsed": "Game Minutes Elapsed",
            "win_probability_pct": "Win Probability (%)",
            "team": "Team",
        },
        title="Home vs Away Win Probability Over Game Time",
    )

    fig.update_yaxes(range=[0, 100])
    fig.update_layout(hovermode="x unified")

    st.plotly_chart(fig, use_container_width=True)


def show_turning_points(turning_points: pd.DataFrame) -> None:
    st.subheader("Top Turning Points")
    st.caption("Largest win-probability swings in the game.")
    st.dataframe(turning_points, use_container_width=True)


def show_player_impact(player_impact: pd.DataFrame) -> None:
    st.subheader("Player Swing Impact")
    st.caption("Players ranked by total absolute win-probability swing involvement.")
    st.dataframe(player_impact, use_container_width=True)

    top_10 = player_impact.head(10)

    fig = px.bar(
        top_10,
        x="event_player",
        y="total_absolute_swing_pct",
        hover_data=["event_team", "event_count", "avg_absolute_swing_pct"],
        labels={
            "event_player": "Player",
            "total_absolute_swing_pct": "Total Absolute WP Swing (%)",
        },
        title="Top Player Swing Impact",
    )

    st.plotly_chart(fig, use_container_width=True)


def show_clutch_pressure(features: pd.DataFrame) -> None:
    st.subheader("Clutch Pressure Index")
    st.caption(
        "Highest-pressure moments based on score closeness, time remaining, "
        "and win-probability uncertainty."
    )

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

    available_columns = [col for col in columns if col in features.columns]

    st.dataframe(
        features.sort_values("clutch_pressure", ascending=False)[available_columns].head(15),
        use_container_width=True,
    )


def show_comeback_meter(comeback_report: pd.DataFrame) -> None:
    st.subheader("Comeback Reality Meter")
    st.caption("Moments where a trailing team had a comeback scenario worth analyzing.")
    st.dataframe(comeback_report, use_container_width=True)


def show_hidden_momentum(momentum_report: pd.DataFrame) -> None:
    st.subheader("Hidden Momentum Index")
    st.caption(
        "Recent-flow score based on score margin changes, "
        "win-probability movement, and event value."
    )
    st.dataframe(momentum_report, use_container_width=True)


def show_recap(recap: str) -> None:
    st.subheader("Auto Post-Game Recap")
    st.markdown(recap)


def main() -> None:
    st.title("🏀 ClutchCast AI")
    st.caption("NBA win probability, turning-point, momentum, and game-story engine.")

    data = load_dashboard_data()

    predictions = data["predictions"]
    features = data["features"]
    turning_points = data["turning_points"]
    player_impact = data["player_impact"]
    comeback_report = data["comeback_report"]
    momentum_report = data["momentum_report"]
    recap = data["recap"]

    show_game_summary(predictions)
    show_win_probability_chart(predictions)

    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "Turning Points",
            "Player Impact",
            "Clutch Pressure",
            "Comeback Meter",
            "Hidden Momentum",
            "Recap",
        ]
    )

    with tab1:
        show_turning_points(turning_points)

    with tab2:
        show_player_impact(player_impact)

    with tab3:
        show_clutch_pressure(features)

    with tab4:
        show_comeback_meter(comeback_report)

    with tab5:
        show_hidden_momentum(momentum_report)

    with tab6:
        show_recap(recap)


if __name__ == "__main__":
    main()