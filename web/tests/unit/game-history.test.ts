import { describe, expect, it } from 'vitest';
import { buildGameHistory } from '../../src/lib/game-history';

describe('buildGameHistory', () => {
  it('counts only completed games and groups results under stable bot names', () => {
    const stats = buildGameHistory([
      {
        id: 1,
        game_id: 'lost_cities',
        finished_at: '2026-10-01T12:00:00Z',
        winner: 'player_1',
        result_summary_json: JSON.stringify({
          players: [
            { player_id: 'player_1', name: 'Alex' },
            { player_id: 'player_2', name: 'Old Bot 1' },
          ],
        }),
      },
      {
        id: 2,
        game_id: 'lost_cities',
        finished_at: '2026-10-02T12:00:00Z',
        winner: 'player_2',
        final_scores_json: JSON.stringify({ player_1: 48, player_2: 72 }),
        result_summary_json: JSON.stringify({
          players: [
            { player_id: 'player_1', name: 'Alex' },
            { player_id: 'player_2', name: 'Stacy' },
          ],
        }),
      },
      {
        id: 3,
        game_id: 'lost_cities',
        finished_at: null,
        winner: null,
        result_summary_json: null,
      },
      {
        id: 4,
        game_id: 'bus',
        finished_at: '2026-10-03T12:00:00Z',
        winner: 'player_1',
        result_summary_json: JSON.stringify({ players: [{ player_id: 'player_1', name: 'Alex' }] }),
      },
    ], 'lost_cities');

    expect(stats).toMatchObject({ gamesPlayed: 2, wins: 1, losses: 1, draws: 0, winRate: 50 });
    expect(stats.opponents).toEqual([{ name: 'Stacy', games: 2, wins: 1, losses: 1, draws: 0 }]);
    expect(stats.history).toHaveLength(2);
    expect(stats.history[1]).toMatchObject({ result: 'Loss', opponents: ['Stacy'], score: 48 });
  });

  it('returns empty lifetime stats when there are no completed games', () => {
    expect(buildGameHistory([{ id: 1, finished_at: null }])).toMatchObject({
      gamesPlayed: 0,
      wins: 0,
      losses: 0,
      draws: 0,
      winRate: 0,
      opponents: [],
      history: [],
    });
  });
});
