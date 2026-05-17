import argparse
from pathlib import Path

import pandas as pd
import plotly.express as px


PROCESSED_DIR = Path("data/processed")
FIGURES_DIR = Path("reports/figures")
FIGURES_DIR.mkdir(parents=True, exist_ok=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a win probability chart.")
    parser.add_argument("--game-id", type=str, default=None)
    return parser.parse_args()


def get_prediction_path(game_id: str | None) -> Path:
    if game_id:
        normalized_game_id = str(game_id).zfill(10)
        input_path = PROCESSED_DIR / f"baseline_predictions_{normalized_game_id}.csv"

        if not input_path.exists():
            raise FileNotFoundError(
                f"Missing baseline predictions for game {normalized_game_id}: {input_path}\n"
                f"Run: python src/train_baseline.py --game-id {normalized_game_id}"
            )

        return input_path

    files = sorted(PROCESSED_DIR.glob("baseline_predictions_*.csv"))

    if not files:
        raise FileNotFoundError(
            "No baseline prediction files found. Run src/train_baseline.py first."
        )

    input_path = files[-1]
    print(f"No --game-id provided. Using latest baseline predictions file: {input_path}")
    return input_path


def load_predictions(game_id: str | None = None) -> pd.DataFrame:
    input_path = get_prediction_path(game_id)
    print(f"Loading predictions from: {input_path}")
    return pd.read_csv(input_path, dtype={"game_id": str})


def add_game_progress(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()

    total_game_seconds = 48 * 60
    output["game_seconds_elapsed"] = total_game_seconds - output["seconds_remaining"]
    output["game_minutes_elapsed"] = output["game_seconds_elapsed"] / 60

    return output


def create_win_probability_chart(df: pd.DataFrame) -> None:
    game_id = str(df["game_id"].iloc[0]).zfill(10)

    fig = px.line(
        df,
        x="game_minutes_elapsed",
        y="home_win_prob_pct",
        hover_data=[
            "period",
            "clock",
            "home_score",
            "away_score",
            "score_margin_home",
            "event_description",
        ],
        title=f"ClutchCast AI - Baseline Home Win Probability ({game_id})",
        labels={
            "game_minutes_elapsed": "Game Minutes Elapsed",
            "home_win_prob_pct": "Home Win Probability (%)",
        },
    )

    fig.update_yaxes(range=[0, 100])
    fig.update_layout(
        hovermode="x unified",
        template="plotly_white",
    )

    output_html = FIGURES_DIR / f"win_probability_{game_id}.html"
    fig.write_html(output_html)

    print(f"Saved interactive chart to: {output_html}")


def main() -> None:
    args = parse_args()
    predictions = load_predictions(args.game_id)
    predictions = add_game_progress(predictions)
    create_win_probability_chart(predictions)

    print("\nSuccess.")
    print("Open the generated HTML file in your browser to view the chart.")


if __name__ == "__main__":
    main()
