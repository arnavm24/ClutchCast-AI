import { NextResponse } from "next/server";
import { NBA_FETCH_HEADERS, SCOREBOARD_URL, TodayGame } from "@/lib/nba";

export const revalidate = 0;

export async function GET() {
  try {
    const response = await fetch(SCOREBOARD_URL, { cache: "no-store", headers: NBA_FETCH_HEADERS });
    if (!response.ok) {
      return NextResponse.json({ games: [], error: `NBA scoreboard returned ${response.status}` }, { status: 200 });
    }
    const payload = await response.json();
    const rawGames = payload?.scoreboard?.games ?? [];
    const games: TodayGame[] = rawGames.map((game: Record<string, unknown>) => {
      const home = game.homeTeam as Record<string, unknown>;
      const away = game.awayTeam as Record<string, unknown>;
      return {
        gameId: String(game.gameId),
        gameStatus: Number(game.gameStatus),
        gameStatusText: String(game.gameStatusText ?? ""),
        period: Number(game.period ?? 0),
        gameClock: String(game.gameClock ?? ""),
        gameTimeUTC: String(game.gameTimeUTC ?? ""),
        homeTeam: { teamId: Number(home?.teamId), teamTricode: String(home?.teamTricode ?? ""), score: Number(home?.score ?? 0) },
        awayTeam: { teamId: Number(away?.teamId), teamTricode: String(away?.teamTricode ?? ""), score: Number(away?.score ?? 0) },
      };
    });
    return NextResponse.json({ games, date: payload?.scoreboard?.gameDate ?? null });
  } catch (error) {
    return NextResponse.json({ games: [], error: String(error) }, { status: 200 });
  }
}
