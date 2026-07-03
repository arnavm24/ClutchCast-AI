import pandas as pd
import streamlit as st

from ui.config import MODE_LABELS
from ui.data_loaders import (
    get_available_game_ids,
    get_available_modes,
    load_demo_games,
    load_drama_leaderboard,
    load_game_index,
)
from ui.formatting import esc, render_html


def _select_game(game_id: str) -> None:
    st.session_state["pending_game_id"] = str(game_id)
    st.rerun()


def _index_label(row: pd.Series) -> str:
    home = str(row.get("home_team") or "Home")
    away = str(row.get("away_team") or "Away")
    score = f"{int(row.get('final_away_score', 0))}-{int(row.get('final_home_score', 0))}"
    ot = " · OT" if bool(row.get("went_overtime", False)) else ""
    return f"{away} @ {home} · {score}{ot} · {row.get('game_id', '')}"


def show_demo_buttons(available_ids: set[str]) -> None:
    demos = load_demo_games()
    if not demos:
        return
    st.markdown("### Demo Games")
    st.caption("One click loads a curated example.")
    for demo in demos:
        game_id = str(demo.get("game_id", ""))
        if not game_id:
            continue
        if st.button(demo.get("label", game_id), key=f"demo_{demo.get('key', game_id)}", use_container_width=True):
            if game_id in available_ids:
                _select_game(game_id)
            else:
                st.code(f"python src/batch_analyze.py --game-ids {game_id}", language="powershell")
        tagline = demo.get("tagline", "")
        if tagline:
            render_html(f'<div class="demo-tagline">{esc(tagline)}</div>')


def show_game_search(available_ids: set[str]) -> None:
    index = load_game_index()
    if index.empty:
        return
    with st.expander("🔎 Find a game"):
        teams = sorted(set(index["home_team"].dropna().astype(str)) | set(index["away_team"].dropna().astype(str)))
        teams = [team for team in teams if team and team.lower() != "nan"]
        picked_teams = st.multiselect("Team", teams, key="search_teams")
        col1, col2 = st.columns(2)
        with col1:
            close_only = st.checkbox("Close games (≤5)", key="search_close")
        with col2:
            overtime_only = st.checkbox("Overtime", key="search_ot")
        analyzed_only = st.checkbox("Analyzed games only", value=True, key="search_analyzed")

        results = index.copy()
        results["game_id"] = results["game_id"].astype(str)
        if picked_teams:
            results = results[results["home_team"].isin(picked_teams) | results["away_team"].isin(picked_teams)]
        if close_only and "final_margin" in results.columns:
            results = results[results["final_margin"].abs() <= 5]
        if overtime_only and "went_overtime" in results.columns:
            results = results[results["went_overtime"] == True]  # noqa: E712
        if analyzed_only:
            results = results[results["game_id"].isin(available_ids)]

        st.caption(f"{len(results)} game(s) match.")
        if results.empty:
            return
        results = results.reset_index(drop=True)
        pick = st.selectbox("Matching games", range(len(results)), format_func=lambda i: _index_label(results.iloc[i]), key="search_pick")
        picked_id = str(results.iloc[pick]["game_id"])
        if picked_id in available_ids:
            if st.button("Load game", key="search_load", use_container_width=True):
                _select_game(picked_id)
        else:
            st.caption("Not analyzed yet — run:")
            st.code(f"python src/batch_analyze.py --game-ids {picked_id}", language="powershell")


def show_drama_leaderboard(available_ids: set[str]) -> None:
    board = load_drama_leaderboard()
    if board.empty:
        return
    st.markdown("### 🎭 Most Dramatic Games")
    for rank, (_, row) in enumerate(board.head(5).iterrows(), start=1):
        game_id = str(row["game_id"])
        home = str(row.get("home_team") or "Home")
        away = str(row.get("away_team") or "Away")
        ot = " · OT" if bool(row.get("went_overtime", False)) else ""
        label = f"{row['drama_score']:.0f} · {away} @ {home}{ot}"
        if game_id in available_ids:
            if st.button(label, key=f"drama_{game_id}", use_container_width=True):
                _select_game(game_id)
        else:
            render_html(f'<div class="drama-row"><span class="drama-score">{row["drama_score"]:.0f}</span><span>{esc(away)} @ {esc(home)}{esc(ot)}</span></div>')


def render(champion_key: str, champion_label: str) -> tuple[str, str]:
    """Render sidebar; returns (selected_game_id, model_key)."""
    available_game_ids = get_available_game_ids()
    available_set = set(available_game_ids)
    selected_game_id = ""
    model_key = champion_key

    pending = st.session_state.pop("pending_game_id", None)
    if pending and pending in available_set:
        st.session_state["selected_game_id"] = pending

    with st.sidebar:
        st.markdown("## ClutchCast AI")
        if available_game_ids:
            if st.session_state.get("selected_game_id") not in available_set:
                st.session_state["selected_game_id"] = available_game_ids[-1]
            selected_game_id = st.selectbox("Analyzed game", available_game_ids, key="selected_game_id")
            available_modes = get_available_modes(selected_game_id)
            default_mode = champion_key if champion_key in available_modes else available_modes[-1]
            st.markdown(f"**Champion Model:** {champion_label}")
            st.caption("Main dashboard defaults to the champion when its prediction file exists.")
            advanced = st.checkbox("Inspect another model")
            model_key = st.selectbox("Model view", available_modes, index=available_modes.index(default_mode), format_func=lambda key: MODE_LABELS[key]) if advanced else default_mode
        else:
            st.warning("No historical games found yet.")
            st.code("python src/batch_analyze.py --test-games --limit 20", language="powershell")
        st.divider()
        show_demo_buttons(available_set)
        show_game_search(available_set)
        show_drama_leaderboard(available_set)
        st.divider()
        st.markdown("### Live Backend MVP")
        st.caption("Live Game polls Flask/SocketIO backend.")
        st.code("python backend/app.py", language="powershell")

    return selected_game_id, model_key
