# ClutchCast AI

**Live at [clutchcast-ai.vercel.app](https://clutchcast-ai.vercel.app)**

ClutchCast AI is an NBA win-probability and game-intelligence platform. It turns NBA play-by-play data into game-state rows, trains six probability models fairly, selects a Champion Model by proper probability metrics, and ships the result as a Next.js web app — win-probability timelines for every analyzed game (including the NBA Finals), player impact rankings, today's slate, and live in-game predictions computed by the champion model running in the visitor's browser.

The project has three layers:

- **Web app (`web/`)** — the product: Next.js on Vercel, no Python at runtime. Historical analysis is precomputed to static JSON by `src/export_web_data.py`; the champion network's weights are exported and executed in TypeScript (parity-tested against PyTorch to 1e-8).
- **ML pipeline (`src/`)** — data building, feature engineering, six-model training, champion selection, and calibration reporting.
- **Local analyst tools (`app/`, `backend/`)** — a Streamlit dashboard and Flask live backend for deep local analysis (What-If simulator, model comparison, replay mode).

## Why It Exists

Most sports prediction demos stop at a cool chart. ClutchCast AI is designed to be more technically honest: every model trains on the same data, uses the same features, evaluates on the same held-out games, and competes on probability-quality metrics instead of vibes.

## Tech Stack

- `nba_api` for NBA play-by-play and game metadata
- `pandas` for state building, feature engineering, and reports
- `scikit-learn` for logistic regression, random forest, scaling, and metrics
- `PyTorch` for a tabular neural-network benchmark
- `Streamlit` and `Plotly` for the historical dashboard and Live Game tab
- `Flask` and `Flask-SocketIO` for the local live prediction MVP

## Modeling Approach

ClutchCast AI compares six approaches:

1. Baseline rule model: interpretable formula based on score margin, time, and home-court edge.
2. Logistic regression: scaled, interpretable ML benchmark.
3. Random forest: nonlinear tabular model with feature importance.
4. Gradient boosting: sklearn `HistGradientBoostingClassifier` (LightGBM-class trees).
5. PyTorch neural network: simple tabular MLP with validation early stopping.
6. GRU sequence model: reads the trailing 24 events as a time-series instead of hand-rolled rolling aggregates.

Training data covers the 2022-23 and 2023-24 regular seasons (600 games, ~288k game states, 480 train / 120 held-out test games). Pregame team-strength priors come from each team's previous-season win percentage (`src/team_strength.py`) — prior-season results cannot leak information about the games being predicted.

An isotonic calibration layer (`src/calibrate_champion.py`) is fitted on validation games carved from the train split and is applied at inference only if it improves held-out probability quality. On the current champion it does not (the champion is already well calibrated), so it is intentionally not applied — the before/after evidence lives in `reports/champion_calibration_effect.csv`.

Current held-out results (120 test games): the champion PyTorch NN scores Brier 0.1577 / log loss 0.4618 / ROC-AUC 0.853, with the GRU sequence model a near-tie at 0.1579. Gradient boosting posts the highest accuracy (74.4%) but the worst Brier — a concrete example of why the champion is selected on probability quality, not accuracy.

All ML models use:

- `data/processed/model_training_dataset.csv`
- `data/processed/model_feature_columns.txt`
- `data/processed/train_game_ids.txt`
- `data/processed/test_game_ids.txt`

The split is by `game_id`, not by row, so events from the same game cannot leak between train and test.

## Champion Model Selection

The Champion Model is selected by `src/compare_models.py --leaderboard` using this ranking order:

1. Lowest Brier score
2. Lowest log loss
3. Highest ROC-AUC
4. Highest accuracy

Outputs:

- `reports/model_leaderboard.csv`
- `reports/champion_model.json`

The Streamlit dashboard defaults to the champion model when its prediction file exists. Other models remain available in the technical Model Evaluation tab.

## Feature Engineering

`src/model_features.py` is the single source of truth for training and inference features. Current features include:

- Time context: remaining/elapsed fractions, quarter indicators, second half, final minutes, overtime.
- Score context: margin, lead flags, possession-size flags, blowout flag, margin-time interactions.
- Event context: shots, makes, misses, threes, free throws, turnovers, rebounds, steals, blocks, fouls, timeouts, substitutions.
- Recent flow: rolling score-margin changes, total-score changes, event value, and home-perspective event value.
- Conservative event direction: event-by-home/away is assigned only when the current event changes the score, avoiding fragile future-derived team inference.

No raw text columns, identifiers, final result leakage, or future score changes are included as model features.

## Dashboard Features

The Streamlit dashboard (now a modular `app/ui/` package) includes:

- Game Overview with hero scoreboard, team win probabilities, model status, top intelligence cards, and a compact "Why This Probability?" card
- Champion Win Probability Timeline with a moment slider — scrub to any play and see the game state and top probability drivers at that moment
- What-If Simulator: set a hypothetical margin/quarter/clock and the champion model re-scores the state live
- Live Game Center: prominent data-quality banner (Full Champion Model / Historical / Scoreboard Fallback / Artifacts Missing / Replay), live win-probability timeline that persists across refreshes, last-5-plays feed, scoring-run detection, largest live swing, and momentum badge
- Replay mode: stream any analyzed game through the live pipeline offline — demos the Live Game Center without a live NBA game
- Game Insights: drama score, most valuable play, most damaging play, and clutch-time scoring
- Turning Points and Player Impact
- Player Matchup: side-by-side player cards with NBA headshots (initials fallback when offline), total/net/clutch impact, helped-vs-hurt split, top play, and a dual-player impact timeline
- Clutch Pressure and Comeback Reality
- Game Recap
- Model Evaluation with leaderboard plus a full calibration report: reliability diagram, expected calibration error, Brier by quarter, and overconfidence flags — the champion is selected by probability quality, not model complexity
- Sidebar: curated demo games (close finish, OT thriller, comeback, blowout, highest drama), game search (team / close games / overtime filters), and a Most Dramatic Games leaderboard

Historical tabs use saved CSV/report files. The Live Game tab polls the backend endpoint `GET /predict/<game_id>?mode=live`; the `prediction_source` field drives the data-quality banner.

## Local Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Rebuild Dataset And Features

```powershell
python src/build_training_dataset.py --seasons 2022-23 2023-24 --max-games 300
python src/team_strength.py --apply-to-seasons 2022-23 2023-24
python src/model_features.py
```

`--max-games` applies per season. Raw files already on disk are reused, so reruns only download what is missing.

## Train Models

```powershell
python src/team_strength.py --apply-to-seasons 2022-23 2023-24
python src/train_model.py
python src/train_advanced_model.py
python src/train_gradient_boosting.py
python src/train_neural_network.py
python src/train_sequence_model.py
```

## Select Champion Model

```powershell
python src/compare_models.py --leaderboard
python src/calibrate_champion.py
```

## Automated Weekly Refresh

`src/refresh_all.py` runs the whole lifecycle unattended: download new games for the current season, retrain all six models, re-select the champion, re-run calibration, analyze the newest completed games, export web data, build, parity-check, and push (Vercel auto-deploys from main). It exits early when there are no new games, so offseason runs are free.

```powershell
# one-time setup: registers "ClutchCast Weekly Refresh" (Mondays 6:00 AM)
powershell -ExecutionPolicy Bypass -File scripts\register_refresh_task.ps1

# manual run / dry run
python src/refresh_all.py --skip-push
```

Logs land in `reports/refresh_logs/`.

## Calibration Report

Evaluates every model (plus the live scoreboard fallback) on held-out test games: reliability bins, expected calibration error, Brier by quarter, and overconfidence flags. Shares the exact prediction code path with the leaderboard via `src/model_predictions.py`.

```powershell
python src/calibration_report.py
```

## Batch Analysis, Game Index, And Demo Games

Analyze many games offline from `data/raw` (no network), build the searchable game index, and pick curated demo games for the sidebar:

```powershell
python src/game_index.py
python src/batch_analyze.py --test-games --limit 20 --skip-existing
python src/demo_games.py
```

`batch_analyze.py` also accepts `--game-ids id1 id2 ...` and `--from-file path`.

## Analyze A Past Game

Replace `YOUR_GAME_ID` with an NBA game ID.

```powershell
python src/run_pipeline.py --game-id YOUR_GAME_ID --model baseline
python src/run_pipeline.py --game-id YOUR_GAME_ID --model ml
python src/run_pipeline.py --game-id YOUR_GAME_ID --model advanced
python src/run_pipeline.py --game-id YOUR_GAME_ID --model neural
python src/compare_models.py --game-id YOUR_GAME_ID
python src/game_insights.py --game-id YOUR_GAME_ID
python src/recap.py --game-id YOUR_GAME_ID
streamlit run app/streamlit_app.py
```

## Live Game Mode

Terminal 1:

```powershell
python backend/app.py
```

Terminal 2:

```powershell
streamlit run app/streamlit_app.py
```

Then open the **Live Game** tab, enter the live NBA `GAME_ID`, click **Fetch Live Prediction**, and enable **Auto-refresh every 10 seconds** to keep polling the backend.

The Live Game tab displays the current period, clock, score, home/away win probability, last play, champion model, and backend status. Live accuracy and update speed depend on NBA API availability and delay.

Live data fallback order:

1. Direct NBA CDN live play-by-play JSON at `https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_GAME_ID.json`.
2. Direct NBA CDN live scoreboard JSON at `https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json`.
3. `nba_api.live.nba.endpoints.playbyplay.PlayByPlay`, kept only as a fallback wrapper.
4. `nba_api.live.nba.endpoints.scoreboard.ScoreBoard`, kept only as a fallback wrapper.
5. `nba_api.live.nba.endpoints.boxscore.BoxScore`, as score/status support when live scoreboard is broken.
6. `ScoreboardV2`, only as a last free-data fallback.

If the CDN/debug output says `NBA live scoreboard endpoint is not returning JSON from this environment`, or if all free endpoints return stale scheduled data, reliable production live tracking requires a dedicated live sports data provider.

Live debugging:

```powershell
python src/debug_live_scoreboard.py GAME_ID
curl.exe http://127.0.0.1:5000/games/today
curl.exe "http://127.0.0.1:5000/predict/GAME_ID?mode=live"
```

## Live Backend MVP

The backend is intentionally local-first and polling-based. It is not a production sports-data service.

Health check:

```powershell
curl.exe http://127.0.0.1:5000/health
```

Historical prediction endpoint:

```powershell
curl.exe "http://127.0.0.1:5000/predict/YOUR_GAME_ID?mode=historical"
```

Live polling prediction endpoint:

```powershell
curl.exe "http://127.0.0.1:5000/predict/YOUR_GAME_ID?mode=live"
```

WebSocket event:

- Event name: `subscribe_game`
- Payload: `{ "game_id": "YOUR_GAME_ID", "mode": "live" }`
- Emits: `prediction_update`

## Future Live Architecture

```text
nba_api polling -> pandas state builder -> champion model -> Flask API -> WebSocket -> live dashboard
```

The backend already shares the Champion Model inference path with historical analysis through `src/champion_inference.py`.

## Current Limitations

- Accuracy depends heavily on training data size and season coverage.
- `nba_api` is unofficial and can be slow or temporarily unavailable.
- Live mode is local-first and polling-based, not a production low-latency sports feed.
- Possession, lineup, team-strength, rest, injuries, and betting-market context are future improvements.
- Team logos use the public NBA static logo path when the abbreviation is recognized, and fall back gracefully when unavailable.
- The neural network is a benchmark, not assumed to be best. The champion is whatever wins on probability metrics.

## Generated Artifacts

Generated data, model binaries, predictions, and reports are intentionally ignored:

- `data/`
- `models/`
- `reports/`

Do not commit datasets, trained models, prediction CSVs, or leaderboard/report outputs.

## Final Command Checklist

```powershell
python src/build_training_dataset.py --seasons 2022-23 2023-24 --max-games 300
python src/team_strength.py --apply-to-seasons 2022-23 2023-24
python src/model_features.py
python src/train_model.py
python src/train_advanced_model.py
python src/train_gradient_boosting.py
python src/train_neural_network.py
python src/train_sequence_model.py
python src/compare_models.py --leaderboard
python src/calibrate_champion.py
python src/calibration_report.py
python src/game_index.py
python src/batch_analyze.py --test-games --limit 20 --skip-existing
python src/demo_games.py
python src/run_pipeline.py --game-id YOUR_GAME_ID --model baseline
python src/run_pipeline.py --game-id YOUR_GAME_ID --model ml
python src/run_pipeline.py --game-id YOUR_GAME_ID --model advanced
python src/run_pipeline.py --game-id YOUR_GAME_ID --model neural
python src/compare_models.py --game-id YOUR_GAME_ID
python src/game_insights.py --game-id YOUR_GAME_ID
python src/recap.py --game-id YOUR_GAME_ID
python backend/app.py
streamlit run app/streamlit_app.py
```
