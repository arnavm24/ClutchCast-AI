"use client";

import { motion } from "framer-motion";
import Link from "next/link";
import type { GameSummary } from "@/lib/data";
import { teamColor } from "@/lib/nba";
import TeamMark from "./TeamMark";

function formatDate(date: string | null) {
  if (!date) return "";
  const d = new Date(date);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

export default function GameCard({ game, badge }: { game: GameSummary; badge?: string }) {
  const homeWon = game.finalHome > game.finalAway;
  return (
    <Link href={`/game/${game.id}`} className="block">
      <motion.div whileHover={{ y: -3 }} whileTap={{ scale: 0.985 }} className="panel panel-hover px-5 py-4">
        <div className="mb-3 flex items-center justify-between text-[11px] font-bold uppercase tracking-widest text-muted">
          <span>
            {formatDate(game.date)}
            {game.overtime ? " · OT" : ""}
            {game.playoffRound === 4 ? <span className="text-amber-300"> · 🏆 Finals</span> : game.playoffRound > 0 ? " · Playoffs" : ""}
          </span>
          {badge ? (
            <span className="rounded-full bg-gradient-to-r from-orange-500/20 to-blue-600/20 px-2.5 py-1 text-[10px] text-orange-200">{badge}</span>
          ) : game.drama != null ? (
            <span className="text-amber-300/90">🎭 {Math.round(game.drama)}</span>
          ) : null}
        </div>
        {[{ code: game.away, score: game.finalAway, won: !homeWon }, { code: game.home, score: game.finalHome, won: homeWon }].map((team) => (
          <div key={team.code} className="flex items-center gap-3 py-1">
            <TeamMark tricode={team.code} size={30} />
            <span className={`text-sm font-extrabold ${team.won ? "text-foreground" : "text-muted"}`} style={team.won ? { color: teamColor(team.code) } : undefined}>
              {team.code}
            </span>
            <span className={`score-num ml-auto text-xl font-black ${team.won ? "text-foreground" : "text-muted"}`}>{team.score}</span>
          </div>
        ))}
        <div className="mt-2 text-[11px] font-semibold text-muted">
          {Math.abs(game.margin) <= 3 ? "Down to the wire" : Math.abs(game.margin) >= 20 ? "Blowout" : `${game.leadChanges} lead changes`} · view breakdown →
        </div>
      </motion.div>
    </Link>
  );
}
