"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import { useEffect, useState } from "react";
import type { TodayGame } from "@/lib/nba";
import TeamMark from "./TeamMark";

export default function TodayGames() {
  const [games, setGames] = useState<TodayGame[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = () =>
      fetch("/api/today")
        .then((r) => r.json())
        .then((d) => {
          if (!cancelled) setGames(d.games ?? []);
        })
        .catch(() => {
          if (!cancelled) setGames([]);
        });
    load();
    const interval = setInterval(load, 30_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, []);

  if (games === null) {
    return <div className="panel animate-pulse px-6 py-8 text-sm text-muted">Checking tonight&apos;s slate…</div>;
  }

  if (games.length === 0) {
    return (
      <div className="panel px-6 py-8">
        <div className="text-sm font-bold text-foreground">No NBA games today</div>
        <p className="mt-1 text-sm text-muted">
          It&apos;s the offseason — the schedule picks back up in October. Meanwhile, relive the featured games below: every one has a full win-probability breakdown.
        </p>
      </div>
    );
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
      {games.map((game, index) => {
        const live = game.gameStatus === 2;
        const final = game.gameStatus === 3;
        return (
          <motion.div
            key={game.gameId}
            initial={{ opacity: 0, y: 16 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: index * 0.06 }}
          >
            <Link href={live || final ? `/live/${game.gameId}` : "#"} className={live || final ? "" : "pointer-events-none"}>
              <div className="panel panel-hover px-5 py-4">
                <div className="mb-3 flex items-center justify-between text-[11px] font-bold uppercase tracking-widest">
                  {live ? (
                    <span className="flex items-center gap-2 text-red-400">
                      <span className="live-dot h-2 w-2 rounded-full bg-red-500" /> Live · Q{game.period} {game.gameClock.replace("PT", "").replace("M", ":").replace(/\.\d+S/, "")}
                    </span>
                  ) : (
                    <span className="text-muted">{game.gameStatusText}</span>
                  )}
                  {(live || final) && <span className="text-muted">tap for win prob →</span>}
                </div>
                {[game.awayTeam, game.homeTeam].map((team) => (
                  <div key={team.teamTricode} className="flex items-center gap-3 py-1">
                    <TeamMark tricode={team.teamTricode} size={30} />
                    <span className="text-sm font-extrabold">{team.teamTricode}</span>
                    <span className="score-num ml-auto text-xl font-black">{game.gameStatus === 1 ? "–" : team.score}</span>
                  </div>
                ))}
              </div>
            </Link>
          </motion.div>
        );
      })}
    </div>
  );
}
