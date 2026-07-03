import Reveal from "@/components/Reveal";
import ReliabilityChart from "@/components/ReliabilityChart";
import { loadModels } from "@/lib/data";

export const metadata = { title: "The Model — ClutchCast AI" };

export default async function ModelsPage() {
  const data = await loadModels();
  const champion = data.champion;
  const leaderboard = data.leaderboard;
  const summaryByKey = new Map(data.calibrationSummary.map((row) => [String(row.model_key), row]));

  return (
    <div className="pt-12">
      <Reveal>
        <p className="eyebrow">Under the hood</p>
        <h1 className="mt-3 max-w-3xl text-4xl font-black leading-tight tracking-tight sm:text-5xl">
          Six models compete. The most <span className="brand-gradient">honest</span> one wins.
        </h1>
        <p className="mt-4 max-w-2xl text-muted">
          Every model trains on the same three seasons ({String(champion.train_games)} games) and is tested on{" "}
          {String(champion.test_games)} games it has never seen. The champion is chosen by probability quality — when it
          says 70%, does the team actually win 70% of the time? — not by accuracy or complexity.
        </p>
      </Reveal>

      <Reveal className="mt-12">
        <h2 className="mb-4 text-xl font-black tracking-tight">Leaderboard</h2>
        <div className="panel overflow-x-auto">
          <table className="w-full min-w-[560px] text-sm">
            <thead>
              <tr className="border-b border-line text-left text-[11px] uppercase tracking-widest text-muted">
                <th className="px-5 py-3">#</th>
                <th className="px-5 py-3">Model</th>
                <th className="px-5 py-3">Brier ↓</th>
                <th className="px-5 py-3">Log loss ↓</th>
                <th className="px-5 py-3">ROC-AUC ↑</th>
                <th className="px-5 py-3">Accuracy</th>
                <th className="px-5 py-3">Calibration (ECE)</th>
              </tr>
            </thead>
            <tbody>
              {leaderboard.map((row) => {
                const isChampion = row.model_key === champion.model_key;
                const cal = summaryByKey.get(String(row.model_key));
                return (
                  <tr key={String(row.model_key)} className={`border-b border-line/50 ${isChampion ? "bg-orange-500/[0.06]" : ""}`}>
                    <td className="px-5 py-3 font-black text-muted">{String(row.rank)}</td>
                    <td className="px-5 py-3 font-bold">
                      {String(row.model_name)} {isChampion && <span className="ml-1 rounded-full bg-orange-500/20 px-2 py-0.5 text-[10px] font-black uppercase text-orange-300">Champion</span>}
                    </td>
                    <td className="score-num px-5 py-3 font-bold">{Number(row.brier_score).toFixed(4)}</td>
                    <td className="score-num px-5 py-3 text-muted">{Number(row.log_loss).toFixed(4)}</td>
                    <td className="score-num px-5 py-3 text-muted">{Number(row.roc_auc).toFixed(3)}</td>
                    <td className="score-num px-5 py-3 text-muted">{(Number(row.accuracy) * 100).toFixed(1)}%</td>
                    <td className="score-num px-5 py-3 text-muted">
                      {cal ? Number(cal.ece).toFixed(4) : "—"}
                      {cal?.overconfident === true && <span className="ml-2 text-[10px] font-black uppercase text-amber-400">overconfident</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted">
          Note the gradient boosting row: strong accuracy, weak Brier score — a model can pick winners well while its
          percentages run too hot. That is exactly why accuracy alone doesn&apos;t decide the champion.
        </p>
      </Reveal>

      <Reveal className="mt-12">
        <h2 className="mb-1 text-xl font-black tracking-tight">Does 70% mean 70%?</h2>
        <p className="mb-5 max-w-2xl text-sm text-muted">
          Each dot buckets thousands of held-out predictions. On the dashed line, predicted probability matches reality.
          Below the line at the right edge means overconfidence.
        </p>
        <div className="panel px-4 py-5 sm:px-6">
          <ReliabilityChart curves={data.calibrationCurves} championKey={String(champion.model_key)} />
        </div>
      </Reveal>

      {data.calibrationEffect.length > 0 && (
        <Reveal className="mt-12">
          <div className="panel px-6 py-6">
            <div className="eyebrow">Engineering note</div>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-foreground/90">
              We also fit an isotonic calibration layer for the champion. On held-out games it{" "}
              {data.calibrationEffect.some((row) => row.applied === true) ? "improved probability quality and is applied at inference." : (
                <>did <span className="font-bold">not</span> improve probability quality (Brier {Number(data.calibrationEffect[0]?.brier_score).toFixed(4)} raw vs {Number(data.calibrationEffect[1]?.brier_score).toFixed(4)} calibrated), so it is deliberately not applied — the champion is already well calibrated.</>
              )}
            </p>
          </div>
        </Reveal>
      )}
    </div>
  );
}
