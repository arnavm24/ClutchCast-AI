"use client";

// Live game view: polls /api/live/{id} every 10s. The win probability is
// computed by the champion model running in TypeScript on the server route.

import { AnimatePresence, motion } from "framer-motion";
import Link from "next/link";
import { useEffect, useRef, useState } from "react";
import { currentFeatureRecord, LiveEvent } from "@/lib/features";
import { featureVector, ModelBundle, predictHomeWinProbability } from "@/lib/model";
import { currentSeason, playByPlayUrl, SCOREBOARD_URL, teamColor } from "@/lib/nba";
import TeamMark from "./TeamMark";

interface LivePayload {
  gameId: string;
  home: string;
  away: string;
  homeScore: number;
  awayScore: number;
  period: number;
  clock: string;
  status: string;
  gameStatus: number;
  homeWinProb: number;
  source: string;
  model?: string;
  lastPlay?: string;
  error?: string;
}

interface HistoryPoint {
  wp: number;
  label: string;
}

// Client-side inference: the champion model weights load once and every win
// probability on this page is computed in the visitor's browser.
async function computeLiveDirect(gameId: string, bundleRef: { current: ModelBundle | null }): Promise<LivePayload | null> {
  const [sbResponse, pbpResponse] = await Promise.all([
    fetch(SCOREBOARD_URL, { cache: "no-store" }),
    fetch(playByPlayUrl(gameId), { cache: "no-store" }).catch(() => null),
  ]);
  if (!sbResponse.ok) return null;
  const scoreboard = await sbResponse.json();
  const game = (scoreboard?.scoreboard?.games ?? []).find((g: { gameId: string }) => String(g.gameId) === gameId);
  if (!game) return { error: "Game not on today's scoreboard", source: "unavailable" } as LivePayload;

  const base = {
    gameId,
    home: String(game.homeTeam?.teamTricode ?? ""),
    away: String(game.awayTeam?.teamTricode ?? ""),
    homeScore: Number(game.homeTeam?.score ?? 0),
    awayScore: Number(game.awayTeam?.score ?? 0),
    period: Number(game.period ?? 0),
    clock: String(game.gameClock ?? ""),
    status: String(game.gameStatusText ?? ""),
    gameStatus: Number(game.gameStatus ?? 1),
  };

  if (!pbpResponse || !pbpResponse.ok) {
    const margin = base.homeScore - base.awayScore;
    const leverage = base.period >= 4 ? 0.04 : base.period >= 2 ? 0.03 : 0.025;
    const prob = base.gameStatus === 3 ? (margin > 0 ? 1 : margin < 0 ? 0 : 0.5) : Math.max(0.02, Math.min(0.98, 0.5 + margin * leverage));
    return { ...base, homeWinProb: prob, source: "scoreboard_fallback", lastPlay: "" };
  }

  const payload = await pbpResponse.json();
  const actions = payload?.game?.actions ?? [];
  if (actions.length === 0) return { ...base, homeWinProb: 0.5, source: "pregame", lastPlay: "" };

  if (!bundleRef.current) {
    bundleRef.current = (await fetch("/data/model.json").then((r) => r.json())) as ModelBundle;
  }
  const bundle = bundleRef.current;
  const events: LiveEvent[] = actions.map((a: Record<string, unknown>) => ({
    period: Number(a.period ?? 1),
    clock: String(a.clock ?? "PT12M00.00S"),
    teamTricode: String(a.teamTricode ?? ""),
    description: String(a.description ?? ""),
    actionType: String(a.actionType ?? ""),
    scoreHome: (a.scoreHome as string) ?? null,
    scoreAway: (a.scoreAway as string) ?? null,
  }));
  const record = currentFeatureRecord(events, { homeTricode: base.home, awayTricode: base.away, season: currentSeason() }, bundle.teamStrength);
  let prob = predictHomeWinProbability(bundle, featureVector(bundle, record));
  if (base.gameStatus === 3) prob = base.homeScore > base.awayScore ? 1 : base.homeScore < base.awayScore ? 0 : 0.5;
  return { ...base, homeWinProb: prob, source: "champion_model_live", model: `${bundle.championName} · in your browser`, lastPlay: String(events[events.length - 1].description) };
}

const SOURCE_BADGES: Record<string, { label: string; className: string }> = {
  champion_model_live: { label: "Full champion model · live play-by-play", className: "border-emerald-400/40 bg-emerald-500/10 text-emerald-300" },
  scoreboard_fallback: { label: "Scoreboard fallback · simple baseline", className: "border-amber-400/40 bg-amber-500/10 text-amber-300" },
  pregame: { label: "Pregame · waiting for tip-off", className: "border-sky-400/40 bg-sky-500/10 text-sky-300" },
  unavailable: { label: "Live data unavailable", className: "border-rose-400/40 bg-rose-500/10 text-rose-300" },
  error: { label: "Live data error", className: "border-rose-400/40 bg-rose-500/10 text-rose-300" },
};

function formatClock(clock: string) {
  return clock.replace("PT", "").replace("M", ":").replace(/\.\d+S/, "").replace("S", "");
}

export default function LiveGame({ gameId }: { gameId: string }) {
  const [data, setData] = useState<LivePayload | null>(null);
  const historyRef = useRef<HistoryPoint[]>([]);
  const [, force] = useState(0);

  const bundleRef = useRef<ModelBundle | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      try {
        let payload: LivePayload | null = null;
        try {
          payload = await computeLiveDirect(gameId.padStart(10, "0"), bundleRef);
        } catch {
          payload = null;
        }
        if (payload === null) {
          const response = await fetch(`/api/live/${gameId}`);
          payload = (await response.json()) as LivePayload;
        }
        if (cancelled) return;
        setData(payload);
        if (payload.homeWinProb != null && !payload.error) {
          const history = historyRef.current;
          const wp = payload.homeWinProb * 100;
          const label = `Q${payload.period} ${formatClock(payload.clock)}`;
          if (history.length === 0 || Math.abs(history[history.length - 1].wp - wp) > 0.01 || history[history.length - 1].label !== label) {
            history.push({ wp, label });
            force((n) => n + 1);
          }
        }
      } catch {
        if (!cancelled) setData((prev) => prev ?? ({ error: "network" } as LivePayload));
      }
    };
    load();
    const interval = setInterval(load, 10_000);
    return () => {
      cancelled = true;
      clearInterval(interval);
    };
  }, [gameId]);

  if (!data) {
    return <div className="panel mt-12 animate-pulse px-6 py-10 text-sm text-muted">Connecting to the game…</div>;
  }

  if (data.error && !data.home) {
    return (
      <div className="mt-12">
        <div className="panel px-6 py-10 text-center">
          <div className="text-lg font-black">This game isn&apos;t live right now</div>
          <p className="mt-2 text-sm text-muted">{data.error === "network" ? "Couldn't reach the live feed." : data.error}</p>
          <Link href="/" className="mt-5 inline-block rounded-full border border-line px-5 py-2 text-sm font-bold hover:bg-white/5">
            ← Back to games
          </Link>
        </div>
      </div>
    );
  }

  const homeWp = data.homeWinProb * 100;
  const homeColor = teamColor(data.home);
  const awayColor = teamColor(data.away);
  const badge = SOURCE_BADGES[data.source] ?? SOURCE_BADGES.unavailable;
  const history = historyRef.current;
  const live = data.gameStatus === 2;

  return (
    <div className="pt-8">
      <div className="mb-5 flex items-center justify-between">
        <Link href="/" className="text-sm font-bold text-muted hover:text-foreground">← All games</Link>
        <span className={`rounded-full border px-3 py-1.5 text-[11px] font-black uppercase tracking-widest ${badge.className}`}>{badge.label}</span>
      </div>

      <div className="panel relative overflow-hidden px-6 py-8 sm:px-10">
        <div className="mb-6 flex items-center justify-center gap-2 text-xs font-black uppercase tracking-widest">
          {live && <span className="live-dot h-2 w-2 rounded-full bg-red-500" />}
          <span className={live ? "text-red-400" : "text-muted"}>{live ? `Live · Q${data.period} ${formatClock(data.clock)}` : data.status}</span>
        </div>
        <div className="flex items-center justify-between gap-6">
          {[{ code: data.away, score: data.awayScore, color: awayColor }, { code: data.home, score: data.homeScore, color: homeColor }].map((team, index) => (
            <div key={team.code} className={`flex items-center gap-4 ${index === 1 ? "flex-row-reverse text-right" : ""}`}>
              <TeamMark tricode={team.code} size={60} />
              <div>
                <div className="text-[11px] font-bold uppercase tracking-[0.2em] text-muted">{team.code}</div>
                <AnimatePresence mode="popLayout">
                  <motion.div key={team.score} initial={{ y: -14, opacity: 0 }} animate={{ y: 0, opacity: 1 }} className="score-num text-6xl font-black leading-none">
                    {team.score}
                  </motion.div>
                </AnimatePresence>
              </div>
            </div>
          ))}
        </div>

        <div className="mt-8">
          <div className="mb-2 flex justify-between text-xs font-black tabular-nums">
            <span style={{ color: awayColor }}>{data.away} {(100 - homeWp).toFixed(1)}%</span>
            <span className="text-muted">win probability{data.model ? ` · ${data.model}` : ""}</span>
            <span style={{ color: homeColor }}>{data.home} {homeWp.toFixed(1)}%</span>
          </div>
          <div className="flex h-4 overflow-hidden rounded-full border border-line bg-black/40">
            <motion.div animate={{ width: `${100 - homeWp}%` }} transition={{ duration: 0.8, ease: "easeOut" }} style={{ background: awayColor }} />
            <motion.div animate={{ width: `${homeWp}%` }} transition={{ duration: 0.8, ease: "easeOut" }} style={{ background: homeColor }} />
          </div>
        </div>

        {data.lastPlay && (
          <AnimatePresence mode="wait">
            <motion.p key={data.lastPlay} initial={{ opacity: 0, y: 8 }} animate={{ opacity: 1, y: 0 }} exit={{ opacity: 0 }} className="mt-5 text-center text-sm text-muted">
              {data.lastPlay}
            </motion.p>
          </AnimatePresence>
        )}
      </div>

      {history.length > 1 && (
        <div className="panel mt-6 px-6 py-5">
          <div className="eyebrow mb-3">Win probability this session</div>
          <svg viewBox="0 0 600 120" className="w-full">
            <line x1="0" x2="600" y1="60" y2="60" stroke="rgba(148,163,184,0.2)" strokeDasharray="4 6" />
            <motion.polyline
              fill="none"
              stroke={homeColor}
              strokeWidth="3"
              strokeLinejoin="round"
              points={history.map((p, i) => `${(i / Math.max(history.length - 1, 1)) * 590 + 5},${115 - (p.wp / 100) * 110}`).join(" ")}
              initial={{ pathLength: 0 }}
              animate={{ pathLength: 1 }}
              transition={{ duration: 0.6 }}
            />
          </svg>
          <div className="mt-1 flex justify-between text-[10px] font-bold text-muted">
            <span>{history[0].label}</span>
            <span>{history[history.length - 1].label}</span>
          </div>
        </div>
      )}

      <p className="mt-6 text-center text-xs text-muted">Updates every 10 seconds while the game is live.</p>
    </div>
  );
}
