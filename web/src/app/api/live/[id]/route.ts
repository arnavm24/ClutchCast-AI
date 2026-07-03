import { NextResponse } from "next/server";
import { promises as fs } from "fs";
import path from "path";
import { currentFeatureRecord, LiveEvent } from "@/lib/features";
import { ModelBundle, featureVector, predictHomeWinProbability } from "@/lib/model";
import { NBA_FETCH_HEADERS, SCOREBOARD_URL, currentSeason, playByPlayUrl } from "@/lib/nba";

export const revalidate = 0;

let cachedBundle: ModelBundle | null = null;

async function loadBundle(): Promise<ModelBundle> {
  if (cachedBundle) return cachedBundle;
  const file = await fs.readFile(path.join(process.cwd(), "public", "data", "model.json"), "utf-8");
  cachedBundle = JSON.parse(file) as ModelBundle;
  return cachedBundle;
}

interface RawAction {
  period: number;
  clock: string;
  teamTricode?: string;
  description?: string;
  actionType?: string;
  scoreHome?: string;
  scoreAway?: string;
}

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const gameId = id.padStart(10, "0");
  try {
    const [pbpResponse, sbResponse] = await Promise.all([
      fetch(playByPlayUrl(gameId), { cache: "no-store", headers: NBA_FETCH_HEADERS }),
      fetch(SCOREBOARD_URL, { cache: "no-store", headers: NBA_FETCH_HEADERS }),
    ]);

    if (!sbResponse.ok) {
      return NextResponse.json({ error: "NBA scoreboard unavailable", source: "unavailable" });
    }
    const scoreboard = await sbResponse.json();
    const game = (scoreboard?.scoreboard?.games ?? []).find(
      (g: { gameId: string }) => String(g.gameId) === gameId,
    );
    if (!game) {
      return NextResponse.json({ error: "Game not on today's scoreboard", source: "unavailable" });
    }

    const home = String(game.homeTeam?.teamTricode ?? "");
    const away = String(game.awayTeam?.teamTricode ?? "");
    const base = {
      gameId,
      home,
      away,
      homeScore: Number(game.homeTeam?.score ?? 0),
      awayScore: Number(game.awayTeam?.score ?? 0),
      period: Number(game.period ?? 0),
      clock: String(game.gameClock ?? ""),
      status: String(game.gameStatusText ?? ""),
      gameStatus: Number(game.gameStatus ?? 1),
    };

    if (!pbpResponse.ok) {
      // Scoreboard-only fallback: simple leverage baseline, clearly labeled.
      const margin = base.homeScore - base.awayScore;
      const leverage = base.period >= 4 ? 0.04 : base.period >= 2 ? 0.03 : 0.025;
      const prob = base.gameStatus === 3 ? (margin > 0 ? 1 : margin < 0 ? 0 : 0.5) : Math.max(0.02, Math.min(0.98, 0.5 + margin * leverage));
      return NextResponse.json({ ...base, homeWinProb: prob, source: "scoreboard_fallback", lastPlay: "" });
    }

    const payload = await pbpResponse.json();
    const actions: RawAction[] = payload?.game?.actions ?? [];
    if (actions.length === 0) {
      return NextResponse.json({ ...base, homeWinProb: 0.5, source: "pregame", lastPlay: "" });
    }

    const events: LiveEvent[] = actions.map((action) => ({
      period: Number(action.period ?? 1),
      clock: String(action.clock ?? "PT12M00.00S"),
      teamTricode: String(action.teamTricode ?? ""),
      description: String(action.description ?? ""),
      actionType: String(action.actionType ?? ""),
      scoreHome: action.scoreHome ?? null,
      scoreAway: action.scoreAway ?? null,
    }));

    const bundle = await loadBundle();
    const record = currentFeatureRecord(events, { homeTricode: home, awayTricode: away, season: currentSeason() }, bundle.teamStrength);
    let prob = predictHomeWinProbability(bundle, featureVector(bundle, record));
    if (base.gameStatus === 3) {
      prob = base.homeScore > base.awayScore ? 1 : base.homeScore < base.awayScore ? 0 : 0.5;
    }

    const last = events[events.length - 1];
    return NextResponse.json({
      ...base,
      homeWinProb: prob,
      source: "champion_model_live",
      model: bundle.championName,
      lastPlay: last.description,
      events: events.length,
    });
  } catch (error) {
    return NextResponse.json({ error: String(error), source: "error" });
  }
}
