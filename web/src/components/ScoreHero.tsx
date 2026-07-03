"use client";

import { motion } from "framer-motion";
import type { GameDetail } from "@/lib/data";
import { teamColor } from "@/lib/nba";
import CountUp from "./CountUp";
import TeamMark from "./TeamMark";

export default function ScoreHero({ game }: { game: GameDetail }) {
  const homeWon = game.finalHome > game.finalAway;
  const homeColor = teamColor(game.home);
  const awayColor = teamColor(game.away);
  const finalPoint = game.timeline[game.timeline.length - 1];
  const homeWp = finalPoint?.wp ?? (homeWon ? 100 : 0);

  const team = (code: string, score: number, won: boolean, color: string, align: "left" | "right") => (
    <div className={`flex items-center gap-4 ${align === "right" ? "flex-row-reverse text-right" : ""}`}>
      <TeamMark tricode={code} size={64} />
      <div>
        <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-muted">{code}</div>
        <CountUp value={score} className={`score-num block text-6xl font-black leading-none sm:text-7xl ${won ? "" : "opacity-50"}`} duration={1.4} />
        {won && (
          <motion.span initial={{ opacity: 0, y: 6 }} animate={{ opacity: 1, y: 0 }} transition={{ delay: 1.2 }} className="mt-1 inline-block rounded-full px-2.5 py-0.5 text-[10px] font-black uppercase tracking-widest" style={{ background: `${color}26`, color }}>
            Winner
          </motion.span>
        )}
      </div>
    </div>
  );

  return (
    <motion.div initial={{ opacity: 0, scale: 0.985 }} animate={{ opacity: 1, scale: 1 }} transition={{ duration: 0.6 }} className="panel relative overflow-hidden px-6 py-8 sm:px-10">
      <div
        className="pointer-events-none absolute inset-0 opacity-40"
        style={{ background: `radial-gradient(600px 240px at 12% 0%, ${awayColor}22, transparent 60%), radial-gradient(600px 240px at 88% 0%, ${homeColor}22, transparent 60%)` }}
      />
      <div className="relative flex flex-col items-center justify-between gap-8 sm:flex-row">
        {team(game.away, game.finalAway, !homeWon, awayColor, "left")}
        <div className="text-center">
          <div className="eyebrow">Final{game.overtime ? ` · ${game.nOvertimes > 1 ? `${game.nOvertimes}OT` : "OT"}` : ""}</div>
          <div className="mt-1 text-sm font-bold text-muted">{game.model}</div>
        </div>
        {team(game.home, game.finalHome, homeWon, homeColor, "right")}
      </div>

      <div className="relative mt-8">
        <div className="mb-2 flex justify-between text-xs font-black tabular-nums">
          <span style={{ color: awayColor }}>{game.away} {(100 - homeWp).toFixed(0)}%</span>
          <span className="text-muted">final win probability</span>
          <span style={{ color: homeColor }}>{game.home} {homeWp.toFixed(0)}%</span>
        </div>
        <div className="flex h-3.5 overflow-hidden rounded-full border border-line bg-black/40">
          <motion.div initial={{ width: "50%" }} animate={{ width: `${100 - homeWp}%` }} transition={{ duration: 1.3, ease: "easeOut" }} style={{ background: `linear-gradient(90deg, ${awayColor}, ${awayColor}99)` }} />
          <motion.div initial={{ width: "50%" }} animate={{ width: `${homeWp}%` }} transition={{ duration: 1.3, ease: "easeOut" }} style={{ background: `linear-gradient(90deg, ${homeColor}99, ${homeColor})` }} />
        </div>
      </div>
    </motion.div>
  );
}
