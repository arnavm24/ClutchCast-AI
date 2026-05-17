from pathlib import Path

import pandas as pd


PROCESSED_DIR = Path("data/processed")
PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

TARGET_COLUMN = "home_won"

BASE_FEATURE_COLUMNS = [
    "period",
    "seconds_remaining",
    "home_score",
    "away_score",
    "score_margin_home",
    "abs_score_margin",
    "total_score",
    "is_4th_quarter",
    "is_clutch_time",
]

TEAM_STRENGTH_PATH = PROCESSED_DIR / "team_strength.csv"
DEFAULT_TEAM_STRENGTH = 0.5


def load_training_dataset() -> pd.DataFrame:
    input_path = PROCESSED_DIR / "training_dataset.csv"

    if not input_path.exists():
        raise FileNotFoundError(
            "Missing training dataset. Run:\n"
            'python src/build_training_dataset.py --season 2023-24 --season-type "Regular Season" --max-games 300'
        )

    print(f"Loading training dataset from: {input_path}")
    data = pd.read_csv(input_path, dtype={"game_id": str})

    if data.empty:
        raise ValueError("Training dataset is empty.")

    data["game_id"] = data["game_id"].astype(str).str.zfill(10)
    return data


def contains_keyword(series: pd.Series, keywords: list[str]) -> pd.Series:
    text = series.fillna("").astype(str).str.lower()
    result = pd.Series(False, index=series.index)

    for keyword in keywords:
        result = result | text.str.contains(keyword, regex=False)

    return result.astype(int)


def add_time_features(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    regulation_seconds = 48 * 60

    output["time_remaining_fraction"] = (
        output["seconds_remaining"] / regulation_seconds
    ).clip(0, 1)
    output["time_elapsed_fraction"] = (1 - output["time_remaining_fraction"]).clip(0, 1)

    output["period_1"] = (output["period"] == 1).astype(int)
    output["period_2"] = (output["period"] == 2).astype(int)
    output["period_3"] = (output["period"] == 3).astype(int)
    output["period_4"] = (output["period"] == 4).astype(int)
    output["is_second_half"] = output["period"].between(3, 4).astype(int)
    output["is_overtime"] = (output["period"] > 4).astype(int)
    output["overtime_period_number"] = (output["period"] - 4).clip(lower=0)

    output["is_final_5_minutes"] = (output["seconds_remaining"] <= 5 * 60).astype(int)
    output["is_final_2_minutes"] = (output["seconds_remaining"] <= 2 * 60).astype(int)
    output["is_final_1_minute"] = (output["seconds_remaining"] <= 60).astype(int)

    return output


def add_score_margin_features(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()

    output["home_lead"] = (output["score_margin_home"] > 0).astype(int)
    output["away_lead"] = (output["score_margin_home"] < 0).astype(int)
    output["tied_game"] = (output["score_margin_home"] == 0).astype(int)

    output["one_possession_game"] = (output["abs_score_margin"] <= 3).astype(int)
    output["two_possession_game"] = (output["abs_score_margin"] <= 6).astype(int)
    output["three_possession_game"] = (output["abs_score_margin"] <= 9).astype(int)
    output["blowout_margin"] = (output["abs_score_margin"] >= 20).astype(int)

    output["margin_squared"] = output["score_margin_home"] ** 2
    output["score_margin_time_weighted"] = (
        output["score_margin_home"] * output["time_elapsed_fraction"]
    )
    output["abs_margin_time_weighted"] = (
        output["abs_score_margin"] * output["time_elapsed_fraction"]
    )

    return output


def add_event_type_features(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    description = output["event_description"]

    shot_keywords = [
        "jump shot",
        "layup",
        "dunk",
        "hook shot",
        "tip shot",
        "floating",
        "driving",
        "pullup",
    ]

    output["is_shot"] = contains_keyword(description, shot_keywords)
    output["is_three_pointer"] = contains_keyword(description, ["3pt"])
    output["is_free_throw"] = contains_keyword(description, ["free throw"])
    output["is_missed_shot"] = contains_keyword(description, ["miss"])
    output["is_made_shot"] = (
        ((output["is_shot"] == 1) | (output["is_free_throw"] == 1))
        & (output["is_missed_shot"] == 0)
    ).astype(int)

    output["is_turnover"] = contains_keyword(description, ["turnover"])
    output["is_rebound"] = contains_keyword(description, ["rebound"])
    output["is_offensive_rebound"] = contains_keyword(description, ["rebound (off:"])
    output["is_steal"] = contains_keyword(description, ["steal"])
    output["is_block"] = contains_keyword(description, ["block"])
    output["is_foul"] = contains_keyword(description, ["foul", "p.foul", "s.foul"])
    output["is_timeout"] = contains_keyword(description, ["timeout"])
    output["is_substitution"] = contains_keyword(description, ["sub:"])

    return output


def classify_event_value(description: str) -> int:
    desc = str(description).lower()

    if "timeout" in desc or "sub:" in desc or "start" in desc or "end" in desc:
        return 0
    if "turnover" in desc:
        return -4
    if "steal" in desc:
        return 4
    if "block" in desc:
        return 3
    if "3pt" in desc and "miss" not in desc:
        return 5
    if "dunk" in desc and "miss" not in desc:
        return 4
    if "layup" in desc and "miss" not in desc:
        return 3
    if "jump shot" in desc and "miss" not in desc:
        return 3
    if "free throw" in desc and "miss" not in desc:
        return 1
    if "miss" in desc:
        return -2
    if "rebound" in desc and "off:" in desc:
        return 2
    if "rebound" in desc:
        return 1

    return 0


def add_event_value_features(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    output["event_value"] = output["event_description"].apply(classify_event_value)
    return output


def infer_home_away_teams_from_scoring(output: pd.DataFrame) -> pd.DataFrame:
    output["home_team_abbrev"] = ""
    output["away_team_abbrev"] = ""

    for game_id, game_rows in output.groupby("game_id", sort=False):
        home_candidates = set(
            game_rows.loc[
                (game_rows["home_score_delta"] > 0) & (game_rows["event_team"] != ""),
                "event_team",
            ]
        )
        away_candidates = set(
            game_rows.loc[
                (game_rows["away_score_delta"] > 0) & (game_rows["event_team"] != ""),
                "event_team",
            ]
        )

        if len(home_candidates) == 1 and len(away_candidates) == 1:
            home_team = next(iter(home_candidates))
            away_team = next(iter(away_candidates))

            if home_team != away_team:
                mask = output["game_id"] == game_id
                output.loc[mask, "home_team_abbrev"] = home_team
                output.loc[mask, "away_team_abbrev"] = away_team

    return output


def add_team_event_direction_features(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy().sort_values(["game_id", "event_num"]).copy()

    output["event_team"] = output["event_team"].fillna("").astype(str)
    output["home_score_delta"] = output.groupby("game_id")["home_score"].diff().fillna(0).clip(lower=0)
    output["away_score_delta"] = output.groupby("game_id")["away_score"].diff().fillna(0).clip(lower=0)

    output = infer_home_away_teams_from_scoring(output)

    # Team side is considered reliable only when scoring events identify exactly
    # one home scoring team and one away scoring team for that game.
    output["event_by_home"] = (
        (output["home_team_abbrev"] != "")
        & (output["event_team"] == output["home_team_abbrev"])
    ).astype(int)
    output["event_by_away"] = (
        (output["away_team_abbrev"] != "")
        & (output["event_team"] == output["away_team_abbrev"])
    ).astype(int)

    output["signed_event_value_home_perspective"] = 0
    output.loc[output["event_by_home"] == 1, "signed_event_value_home_perspective"] = (
        output.loc[output["event_by_home"] == 1, "event_value"]
    )
    output.loc[output["event_by_away"] == 1, "signed_event_value_home_perspective"] = -(
        output.loc[output["event_by_away"] == 1, "event_value"]
    )

    return output


def add_team_action_features(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()

    action_columns = [
        "turnover",
        "rebound",
        "offensive_rebound",
        "steal",
        "block",
        "foul",
        "timeout",
    ]

    source_columns = {
        "turnover": "is_turnover",
        "rebound": "is_rebound",
        "offensive_rebound": "is_offensive_rebound",
        "steal": "is_steal",
        "block": "is_block",
        "foul": "is_foul",
        "timeout": "is_timeout",
    }

    for action in action_columns:
        source = source_columns[action]
        output[f"home_{action}"] = ((output["event_by_home"] == 1) & (output[source] == 1)).astype(int)
        output[f"away_{action}"] = ((output["event_by_away"] == 1) & (output[source] == 1)).astype(int)

    return output


def estimate_possession_side_for_game(game_rows: pd.DataFrame) -> pd.Series:
    possession_side = []
    current_side = 0

    for _, row in game_rows.iterrows():
        event_side = 1 if row["event_by_home"] == 1 else -1 if row["event_by_away"] == 1 else 0

        if event_side != 0:
            if row["is_steal"] == 1:
                current_side = event_side
            elif row["is_turnover"] == 1:
                current_side = -event_side
            elif row["is_rebound"] == 1:
                current_side = event_side
            elif row["is_timeout"] == 1:
                current_side = event_side
            elif row["is_made_shot"] == 1 and row["is_free_throw"] == 0:
                current_side = -event_side

        possession_side.append(current_side)

    return pd.Series(possession_side, index=game_rows.index)


def add_possession_features(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy().sort_values(["game_id", "event_num"]).copy()

    output["estimated_possession_side"] = (
        output.groupby("game_id", group_keys=False)
        .apply(estimate_possession_side_for_game)
        .sort_index()
    )

    output["home_has_possession"] = (output["estimated_possession_side"] == 1).astype(int)
    output["away_has_possession"] = (output["estimated_possession_side"] == -1).astype(int)
    output["possession_value_home_perspective"] = output["estimated_possession_side"]
    output["estimated_possession_team"] = "unknown"
    output.loc[output["estimated_possession_side"] == 1, "estimated_possession_team"] = "home"
    output.loc[output["estimated_possession_side"] == -1, "estimated_possession_team"] = "away"

    return output


def load_team_strengths() -> dict[str, float]:
    if not TEAM_STRENGTH_PATH.exists():
        return {}

    strengths = pd.read_csv(TEAM_STRENGTH_PATH)
    team_column = "team" if "team" in strengths.columns else "team_abbrev"
    value_column = "strength" if "strength" in strengths.columns else "team_strength"

    if team_column not in strengths.columns or value_column not in strengths.columns:
        return {}

    return dict(zip(strengths[team_column].astype(str), strengths[value_column].astype(float)))


def add_team_strength_features(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()
    strengths = load_team_strengths()

    output["home_team_strength"] = (
        output["home_team_abbrev"].map(strengths).fillna(DEFAULT_TEAM_STRENGTH)
    )
    output["away_team_strength"] = (
        output["away_team_abbrev"].map(strengths).fillna(DEFAULT_TEAM_STRENGTH)
    )
    output["team_strength_diff_home"] = output["home_team_strength"] - output["away_team_strength"]

    return output


def add_rolling_features(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy().sort_values(["game_id", "event_num"]).copy()

    for window in [5, 10]:
        output[f"recent_margin_change_{window}"] = (
            output.groupby("game_id")["score_margin_home"].diff(window).fillna(0)
        )
        output[f"recent_total_score_change_{window}"] = (
            output.groupby("game_id")["total_score"].diff(window).fillna(0)
        )
        output[f"recent_event_value_{window}"] = (
            output.groupby("game_id")["event_value"]
            .rolling(window=window, min_periods=1)
            .sum()
            .reset_index(level=0, drop=True)
        )
        output[f"recent_home_perspective_event_value_{window}"] = (
            output.groupby("game_id")["signed_event_value_home_perspective"]
            .rolling(window=window, min_periods=1)
            .sum()
            .reset_index(level=0, drop=True)
        )
        output[f"home_points_last_{window}_events"] = (
            output.groupby("game_id")["home_score_delta"]
            .rolling(window=window, min_periods=1)
            .sum()
            .reset_index(level=0, drop=True)
        )
        output[f"away_points_last_{window}_events"] = (
            output.groupby("game_id")["away_score_delta"]
            .rolling(window=window, min_periods=1)
            .sum()
            .reset_index(level=0, drop=True)
        )

    output["home_run_last_10_events"] = output["home_points_last_10_events"] - output["away_points_last_10_events"]
    output["away_run_last_10_events"] = output["away_points_last_10_events"] - output["home_points_last_10_events"]

    return output


def build_model_features(df: pd.DataFrame) -> pd.DataFrame:
    output = df.copy()

    required_columns = BASE_FEATURE_COLUMNS + [
        TARGET_COLUMN,
        "game_id",
        "event_num",
        "event_description",
        "event_team",
    ]

    missing = [col for col in required_columns if col not in output.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    output = add_time_features(output)
    output = add_score_margin_features(output)
    output = add_event_type_features(output)
    output = add_event_value_features(output)
    output = add_team_event_direction_features(output)
    output = add_team_action_features(output)
    output = add_possession_features(output)
    output = add_team_strength_features(output)
    output = add_rolling_features(output)

    return output.fillna(0)


def get_model_feature_columns(df: pd.DataFrame) -> list[str]:
    excluded_columns = {
        "game_id",
        "event_num",
        "clock",
        "event_team",
        "event_player",
        "event_description",
        "event_type",
        "home_team_abbrev",
        "away_team_abbrev",
        "estimated_possession_team",
        TARGET_COLUMN,
    }

    return [column for column in df.columns if column not in excluded_columns]


def save_feature_list(feature_columns: list[str]) -> None:
    output_path = PROCESSED_DIR / "model_feature_columns.txt"
    output_path.write_text("\n".join(feature_columns), encoding="utf-8")
    print(f"Saved model feature list to: {output_path}")


def main() -> None:
    data = load_training_dataset()
    model_data = build_model_features(data)
    feature_columns = get_model_feature_columns(model_data)

    output_path = PROCESSED_DIR / "model_training_dataset.csv"
    model_data.to_csv(output_path, index=False)
    save_feature_list(feature_columns)

    print("\nSuccess.")
    print(f"Saved improved model dataset to: {output_path}")
    print(f"Rows: {len(model_data)}")
    print(f"Total columns: {len(model_data.columns)}")
    print(f"Model feature columns: {len(feature_columns)}")

    print("\nFeature columns:")
    for column in feature_columns:
        print(f"- {column}")


if __name__ == "__main__":
    main()
