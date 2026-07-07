"use client";

import { motion } from "framer-motion";
import { useState } from "react";
import type { PlayerImpact } from "@/lib/data";
import { headshotUrl, teamColor } from "@/lib/nba";
import CountUp from "./CountUp";

export default function PlayerCard({ player, rank }: { player: PlayerImpact; rank: number }) {
  const accent = teamColor(player.team);
  const initials = player.name.slice(0, 2).toUpperCase();
  const [imageFailed, setImageFailed] = useState(false);
  const showImage = player.personId && !imageFailed;

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
        <span
          className="relative inline-flex h-20 w-20 shrink-0 items-center justify-center overflow-hidden rounded-full border-2"
          style={{
            borderColor: accent,
            // Light backdrop so the transparent headshot PNGs stay crisp on the dark theme.
            background: showImage ? "radial-gradient(circle at 50% 30%, #e2e8f0, #94a3b8)" : `linear-gradient(135deg, ${accent}cc, #1e293b)`,
          }}
        >
          {showImage ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={headshotUrl(player.personId!)}
              alt={player.name}
              className="absolute inset-0 h-full w-full object-cover object-top"
              loading="lazy"
              onError={() => setImageFailed(true)}
            />
          ) : (
            <span className="text-xl font-black text-white">{initials}</span>
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
          <div className="text-[10px] font-bold uppercase tracking-widest text-muted">Win probability impact</div>
        </div>
      </div>
    </motion.div>
  );
}
