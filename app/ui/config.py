from pathlib import Path
from urllib.parse import quote

PROJECT_ROOT = Path(__file__).resolve().parents[2]
PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
REPORTS_DIR = PROJECT_ROOT / "reports"
APP_DIR = PROJECT_ROOT / "app"
DEMO_GAMES_PATH = APP_DIR / "demo_games.json"
BACKEND_BASE_URL = "http://127.0.0.1:5000"

DEFAULT_HOME_COLOR = "#3B82F6"
DEFAULT_AWAY_COLOR = "#EF4444"
CHART_AWAY_COLOR = "#38BDF8"
CHART_HOME_COLOR = "#F43F5E"

CLUTCHCAST_ICON_SVG = """
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs><radialGradient id="g" cx="30%" cy="25%" r="80%"><stop offset="0" stop-color="#FDBA74"/><stop offset=".42" stop-color="#F97316"/><stop offset="1" stop-color="#1D4ED8"/></radialGradient></defs>
  <rect width="64" height="64" rx="18" fill="#070A12"/>
  <circle cx="32" cy="32" r="23" fill="url(#g)"/>
  <path d="M14 34h36M31 9c6 12 6 34 0 46M13 25c12 5 26 5 38 0M13 43c12-5 26-5 38 0" stroke="rgba(255,255,255,.48)" stroke-width="2.2" fill="none" stroke-linecap="round"/>
  <text x="32" y="39" text-anchor="middle" font-family="Arial, Helvetica, sans-serif" font-size="18" font-weight="900" fill="#F8FAFC">CC</text>
</svg>
""".strip()
CLUTCHCAST_ICON_DATA_URL = "data:image/svg+xml;charset=utf-8," + quote(CLUTCHCAST_ICON_SVG)

MODE_LABELS = {
    "baseline": "Baseline Model",
    "logistic_regression": "Logistic Regression",
    "random_forest": "Random Forest",
    "gradient_boosting": "Gradient Boosting",
    "pytorch_neural_network": "Neural Network",
    "sequence_gru": "GRU Sequence Model",
}

MODE_FILES = {
    "baseline": "baseline_predictions_{game_id}.csv",
    "logistic_regression": "ml_predictions_{game_id}.csv",
    "random_forest": "advanced_predictions_{game_id}.csv",
    "gradient_boosting": "gbm_predictions_{game_id}.csv",
    "pytorch_neural_network": "neural_predictions_{game_id}.csv",
    "sequence_gru": "seq_predictions_{game_id}.csv",
}

TEAM_IDS = {
    "ATL": "1610612737", "BOS": "1610612738", "BKN": "1610612751", "CHA": "1610612766",
    "CHI": "1610612741", "CLE": "1610612739", "DAL": "1610612742", "DEN": "1610612743",
    "DET": "1610612765", "GSW": "1610612744", "HOU": "1610612745", "IND": "1610612754",
    "LAC": "1610612746", "LAL": "1610612747", "MEM": "1610612763", "MIA": "1610612748",
    "MIL": "1610612749", "MIN": "1610612750", "NOP": "1610612740", "NYK": "1610612752",
    "OKC": "1610612760", "ORL": "1610612753", "PHI": "1610612755", "PHX": "1610612756",
    "POR": "1610612757", "SAC": "1610612758", "SAS": "1610612759", "TOR": "1610612761",
    "UTA": "1610612762", "WAS": "1610612764",
}

TEAM_COLORS = {
    "ATL": "#E03A3E", "BOS": "#007A33", "BKN": "#FFFFFF", "CHA": "#1D1160",
    "CHI": "#CE1141", "CLE": "#860038", "DAL": "#00538C", "DEN": "#FEC524",
    "DET": "#C8102E", "GSW": "#1D428A", "HOU": "#CE1141", "IND": "#FDBB30",
    "LAC": "#C8102E", "LAL": "#FDB927", "MEM": "#5D76A9", "MIA": "#98002E",
    "MIL": "#00471B", "MIN": "#0C2340", "NOP": "#0C2340", "NYK": "#F58426",
    "OKC": "#007AC1", "ORL": "#0077C0", "PHI": "#006BB6", "PHX": "#E56020",
    "POR": "#E03A3E", "SAC": "#5A2D81", "SAS": "#C4CED4", "TOR": "#CE1141",
    "UTA": "#002B5C", "WAS": "#002B5C",
}


def team_color(team: str, fallback: str) -> str:
    return TEAM_COLORS.get(str(team).upper(), fallback)


def team_logo_url(team: str) -> str | None:
    team_id = TEAM_IDS.get(str(team).upper())
    if not team_id:
        return None
    return f"https://cdn.nba.com/logos/nba/{team_id}/primary/L/logo.svg"


def player_headshot_url(person_id: int | str) -> str:
    return f"https://cdn.nba.com/headshots/nba/latest/1040x760/{person_id}.png"
