import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, waitFor } from '@testing-library/svelte';

const mockGetGame = vi.fn();
const mockGetSessions = vi.fn();
const mockGetLegalMoves = vi.fn();
const mockGetAiMove = vi.fn();
const mockMakeMove = vi.fn();
const mockStartSession = vi.fn();
const mockConfirmTurn = vi.fn();
const mockUndoMove = vi.fn();
const mockDebugLoadState = vi.fn();
const mockLoadSession = vi.fn();

vi.mock('../../src/lib/api.ts', () => ({
  getGame: (...args) => mockGetGame(...args),
  getSessions: (...args) => mockGetSessions(...args),
  getLegalMoves: (...args) => mockGetLegalMoves(...args),
  getAiMove: (...args) => mockGetAiMove(...args),
  makeMove: (...args) => mockMakeMove(...args),
  startSession: (...args) => mockStartSession(...args),
  confirmTurn: (...args) => mockConfirmTurn(...args),
  undoMove: (...args) => mockUndoMove(...args),
  debugLoadState: (...args) => mockDebugLoadState(...args),
  loadSession: (...args) => mockLoadSession(...args),
}));

import PlayPage from '../../src/routes/games/[gameId]/play/+page.svelte';

const emptyScreenState = {
  current_player: 'player_1',
  legal_moves: [],
  winner: null,
  phase: { phase_name: 'play_a_card', confirm_required: false },
};

describe('PlayPage session persistence', () => {
  beforeEach(() => {
    vi.clearAllMocks();
    window.localStorage.clear();
    window.history.pushState({}, '', '/games/checkers/play');
    mockGetSessions.mockResolvedValue([]);
    mockGetLegalMoves.mockResolvedValue({
      legal_moves: [],
      screen_state: emptyScreenState,
    });
  });

  afterEach(() => {
    window.history.pushState({}, '', '/');
  });

  it('keeps the sessionId in the URL when loading an existing session', async () => {
    window.history.pushState({}, '', '/games/checkers/play?sessionId=42');
    mockLoadSession.mockResolvedValue({
      state: { player_turn: 'player_1', winner: null },
      screen_state: emptyScreenState,
    });

    render(PlayPage, {
      props: { data: { gameId: 'checkers', debug: false } },
    });

    await waitFor(() => {
      expect(mockLoadSession).toHaveBeenCalledWith(42);
      expect(window.location.search).toBe('?sessionId=42');
    });

    expect(mockStartSession).not.toHaveBeenCalled();
  });

  it('writes a new sessionId into the URL after auto-starting a game', async () => {
    mockGetGame
      .mockResolvedValueOnce({ state: null })
      .mockResolvedValueOnce({
        state: { player_turn: 'player_1', winner: null },
        screen_state: emptyScreenState,
      });
    mockStartSession.mockResolvedValue({
      session_id: 77,
      screen_state: emptyScreenState,
    });

    render(PlayPage, {
      props: { data: { gameId: 'checkers', debug: false } },
    });

    await waitFor(() => {
      expect(mockStartSession).toHaveBeenCalled();
      expect(window.location.search).toBe('?sessionId=77');
    });

    expect(mockGetGame).toHaveBeenLastCalledWith('checkers', 77);
  });
});
