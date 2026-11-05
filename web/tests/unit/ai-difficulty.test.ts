import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { getAiMove } from '../../src/lib/api';

describe('getAiMove', () => {
  const fetchMock = vi.fn();

  beforeEach(() => {
    fetchMock.mockResolvedValue({
      ok: true,
      json: async () => ({ status: 'ok' }),
    });
    vi.stubGlobal('fetch', fetchMock);
  });

  afterEach(() => {
    vi.unstubAllGlobals();
    vi.clearAllMocks();
  });

  it('sends the selected difficulty with PPO requests', async () => {
    await getAiMove(42, 'ppo', 'medium');

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      sessionId: 42,
      provider: 'ppo',
      aiDifficulty: 'medium',
    });
  });

  it('does not send a model difficulty for MCTS requests', async () => {
    await getAiMove(42, 'mcts', 'easy');

    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      sessionId: 42,
      provider: 'mcts',
    });
  });
});
