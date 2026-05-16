from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")
REPORTS_DIR = Path("reports")
REPORTS_DIR.mkdir(parents=True, exist_ok=True)


def load_latest_file(pattern: str, folder: Path) -> Path:
    files = list(folder.glob(pattern))

    if not files:
        raise FileNotFoundError(f"No files found matching: {folder / pattern}")

    return files[0]


def load_data() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """
    Loads the main files needed to generate the game recap.
    """
    momentum_path = load_latest_file("momentum_*.csv", PROCESSED_DIR)
    turning_points_path = load_latest_file("turning_points_*.csv", REPORTS_DIR)
    player_impact_path = load_latest_file("player_impact_*.csv", REPORTS_DIR)
    comeback_report_path = load_latest_file("comeback_report_*.csv", REPORTS_DIR)

    print(f"Loading momentum data from: {momentum_path}")
    print(f"Loading turning points from: {turning_points_path}")
    print(f"Loading player impact from: {player_impact_path}")
    print(f"Loading comeback report from: {comeback_report_path}")

    momentum = pd.read_csv(momentum_path, dtype={"game_id": str})
    turning_points = pd.read_csv(turning_points_path)
    player_impact = pd.read_csv(player_impact_path)
    comeback_report = pd.read_csv(comeback_report_path)

    return momentum, turning_points, player_impact, comeback_report


def get_final_score(momentum: pd.DataFrame) -> tuple[int, int, int]:
    """
    Returns final home score, away score, and home margin.
    """
    final_row = momentum.iloc[-1]

    home_score = int(final_row["home_score"])
    away_score = int(final_row["away_score"])
    home_margin = int(final_row["score_margin_home"])

    return home_score, away_score, home_margin


def describe_winner(home_margin: int) -> str:
    """
    Describes the game result from the home-team perspective.
    """
    if home_margin > 0:
        return f"The home team won by {home_margin} points."
    if home_margin < 0:
        return f"The away team won by {abs(home_margin)} points."
    return "The game ended tied in the available data, which likely indicates an issue."


def format_top_turning_point(turning_points: pd.DataFrame) -> str:
    """
    Creates a sentence describing the biggest turning point.
    """
    if turning_points.empty:
        return "No clear turning point was detected."

    top = turning_points.iloc[0]

    return (
        f"The biggest win-probability swing came in period {top['period']} "
        f"at {top['clock']}, when the home win probability moved from "
        f"{top['wp_before_pct']}% to {top['wp_after_pct']}% "
        f"({top['wp_swing_pct']} percentage points). "
        f"The play was: {top['event_description']}."
    )


def format_top_player(player_impact: pd.DataFrame) -> str:
    """
    Creates a sentence describing the player with the highest swing impact.
    """
    if player_impact.empty:
        return "No player impact data was available."

    top = player_impact.iloc[0]

    return (
        f"The player with the highest total swing involvement was "
        f"{top['event_player']} ({top['event_team']}), with "
        f"{top['total_absolute_swing_pct']} total absolute win-probability "
        f"swing percentage points across {int(top['event_count'])} tracked events."
    )


def format_comeback_context(comeback_report: pd.DataFrame) -> str:
    """
    Creates a sentence describing the most interesting comeback window.
    """
    if comeback_report.empty:
        return "No meaningful comeback window was detected."

    top = comeback_report.iloc[0]

    return (
        f"The most notable comeback window occurred in period {top['period']} "
        f"at {top['clock']}. The trailing team was {top['trailing_team']}, "
        f"down {int(top['deficit'])}, with a comeback probability of "
        f"{top['comeback_probability_pct']}%. The model classified this as "
        f"'{top['comeback_status']}'."
    )


def format_momentum_context(momentum: pd.DataFrame) -> str:
    """
    Creates a sentence describing the strongest hidden momentum moment.
    """
    if momentum.empty or "hidden_momentum_score" not in momentum.columns:
        return "No hidden momentum data was available."

    data = momentum.copy()
    data["abs_hidden_momentum"] = data["hidden_momentum_score"].abs()
    top = data.sort_values("abs_hidden_momentum", ascending=False).iloc[0]

    return (
        f"The strongest hidden momentum reading came in period {top['period']} "
        f"at {top['clock']}, with a score of {top['hidden_momentum_score']}. "
        f"The model labeled this moment as '{top['momentum_label']}'. "
        f"The event was: {top['event_description']}."
    )


def generate_recap(
    momentum: pd.DataFrame,
    turning_points: pd.DataFrame,
    player_impact: pd.DataFrame,
    comeback_report: pd.DataFrame,
) -> str:
    """
    Generates a readable post-game recap from model outputs.
    """
    game_id = str(momentum["game_id"].iloc[0]).zfill(10)
    home_score, away_score, home_margin = get_final_score(momentum)

    result_sentence = describe_winner(home_margin)
    turning_point_sentence = format_top_turning_point(turning_points)
    player_sentence = format_top_player(player_impact)
    comeback_sentence = format_comeback_context(comeback_report)
    momentum_sentence = format_momentum_context(momentum)

    recap = f"""# ClutchCast AI Post-Game Recap

Game ID: {game_id}

Final Score:
Home {home_score} - Away {away_score}

Result:
{result_sentence}

Game Story:
{turning_point_sentence}

Player Swing Impact:
{player_sentence}

Comeback Reality:
{comeback_sentence}

Hidden Momentum:
{momentum_sentence}

Model Note:
This recap is generated from the current V1 rule-based win-probability engine. It is useful for explaining the pipeline and product concept, but the next major upgrade is training a real model on many historical games.
"""

    return recap


def main() -> None:
    momentum, turning_points, player_impact, comeback_report = load_data()

    recap = generate_recap(
        momentum=momentum,
        turning_points=turning_points,
        player_impact=player_impact,
        comeback_report=comeback_report,
    )

    game_id = str(momentum["game_id"].iloc[0]).zfill(10)
    output_path = REPORTS_DIR / f"post_game_recap_{game_id}.md"

    output_path.write_text(recap, encoding="utf-8")

    print("\nSuccess.")
    print(f"Saved post-game recap to: {output_path}")
    print("\nGenerated recap:")
    print(recap)


if __name__ == "__main__":
    main()