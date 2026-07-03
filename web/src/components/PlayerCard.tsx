"use client";

import { motion } from "framer-motion";
import type { PlayerImpact } from "@/lib/data";
import { headshotUrl, teamColor } from "@/lib/nba";
import CountUp from "./CountUp";

export default function PlayerCard({ player, rank }: { player: PlayerImpact; rank: number }) {
  const accent = teamColor(player.team);
  const initials = player.name.slice(0, 2).toUpperCase();
  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      whileInView={{ opacity: 1, y: 0 }}
      viewport={{ once: true }}
      transition={{ delay: rank * 0.07 }}
      whileHover={{ y: -4 }}
      className="panel relative overflow-hidden px-5 pb-5 pt-4"
      style={{ borderTop: `3px solid ${accent}` }}
    >
      <div className="flex items-center gap-4">
        <span className="relative inline-flex h-16 w-16 shrink-0 items-center justify-center overflow-hidden rounded-full border-2 bg-gradient-to-br from-orange-500/60 to-blue-600/60" style={{ borderColor: accent }}>
          <span className="absolute text-lg font-black text-white">{initials}</span>
          {player.personId && (
            // eslint-disable-next-line @next/next/no-img-element
            <img src={headshotUrl(player.personId)} alt="" className="absolute inset-0 h-full w-full object-cover object-top" loading="lazy" />
          )}
        </span>
        <div className="min-w-0">
          <div className="truncate text-base font-black">{player.name}</div>
          <div className="text-[11px] font-bold uppercase tracking-widest text-muted">
            {player.team} · {player.events} tracked plays
          </div>
        </div>
        <div className="ml-auto text-right">
          <CountUp value={player.impact} decimals={1} className="score-num text-2xl font-black" />
          <div className="text-[10px] font-bold uppercase tracking-widest text-muted">WP impact</div>
        </div>
      </div>
    </motion.div>
  );
}
