"use client";

// Browse every indexed game — no game IDs required. Filter by team, closeness,
// overtime; sort by drama or date. Only analyzed games are clickable.

import { AnimatePresence, motion } from "framer-motion";
import { useMemo, useState } from "react";
import type { GameSummary } from "@/lib/data";
import GameCard from "./GameCard";

const TEAMS = [
  "ATL","BOS","BKN","CHA","CHI","CLE","DAL","DEN","DET","GSW","HOU","IND","LAC","LAL","MEM",
  "MIA","MIL","MIN","NOP","NYK","OKC","ORL","PHI","PHX","POR","SAC","SAS","TOR","UTA","WAS",
];

type SortKey = "date" | "drama" | "closest";

export default function GameBrowser({ games }: { games: GameSummary[] }) {
  const [team, setTeam] = useState("");
  const [closeOnly, setCloseOnly] = useState(false);
  const [overtimeOnly, setOvertimeOnly] = useState(false);
  const [playoffsOnly, setPlayoffsOnly] = useState(false);
  const [sort, setSort] = useState<SortKey>("drama");
  const [limit, setLimit] = useState(12);

  const filtered = useMemo(() => {
    let rows = games.filter((g) => g.analyzed);
    if (team) rows = rows.filter((g) => g.home === team || g.away === team);
    if (closeOnly) rows = rows.filter((g) => Math.abs(g.margin) <= 5);
    if (overtimeOnly) rows = rows.filter((g) => g.overtime);
    if (playoffsOnly) rows = rows.filter((g) => g.playoffRound > 0);
    rows = [...rows].sort((a, b) => {
      if (sort === "drama") return (b.drama ?? -1) - (a.drama ?? -1);
      if (sort === "closest") return Math.abs(a.margin) - Math.abs(b.margin);
      return (b.date ?? "").localeCompare(a.date ?? "");
    });
    return rows;
  }, [games, team, closeOnly, overtimeOnly, sort]);

  const toggleClass = (active: boolean) =>
    `rounded-full border px-4 py-2 text-xs font-bold transition ${
      active ? "border-orange-400/60 bg-orange-500/15 text-orange-200" : "border-line bg-white/[0.03] text-muted hover:text-foreground"
    }`;

  return (
    <div>
      <div className="mb-5 flex flex-wrap items-center gap-2">
        <select
          value={team}
          onChange={(e) => setTeam(e.target.value)}
          className="rounded-full border border-line bg-[#0b1120] px-4 py-2 text-xs font-bold text-foreground outline-none"
        >
          <option value="">All teams</option>
          {TEAMS.map((t) => (
            <option key={t} value={t}>{t}</option>
          ))}
        </select>
        <button className={toggleClass(closeOnly)} onClick={() => setCloseOnly(!closeOnly)}>Close finishes</button>
        <button className={toggleClass(overtimeOnly)} onClick={() => setOvertimeOnly(!overtimeOnly)}>Overtime</button>
        <button className={toggleClass(playoffsOnly)} onClick={() => setPlayoffsOnly(!playoffsOnly)}>🏆 Playoffs</button>
        <div className="ml-auto flex items-center gap-1 text-xs font-bold text-muted">
          sort
          {(["drama", "date", "closest"] as SortKey[]).map((key) => (
            <button key={key} className={toggleClass(sort === key)} onClick={() => setSort(key)}>
              {key === "drama" ? "🎭 drama" : key === "date" ? "newest" : "closest"}
            </button>
          ))}
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <AnimatePresence mode="popLayout">
          {filtered.slice(0, limit).map((game) => (
            <motion.div key={game.id} layout initial={{ opacity: 0, scale: 0.96 }} animate={{ opacity: 1, scale: 1 }} exit={{ opacity: 0, scale: 0.96 }} transition={{ duration: 0.25 }}>
              <GameCard game={game} />
            </motion.div>
          ))}
        </AnimatePresence>
      </div>

      {filtered.length === 0 && (
        <div className="panel px-6 py-8 text-sm text-muted">No analyzed games match those filters yet.</div>
      )}
      {filtered.length > limit && (
        <div className="mt-6 text-center">
          <button className={toggleClass(false)} onClick={() => setLimit(limit + 12)}>
            Show more ({filtered.length - limit} remaining)
          </button>
        </div>
      )}
    </div>
  );
}
