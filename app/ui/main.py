import pandas as pd
import streamlit as st

from ui.config import CLUTCHCAST_ICON_DATA_URL, MODE_LABELS
from ui.theme import apply_custom_css


def run() -> None:
    st.set_page_config(page_title="ClutchCast AI", page_icon=CLUTCHCAST_ICON_DATA_URL, layout="wide", initial_sidebar_state="expanded")
    apply_custom_css()

    from champion_inference import load_champion_metadata

    from ui import sidebar
    from ui.components import show_brand_header
    from ui.data_loaders import get_team_labels, load_dashboard_data
    from ui.tabs import evaluation, insights, live, overview, player_impact, pressure, recap, turning_points, win_probability

    champion = load_champion_metadata()
    champion_key = champion.get("model_key", "baseline")
    champion_label = champion.get("model_name", MODE_LABELS.get(champion_key, "Baseline Model"))

    selected_game_id, model_key = sidebar.render(champion_key, champion_label)

    data = None
    predictions = pd.DataFrame()
    home_team, away_team = "Home", "Away"
    model_label = MODE_LABELS.get(model_key, model_key)
    champion_view = False

    if selected_game_id:
        data = load_dashboard_data(selected_game_id, model_key)
        predictions = data["predictions"]
        home_team, away_team = get_team_labels(selected_game_id)
        model_label = MODE_LABELS.get(model_key, model_key)
        champion_view = model_key == champion_key

    show_brand_header(selected_game_id, home_team, away_team)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8, tab9 = st.tabs([
        "🏀 Game Overview", "📈 Win Probability", "🔴 Live Game", "🧠 Game Insights", "🔄 Turning Points",
        "⭐ Player Impact", "⏱ Pressure & Comebacks", "🧪 Model Evaluation", "📰 Game Recap",
    ])

    def show_missing_historical_tab(command: str) -> None:
        st.info("No historical prediction files are available yet. Live Game can still be used if the backend is running.")
        st.code(command, language="powershell")

    missing_command = "python src/batch_analyze.py --test-games --limit 20"
    with tab1:
        overview.render(data, predictions, selected_game_id, home_team, away_team, model_label, champion_label, champion_view, model_key) if data is not None else show_missing_historical_tab(missing_command)
    with tab2:
        win_probability.render(data, predictions, selected_game_id, home_team, away_team, champion_view, model_key, model_label) if data is not None else show_missing_historical_tab(missing_command)
    with tab3:
        live.render(champion_label)
    with tab4:
        insights.render(data, selected_game_id) if data is not None else show_missing_historical_tab("python src/game_insights.py --game-id YOUR_GAME_ID")
    with tab5:
        turning_points.render(predictions, selected_game_id) if data is not None else show_missing_historical_tab("python src/turning_points.py --game-id YOUR_GAME_ID")
    with tab6:
        player_impact.render(predictions, selected_game_id, home_team, away_team) if data is not None else show_missing_historical_tab("python src/player_impact.py --game-id YOUR_GAME_ID")
    with tab7:
        pressure.render(predictions, selected_game_id) if data is not None else show_missing_historical_tab(missing_command)
    with tab8:
        evaluation.render(data, champion, selected_game_id) if data is not None else show_missing_historical_tab("python src/compare_models.py --leaderboard")
    with tab9:
        recap.render(data, selected_game_id) if data is not None else show_missing_historical_tab("python src/recap.py --game-id YOUR_GAME_ID")
