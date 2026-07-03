import time

import pandas as pd
import streamlit as st

from ui.analytics import append_live_history, detect_current_run, largest_live_swing, momentum_signal
from ui.backend_client import fetch_backend_json
from ui.charts import live_timeline_chart
from ui.components import (
    classify_prediction_source,
    render_metric_card,
    render_quality_banner,
    render_scoreboard,
    show_backend_status,
    show_empty_report_card,
)
from ui.config import PROCESSED_DIR, team_color
from ui.data_loaders import get_available_game_ids, get_prediction_path, get_available_modes, get_team_labels
from ui.formatting import as_float, as_int, clean_table_columns, esc, format_nba_clock, render_html, short_text


def _history_store() -> dict:
    return st.session_state.setdefault("live_wp_history", {})


def _history_csv_path(game_id: str):
    return PROCESSED_DIR / f"live_history_{game_id}.csv"


def get_history(game_id: str) -> list[dict]:
    store = _history_store()
    if game_id not in store:
        path = _history_csv_path(game_id)
        if path.exists():
            try:
                store[game_id] = pd.read_csv(path).to_dict("records")
            except Exception:
                store[game_id] = []
        else:
            store[game_id] = []
    return store[game_id]


def persist_history(game_id: str) -> None:
    history = _history_store().get(game_id, [])
    if history:
        try:
            pd.DataFrame(history).to_csv(_history_csv_path(game_id), index=False)
        except OSError:
            pass


def record_payload(game_id: str, payload: dict) -> list[dict]:
    history = get_history(game_id)
    before = len(history)
    append_live_history(history, payload)
    if len(history) != before:
        st.session_state["live_last_change_ts"] = time.time()
        persist_history(game_id)
    return history


def show_quality_banner(payload: dict, auto_refresh: bool) -> None:
    kind = classify_prediction_source(payload.get("prediction_source", ""), payload.get("fallback_reason", ""))
    detail = str(payload.get("fallback_reason") or payload.get("warning") or "")
    chip = ""
    last_change = st.session_state.get("live_last_change_ts")
    period = as_int(payload.get("period"))
    if auto_refresh and last_change and (time.time() - last_change) > 60 and period > 0:
        chip = "Data Delay Possible"
    render_quality_banner(kind, detail=detail, chip=chip)


def show_live_scoreboard(payload: dict, champion_label: str, eyebrow: str = "Live Game Center") -> tuple[str, str]:
    game_id = str(payload.get("game_id", "")).zfill(10)
    fallback_home, fallback_away = get_team_labels(game_id) if game_id and game_id != "0000000000" else ("Home", "Away")
    home_team = str(payload.get("home_team") or fallback_home)
    away_team = str(payload.get("away_team") or fallback_away)
    model_name = payload.get("model_name") or payload.get("champion", {}).get("model_name") or champion_label
    champion_name = payload.get("champion", {}).get("model_name", champion_label)
    render_scoreboard(
        home_team=home_team,
        away_team=away_team,
        home_score=as_int(payload.get("home_score")),
        away_score=as_int(payload.get("away_score")),
        home_prob=as_float(payload.get("home_win_prob_pct"), 50.0),
        away_prob=as_float(payload.get("away_win_prob_pct"), 50.0),
        period=as_int(payload.get("period")),
        clock=format_nba_clock(payload.get("clock", "")),
        model_label=str(model_name),
        champion_label=str(champion_name),
        eyebrow=eyebrow,
    )
    return home_team, away_team


def show_broadcast_panels(history: list[dict], home_team: str, away_team: str, chart_prefix: str) -> None:
    if len(history) < 2:
        st.caption("The live timeline, scoring runs, and swings build up as updates arrive — keep polling or start a replay.")
        return
    run = detect_current_run(history, home_team, away_team)
    swing = largest_live_swing(history)
    momentum = momentum_signal(history)
    momentum_team = home_team if momentum >= 0 else away_team
    momentum_label = "🔥 Strong momentum" if abs(momentum) >= 10 else "📈 Building momentum" if abs(momentum) >= 4 else "😐 Flat stretch"
    chips = []
    if run:
        color = team_color(run["team"], "#3B82F6")
        chips.append(f'<span class="run-chip" style="background:{esc(color)}33; color:#F8FAFC; border-color:{esc(color)}88;">🏃 {esc(run["team"])} {esc(run["run"])} run</span>')
    chips.append(f'<span class="run-chip" style="background:rgba(15,23,42,.7); color:#DDE7F4;">{momentum_label} · {esc(momentum_team)} +{abs(momentum):.1f} WP</span>')
    render_html('<div style="display:flex; gap:10px; flex-wrap:wrap; margin:12px 0;">' + "".join(chips) + "</div>")

    left, right = st.columns([1.6, 1], gap="large")
    with left:
        st.markdown("#### Live Win Probability Timeline")
        live_timeline_chart(history, home_team, away_team, chart_key=f"{chart_prefix}_timeline_{len(history)}")
    with right:
        st.markdown("#### Broadcast Board")
        cards = []
        if swing:
            cards.append(render_metric_card("Largest Live Swing", f"{swing['swing']:+.1f} pts", short_text(str(swing.get("last_play") or "No play detail"), 120)))
        plays = []
        for snapshot in reversed(history):
            play = str(snapshot.get("last_play") or "").strip()
            if play and play not in plays:
                plays.append(play)
            if len(plays) == 5:
                break
        if plays:
            plays_html = "".join(f'<div class="driver-row"><span class="driver-name">{esc(short_text(play, 90))}</span></div>' for play in plays)
            cards.append(f'<div class="metric-card"><div class="metric-label">Last {len(plays)} Plays</div>{plays_html}<div class="metric-detail">Collected from live updates while polling.</div></div>')
        render_html("".join(cards))


def show_live_detail_cards(payload: dict, health: dict | None, champion_label: str) -> None:
    game_id = str(payload.get("game_id", "")).zfill(10)
    model_name = payload.get("model_name") or payload.get("champion", {}).get("model_name") or champion_label
    champion_name = payload.get("champion", {}).get("model_name", champion_label)
    has_play_by_play = bool(payload.get("has_play_by_play"))
    prediction_source = str(payload.get("prediction_source", "live_prediction"))
    data_source = str(payload.get("data_source", "backend"))
    status_text = "Backend online" if health and health.get("ok") else "Backend status unknown"
    cards = [
        render_metric_card("Last Play", short_text(payload.get("last_play", "No play available"), 42), short_text(payload.get("last_play", "No play available"), 160)),
        render_metric_card("Data Source", data_source.replace("_", " ").title(), f"Matched by: {payload.get('matched_by', 'unknown')}"),
        render_metric_card("Play-by-Play", "Available" if has_play_by_play else "Unavailable", f"Rows: {payload.get('play_by_play_rows', 0)} · Live rows: {payload.get('live_play_by_play_rows', 0)}"),
        render_metric_card("Prediction Source", str(model_name), prediction_source.replace("_", " ").title()),
    ]
    render_html('<div class="metric-grid">' + "".join(cards) + '</div>')
    detail_cards = [
        render_metric_card("Backend Status", status_text, f"GET /predict/{esc(game_id)}?mode=live"),
        render_metric_card("Fallback Reason", short_text(str(payload.get("fallback_reason") or "Full model path is active."), 44), short_text(str(payload.get("fallback_reason") or "Champion model inference used live play-by-play."), 160)),
        render_metric_card("Champion Model", str(champion_name), "Automatically used once live play-by-play becomes available."),
    ]
    render_html('<div class="summary-grid">' + "".join(detail_cards) + '</div>')


def show_today_games_helper() -> str | None:
    selected_game_id = None
    if st.button("Load Today's Games", key="live_load_today_games"):
        with st.spinner("Fetching today's games from the live backend..."):
            result = fetch_backend_json("/games/today", timeout=10.0)
        if not result["ok"]:
            st.error(result.get("data", {}).get("error", "Could not load today's games."))
        else:
            st.session_state["live_today_games"] = result.get("data", {}).get("games", [])

    games = st.session_state.get("live_today_games", [])
    if not games:
        return None

    def game_label(game: dict) -> str:
        away = game.get("away_team") or "Away"
        home = game.get("home_team") or "Home"
        clock = game.get("clock") or game.get("status") or ""
        return f"{game.get('GAME_ID')} | {away} {game.get('away_score', 0)} at {home} {game.get('home_score', 0)} | Q{game.get('period', 0)} {clock} | {game.get('data_source', 'scoreboard')}"

    display = pd.DataFrame(games)
    selected_index = st.selectbox("Today's games from live scoreboard", range(len(games)), format_func=lambda index: game_label(games[index]), key="live_today_games_select")
    if st.button("Use Selected GAME_ID", key="live_use_today_game"):
        selected_game_id = str(games[selected_index].get("GAME_ID", "")).zfill(10)
        st.session_state["live_game_id"] = selected_game_id
        st.success(f"Selected GAME_ID {selected_game_id}.")
    st.dataframe(clean_table_columns(display), width="stretch", hide_index=True)
    return selected_game_id


def replay_payload_from_row(row: pd.Series, game_id: str, home_team: str, away_team: str, champion_label: str) -> dict:
    return {
        "game_id": game_id,
        "home_team": home_team,
        "away_team": away_team,
        "period": as_int(row.get("period")),
        "clock": row.get("clock", ""),
        "home_score": as_int(row.get("home_score")),
        "away_score": as_int(row.get("away_score")),
        "home_win_prob_pct": as_float(row.get("home_win_prob_pct"), 50.0),
        "away_win_prob_pct": as_float(row.get("away_win_prob_pct"), 50.0),
        "last_play": str(row.get("event_description") or ""),
        "prediction_source": "replay_historical",
        "model_name": champion_label,
    }


def show_replay_mode(champion_label: str) -> None:
    with st.expander("🎬 Replay an analyzed game through the live pipeline (works offline)"):
        render_html('<div class="tab-intro">Feeds a saved game through the exact same live rendering path — timeline, runs, swings, and badges — so the Live Game Center can be demoed without a live NBA game.</div>')
        game_ids = get_available_game_ids()
        if not game_ids:
            st.info("Analyze a game first (see the sidebar) to unlock replay mode.")
            return
        col1, col2, col3 = st.columns([1.4, 1, 1])
        with col1:
            replay_game = st.selectbox("Analyzed game to replay", game_ids, key="replay_game_select")
        with col2:
            speed = st.slider("Events per update", 1, 40, 12, key="replay_speed")
        with col3:
            running = st.toggle("Run replay", key="replay_running")
            if st.button("Restart replay", key="replay_restart"):
                st.session_state["replay_cursor"] = 0
                _history_store()[f"replay_{replay_game}"] = []

        modes = get_available_modes(replay_game)
        if not modes:
            return
        predictions = pd.read_csv(get_prediction_path(replay_game, modes[-1]), dtype={"game_id": str})
        home_team, away_team = get_team_labels(replay_game)
        history_key = f"replay_{replay_game}"

        def replay_body() -> None:
            cursor = st.session_state.get("replay_cursor", 0)
            if running:
                cursor = min(cursor + speed, len(predictions) - 1)
                st.session_state["replay_cursor"] = cursor
            if cursor <= 0 and not running:
                st.caption("Toggle 'Run replay' to start streaming this game.")
                return
            row = predictions.iloc[cursor]
            payload = replay_payload_from_row(row, replay_game, home_team, away_team, champion_label)
            history = _history_store().setdefault(history_key, [])
            append_live_history(history, payload)
            render_quality_banner("replay", detail=f"Event {cursor + 1} of {len(predictions)} · {champion_label}")
            show_live_scoreboard(payload, champion_label, eyebrow="Replay · Live Game Center Demo")
            show_broadcast_panels(history, home_team, away_team, chart_prefix="replay")
            if cursor >= len(predictions) - 1 and running:
                st.success("Replay finished — final state reached.")

        if running:
            st.fragment(run_every="2s")(replay_body)()
        else:
            replay_body()


def render(champion_label: str) -> None:
    st.subheader("Live Game")
    render_html('<div class="tab-intro">Streamlit polls the local Flask backend for live NBA updates. Start the backend first with <code>python backend/app.py</code>. The banner below always shows exactly which data path produced the current probability.</div>')

    col1, col2, col3 = st.columns([1.4, 1, 1])
    with col1:
        game_id = st.text_input("Live GAME_ID", value=st.session_state.get("live_game_id", ""), placeholder="Example: 0042300312", key="live_game_id_input")
        game_id = str(game_id).strip().zfill(10) if str(game_id).strip() else ""
        st.session_state["live_game_id"] = game_id
    with col2:
        auto_refresh = st.checkbox("Auto-refresh every 10 seconds", key="live_auto_refresh")
    with col3:
        st.caption("Live accuracy/update speed depends on NBA API availability and delay.")

    check_status = st.button("Check Backend Status", key="live_check_backend")
    fetch_live = st.button("Fetch Live Prediction", type="primary", key="live_fetch_prediction")
    selected_today_game = show_today_games_helper()
    if selected_today_game:
        game_id = selected_today_game

    def live_body() -> None:
        health = None
        if check_status or fetch_live or auto_refresh:
            health = fetch_backend_json("/health", timeout=2.0)
            show_backend_status(health)

        should_fetch = bool(game_id) and (fetch_live or auto_refresh)
        payload = None
        if should_fetch:
            with st.spinner("Fetching live prediction from backend..."):
                result = fetch_backend_json(f"/predict/{game_id}?mode=live", timeout=20.0)
            if result["ok"]:
                candidate = result["data"]
                if isinstance(candidate, dict) and candidate.get("error"):
                    st.error(candidate["error"])
                else:
                    payload = candidate
                    st.session_state["last_live_payload"] = payload
                    record_payload(game_id, payload)
            else:
                error = result.get("data", {}).get("error", "Backend request failed.")
                st.error(error)
                if "play-by-play" in str(error).lower() or "not" in str(error).lower():
                    st.info("The game may not have started yet, or NBA API may not have play-by-play data available.")
        if payload is None and st.session_state.get("last_live_payload"):
            payload = st.session_state["last_live_payload"]

        if payload:
            show_quality_banner(payload, auto_refresh)
            home_team, away_team = show_live_scoreboard(payload, champion_label)
            warning = str(payload.get("warning") or "")
            if warning:
                st.warning(warning)
            history = get_history(str(payload.get("game_id", game_id)).zfill(10)) if game_id else []
            show_broadcast_panels(history, home_team, away_team, chart_prefix="live")
            show_live_detail_cards(payload, health, champion_label)
        else:
            show_empty_report_card("Live Game", "python backend/app.py")

    if auto_refresh:
        st.fragment(run_every="10s")(live_body)()
        st.caption("Auto-refresh is on — updates arrive every 10 seconds without reloading the page, so the timeline keeps building.")
    else:
        live_body()

    show_replay_mode(champion_label)

    st.markdown("### Live Backend MVP Note")
    st.info("This is a local-first polling MVP. It does not use a paid feed and should be expected to lag or fail when nba_api is delayed or unavailable.")
