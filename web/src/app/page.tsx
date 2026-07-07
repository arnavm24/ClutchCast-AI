import Link from "next/link";
import GameCard from "@/components/GameCard";
import GameBrowser from "@/components/GameBrowser";
import Reveal from "@/components/Reveal";
import TodayGames from "@/components/TodayGames";
import { loadGamesIndex } from "@/lib/data";

export default async function HomePage() {
  const { featured, games } = await loadGamesIndex();
  const byId = new Map(games.map((g) => [g.id, g]));
  const featuredGames = featured
    .map((f) => ({ meta: f, game: byId.get(f.game_id) }))
    .filter((f) => f.game);

  return (
    <div className="pt-12">
      <Reveal>
        <p className="eyebrow">NBA win probability, play by play</p>
        <h1 className="mt-3 max-w-3xl text-4xl font-black leading-[1.05] tracking-tight sm:text-6xl">
          Every game has a moment it was <span className="brand-gradient">decided</span>. Find it.
        </h1>
        <p className="mt-4 max-w-2xl text-base text-muted sm:text-lg">
          ClutchCast AI tracks the win probability of every play. It is trained on three NBA seasons, tested on games
          it has never seen, and honest about how sure it really is.
        </p>
      </Reveal>

      <Reveal delay={0.1} className="mt-14">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-xl font-black tracking-tight">Tonight</h2>
          <span className="text-xs font-semibold text-muted">auto-refreshes every 30s</span>
        </div>
        <TodayGames />
      </Reveal>

      {featuredGames.length > 0 && (
        <Reveal delay={0.15} className="mt-14">
          <div className="mb-4 flex items-baseline justify-between">
            <h2 className="text-xl font-black tracking-tight">Featured games</h2>
            <span className="text-xs font-semibold text-muted">chosen by the model</span>
          </div>
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
            {featuredGames.map(({ meta, game }) => (
              <GameCard key={meta.key} game={game!} badge={meta.label} />
            ))}
          </div>
        </Reveal>
      )}

      <Reveal delay={0.1} className="mt-14">
        <div className="mb-4 flex items-baseline justify-between">
          <h2 className="text-xl font-black tracking-tight">Browse every game</h2>
          <Link href="/models" className="text-xs font-bold text-orange-300 hover:underline">
            how the model works →
          </Link>
        </div>
        <GameBrowser games={games} />
      </Reveal>
    </div>
  );
}
