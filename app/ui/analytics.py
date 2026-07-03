import pandas as pd

from ui.formatting import as_float


def is_rankable_event(df: pd.DataFrame) -> pd.Series:
    description = df["event_description"].fillna("").astype(str).str.lower()
    event_team = df["event_team"].fillna("").astype(str).str.strip()
    event_player = df["event_player"].fillna("").astype(str).str.strip()
    return (
        (df["seconds_remaining"] > 0)
        & ~description.str.contains("end of", regex=False)
        & ~description.str.contains("instant replay", regex=False)
        & ~description.str.contains("timeout", regex=False)
        & ~description.str.contains("sub:", regex=False)
        & (event_team != "")
        & (event_player != "")
    )


def get_insight(data: dict, name: str, field: str = "details", default: str = "Run game insights to populate this.") -> str:
    insights = data.get("game_insights", pd.DataFrame())
    if insights.empty or "insight" not in insights.columns:
        return default
    rows = insights[insights["insight"] == name]
    if rows.empty or field not in rows.columns:
        return default
    value = rows.iloc[0][field]
    return default if pd.isna(value) or str(value).strip() == "" else str(value)


def build_turning_points(predictions: pd.DataFrame, top_n: int = 10) -> pd.DataFrame:
    data = predictions.copy()
    data["wp_before_pct"] = (data["home_win_prob"].shift(1).fillna(data["home_win_prob"]) * 100).round(1)
    data["wp_after_pct"] = data["home_win_prob_pct"]
    data["wp_swing_pct"] = (data["wp_after_pct"] - data["wp_before_pct"]).round(1)
    data = data[(data["abs_wp_change"] > 0) & is_rankable_event(data)]
    cols = ["period", "clock", "home_score", "away_score", "score_margin_home", "event_team", "event_player", "event_description", "wp_before_pct", "wp_after_pct", "wp_swing_pct"]
    return data.sort_values("abs_wp_change", ascending=False).head(top_n)[cols]


def build_player_impact(predictions: pd.DataFrame) -> pd.DataFrame:
    data = predictions[is_rankable_event(predictions)].copy()
    if data.empty:
        return pd.DataFrame()
    data["positive_swing_pct"] = (data["wp_change"] * 100).round(2)
    data["absolute_swing_pct"] = (data["abs_wp_change"] * 100).round(2)
    grouped = data.groupby(["event_player", "event_team"], as_index=False).agg(
        total_raw_home_wp_swing_pct=("positive_swing_pct", "sum"),
        total_absolute_swing_pct=("absolute_swing_pct", "sum"),
        avg_absolute_swing_pct=("absolute_swing_pct", "mean"),
        event_count=("event_player", "count"),
    )
    grouped = grouped.round(2).sort_values("total_absolute_swing_pct", ascending=False).reset_index(drop=True)
    grouped.insert(0, "rank", range(1, len(grouped) + 1))
    return grouped


def build_player_events(predictions: pd.DataFrame, home_team: str) -> pd.DataFrame:
    """Per-event player swings with team perspective and clutch flags, for matchup cards."""
    data = predictions[is_rankable_event(predictions)].copy()
    if data.empty:
        return pd.DataFrame()
    data["wp_before_pct"] = (data["home_win_prob"].shift(1).fillna(data["home_win_prob"]) * 100).round(1)
    data["wp_after_pct"] = data["home_win_prob_pct"]
    data["home_swing_pct"] = (data["wp_change"] * 100).round(2)
    data["abs_swing_pct"] = (data["abs_wp_change"] * 100).round(2)
    is_home = data["event_team"].astype(str).str.upper() == str(home_team).upper()
    data["team_swing_pct"] = data["home_swing_pct"].where(is_home, -data["home_swing_pct"]).round(2)
    data["is_clutch"] = (data["period"] >= 4) & (data["seconds_remaining"] <= 300)
    data["game_minutes_elapsed"] = ((48 * 60) - data["seconds_remaining"]) / 60
    cols = [
        "period", "clock", "seconds_remaining", "game_minutes_elapsed", "home_score", "away_score",
        "event_player", "event_team", "event_description",
        "wp_before_pct", "wp_after_pct", "home_swing_pct", "abs_swing_pct", "team_swing_pct", "is_clutch",
    ]
    return data[cols].reset_index(drop=True)


def summarize_player(events: pd.DataFrame, player: str, team: str) -> dict:
    rows = events[(events["event_player"] == player) & (events["event_team"] == team)]
    if rows.empty:
        return {}
    positive = rows.loc[rows["team_swing_pct"] > 0, "team_swing_pct"].sum()
    negative = rows.loc[rows["team_swing_pct"] < 0, "team_swing_pct"].sum()
    clutch = rows.loc[rows["is_clutch"], "team_swing_pct"].sum()
    top = rows.loc[rows["team_swing_pct"].idxmax()]
    return {
        "player": player,
        "team": team,
        "events": int(len(rows)),
        "total_impact": float(rows["abs_swing_pct"].sum()),
        "net_impact": float(rows["team_swing_pct"].sum()),
        "clutch_impact": float(clutch),
        "positive_swing": float(positive),
        "negative_swing": float(abs(negative)),
        "top_play": str(top["event_description"]),
        "top_play_period": int(top["period"]),
        "top_play_clock": top["clock"],
        "top_play_swing": float(top["team_swing_pct"]),
    }


def calculate_clutch_pressure(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    elapsed_ratio = (1 - (output["seconds_remaining"] / (48 * 60))).clip(0, 1)
    closeness = (1 - (output["abs_score_margin"] / 20)).clip(0, 1)
    uncertainty = 1 - ((output["home_win_prob"] - 0.5).abs() / 0.5).clip(0, 1)
    output["clutch_pressure"] = ((0.40 * closeness + 0.35 * elapsed_ratio + 0.25 * uncertainty) * 100).round(1)
    output["pressure_level"] = pd.cut(output["clutch_pressure"], bins=[-1, 25, 50, 75, 100], labels=["Low", "Medium", "High", "Extreme"])
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
    data["required_points_per_minute"] = data.apply(lambda row: round(row["deficit"] / max(row["seconds_remaining"] / 60, 0.01), 2) if row["deficit"] > 0 else 0, axis=1)
    data["comeback_status"] = pd.cut(data["comeback_probability"], bins=[-1, .03, .10, .25, .40, 1], labels=["Nearly impossible", "Very unlikely", "Difficult", "Possible", "Very realistic"])
    rows = data[(data["trailing_team"] != "Tie") & (data["seconds_remaining"] > 0) & (data["deficit"] >= 5)].copy()
    if rows.empty:
        return pd.DataFrame()
    rows["interest_score"] = rows["deficit"] * .45 + rows["clutch_pressure"] * .35 + rows["comeback_probability_pct"] * .20
    cols = ["period", "clock", "home_score", "away_score", "trailing_team", "deficit", "comeback_probability_pct", "comeback_status", "required_points_per_minute", "clutch_pressure", "pressure_level", "event_description"]
    return rows.sort_values("interest_score", ascending=False).head(10)[cols]


def append_live_history(history: list[dict], payload: dict) -> list[dict]:
    """Append a live payload snapshot to history, deduping identical states."""
    snapshot = {
        "period": payload.get("period", 0),
        "clock": str(payload.get("clock", "")),
        "home_score": payload.get("home_score", 0),
        "away_score": payload.get("away_score", 0),
        "home_win_prob_pct": as_float(payload.get("home_win_prob_pct"), 50.0),
        "away_win_prob_pct": as_float(payload.get("away_win_prob_pct"), 50.0),
        "prediction_source": str(payload.get("prediction_source", "")),
        "last_play": str(payload.get("last_play", "")),
    }
    if history:
        last = history[-1]
        same = all(last.get(key) == snapshot.get(key) for key in ("period", "clock", "home_score", "away_score", "home_win_prob_pct"))
        if same:
            return history
    history.append(snapshot)
    return history


def detect_current_run(history: list[dict], home_team: str, away_team: str) -> dict | None:
    """Detect a scoring run from live score history, e.g. 'SAS 10-2 run'."""
    if len(history) < 2:
        return None
    home_pts = 0
    away_pts = 0
    for index in range(len(history) - 1, 0, -1):
        current, previous = history[index], history[index - 1]
        home_delta = as_float(current.get("home_score")) - as_float(previous.get("home_score"))
        away_delta = as_float(current.get("away_score")) - as_float(previous.get("away_score"))
        if home_delta < 0 or away_delta < 0:
            break
        prospective_home = home_pts + home_delta
        prospective_away = away_pts + away_delta
        if min(prospective_home, prospective_away) > 4:
            break
        home_pts, away_pts = prospective_home, prospective_away
    home_pts, away_pts = int(home_pts), int(away_pts)
    if max(home_pts, away_pts) >= 6 and (max(home_pts, away_pts) - min(home_pts, away_pts)) >= 4:
        if home_pts > away_pts:
            return {"team": home_team, "run": f"{home_pts}-{away_pts}"}
        return {"team": away_team, "run": f"{away_pts}-{home_pts}"}
    return None


def largest_live_swing(history: list[dict]) -> dict | None:
    if len(history) < 2:
        return None
    best = None
    for index in range(1, len(history)):
        swing = as_float(history[index].get("home_win_prob_pct")) - as_float(history[index - 1].get("home_win_prob_pct"))
        if best is None or abs(swing) > abs(best["swing"]):
            best = {"swing": swing, "last_play": history[index].get("last_play", ""), "period": history[index].get("period"), "clock": history[index].get("clock", "")}
    return best


def momentum_signal(history: list[dict], window: int = 5) -> float:
    """WP slope (home perspective, pct points) over the last few snapshots."""
    if len(history) < 2:
        return 0.0
    recent = history[-window:]
    return as_float(recent[-1].get("home_win_prob_pct")) - as_float(recent[0].get("home_win_prob_pct"))


def build_win_probability_story(data: dict, predictions: pd.DataFrame, home_team: str, away_team: str) -> dict:
    from ui.formatting import as_int, format_nba_clock, format_period, short_text

    row = predictions.iloc[-1]
    home_score, away_score = as_int(row.get("home_score")), as_int(row.get("away_score"))
    home_prob, away_prob = as_float(row.get("home_win_prob_pct"), 50), as_float(row.get("away_win_prob_pct"), 50)
    favorite = home_team if home_prob >= away_prob else away_team
    favorite_prob = max(home_prob, away_prob)
    seconds_remaining = as_float(row.get("seconds_remaining"), 0)
    turning = build_turning_points(predictions, top_n=1)
    if turning.empty:
        biggest_swing, biggest_detail = "Pending", "Run reports to identify the biggest swing."
    else:
        swing = turning.iloc[0]
        biggest_swing, biggest_detail = f"{float(swing['wp_swing_pct']):+.1f} pts", short_text(str(swing["event_description"]), 120)
    if seconds_remaining == 0:
        winner = home_team if home_score > away_score else away_team if away_score > home_score else "Neither team"
        losing_peak = predictions["away_win_prob_pct"].max() if winner == home_team else predictions["home_win_prob_pct"].max() if winner == away_team else 50.0
        lede = f"Final: {winner} closed out a {away_score}-{home_score} game. The losing side peaked at {losing_peak:.1f}% win probability."
        state = "Final"
    else:
        leader = home_team if home_score > away_score else away_team if away_score > home_score else "Neither team"
        lede = f"Live story: {leader} leads {away_team} {away_score}, {home_team} {home_score}; {favorite} owns the current model edge at {favorite_prob:.1f}%."
        state = f"{format_period(as_int(row.get('period')))}, {format_nba_clock(row.get('clock', ''))}"
    return {"lede": lede, "state": state, "favorite": f"{favorite} · {favorite_prob:.1f}%", "biggest_swing": biggest_swing, "biggest_detail": biggest_detail, "key_play": short_text(get_insight(data, "Most Valuable Play"), 140)}
