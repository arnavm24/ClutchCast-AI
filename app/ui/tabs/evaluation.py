import pandas as pd
import streamlit as st

from ui.charts import brier_by_quarter_chart, reliability_diagram
from ui.components import render_metric_card, render_summary_card, show_empty_report_card
from ui.config import REPORTS_DIR
from ui.data_loaders import load_csv_if_exists
from ui.formatting import clean_table_columns, render_html


def show_calibration_section(champion: dict) -> None:
    st.markdown("### Probability Quality (Calibration)")
    render_html('<div class="tab-intro">A win-probability model is only useful if its numbers mean what they say: moments scored at 70% should be won about 70% of the time. These charts test exactly that on held-out games the models never trained on.</div>')
    curves = load_csv_if_exists(REPORTS_DIR / "calibration_curves.csv")
    summary = load_csv_if_exists(REPORTS_DIR / "calibration_summary.csv")
    by_quarter = load_csv_if_exists(REPORTS_DIR / "brier_by_quarter.csv")
    if curves.empty or summary.empty:
        show_empty_report_card("Calibration report", "python src/calibration_report.py")
        return

    champion_key = champion.get("model_key", "")
    cards = []
    for _, row in summary.sort_values("ece").iterrows():
        badge = " 🏆" if str(row["model_key"]) == champion_key else (" ⚠ Overconfident" if bool(row.get("overconfident", False)) else "")
        cards.append(render_metric_card(
            f"{row['model_name']}{badge}",
            f"ECE {float(row['ece']):.4f}",
            f"Brier {float(row['brier_score']):.4f} · Max bin error {float(row['max_calibration_error']):.3f}",
        ))
    render_html('<div class="metric-grid">' + "".join(cards) + '</div>')

    st.markdown("#### Reliability Diagram")
    render_html('<div class="tab-intro">Each point is a bucket of predictions. On the dashed line, predicted probability matches reality. Below the line at high probabilities means the model is overconfident.</div>')
    reliability_diagram(curves, champion_key, chart_key="calibration_reliability")

    overconfident = summary[summary.get("overconfident", pd.Series(dtype=bool)) == True]  # noqa: E712
    if not overconfident.empty:
        names = ", ".join(overconfident["model_name"].astype(str))
        st.warning(f"Overconfidence detected on held-out games for: {names}. Their high-probability calls run hotter than reality, so treat extreme percentages from these paths with caution.")

    if not by_quarter.empty:
        st.markdown("#### Brier Score by Quarter")
        render_html('<div class="tab-intro">Early-game predictions are genuinely harder — probability error should shrink as the game reveals itself.</div>')
        brier_by_quarter_chart(by_quarter, chart_key="calibration_brier_quarter")


def render(data: dict, champion: dict, game_id: str) -> None:
    st.subheader("Model Evaluation")
    render_html('<div class="tab-intro">The champion is selected by <strong>probability quality, not model complexity</strong> — every model trains on the same data and competes on Brier score, log loss, ROC-AUC, then accuracy over held-out games.</div>')
    leaderboard, disagreements = data["leaderboard"], data["model_disagreements"]
    if leaderboard.empty:
        show_empty_report_card("Model leaderboard", "python src/compare_models.py --leaderboard")
    else:
        best_brier = leaderboard.sort_values("brier_score", ascending=True).iloc[0]
        best_auc = leaderboard.sort_values("roc_auc", ascending=False).iloc[0]
        cards = [
            render_summary_card("Champion Model", champion.get("model_name", "Champion unavailable"), "Selected by Brier, log loss, ROC-AUC, then accuracy."),
            render_summary_card("Best Brier Score", f"{float(best_brier['brier_score']):.4f}", str(best_brier["model_name"])),
            render_summary_card("Best ROC-AUC", f"{float(best_auc['roc_auc']):.4f}", str(best_auc["model_name"])),
            render_summary_card("Disagreement Peak", "Pending" if disagreements.empty else f"{float(disagreements['max_model_disagreement_pct'].max()):.1f} pts", f"python src/compare_models.py --game-id {game_id}"),
        ]
        render_html('<div class="summary-grid">' + "".join(cards) + '</div>')
        display = leaderboard.copy()
        display["Champion"] = display["model_key"].eq(champion.get("model_key")).map({True: "Yes", False: ""})
        st.dataframe(clean_table_columns(display), width="stretch", hide_index=True)
    show_calibration_section(champion)
    if not disagreements.empty:
        st.markdown("### Biggest Model Disagreement Moments")
        st.dataframe(clean_table_columns(disagreements), width="stretch", hide_index=True)
