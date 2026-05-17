from pathlib import Path
import argparse

import pandas as pd
from nba_api.stats.endpoints import boxscoresummaryv2


PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def format_nba_clock(clock_value) -> str:
    """
    Converts NBA API clock format like PT04M19.00S into 4:19.
    """
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
        seconds = float(seconds_part)

    if seconds.is_integer():
        return f"{minutes}:{int(seconds):02d}"

    return f"{minutes}:{seconds:04.1f}"


def pluralize_point(value: int) -> str:
    if abs(value) == 1:
        return "point"
    return "points"


def get_team_labels(game_id: str) -> tuple[str, str]:
    """
    Returns home and away team abbreviations.

    If the NBA API lookup fails, the recap still works with Home/Away labels.
    """
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


def find_file(folder: Path, pattern: str, game_id: str | None = None) -> Path:
    if game_id:
        files = list(folder.glob(pattern.format(game_id=game_id)))
    else:
        files = sorted(folder.glob(pattern.format(game_id="*")))

    if not files:
        raise FileNotFoundError(f"No files found for pattern: {folder / pattern}")

    return files[-1]


def load_csv(folder: Path, pattern: str, game_id: str | None = None) -> pd.DataFrame:
    path = find_file(folder, pattern, game_id)
    print(f"Loading: {path}")
    return pd.read_csv(path, dtype={"game_id": str})


def get_available_prediction_file(game_id: str) -> Path:
    """
    Uses the strongest available prediction file for recap context.
    Priority:
    1. Neural network
    2. Advanced ML
    3. Logistic regression ML
    4. Baseline
    """
    candidates = [
        PROCESSED_DIR / f"neural_predictions_{game_id}.csv",
        PROCESSED_DIR / f"advanced_predictions_{game_id}.csv",
        PROCESSED_DIR / f"ml_predictions_{game_id}.csv",
        PROCESSED_DIR / f"baseline_predictions_{game_id}.csv",
    ]

    for path in candidates:
        if path.exists():
            return path

    raise FileNotFoundError(
        f"No prediction file found for game {game_id}. Run the pipeline first."
    )


def get_prediction_label(path: Path) -> str:
    filename = path.name

    if filename.startswith("neural_predictions_"):
        return "PyTorch neural network model"

    if filename.startswith("advanced_predictions_"):
        return "advanced random forest model"

    if filename.startswith("ml_predictions_"):
        return "logistic regression model"

    return "rule-based baseline model"


def load_predictions(game_id: str) -> tuple[pd.DataFrame, str]:
    path = get_available_prediction_file(game_id)
    print(f"Loading predictions from: {path}")

    predictions = pd.read_csv(path, dtype={"game_id": str})
    prediction_label = get_prediction_label(path)

    return predictions, prediction_label


def describe_result(
    home_team: str,
    away_team: str,
    home_score: int,
    away_score: int,
) -> str:
    margin = home_score - away_score

    if margin > 0:
        return (
            f"{home_team} defeated {away_team} {home_score}-{away_score}, "
            f"winning by {margin} {pluralize_point(margin)}."
        )

    if margin < 0:
        margin = abs(margin)
        return (
            f"{away_team} defeated {home_team} {away_score}-{home_score}, "
            f"winning by {margin} {pluralize_point(margin)}."
        )

    return f"{home_team} and {away_team} finished tied {home_score}-{away_score}."


def get_top_turning_point(turning_points: pd.DataFrame) -> pd.Series:
    return turning_points.iloc[0]


def get_top_player(player_impact: pd.DataFrame) -> pd.Series:
    return player_impact.iloc[0]


def get_top_comeback(comeback_report: pd.DataFrame) -> pd.Series | None:
    if comeback_report.empty:
        return None

    return comeback_report.iloc[0]


def get_top_momentum(momentum_report: pd.DataFrame) -> pd.Series | None:
    if momentum_report.empty:
        return None

    filtered = momentum_report.copy()

    if "event_description" in filtered.columns:
        ignored_keywords = [
            "timeout",
            "sub:",
            "start of",
            "end of",
            "instant replay",
        ]

        mask = ~filtered["event_description"].astype(str).str.lower().apply(
            lambda desc: any(keyword in desc for keyword in ignored_keywords)
        )

        filtered = filtered[mask]

    if filtered.empty:
        return momentum_report.iloc[0]

    return filtered.iloc[0]


def build_recap(
    game_id: str,
    predictions: pd.DataFrame,
    turning_points: pd.DataFrame,
    player_impact: pd.DataFrame,
    comeback_report: pd.DataFrame,
    momentum_report: pd.DataFrame,
    prediction_label: str,
) -> str:
    home_team, away_team = get_team_labels(game_id)

    final_row = predictions.iloc[-1]
    home_score = int(final_row["home_score"])
    away_score = int(final_row["away_score"])

    result_sentence = describe_result(
        home_team=home_team,
        away_team=away_team,
        home_score=home_score,
        away_score=away_score,
    )

    top_turning_point = get_top_turning_point(turning_points)
    top_player = get_top_player(player_impact)
    top_comeback = get_top_comeback(comeback_report)
    top_momentum = get_top_momentum(momentum_report)

    turning_period = int(top_turning_point["period"])
    turning_clock = format_nba_clock(top_turning_point["clock"])
    turning_swing = float(top_turning_point["wp_swing_pct"])
    turning_before = float(top_turning_point["wp_before_pct"])
    turning_after = float(top_turning_point["wp_after_pct"])
    turning_play = str(top_turning_point["event_description"])

    player_name = str(top_player["event_player"])
    player_team = str(top_player["event_team"])
    player_impact_value = float(top_player["total_absolute_swing_pct"])
    player_events = int(top_player["event_count"])

    recap_lines = [
        "# ClutchCast AI Post-Game Recap",
        "",
        f"**Game:** {away_team} at {home_team}",
        f"**Game ID:** `{game_id}`",
        f"**Model Used:** {prediction_label}",
        "",
        "## Final Result",
        "",
        result_sentence,
        "",
        "## Game Story",
        "",
        (
            f"The biggest win-probability swing came in **Q{turning_period} "
            f"with {turning_clock} remaining**, when the home win probability "
            f"moved from **{turning_before:.1f}%** to **{turning_after:.1f}%** "
            f"for a **{turning_swing:+.1f} percentage-point swing**."
        ),
        "",
        f"**Key play:** {turning_play}",
        "",
        "## Player Swing Impact",
        "",
        (
            f"**{player_name} ({player_team})** had the highest total swing involvement, "
            f"creating **{player_impact_value:.1f} total win-probability impact points** "
            f"across **{player_events} tracked events**."
        ),
    ]

    if top_comeback is not None:
        comeback_period = int(top_comeback["period"])
        comeback_clock = format_nba_clock(top_comeback["clock"])
        trailing_team = str(top_comeback["trailing_team"])
        deficit = int(top_comeback["deficit"])
        comeback_probability = float(top_comeback["comeback_probability_pct"])
        comeback_status = str(top_comeback["comeback_status"])
        comeback_play = str(top_comeback["event_description"])

        recap_lines.extend(
            [
                "",
                "## Comeback Reality",
                "",
                (
                    f"The most notable comeback window came in **Q{comeback_period} "
                    f"with {comeback_clock} remaining**. The trailing side was **{trailing_team}**, "
                    f"down **{deficit} {pluralize_point(deficit)}**, with an estimated comeback "
                    f"probability of **{comeback_probability:.1f}%**."
                ),
                "",
                f"ClutchCast classified this situation as **{comeback_status}**.",
                "",
                f"**Context play:** {comeback_play}",
            ]
        )

    if top_momentum is not None:
        momentum_period = int(top_momentum["period"])
        momentum_clock = format_nba_clock(top_momentum["clock"])
        momentum_score = float(top_momentum["hidden_momentum_score"])
        momentum_label = str(top_momentum["momentum_label"])
        momentum_play = str(top_momentum["event_description"])

        recap_lines.extend(
            [
                "",
                "## Hidden Momentum",
                "",
                (
                    f"The strongest hidden-momentum reading came in **Q{momentum_period} "
                    f"with {momentum_clock} remaining**, with a momentum score of "
                    f"**{momentum_score:.1f}**."
                ),
                "",
                f"ClutchCast labeled the moment as **{momentum_label}**.",
                "",
                f"**Momentum play:** {momentum_play}",
            ]
        )

    recap_lines.extend(
        [
            "",
            "## Model Note",
            "",
            (
                "This recap was generated from ClutchCast AI's current analytics pipeline. "
                "The system compares rule-based, logistic regression, random forest, and "
                "PyTorch neural-network win-probability models, then uses the generated "
                "game reports to explain turning points, player impact, comeback pressure, "
                "and momentum swings."
            ),
            "",
        ]
    )

    return "\n".join(recap_lines)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate a polished ClutchCast AI post-game recap."
    )

    parser.add_argument(
        "--game-id",
        type=str,
        default=None,
        help="Specific NBA game ID to recap, example: 0042300312.",
    )

    return parser.parse_args()


def main() -> None:
    args = parse_args()

    if args.game_id:
        game_id = str(args.game_id).zfill(10)
    else:
        prediction_files = sorted(PROCESSED_DIR.glob("*_predictions_*.csv"))

        if not prediction_files:
            raise FileNotFoundError("No prediction files found. Run the pipeline first.")

        latest_file = prediction_files[-1]
        game_id = latest_file.stem.split("_")[-1]

    predictions, prediction_label = load_predictions(game_id)

    turning_points = load_csv(
        REPORTS_DIR,
        "turning_points_{game_id}.csv",
        game_id,
    )

    player_impact = load_csv(
        REPORTS_DIR,
        "player_impact_{game_id}.csv",
        game_id,
    )

    comeback_report = load_csv(
        REPORTS_DIR,
        "comeback_report_{game_id}.csv",
        game_id,
    )

    momentum_report = load_csv(
        REPORTS_DIR,
        "momentum_report_{game_id}.csv",
        game_id,
    )

    recap = build_recap(
        game_id=game_id,
        predictions=predictions,
        turning_points=turning_points,
        player_impact=player_impact,
        comeback_report=comeback_report,
        momentum_report=momentum_report,
        prediction_label=prediction_label,
    )

    output_path = REPORTS_DIR / f"post_game_recap_{game_id}.md"
    output_path.write_text(recap, encoding="utf-8")

    print("\nSuccess.")
    print(f"Saved post-game recap to: {output_path}")
    print("\nGenerated recap:")
    print(recap)


if __name__ == "__main__":
    main()