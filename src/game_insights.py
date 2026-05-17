import argparse
from pathlib import Path

import pandas as pd

from champion_inference import get_prediction_file_prefix, load_champion_metadata


PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)

MODEL_FALLBACKS = [
    ("advanced_predictions", "random_forest"),
    ("ml_predictions", "logistic_regression"),
    ("neural_predictions", "pytorch_neural_network"),
    ("baseline_predictions", "baseline"),
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate focused ClutchCast game insights.")
    parser.add_argument("--game-id", required=True, type=str, help="NBA game ID, example: 0042300312.")
    return parser.parse_args()


def normalize_game_id(game_id: str) -> str:
    return str(game_id).zfill(10)


def format_nba_clock(clock_value) -> str:
    clock = str(clock_value)
    if not clock.startswith("PT"):
        return clock

    clock = clock.replace("PT", "")
    minutes = 0
    seconds = 0.0

    if "M" in clock:
        minutes_part, clock = clock.split("M")
        minutes = int(minutes_part)

    if "S" in clock:
        seconds = float(clock.replace("S", ""))

    if seconds.is_integer():
        return f"{minutes}:{int(seconds):02d}"

    return f"{minutes}:{seconds:04.1f}"


def format_period_clock(period: int, clock_value) -> str:
    label = f"Q{period}" if period <= 4 else f"OT{period - 4}"
    return f"{label}, {format_nba_clock(clock_value)}"


def load_game_state(game_id: str) -> pd.DataFrame:
    path = PROCESSED_DIR / f"game_state_{game_id}.csv"
    if not path.exists():
        raise FileNotFoundError(
            f"Missing game-state file: {path}\n"
            f"Run: python src/game_state.py --game-id {game_id}"
        )

    print(f"Loading game state from: {path}")
    return pd.read_csv(path, dtype={"game_id": str})


def get_prediction_path(game_id: str) -> tuple[Path, str]:
    champion = load_champion_metadata()
    champion_key = champion.get("model_key", "baseline")
    champion_prefix = get_prediction_file_prefix(champion_key)
    champion_path = PROCESSED_DIR / f"{champion_prefix}_{game_id}.csv"

    if champion_path.exists():
        return champion_path, champion_key

    for prefix, model_key in MODEL_FALLBACKS:
        path = PROCESSED_DIR / f"{prefix}_{game_id}.csv"
        if path.exists():
            return path, model_key

    raise FileNotFoundError(
        f"No prediction file found for game {game_id}. Run the pipeline first."
    )


def load_predictions(game_id: str) -> tuple[pd.DataFrame, str]:
    path, model_key = get_prediction_path(game_id)
    print(f"Loading predictions from: {path}")
    return pd.read_csv(path, dtype={"game_id": str}), model_key


def is_non_terminal_state(df: pd.DataFrame) -> pd.Series:
    description = df["event_description"].fillna("").astype(str).str.lower()
    return (
        (df["seconds_remaining"] > 0)
        & ~description.str.contains("end of", regex=False)
        & ~description.str.contains("instant replay", regex=False)
    )


def is_rankable_play(df: pd.DataFrame) -> pd.Series:
    description = df["event_description"].fillna("").astype(str).str.lower()
    event_team = df["event_team"].fillna("").astype(str).str.strip()
    event_player = df["event_player"].fillna("").astype(str).str.strip()

    timeout_or_sub = (
        description.str.contains("timeout", regex=False)
        | description.str.contains("sub:", regex=False)
        | description.str.contains("substitution", regex=False)
    )

    return (
        is_non_terminal_state(df)
        & ~timeout_or_sub
        & (event_team != "")
        & (event_player != "")
    )


def infer_home_away_teams(predictions: pd.DataFrame) -> tuple[str | None, str | None]:
    data = predictions.copy().sort_values(["game_id", "event_num"])
    data["home_score_delta"] = data.groupby("game_id")["home_score"].diff().fillna(0).clip(lower=0)
    data["away_score_delta"] = data.groupby("game_id")["away_score"].diff().fillna(0).clip(lower=0)
    data["event_team"] = data["event_team"].fillna("").astype(str).str.strip()

    home_candidates = set(data.loc[(data["home_score_delta"] > 0) & (data["event_team"] != ""), "event_team"])
    away_candidates = set(data.loc[(data["away_score_delta"] > 0) & (data["event_team"] != ""), "event_team"])

    if len(home_candidates) == 1 and len(away_candidates) == 1:
        home_team = next(iter(home_candidates))
        away_team = next(iter(away_candidates))
        if home_team != away_team:
            return home_team, away_team

    return None, None


def row_identity(row: pd.Series | None) -> tuple | None:
    if row is None:
        return None
    return (
        row.get("game_id", ""),
        row.get("event_num", row.name),
        row.get("period", ""),
        row.get("clock", ""),
        row.get("event_description", ""),
    )


def calculate_clutch_pressure(df: pd.DataFrame) -> pd.Series:
    elapsed_ratio = (1 - (df["seconds_remaining"] / (48 * 60))).clip(0, 1)
    closeness = (1 - (df["abs_score_margin"] / 20)).clip(0, 1)
    uncertainty = 1 - ((df["home_win_prob"] - 0.5).abs() / 0.5).clip(0, 1)
    return ((0.40 * closeness + 0.35 * elapsed_ratio + 0.25 * uncertainty) * 100).round(1)


def count_lead_changes(score_margin: pd.Series) -> int:
    non_tie = score_margin[score_margin != 0]
    if non_tie.empty:
        return 0

    signs = non_tie.apply(lambda value: 1 if value > 0 else -1)
    return int((signs != signs.shift()).sum() - 1)


def build_game_drama_score(predictions: pd.DataFrame, winner: str) -> tuple[int, str]:
    data = predictions.copy()
    data["clutch_pressure"] = calculate_clutch_pressure(data)
    drama_rows = data[is_non_terminal_state(data)].copy()

    if drama_rows.empty:
        drama_rows = data.copy()

    final_margin = abs(int(data["score_margin_home"].iloc[-1]))
    ties = int((data["score_margin_home"] == 0).sum())
    lead_changes = count_lead_changes(data["score_margin_home"])
    major_swings = int((drama_rows["abs_wp_change"] >= 0.10).sum())

    if winner == "home":
        losing_team_max_wp = float(data["away_win_prob"].max())
        max_deficit_overcome = int(max(0, -data["score_margin_home"].min()))
    else:
        losing_team_max_wp = float(data["home_win_prob"].max())
        max_deficit_overcome = int(max(0, data["score_margin_home"].max()))

    final_margin_component = max(0, 100 - final_margin * 8)
    lead_change_component = min(100, lead_changes * 18)
    tie_component = min(100, ties * 2)
    swing_component = min(100, major_swings * 20)
    losing_wp_component = losing_team_max_wp * 100
    comeback_component = min(100, max_deficit_overcome * 8)
    clutch_component = float(drama_rows["clutch_pressure"].max())

    score = round(
        0.20 * final_margin_component
        + 0.15 * lead_change_component
        + 0.10 * tie_component
        + 0.15 * swing_component
        + 0.20 * losing_wp_component
        + 0.10 * comeback_component
        + 0.10 * clutch_component
    )
    score = int(max(0, min(100, score)))

    explanation = (
        f"Drama score {score}/100: final margin {final_margin}, "
        f"{lead_changes} lead changes, {ties} tied states, {major_swings} major WP swings, "
        f"losing team max WP {losing_wp_component:.1f}%, max deficit overcome {max_deficit_overcome}, "
        f"peak clutch pressure {clutch_component:.1f}."
    )

    return score, explanation


def best_row(rows: pd.DataFrame, sort_column: str, ascending: bool, excluded_identity: tuple | None = None) -> pd.Series | None:
    if excluded_identity is not None and not rows.empty:
        rows = rows[rows.apply(lambda row: row_identity(row) != excluded_identity, axis=1)]

    if rows.empty:
        return None

    return rows.sort_values(sort_column, ascending=ascending).iloc[0]


def identify_swing_plays(predictions: pd.DataFrame, winner: str, home_team: str | None, away_team: str | None) -> tuple[pd.Series | None, pd.Series | None]:
    data = predictions[is_rankable_play(predictions)].copy()
    if data.empty:
        return None, None

    winner_team = home_team if winner == "home" else away_team
    loser_team = away_team if winner == "home" else home_team
    loser = "away" if winner == "home" else "home"

    data["winning_team_wp_swing"] = data["wp_change"] if winner == "home" else -data["wp_change"]
    data["losing_team_wp_swing"] = data["wp_change"] if loser == "home" else -data["wp_change"]

    valuable_candidates = data[data["winning_team_wp_swing"] > 0].copy()
    damaging_candidates = data[data["losing_team_wp_swing"] < 0].copy()

    valuable_preferred = valuable_candidates
    if winner_team:
        preferred = valuable_candidates[valuable_candidates["event_team"] == winner_team]
        if not preferred.empty:
            valuable_preferred = preferred

    damaging_preferred = damaging_candidates
    if loser_team:
        preferred = damaging_candidates[damaging_candidates["event_team"] == loser_team]
        if not preferred.empty:
            damaging_preferred = preferred

    valuable_play = best_row(valuable_preferred, "winning_team_wp_swing", ascending=False)
    damaging_play = best_row(damaging_preferred, "losing_team_wp_swing", ascending=True)

    if row_identity(valuable_play) == row_identity(damaging_play):
        valuable_identity = row_identity(valuable_play)
        replacement = best_row(
            damaging_preferred,
            "losing_team_wp_swing",
            ascending=True,
            excluded_identity=valuable_identity,
        )
        if replacement is None and not damaging_candidates.equals(damaging_preferred):
            replacement = best_row(
                damaging_candidates,
                "losing_team_wp_swing",
                ascending=True,
                excluded_identity=valuable_identity,
            )
        if replacement is not None:
            damaging_play = replacement

    return valuable_play, damaging_play


def add_score_deltas(game_state: pd.DataFrame) -> pd.DataFrame:
    data = game_state.copy().sort_values(["game_id", "event_num"])
    data["home_points"] = data.groupby("game_id")["home_score"].diff().fillna(data["home_score"]).clip(lower=0)
    data["away_points"] = data.groupby("game_id")["away_score"].diff().fillna(data["away_score"]).clip(lower=0)
    return data


def build_clutch_scoring_summary(game_state: pd.DataFrame) -> tuple[str, str]:
    data = add_score_deltas(game_state)
    clutch = data[(data["period"] >= 4) & (data["seconds_remaining"] <= 5 * 60)].copy()

    if clutch.empty:
        return "No final-five-minute fourth-quarter/overtime rows were found.", ""

    home_points = int(clutch["home_points"].sum())
    away_points = int(clutch["away_points"].sum())

    scoring_rows = clutch[
        ((clutch["home_points"] > 0) | (clutch["away_points"] > 0))
        & (clutch["event_player"].fillna("").astype(str).str.strip() != "")
    ].copy()

    scorer_text = "Player-level clutch scoring could not be parsed reliably from this game state."
    if not scoring_rows.empty:
        scoring_rows["points"] = scoring_rows["home_points"] + scoring_rows["away_points"]
        scorer_summary = (
            scoring_rows.groupby(["event_player", "event_team"], as_index=False)["points"]
            .sum()
            .sort_values("points", ascending=False)
        )
        scorer_summary = scorer_summary[scorer_summary["points"] > 0]

        if not scorer_summary.empty:
            top_points = scorer_summary["points"].max()
            top_scorers = scorer_summary[scorer_summary["points"] == top_points]
            scorer_text = ", ".join(
                f"{row.event_player} ({row.event_team}) {int(row.points)} pts"
                for row in top_scorers.itertuples(index=False)
            )

    summary = f"Final 5 minutes of 4Q/OT scoring: Home {home_points}, Away {away_points}."
    return summary, scorer_text


def format_play(row: pd.Series | None, swing_column: str) -> tuple[str, str]:
    if row is None:
        return "No eligible play found.", ""

    swing_pct = float(row[swing_column]) * 100
    when = format_period_clock(int(row["period"]), row.get("clock", ""))
    details = (
        f"{when}, {row['event_team']} - {row['event_player']}: "
        f"{row['event_description']} ({swing_pct:+.1f} WP points)"
    )
    return str(row["event_description"]), details


def build_insights(game_id: str, game_state: pd.DataFrame, predictions: pd.DataFrame, model_key: str) -> tuple[pd.DataFrame, str]:
    final_margin = int(predictions["score_margin_home"].iloc[-1])
    if final_margin > 0:
        winner = "home"
        loser = "away"
    elif final_margin < 0:
        winner = "away"
        loser = "home"
    else:
        winner = "tie"
        loser = "tie"

    home_team, away_team = infer_home_away_teams(predictions)
    effective_winner = winner if winner != "tie" else "home"

    drama_score, drama_explanation = build_game_drama_score(predictions, effective_winner)
    valuable_play, damaging_play = identify_swing_plays(predictions, effective_winner, home_team, away_team)
    clutch_summary, clutch_scorers = build_clutch_scoring_summary(game_state)

    valuable_value, valuable_details = format_play(valuable_play, "winning_team_wp_swing")
    damaging_value, damaging_details = format_play(damaging_play, "losing_team_wp_swing")

    rows = [
        {
            "game_id": game_id,
            "insight": "Game Drama Score",
            "value": drama_score,
            "details": drama_explanation,
        },
        {
            "game_id": game_id,
            "insight": "Most Valuable Play",
            "value": valuable_value,
            "details": valuable_details,
        },
        {
            "game_id": game_id,
            "insight": "Most Damaging Play",
            "value": damaging_value,
            "details": damaging_details,
        },
        {
            "game_id": game_id,
            "insight": "Clutch-Time Scoring Summary",
            "value": clutch_summary,
            "details": clutch_scorers,
        },
    ]

    insights = pd.DataFrame(rows)

    markdown = "\n".join(
        [
            "# ClutchCast AI Game Insights",
            "",
            f"**Game ID:** `{game_id}`",
            f"**Prediction Source:** `{model_key}`",
            f"**Winner:** {winner.title() if winner != 'tie' else 'Tie'}",
            f"**Losing Side:** {loser.title() if loser != 'tie' else 'Tie'}",
            "",
            "## Game Drama Score",
            "",
            f"**{drama_score}/100**",
            "",
            drama_explanation,
            "",
            "## Most Valuable Play",
            "",
            valuable_details or valuable_value,
            "",
            "## Most Damaging Play",
            "",
            damaging_details or damaging_value,
            "",
            "## Clutch-Time Scoring Summary",
            "",
            clutch_summary,
            "",
            f"**Top clutch scorer(s):** {clutch_scorers}",
            "",
        ]
    )

    return insights, markdown


def main() -> None:
    args = parse_args()
    game_id = normalize_game_id(args.game_id)

    game_state = load_game_state(game_id)
    predictions, model_key = load_predictions(game_id)
    insights, markdown = build_insights(game_id, game_state, predictions, model_key)

    csv_path = REPORTS_DIR / f"game_insights_{game_id}.csv"
    markdown_path = REPORTS_DIR / f"game_insights_{game_id}.md"

    insights.to_csv(csv_path, index=False)
    markdown_path.write_text(markdown, encoding="utf-8")

    print("\nSuccess.")
    print(f"Saved game insights CSV to: {csv_path}")
    print(f"Saved game insights report to: {markdown_path}")
    print("\nGame insights:")
    print(insights.to_string(index=False))


if __name__ == "__main__":
    main()
