// Server-side loaders for the precomputed data exported by src/export_web_data.py.
import { promises as fs } from "fs";
import path from "path";

const DATA_DIR = path.join(process.cwd(), "public", "data");

export interface GameSummary {
  id: string;
  date: string | null;
  season: string;
  home: string;
  away: string;
  finalHome: number;
  finalAway: number;
  margin: number;
  overtime: boolean;
  leadChanges: number;
  drama: number | null;
  playoffRound: number;
  analyzed: boolean;
}

export interface FeaturedGame {
  key: string;
  label: string;
  game_id: string;
  tagline: string;
}

export interface TimelinePoint {
  t: number;
  wp: number;
  hs: number;
  as: number;
  per: number;
  clock: string;
  play: string;
}

export interface TurningPoint {
  per: number;
  clock: string;
  player: string;
  team: string;
  play: string;
  before: number;
  after: number;
  swing: number;
}

export interface PlayerImpact {
  name: string;
  team: string;
  personId: number | null;
  impact: number;
  net: number;
  events: number;
}

export interface GameDetail {
  id: string;
  date: string | null;
  home: string;
  away: string;
  finalHome: number;
  finalAway: number;
  overtime: boolean;
  nOvertimes: number;
  model: string;
  timeline: TimelinePoint[];
  turningPoints: TurningPoint[];
  players: PlayerImpact[];
  insights: Record<string, { value: string; details: string }>;
  recap: Record<string, string>;
}

async function readJson<T>(relative: string): Promise<T> {
  const file = await fs.readFile(path.join(DATA_DIR, relative), "utf-8");
  return JSON.parse(file) as T;
}

export async function loadGamesIndex(): Promise<{ featured: FeaturedGame[]; games: GameSummary[] }> {
  return readJson("games.json");
}

export async function loadGame(id: string): Promise<GameDetail | null> {
  try {
    return await readJson<GameDetail>(path.join("games", `${id}.json`));
  } catch {
    return null;
  }
}

export async function listAnalyzedGameIds(): Promise<string[]> {
  const files = await fs.readdir(path.join(DATA_DIR, "games"));
  return files.filter((f) => f.endsWith(".json")).map((f) => f.replace(".json", ""));
}

export interface ModelsData {
  champion: Record<string, string | number | null>;
  leaderboard: Record<string, string | number | null>[];
  calibrationCurves: Record<string, string | number>[];
  calibrationSummary: Record<string, string | number | boolean>[];
  brierByQuarter: Record<string, string | number>[];
  calibrationEffect: Record<string, string | number | boolean>[];
}

export async function loadModels(): Promise<ModelsData> {
  return readJson("models.json");
}
