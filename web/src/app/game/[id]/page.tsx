import Link from "next/link";
import { notFound } from "next/navigation";
import PlayerCard from "@/components/PlayerCard";
import Reveal from "@/components/Reveal";
import ScoreHero from "@/components/ScoreHero";
import WinProbChart from "@/components/WinProbChart";
import { listAnalyzedGameIds, loadGame } from "@/lib/data";

export async function generateStaticParams() {
  const ids = await listAnalyzedGameIds();
  return ids.map((id) => ({ id }));
}

export async function generateMetadata({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const game = await loadGame(id);
  if (!game) return { title: "Game not found" };
  const title = `${game.away} ${game.finalAway}-${game.finalHome} ${game.home}${game.overtime ? " (OT)" : ""}`;
  const description = `Win probability timeline, turning points, and player impact for ${game.away} at ${game.home}.`;
  return { title, description, openGraph: { title, description } };
}

function periodLabel(per: number) {
  return per <= 4 ? `Q${per}` : per === 5 ? "OT" : `${per - 4}OT`;
}

export default async function GamePage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const game = await loadGame(id);
  if (!game) notFound();

  const drama = game.insights["Game Drama Score"];
  const mvp = game.insights["Most Valuable Play"];
  const damaging = game.insights["Most Damaging Play"];
  const clutch = game.insights["Clutch-Time Scoring Summary"];
  const date = game.date
    ? new Date(game.date).toLocaleDateString("en-US", { weekday: "long", month: "long", day: "numeric", year: "numeric" })
    : null;

  return (
    <div className="pt-8">
      <div className="mb-5 flex items-center justify-between">
        <Link href="/" className="text-sm font-bold text-muted transition hover:text-foreground">← All games</Link>
        {date && <span className="text-sm font-semibold text-muted">{date}</span>}
      </div>

      <ScoreHero game={game} />

      <Reveal className="mt-12">
        <h2 className="mb-1 text-xl font-black tracking-tight">The story of the game</h2>
        <p className="mb-5 text-sm text-muted">Win probability after every play. Hover to relive any moment.</p>
        <div className="panel px-4 py-5 sm:px-6">
          <WinProbChart timeline={game.timeline} home={game.home} away={game.away} />
        </div>
      </Reveal>

      {(drama || mvp || damaging || clutch) && (
        <Reveal className="mt-12">
          <div className="grid gap-4 sm:grid-cols-2">
            {drama && (
              <div className="panel px-5 py-5">
                <div className="eyebrow">Drama score</div>
                <div className="score-num mt-2 text-4xl font-black text-amber-300">{drama.value}<span className="text-lg text-muted">/100</span></div>
                <p className="mt-2 text-sm leading-relaxed text-muted">{drama.details}</p>
              </div>
            )}
            {mvp && (
              <div className="panel px-5 py-5">
                <div className="eyebrow">Play of the game</div>
                <p className="mt-2 text-sm leading-relaxed text-foreground">{mvp.details}</p>
              </div>
            )}
            {damaging && (
              <div className="panel px-5 py-5">
                <div className="eyebrow">The dagger (for the loser)</div>
                <p className="mt-2 text-sm leading-relaxed text-muted">{damaging.details}</p>
              </div>
            )}
            {clutch && (
              <div className="panel px-5 py-5">
                <div className="eyebrow">Clutch-time scoring</div>
                <p className="mt-2 text-sm leading-relaxed text-muted">{clutch.details}</p>
              </div>
            )}
          </div>
        </Reveal>
      )}

      {game.turningPoints.length > 0 && (
        <Reveal className="mt-12">
          <h2 className="mb-1 text-xl font-black tracking-tight">Turning points</h2>
          <p className="mb-5 text-sm text-muted">The plays that moved winning odds the most.</p>
          <div className="scrollbar-hidden -mx-5 flex gap-4 overflow-x-auto px-5 pb-2">
            {game.turningPoints.map((tp, i) => (
              <div key={i} className="panel w-72 shrink-0 px-5 py-4">
                <div className="flex items-baseline justify-between">
                  <span className="text-xs font-black uppercase tracking-widest text-muted">{periodLabel(tp.per)} {tp.clock}</span>
                  <span className={`score-num text-lg font-black ${tp.swing >= 0 ? "text-emerald-400" : "text-rose-400"}`}>
                    {tp.swing >= 0 ? "+" : ""}{tp.swing.toFixed(1)}
                  </span>
                </div>
                <div className="mt-2 text-sm font-bold">{tp.player} <span className="text-muted">({tp.team})</span></div>
                <p className="mt-1 line-clamp-2 text-xs leading-relaxed text-muted">{tp.play}</p>
                <div className="mt-3 text-[11px] font-bold tabular-nums text-muted">
                  Home win probability: {tp.before.toFixed(0)}% <span className="text-foreground">→</span> {tp.after.toFixed(0)}%
                </div>
              </div>
            ))}
          </div>
        </Reveal>
      )}

      {game.players.length > 0 && (
        <Reveal className="mt-12">
          <h2 className="mb-1 text-xl font-black tracking-tight">Who actually swung it</h2>
          <p className="mb-5 text-sm text-muted">Players ranked by how much they moved the win probability, not by points scored.</p>
          <div className="grid gap-4 sm:grid-cols-2">
            {game.players.slice(0, 6).map((player, i) => (
              <PlayerCard key={`${player.name}-${player.team}`} player={player} rank={i} />
            ))}
          </div>
        </Reveal>
      )}

      {Object.keys(game.recap).length > 0 && (
        <Reveal className="mt-12">
          <h2 className="mb-5 text-xl font-black tracking-tight">Postgame read</h2>
          <div className="panel space-y-5 px-6 py-6 sm:px-8">
            {Object.entries(game.recap)
              .filter(([k]) => k !== "Model Note")
              .map(([section, text]) => (
                <div key={section}>
                  <div className="eyebrow">{section}</div>
                  <p className="mt-1 text-[15px] leading-relaxed text-foreground/90">{text}</p>
                </div>
              ))}
            {game.recap["Model Note"] && (
              <p className="border-t border-line pt-4 text-xs leading-relaxed text-muted">{game.recap["Model Note"]}</p>
            )}
          </div>
        </Reveal>
      )}
    </div>
  );
}
