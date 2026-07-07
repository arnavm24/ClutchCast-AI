import Reveal from "@/components/Reveal";
import ReliabilityChart from "@/components/ReliabilityChart";
import { loadModels } from "@/lib/data";

export const metadata = { title: "The Model" };

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
          {String(champion.test_games)} games it has never seen. The champion is chosen by probability quality, not by
          accuracy or complexity. In plain terms: when it says 70%, does the team actually win 70% of the time?
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
                      {cal ? Number(cal.ece).toFixed(4) : "n/a"}
                      {cal?.overconfident === true && <span className="ml-2 text-[10px] font-black uppercase text-amber-400">overconfident</span>}
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        <p className="mt-3 text-xs text-muted">
          Note the gradient boosting row: strong accuracy, weak Brier score. A model can pick winners well while its
          percentages run too hot, and that is exactly why accuracy alone doesn&apos;t decide the champion.
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

      <Reveal className="mt-12">
        <h2 className="mb-1 text-xl font-black tracking-tight">How it&apos;s built</h2>
        <p className="mb-5 max-w-2xl text-sm text-muted">
          The full lifecycle, from raw play-by-play to the page you are reading, is one codebase.
        </p>
        <div className="mb-5 grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[
            { value: (Number(champion.train_games) + Number(champion.test_games)).toLocaleString(), label: "games across 3 seasons" },
            { value: (Number(champion.train_rows) + Number(champion.test_rows)).toLocaleString(), label: "game states learned from" },
            { value: String(champion.feature_count), label: "engineered features" },
            { value: String(leaderboard.length), label: "models competing" },
          ].map((stat) => (
            <div key={stat.label} className="panel px-5 py-5 text-center">
              <div className="score-num text-3xl font-black">{stat.value}</div>
              <div className="mt-1 text-[11px] font-bold uppercase tracking-widest text-muted">{stat.label}</div>
            </div>
          ))}
        </div>
        <div className="grid gap-4 lg:grid-cols-2">
          <div className="panel px-6 py-6">
            <div className="eyebrow">The pipeline</div>
            <p className="mt-2 text-sm leading-relaxed text-foreground/90">
              A Python pipeline (pandas, scikit-learn, PyTorch) turns every NBA play into a game state, engineers{" "}
              {String(champion.feature_count)} features covering time, score, momentum, possession, and team strength
              priors from the previous season, then trains all {leaderboard.length} models on identical data. Games are
              split at the game level so no moment from a test game ever leaks into training. A scheduled job repeats
              the whole cycle weekly during the season: download, retrain, re-select the champion, redeploy.
            </p>
          </div>
          <div className="panel px-6 py-6">
            <div className="eyebrow">The model runs in your browser</div>
            <p className="mt-2 text-sm leading-relaxed text-foreground/90">
              This site has no Python server. The champion network&apos;s weights are exported to JSON and executed in
              TypeScript, along with a full port of the feature pipeline. Every deploy runs a parity check proving the
              TypeScript output matches the original PyTorch model to eight decimal places. During live games, your
              browser fetches the play-by-play and computes win probability locally every ten seconds.
            </p>
          </div>
        </div>
        <div className="mt-5 text-center">
          <a
            href="https://github.com/arnavm24/ClutchCast-AI"
            target="_blank"
            rel="noopener noreferrer"
            className="inline-block rounded-full border border-orange-400/50 bg-orange-500/10 px-6 py-2.5 text-sm font-bold text-orange-200 transition hover:bg-orange-500/20"
          >
            Read the code on GitHub
          </a>
        </div>
      </Reveal>

      {data.calibrationEffect.length > 0 && (
        <Reveal className="mt-12">
          <div className="panel px-6 py-6">
            <div className="eyebrow">Engineering note</div>
            <p className="mt-2 max-w-3xl text-sm leading-relaxed text-foreground/90">
              We also fit an isotonic calibration layer for the champion. On held-out games it{" "}
              {data.calibrationEffect.some((row) => row.applied === true) ? "improved probability quality and is applied at inference." : (
                <>did <span className="font-bold">not</span> improve probability quality (Brier {Number(data.calibrationEffect[0]?.brier_score).toFixed(4)} raw vs {Number(data.calibrationEffect[1]?.brier_score).toFixed(4)} calibrated), so it is deliberately not applied. The champion is already well calibrated.</>
              )}
            </p>
          </div>
        </Reveal>
      )}
    </div>
  );
}
