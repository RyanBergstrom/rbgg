export const BOT_DISPLAY_NAMES = ['Stacy', 'Trey', 'Bella', 'Stitch'];

export interface GameHistorySession {
  id: number;
  game_id?: string;
  started_at?: string;
  finished_at?: string | null;
  winner?: string | null;
  final_scores_json?: string | Record<string, number> | null;
  result_summary_json?: string | Record<string, unknown> | null;
}

export interface OpponentRecord {
  name: string;
  games: number;
  wins: number;
  losses: number;
  draws: number;
}

export interface CompletedGameRecord {
  id: number;
  date: string | null;
  result: 'Win' | 'Loss' | 'Draw';
  opponents: string[];
  score: number | null;
}

export interface GameHistorySummary {
  gamesPlayed: number;
  wins: number;
  losses: number;
  draws: number;
  winRate: number;
  opponents: OpponentRecord[];
  history: CompletedGameRecord[];
}

function parseObject(value: GameHistorySession['result_summary_json'] | GameHistorySession['final_scores_json']) {
  if (!value) return {};
  if (typeof value === 'object') return value;
  try {
    const parsed = JSON.parse(value);
    return parsed && typeof parsed === 'object' ? parsed : {};
  } catch {
    return {};
  }
}

export function buildGameHistory(sessions: GameHistorySession[], gameId?: string): GameHistorySummary {
  const completed = sessions.filter((session) => Boolean(session.finished_at)
    && (!gameId || !session.game_id || session.game_id === gameId));
  const opponentRecords = new Map<string, OpponentRecord>();
  const history: CompletedGameRecord[] = [];
  let wins = 0;
  let losses = 0;
  let draws = 0;

  for (const session of completed) {
    const summary = parseObject(session.result_summary_json) as {
      winner?: string | null;
      players?: Array<{ player_id?: string; name?: string }>;
      scores?: Record<string, number> | null;
    };
    const players = Array.isArray(summary.players) ? summary.players : [];
    const humanId = players[0]?.player_id || 'player_1';
    const winner = session.winner || summary.winner || null;
    const result: CompletedGameRecord['result'] = winner === humanId
      ? 'Win'
      : winner
        ? 'Loss'
        : 'Draw';

    if (result === 'Win') wins += 1;
    else if (result === 'Loss') losses += 1;
    else draws += 1;

    const opponents = players
      .filter((player) => player.player_id !== humanId)
      .map((player, index) => BOT_DISPLAY_NAMES[index] || player.name || `Bot ${index + 1}`);

    for (const name of opponents) {
      const record = opponentRecords.get(name) || { name, games: 0, wins: 0, losses: 0, draws: 0 };
      record.games += 1;
      if (result === 'Win') record.wins += 1;
      else if (result === 'Loss') record.losses += 1;
      else record.draws += 1;
      opponentRecords.set(name, record);
    }

    const scores = parseObject(session.final_scores_json) as Record<string, number>;
    const summaryScores = summary.scores && typeof summary.scores === 'object' ? summary.scores : {};
    const humanScore = scores[humanId] ?? summaryScores[humanId];
    history.push({
      id: session.id,
      date: session.finished_at || session.started_at || null,
      result,
      opponents,
      score: typeof humanScore === 'number' ? humanScore : null,
    });
  }

  const gamesPlayed = completed.length;
  return {
    gamesPlayed,
    wins,
    losses,
    draws,
    winRate: gamesPlayed ? Math.round((wins / gamesPlayed) * 100) : 0,
    opponents: [...opponentRecords.values()].sort((a, b) => BOT_DISPLAY_NAMES.indexOf(a.name) - BOT_DISPLAY_NAMES.indexOf(b.name)),
    history,
  };
}
