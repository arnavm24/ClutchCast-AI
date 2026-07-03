"use client";

import { motion } from "framer-motion";
import { useMemo, useState } from "react";

const MODEL_COLORS: Record<string, string> = {
  pytorch_neural_network: "#f97316",
  sequence_gru: "#c084fc",
  random_forest: "#4ade80",
  gradient_boosting: "#fde047",
  logistic_regression: "#38bdf8",
  baseline: "#94a3b8",
  scoreboard_fallback: "#f43f5e",
};

const W = 640;
const H = 420;
const PAD = 48;

export default function ReliabilityChart({
  curves,
  championKey,
}: {
  curves: Record<string, string | number>[];
  championKey: string;
}) {
  const models = useMemo(() => {
    const grouped = new Map<string, { name: string; points: { x: number; y: number; count: number }[] }>();
    for (const row of curves) {
      const key = String(row.model_key);
      if (!grouped.has(key)) grouped.set(key, { name: String(row.model_name), points: [] });
      grouped.get(key)!.points.push({ x: Number(row.mean_predicted), y: Number(row.observed_rate), count: Number(row.count) });
    }
    for (const model of grouped.values()) model.points.sort((a, b) => a.x - b.x);
    return grouped;
  }, [curves]);

  const [active, setActive] = useState<string>(championKey);
  const x = (v: number) => PAD + v * (W - PAD - 16);
  const y = (v: number) => H - PAD + v * -(H - PAD - 16);

  return (
    <div>
      <div className="mb-4 flex flex-wrap gap-2">
        {[...models.keys()].map((key) => (
          <button
            key={key}
            onClick={() => setActive(key)}
            className={`rounded-full border px-3 py-1.5 text-[11px] font-bold transition ${
              active === key ? "border-white/40 bg-white/10 text-foreground" : "border-line text-muted hover:text-foreground"
            }`}
          >
            <span className="mr-1.5 inline-block h-2 w-2 rounded-full" style={{ background: MODEL_COLORS[key] ?? "#94a3b8" }} />
            {models.get(key)!.name}
            {key === championKey ? " 🏆" : ""}
          </button>
        ))}
      </div>
      <svg viewBox={`0 0 ${W} ${H}`} className="w-full">
        {[0, 0.25, 0.5, 0.75, 1].map((g) => (
          <g key={g}>
            <line x1={x(0)} x2={x(1)} y1={y(g)} y2={y(g)} stroke="rgba(148,163,184,0.1)" />
            <text x={x(0) - 8} y={y(g) + 4} textAnchor="end" fontSize="11" fill="#64748b">{Math.round(g * 100)}%</text>
            <text x={x(g)} y={H - PAD + 22} textAnchor="middle" fontSize="11" fill="#64748b">{Math.round(g * 100)}%</text>
          </g>
        ))}
        <text x={W / 2} y={H - 8} textAnchor="middle" fontSize="11" fill="#94a3b8" fontWeight="bold">predicted home win probability</text>
        <line x1={x(0)} y1={y(0)} x2={x(1)} y2={y(1)} stroke="rgba(226,232,240,0.4)" strokeDasharray="6 6" />
        {[...models.entries()].map(([key, model]) => {
          const isActive = key === active;
          const color = MODEL_COLORS[key] ?? "#94a3b8";
          const path = model.points.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.x).toFixed(1)},${y(p.y).toFixed(1)}`).join("");
          return (
            <g key={key} opacity={isActive ? 1 : 0.18}>
              <motion.path d={path} fill="none" stroke={color} strokeWidth={isActive ? 3.5 : 2} initial={{ pathLength: 0 }} animate={{ pathLength: 1 }} transition={{ duration: 1.2 }} />
              {isActive && model.points.map((p, i) => <circle key={i} cx={x(p.x)} cy={y(p.y)} r={4.5} fill={color} stroke="#05070d" strokeWidth={1.5} />)}
            </g>
          );
        })}
      </svg>
    </div>
  );
}
