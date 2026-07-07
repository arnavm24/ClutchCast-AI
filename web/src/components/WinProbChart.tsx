"use client";

// The centerpiece: animated, scrubbable win-probability timeline.
// Custom SVG — the line draws itself in, hovering scrubs a moment card.

import { motion } from "framer-motion";
import { useCallback, useMemo, useRef, useState } from "react";
import type { TimelinePoint } from "@/lib/data";
import { teamColor } from "@/lib/nba";

const W = 900;
const H = 330;
const PAD = { top: 18, right: 16, bottom: 30, left: 42 };

function periodLabel(per: number) {
  return per <= 4 ? `Q${per}` : per === 5 ? "OT" : `${per - 4}OT`;
}

export default function WinProbChart({
  timeline,
  home,
  away,
}: {
  timeline: TimelinePoint[];
  home: string;
  away: string;
}) {
  const [hoverIndex, setHoverIndex] = useState<number | null>(null);
  const svgRef = useRef<SVGSVGElement>(null);

  const maxT = Math.max(48, timeline[timeline.length - 1]?.t ?? 48);
  const x = useCallback((t: number) => PAD.left + ((W - PAD.left - PAD.right) * t) / maxT, [maxT]);
  const y = useCallback((wp: number) => PAD.top + ((H - PAD.top - PAD.bottom) * (100 - wp)) / 100, []);

  const homePath = useMemo(
    () => timeline.map((p, i) => `${i === 0 ? "M" : "L"}${x(p.t).toFixed(1)},${y(p.wp).toFixed(1)}`).join(""),
    [timeline, x, y],
  );

  const quarterMarks = useMemo(() => {
    const marks: { t: number; label: string }[] = [];
    for (const m of [12, 24, 36, 48]) if (maxT >= m - 0.5) marks.push({ t: m, label: m === 48 ? "Q4" : `Q${m / 12}` });
    let ot = 53;
    let n = 1;
    while (maxT > 48.5 && ot <= maxT + 0.5) {
      marks.push({ t: ot, label: n === 1 ? "OT" : `${n}OT` });
      ot += 5;
      n += 1;
    }
    return marks;
  }, [maxT]);

  const handleMove = (event: React.PointerEvent<SVGSVGElement>) => {
    const svg = svgRef.current;
    if (!svg) return;
    const rect = svg.getBoundingClientRect();
    const px = ((event.clientX - rect.left) / rect.width) * W;
    const t = ((px - PAD.left) / (W - PAD.left - PAD.right)) * maxT;
    let best = 0;
    let bestDist = Infinity;
    for (let i = 0; i < timeline.length; i++) {
      const d = Math.abs(timeline[i].t - t);
      if (d < bestDist) {
        bestDist = d;
        best = i;
      }
    }
    setHoverIndex(best);
  };

  const hovered = hoverIndex !== null ? timeline[hoverIndex] : null;
  const homeColor = teamColor(home, "#f43f5e");
  const awayColor = teamColor(away, "#38bdf8");
  const gradientId = `wp-fill-${home}-${away}`;

  return (
    <div className="relative">
      <svg
        ref={svgRef}
        viewBox={`0 0 ${W} ${H}`}
        className="w-full cursor-crosshair select-none"
        onPointerMove={handleMove}
        onPointerLeave={() => setHoverIndex(null)}
      >
        <defs>
          <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={homeColor} stopOpacity="0.28" />
            <stop offset="100%" stopColor={homeColor} stopOpacity="0" />
          </linearGradient>
        </defs>

        {[0, 25, 50, 75, 100].map((g) => (
          <g key={g}>
            <line x1={PAD.left} x2={W - PAD.right} y1={y(g)} y2={y(g)} stroke="rgba(148,163,184,0.12)" strokeDasharray={g === 50 ? "0" : "3 5"} strokeWidth={g === 50 ? 1.2 : 1} />
            <text x={PAD.left - 8} y={y(g) + 4} textAnchor="end" fontSize="11" fill="#64748b">
              {g}%
            </text>
          </g>
        ))}

        {quarterMarks.map((mark) => (
          <g key={mark.label}>
            <line x1={x(mark.t)} x2={x(mark.t)} y1={PAD.top} y2={H - PAD.bottom} stroke="rgba(226,232,240,0.14)" strokeDasharray="4 6" />
            <text x={x(mark.t) - 4} y={H - 10} textAnchor="end" fontSize="11" fill="#64748b">
              {mark.label}
            </text>
          </g>
        ))}

        <motion.path
          d={`${homePath}L${x(timeline[timeline.length - 1]?.t ?? 0)},${y(0)}L${x(0)},${y(0)}Z`}
          fill={`url(#${gradientId})`}
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={{ duration: 1.4, delay: 0.6 }}
        />
        <motion.path
          d={homePath}
          fill="none"
          stroke={homeColor}
          strokeWidth={3}
          strokeLinejoin="round"
          initial={{ pathLength: 0 }}
          animate={{ pathLength: 1 }}
          transition={{ duration: 1.8, ease: "easeInOut" }}
        />

        {hovered && (
          <g>
            <line x1={x(hovered.t)} x2={x(hovered.t)} y1={PAD.top} y2={H - PAD.bottom} stroke="#fde68a" strokeWidth={1.5} />
            <circle cx={x(hovered.t)} cy={y(hovered.wp)} r={6} fill={homeColor} stroke="white" strokeWidth={2} />
          </g>
        )}
      </svg>

      <div className="mt-3 flex items-center gap-5 text-xs font-semibold text-muted">
        <span className="flex items-center gap-2">
          <span className="h-2.5 w-2.5 rounded-full" style={{ background: homeColor }} /> {home} win probability
        </span>
        <span className="flex items-center gap-2">
          <span className="h-0.5 w-5 border-t border-dashed border-slate-400" /> 50/50
        </span>
        <span className="ml-auto hidden sm:block">hover to scrub the game</span>
      </div>

      <motion.div
        layout
        className="panel mt-4 flex flex-wrap items-center gap-x-6 gap-y-2 px-5 py-4"
        initial={false}
        animate={{ opacity: 1 }}
      >
        {hovered ? (
          <>
            <div className="text-sm font-black tabular-nums text-foreground">
              {periodLabel(hovered.per)} {hovered.clock}
            </div>
            <div className="text-sm font-bold tabular-nums">
              <span style={{ color: awayColor }}>{away} {hovered.as}</span>
              <span className="mx-2 text-muted">·</span>
              <span style={{ color: homeColor }}>{home} {hovered.hs}</span>
            </div>
            <div className="text-sm font-black tabular-nums" style={{ color: homeColor }}>
              {home} {hovered.wp.toFixed(1)}%
            </div>
            <div className="min-w-0 flex-1 truncate text-sm text-muted">{hovered.play || "No play description"}</div>
          </>
        ) : (
          <div className="text-sm text-muted">Hover the chart to relive any moment of the game.</div>
        )}
      </motion.div>
    </div>
  );
}
