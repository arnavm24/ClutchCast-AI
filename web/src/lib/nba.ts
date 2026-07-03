// NBA public CDN helpers (no key required). Proxied through our API routes so
// the browser never depends on NBA CORS behavior.

export const SCOREBOARD_URL = "https://cdn.nba.com/static/json/liveData/scoreboard/todaysScoreboard_00.json";

// The NBA CDN rejects bare datacenter requests; browser-like headers get through.
export const NBA_FETCH_HEADERS: Record<string, string> = {
  "User-Agent":
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0.0.0 Safari/537.36",
  Accept: "application/json,text/plain,*/*",
  Referer: "https://www.nba.com/",
  Origin: "https://www.nba.com",
};

export const playByPlayUrl = (gameId: string) =>
  `https://cdn.nba.com/static/json/liveData/playbyplay/playbyplay_${gameId}.json`;

export const teamLogoUrl = (teamId: number | string) =>
  `https://cdn.nba.com/logos/nba/${teamId}/primary/L/logo.svg`;

export const headshotUrl = (personId: number | string) =>
  `https://cdn.nba.com/headshots/nba/latest/1040x760/${personId}.png`;

export interface TodayGame {
  gameId: string;
  gameStatus: number; // 1 scheduled, 2 live, 3 final
  gameStatusText: string;
  period: number;
  gameClock: string;
  homeTeam: { teamId: number; teamTricode: string; score: number };
  awayTeam: { teamId: number; teamTricode: string; score: number };
  gameTimeUTC: string;
}

export function currentSeason(date = new Date()): string {
  // NBA season flips over in October.
  const year = date.getUTCFullYear();
  const startYear = date.getUTCMonth() >= 9 ? year : year - 1;
  return `${startYear}-${String(startYear + 1).slice(-2)}`;
}

export const TEAM_IDS: Record<string, string> = {
  ATL: "1610612737", BOS: "1610612738", BKN: "1610612751", CHA: "1610612766",
  CHI: "1610612741", CLE: "1610612739", DAL: "1610612742", DEN: "1610612743",
  DET: "1610612765", GSW: "1610612744", HOU: "1610612745", IND: "1610612754",
  LAC: "1610612746", LAL: "1610612747", MEM: "1610612763", MIA: "1610612748",
  MIL: "1610612749", MIN: "1610612750", NOP: "1610612740", NYK: "1610612752",
  OKC: "1610612760", ORL: "1610612753", PHI: "1610612755", PHX: "1610612756",
  POR: "1610612757", SAC: "1610612758", SAS: "1610612759", TOR: "1610612761",
  UTA: "1610612762", WAS: "1610612764",
};

export const TEAM_COLORS: Record<string, string> = {
  ATL: "#E03A3E", BOS: "#007A33", BKN: "#9CA3AF", CHA: "#00788C",
  CHI: "#CE1141", CLE: "#860038", DAL: "#00538C", DEN: "#FEC524",
  DET: "#C8102E", GSW: "#FFC72C", HOU: "#CE1141", IND: "#FDBB30",
  LAC: "#C8102E", LAL: "#FDB927", MEM: "#5D76A9", MIA: "#98002E",
  MIL: "#00471B", MIN: "#78BE20", NOP: "#85714D", NYK: "#F58426",
  OKC: "#007AC1", ORL: "#0077C0", PHI: "#006BB6", PHX: "#E56020",
  POR: "#E03A3E", SAC: "#5A2D81", SAS: "#C4CED4", TOR: "#CE1141",
  UTA: "#F9A01B", WAS: "#E31837",
};

export const teamColor = (tricode: string, fallback = "#3B82F6") => TEAM_COLORS[tricode] ?? fallback;
export const logoFor = (tricode: string) => (TEAM_IDS[tricode] ? teamLogoUrl(TEAM_IDS[tricode]) : null);
