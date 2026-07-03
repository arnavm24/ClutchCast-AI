import pandas as pd

from ui.config import DEFAULT_AWAY_COLOR, DEFAULT_HOME_COLOR, team_color, team_logo_url
from ui.formatting import as_float, as_int, esc, format_nba_clock, format_period, initials, render_html


def render_logo(team: str, color: str) -> str:
    logo_url = team_logo_url(team)
    if logo_url:
        return f'<div class="team-logo-wrap"><img class="team-logo" src="{esc(logo_url)}" alt="{esc(team)} logo"></div>'
    return f'<div class="team-fallback" style="background:{esc(color)};">{esc(team)[:3]}</div>'


def render_team_block(team: str, score: int, prob: float, color: str, side: str) -> str:
    return (
        f'<div class="team-box {esc(side)}" style="border-color:{esc(color)}55;">'
        f'{render_logo(team, color)}<div><div class="team-name">{esc(team)}</div>'
        f'<div class="team-score">{score}</div><div class="team-prob-label">Win Probability</div>'
        f'<div class="team-prob-big">{prob:.1f}%</div></div></div>'
    )


def render_metric_card(label: str, value: str, detail: str = "") -> str:
    return f'<div class="metric-card"><div class="metric-label">{esc(label)}</div><div class="metric-value">{esc(value)}</div><div class="metric-detail">{esc(detail)}</div></div>'


def render_summary_card(label: str, value: str, detail: str = "", big: bool = False, avatar: str | None = None) -> str:
    value_class = "summary-value big" if big else "summary-value"
    avatar_html = f'<div class="avatar">{esc(avatar)}</div>' if avatar else ""
    return f'<div class="summary-card"><div class="player-chip">{avatar_html}<div><div class="summary-label">{esc(label)}</div><div class="{value_class}">{esc(value)}</div></div></div><div class="summary-detail">{esc(detail)}</div></div>'


def render_info_card(title: str, value: str, detail: str, icon: str = "") -> str:
    icon_html = f'<div class="icon-pill">{esc(icon)}</div>' if icon else ""
    return f'<div class="insight-card">{icon_html}<div class="card-kicker">{esc(title)}</div><div class="card-value">{esc(value)}</div><div class="card-detail">{esc(detail)}</div></div>'


def show_empty_report_card(title: str, command: str) -> None:
    render_html(f'<div class="empty-card"><div class="summary-label">{esc(title)}</div><div class="summary-detail">Report data is not available yet.</div><div class="summary-detail"><code>{esc(command)}</code></div></div>')


def show_scoreboard(predictions: pd.DataFrame, home_team: str, away_team: str, model_label: str, champion_label: str) -> None:
    row = predictions.iloc[-1]
    render_scoreboard(
        home_team=home_team,
        away_team=away_team,
        home_score=as_int(row.get("home_score")),
        away_score=as_int(row.get("away_score")),
        home_prob=as_float(row.get("home_win_prob_pct"), 50.0),
        away_prob=as_float(row.get("away_win_prob_pct"), 50.0),
        period=as_int(row.get("period")),
        clock=format_nba_clock(row.get("clock", "")),
        model_label=model_label,
        champion_label=champion_label,
        eyebrow="ClutchCast AI Game Center",
    )


def render_scoreboard(home_team: str, away_team: str, home_score: int, away_score: int, home_prob: float, away_prob: float, period: int, clock: str, model_label: str, champion_label: str, eyebrow: str) -> None:
    home_color = team_color(home_team, DEFAULT_HOME_COLOR)
    away_color = team_color(away_team, DEFAULT_AWAY_COLOR)
    render_html(
        f"""
        <div class="hero-shell">
          <div class="eyebrow">{esc(eyebrow)}</div>
          <div class="scoreboard">
            {render_team_block(away_team, away_score, away_prob, away_color, "away")}
            <div class="clock-card">
              <div class="clock-label">{esc(format_period(period) if period else "Pregame")}</div>
              <div class="clock-value">{esc(clock or "--")}</div>
              <div class="model-pill">{esc(model_label)} &middot; Champion: {esc(champion_label)}</div>
            </div>
            {render_team_block(home_team, home_score, home_prob, home_color, "home")}
          </div>
          <div class="wp-wrap">
            <div class="wp-row"><span>{esc(away_team)} <strong>{away_prob:.1f}%</strong></span><span>{esc(home_team)} <strong>{home_prob:.1f}%</strong></span></div>
            <div class="wp-bar">
              <div class="wp-away" style="width:{away_prob:.3f}%; background: linear-gradient(90deg, {esc(away_color)}, {esc(away_color)}cc);"></div>
              <div class="wp-home" style="width:{home_prob:.3f}%; background: linear-gradient(90deg, {esc(home_color)}cc, {esc(home_color)});"></div>
            </div>
          </div>
        </div>
        """
    )


def show_brand_header(game_id: str, home_team: str, away_team: str) -> None:
    subtitle = f"NBA Win Probability Platform · {away_team} at {home_team} · Game ID {game_id}" if game_id else "NBA Win Probability Platform · Historical and Live Game Center"
    render_html(f'<div class="brand-header"><div class="brand-left"><div class="brand-mark"><span class="brand-cc">CC</span></div><div><div class="brand-title">ClutchCast AI</div><div class="brand-subtitle">{esc(subtitle)}</div></div></div><div class="brand-badge">Historical Dashboard · Live Backend MVP Available</div></div>')


def show_backend_status(result: dict | None) -> None:
    import streamlit as st

    if result and result.get("ok"):
        render_html('<span class="status-badge status-ok">Backend online</span>')
    else:
        render_html('<span class="status-badge status-bad">Backend offline</span>')
        st.warning("Backend is not running. Start it with: python backend/app.py")


QUALITY_BADGES = {
    "full": ("quality-full", "Full Champion Model", "Live play-by-play is feeding the champion model."),
    "historical": ("quality-historical", "Champion Model · Historical Game State", "Prediction built from saved game-state data."),
    "fallback": ("quality-fallback", "Scoreboard Fallback", "Simple margin baseline — live play-by-play unavailable."),
    "missing": ("quality-missing", "Model Artifacts Missing", "Champion model files could not be loaded; using rule fallback."),
    "replay": ("quality-replay", "Replay Mode", "Replaying an analyzed game through the live pipeline."),
}


def classify_prediction_source(prediction_source: str, fallback_reason: str = "") -> str:
    source = str(prediction_source or "").lower()
    reason = str(fallback_reason or "").lower()
    if source == "replay_historical":
        return "replay"
    if source == "champion_model_live_play_by_play":
        return "full"
    if source == "champion_model_historical_game_state":
        return "historical"
    if "artifact" in reason or "model file" in reason or "missing" in reason:
        return "missing"
    return "fallback"


def render_quality_banner(kind: str, detail: str = "", chip: str = "") -> None:
    css_class, title, default_detail = QUALITY_BADGES.get(kind, QUALITY_BADGES["fallback"])
    chip_html = f'<span class="quality-chip">{esc(chip)}</span>' if chip else ""
    render_html(
        f'<div class="quality-banner {css_class}"><span class="q-dot" style="background:currentColor;"></span>'
        f'<div><div class="q-title">{esc(title)}</div><div class="q-detail">{esc(detail or default_detail)}</div></div>{chip_html}</div>'
    )


def render_player_card(name: str, team: str, stats: dict, person_id: int | None, accent: str) -> str:
    from ui.config import player_headshot_url
    from ui.formatting import format_period as fmt_period

    headshot = ""
    if person_id:
        headshot = f'<img class="headshot-img" src="{esc(player_headshot_url(person_id))}" alt="">'
    total = stats.get("total_impact", 0.0)
    clutch = stats.get("clutch_impact", 0.0)
    net = stats.get("net_impact", 0.0)
    positive = stats.get("positive_swing", 0.0)
    negative = stats.get("negative_swing", 0.0)
    split_total = max(positive + negative, 0.001)
    pos_pct = 100 * positive / split_total
    top_when = f"{fmt_period(int(stats.get('top_play_period', 1)))} {format_nba_clock(stats.get('top_play_clock', ''))}"
    markup = f"""
    <div class="player-card" style="--accent:{esc(accent)};">
      <div class="player-card-head">
        <div class="headshot-wrap"><div class="headshot-fallback">{esc(initials(name))}</div>{headshot}</div>
        <div><div class="player-card-name">{esc(name)}</div><div class="player-card-team">{esc(team)} · {stats.get('events', 0)} tracked plays</div></div>
      </div>
      <div class="player-stat-grid">
        <div class="player-stat"><div class="p-label">Total Impact</div><div class="p-value">{total:.1f} pts</div></div>
        <div class="player-stat"><div class="p-label">Net Impact</div><div class="p-value">{net:+.1f} pts</div></div>
        <div class="player-stat"><div class="p-label">Clutch Impact</div><div class="p-value">{clutch:+.1f} pts</div></div>
        <div class="player-stat"><div class="p-label">Biggest Play</div><div class="p-value">{stats.get('top_play_swing', 0.0):+.1f} pts</div></div>
      </div>
      <div class="split-bar"><div class="split-pos" style="width:{pos_pct:.1f}%"></div><div class="split-neg" style="width:{100 - pos_pct:.1f}%"></div></div>
      <div class="split-legend"><span>Helped +{positive:.1f}</span><span>Hurt -{negative:.1f}</span></div>
      <div class="top-play"><div class="tp-kicker">Top Play · {esc(top_when)} · {stats.get('top_play_swing', 0.0):+.1f} WP</div>{esc(str(stats.get('top_play', ''))[:170])}</div>
    </div>
    """
    # Indented multi-line HTML becomes a Markdown code block when concatenated
    # after other markup, so collapse it to a single line.
    return "".join(line.strip() for line in markup.splitlines())
