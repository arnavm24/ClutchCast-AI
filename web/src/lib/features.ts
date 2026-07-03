// Port of src/model_features.py + src/game_state.py for live inference.
// Given the play-by-play events of a game in progress, computes the 85-feature
// record for the CURRENT state. Windows only look backwards (no leakage).
//
// One deliberate improvement over training-time inference: live we know the
// home/away tricodes from the scoreboard, so event direction is exact instead
// of conservatively inferred from scoring.

export interface LiveEvent {
  period: number;
  clock: string; // "PT08M24.00S"
  teamTricode: string;
  description: string;
  actionType: string;
  scoreHome: number | string | null;
  scoreAway: number | string | null;
}

export interface GameMeta {
  homeTricode: string;
  awayTricode: string;
  season: string; // e.g. "2025-26"
}

interface StateRow {
  period: number;
  secondsRemaining: number;
  homeScore: number;
  awayScore: number;
  description: string;
  teamTricode: string;
  eventValue: number;
  eventByHome: boolean;
  eventByAway: boolean;
  homeScoreDelta: number;
  awayScoreDelta: number;
  isSteal: boolean;
  isTurnover: boolean;
  isRebound: boolean;
  isTimeout: boolean;
  isMadeShot: boolean;
  isFreeThrow: boolean;
}

export function parseClockSeconds(clock: string): number {
  const minutes = /(\d+)M/.exec(clock);
  const seconds = /(\d+(?:\.\d+)?)S/.exec(clock);
  return Math.floor((minutes ? parseInt(minutes[1], 10) : 0) * 60 + (seconds ? parseFloat(seconds[1]) : 0));
}

export function gameSecondsRemaining(period: number, clock: string): number {
  const inPeriod = parseClockSeconds(clock);
  if (period <= 4) return inPeriod + (4 - period) * 12 * 60;
  return inPeriod;
}

const SHOT_KEYWORDS = ["jump shot", "layup", "dunk", "hook shot", "tip shot", "floating", "driving", "pullup"];

function containsAny(text: string, keywords: string[]): boolean {
  return keywords.some((k) => text.includes(k));
}

// Mirror of model_features.classify_event_value — order matters.
export function classifyEventValue(description: string): number {
  const desc = description.toLowerCase();
  if (desc.includes("timeout") || desc.includes("sub:") || desc.includes("start") || desc.includes("end")) return 0;
  if (desc.includes("turnover")) return -4;
  if (desc.includes("steal")) return 4;
  if (desc.includes("block")) return 3;
  if (desc.includes("3pt") && !desc.includes("miss")) return 5;
  if (desc.includes("dunk") && !desc.includes("miss")) return 4;
  if (desc.includes("layup") && !desc.includes("miss")) return 3;
  if (desc.includes("jump shot") && !desc.includes("miss")) return 3;
  if (desc.includes("free throw") && !desc.includes("miss")) return 1;
  if (desc.includes("miss")) return -2;
  if (desc.includes("rebound") && desc.includes("off:")) return 2;
  if (desc.includes("rebound")) return 1;
  return 0;
}

function buildStateRows(events: LiveEvent[], meta: GameMeta): StateRow[] {
  const rows: StateRow[] = [];
  let lastHome = 0;
  let lastAway = 0;
  for (const event of events) {
    const home = event.scoreHome !== null && event.scoreHome !== "" ? Number(event.scoreHome) : NaN;
    const away = event.scoreAway !== null && event.scoreAway !== "" ? Number(event.scoreAway) : NaN;
    if (!Number.isNaN(home)) lastHome = home;
    if (!Number.isNaN(away)) lastAway = away;

    const previous = rows[rows.length - 1];
    const desc = (event.description || "").toLowerCase();
    const tricode = (event.teamTricode || "").trim();
    const isShot = containsAny(desc, SHOT_KEYWORDS);
    const isFreeThrow = desc.includes("free throw");
    const isMissed = desc.includes("miss");

    rows.push({
      period: event.period,
      secondsRemaining: gameSecondsRemaining(event.period, event.clock),
      homeScore: lastHome,
      awayScore: lastAway,
      description: desc,
      teamTricode: tricode,
      eventValue: classifyEventValue(event.description || ""),
      eventByHome: tricode !== "" && tricode === meta.homeTricode,
      eventByAway: tricode !== "" && tricode === meta.awayTricode,
      homeScoreDelta: Math.max(lastHome - (previous ? previous.homeScore : 0), 0),
      awayScoreDelta: Math.max(lastAway - (previous ? previous.awayScore : 0), 0),
      isSteal: desc.includes("steal"),
      isTurnover: desc.includes("turnover"),
      isRebound: desc.includes("rebound"),
      isTimeout: desc.includes("timeout"),
      isMadeShot: (isShot || isFreeThrow) && !isMissed,
      isFreeThrow,
    });
  }
  return rows;
}

// Mirror of model_features.estimate_possession_side_for_game.
function possessionSide(rows: StateRow[]): number {
  let side = 0;
  for (const row of rows) {
    const eventSide = row.eventByHome ? 1 : row.eventByAway ? -1 : 0;
    if (eventSide !== 0) {
      if (row.isSteal) side = eventSide;
      else if (row.isTurnover) side = -eventSide;
      else if (row.isRebound) side = eventSide;
      else if (row.isTimeout) side = eventSide;
      else if (row.isMadeShot && !row.isFreeThrow) side = -eventSide;
    }
  }
  return side;
}

function sumLast(values: number[], window: number): number {
  let total = 0;
  for (let i = Math.max(0, values.length - window); i < values.length; i++) total += values[i];
  return total;
}

function diffOver(values: number[], window: number): number {
  const n = values.length;
  if (n === 0) return 0;
  const currentValue = values[n - 1];
  const previousIndex = n - 1 - window;
  if (previousIndex < 0) return 0; // pandas .diff(window) is NaN -> filled with 0
  return currentValue - values[previousIndex];
}

export function currentFeatureRecord(
  events: LiveEvent[],
  meta: GameMeta,
  teamStrength: Record<string, number>,
): Record<string, number> {
  const rows = buildStateRows(events, meta);
  if (rows.length === 0) throw new Error("No events to featurize");
  const current = rows[rows.length - 1];
  const regulation = 48 * 60;

  const margin = current.homeScore - current.awayScore;
  const absMargin = Math.abs(margin);
  const timeRemainingFraction = Math.min(Math.max(current.secondsRemaining / regulation, 0), 1);
  const timeElapsedFraction = 1 - timeRemainingFraction;
  const desc = current.description;

  const isShot = containsAny(desc, SHOT_KEYWORDS) ? 1 : 0;
  const isFreeThrow = desc.includes("free throw") ? 1 : 0;
  const isMissed = desc.includes("miss") ? 1 : 0;
  const isMade = (isShot === 1 || isFreeThrow === 1) && isMissed === 0 ? 1 : 0;

  const eventByHome = current.eventByHome ? 1 : 0;
  const eventByAway = current.eventByAway ? 1 : 0;
  const signedEventValue = eventByHome ? current.eventValue : eventByAway ? -current.eventValue : 0;

  const margins = rows.map((r) => r.homeScore - r.awayScore);
  const totals = rows.map((r) => r.homeScore + r.awayScore);
  const eventValues = rows.map((r) => r.eventValue);
  const signedValues = rows.map((r) => (r.eventByHome ? r.eventValue : r.eventByAway ? -r.eventValue : 0));
  const homeDeltas = rows.map((r) => r.homeScoreDelta);
  const awayDeltas = rows.map((r) => r.awayScoreDelta);

  const side = possessionSide(rows);
  const strengthKey = (team: string) => `${team}|${meta.season}`;
  const homeStrength = teamStrength[strengthKey(meta.homeTricode)] ?? 0.5;
  const awayStrength = teamStrength[strengthKey(meta.awayTricode)] ?? 0.5;

  const teamAction = (flag: boolean, byHome: boolean, byAway: boolean) => ({
    home: flag && byHome ? 1 : 0,
    away: flag && byAway ? 1 : 0,
  });
  const byHome = current.eventByHome;
  const byAway = current.eventByAway;

  const homePtsLast10 = sumLast(homeDeltas, 10);
  const awayPtsLast10 = sumLast(awayDeltas, 10);

  const record: Record<string, number> = {
    period: current.period,
    seconds_remaining: current.secondsRemaining,
    home_score: current.homeScore,
    away_score: current.awayScore,
    score_margin_home: margin,
    abs_score_margin: absMargin,
    total_score: current.homeScore + current.awayScore,
    is_4th_quarter: current.period === 4 ? 1 : 0,
    is_clutch_time: current.period >= 4 && current.secondsRemaining <= 300 && absMargin <= 5 ? 1 : 0,

    time_remaining_fraction: timeRemainingFraction,
    time_elapsed_fraction: timeElapsedFraction,
    period_1: current.period === 1 ? 1 : 0,
    period_2: current.period === 2 ? 1 : 0,
    period_3: current.period === 3 ? 1 : 0,
    period_4: current.period === 4 ? 1 : 0,
    is_second_half: current.period >= 3 && current.period <= 4 ? 1 : 0,
    is_overtime: current.period > 4 ? 1 : 0,
    overtime_period_number: Math.max(current.period - 4, 0),
    is_final_5_minutes: current.secondsRemaining <= 300 ? 1 : 0,
    is_final_2_minutes: current.secondsRemaining <= 120 ? 1 : 0,
    is_final_1_minute: current.secondsRemaining <= 60 ? 1 : 0,

    home_lead: margin > 0 ? 1 : 0,
    away_lead: margin < 0 ? 1 : 0,
    tied_game: margin === 0 ? 1 : 0,
    one_possession_game: absMargin <= 3 ? 1 : 0,
    two_possession_game: absMargin <= 6 ? 1 : 0,
    three_possession_game: absMargin <= 9 ? 1 : 0,
    blowout_margin: absMargin >= 20 ? 1 : 0,
    margin_squared: margin * margin,
    score_margin_time_weighted: margin * timeElapsedFraction,
    abs_margin_time_weighted: absMargin * timeElapsedFraction,

    is_shot: isShot,
    is_three_pointer: desc.includes("3pt") ? 1 : 0,
    is_free_throw: isFreeThrow,
    is_missed_shot: isMissed,
    is_made_shot: isMade,
    is_turnover: desc.includes("turnover") ? 1 : 0,
    is_rebound: desc.includes("rebound") ? 1 : 0,
    is_offensive_rebound: desc.includes("rebound (off:") ? 1 : 0,
    is_steal: desc.includes("steal") ? 1 : 0,
    is_block: desc.includes("block") ? 1 : 0,
    is_foul: desc.includes("foul") || desc.includes("p.foul") || desc.includes("s.foul") ? 1 : 0,
    is_timeout: desc.includes("timeout") ? 1 : 0,
    is_substitution: desc.includes("sub:") ? 1 : 0,

    event_value: current.eventValue,
    home_score_delta: current.homeScoreDelta,
    away_score_delta: current.awayScoreDelta,
    event_by_home: eventByHome,
    event_by_away: eventByAway,
    signed_event_value_home_perspective: signedEventValue,

    home_turnover: teamAction(desc.includes("turnover"), byHome, byAway).home,
    away_turnover: teamAction(desc.includes("turnover"), byHome, byAway).away,
    home_rebound: teamAction(desc.includes("rebound"), byHome, byAway).home,
    away_rebound: teamAction(desc.includes("rebound"), byHome, byAway).away,
    home_offensive_rebound: teamAction(desc.includes("rebound (off:"), byHome, byAway).home,
    away_offensive_rebound: teamAction(desc.includes("rebound (off:"), byHome, byAway).away,
    home_steal: teamAction(desc.includes("steal"), byHome, byAway).home,
    away_steal: teamAction(desc.includes("steal"), byHome, byAway).away,
    home_block: teamAction(desc.includes("block"), byHome, byAway).home,
    away_block: teamAction(desc.includes("block"), byHome, byAway).away,
    home_foul: teamAction(desc.includes("foul"), byHome, byAway).home,
    away_foul: teamAction(desc.includes("foul"), byHome, byAway).away,
    home_timeout: teamAction(desc.includes("timeout"), byHome, byAway).home,
    away_timeout: teamAction(desc.includes("timeout"), byHome, byAway).away,

    estimated_possession_side: side,
    home_has_possession: side === 1 ? 1 : 0,
    away_has_possession: side === -1 ? 1 : 0,
    possession_value_home_perspective: side,

    home_team_strength: homeStrength,
    away_team_strength: awayStrength,
    team_strength_diff_home: homeStrength - awayStrength,
  };

  for (const window of [5, 10]) {
    record[`recent_margin_change_${window}`] = diffOver(margins, window);
    record[`recent_total_score_change_${window}`] = diffOver(totals, window);
    record[`recent_event_value_${window}`] = sumLast(eventValues, window);
    record[`recent_home_perspective_event_value_${window}`] = sumLast(signedValues, window);
    record[`home_points_last_${window}_events`] = sumLast(homeDeltas, window);
    record[`away_points_last_${window}_events`] = sumLast(awayDeltas, window);
  }
  record["home_run_last_10_events"] = homePtsLast10 - awayPtsLast10;
  record["away_run_last_10_events"] = awayPtsLast10 - homePtsLast10;

  return record;
}
