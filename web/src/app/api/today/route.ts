import { NextResponse } from "next/server";
import { NBA_FETCH_HEADERS, SCOREBOARD_URL, TodayGame } from "@/lib/nba";

export const revalidate = 0;

const ESPN_SCOREBOARD_URL = "https://site.api.espn.com/apis/site/v2/sports/basketball/nba/scoreboard";

// ESPN abbreviations that differ from NBA tricodes.
const ESPN_TRICODES: Record<string, string> = {
  GS: "GSW", SA: "SAS", NY: "NYK", NO: "NOP", UTAH: "UTA", WSH: "WAS", PHO: "PHX",
};

async function fromNbaCdn(): Promise<TodayGame[] | null> {
  const response = await fetch(SCOREBOARD_URL, { cache: "no-store", headers: NBA_FETCH_HEADERS });
  if (!response.ok) return null;
  const payload = await response.json();
  const rawGames = payload?.scoreboard?.games ?? [];
  return rawGames.map((game: Record<string, unknown>) => {
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
}

// ESPN's scoreboard is open to datacenter IPs — used when the NBA CDN blocks us
// (e.g. from Vercel). ESPN game IDs can't drive the live model page, so they're
// prefixed and the UI renders them as display-only cards.
async function fromEspn(): Promise<TodayGame[] | null> {
  const response = await fetch(ESPN_SCOREBOARD_URL, { cache: "no-store" });
  if (!response.ok) return null;
  const payload = await response.json();
  const events = payload?.events ?? [];
  const games: TodayGame[] = [];
  for (const event of events) {
    const competition = event?.competitions?.[0];
    const competitors = competition?.competitors ?? [];
    const home = competitors.find((c: { homeAway: string }) => c.homeAway === "home");
    const away = competitors.find((c: { homeAway: string }) => c.homeAway === "away");
    if (!home || !away) continue;
    // ESPN serves the most recent game day during the offseason; only games
    // within a day of now actually belong under "Tonight".
    const tipoff = Date.parse(String(event?.date ?? ""));
    if (Number.isFinite(tipoff) && Math.abs(Date.now() - tipoff) > 24 * 60 * 60 * 1000) continue;
    const state = String(event?.status?.type?.state ?? "pre");
    const tricode = (raw: string) => ESPN_TRICODES[raw] ?? raw;
    games.push({
      gameId: `espn-${event.id}`,
      gameStatus: state === "in" ? 2 : state === "post" ? 3 : 1,
      gameStatusText: String(event?.status?.type?.shortDetail ?? ""),
      period: Number(event?.status?.period ?? 0),
      gameClock: String(event?.status?.displayClock ?? ""),
      gameTimeUTC: String(event?.date ?? ""),
      homeTeam: { teamId: Number(home?.team?.id ?? 0), teamTricode: tricode(String(home?.team?.abbreviation ?? "")), score: Number(home?.score ?? 0) },
      awayTeam: { teamId: Number(away?.team?.id ?? 0), teamTricode: tricode(String(away?.team?.abbreviation ?? "")), score: Number(away?.score ?? 0) },
    });
  }
  return games;
}

export async function GET() {
  try {
    const nba = await fromNbaCdn().catch(() => null);
    if (nba !== null) return NextResponse.json({ games: nba, source: "nba" });
    const espn = await fromEspn().catch(() => null);
    if (espn !== null) return NextResponse.json({ games: espn, source: "espn" });
    return NextResponse.json({ games: [], error: "All scoreboard sources unavailable" }, { status: 200 });
  } catch (error) {
    return NextResponse.json({ games: [], error: String(error) }, { status: 200 });
  }
}
