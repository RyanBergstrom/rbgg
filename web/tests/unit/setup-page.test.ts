import { describe, it, expect, vi, beforeEach } from 'vitest';
import { render, screen, waitFor } from '@testing-library/svelte';

const mockGetGame = vi.fn();
const mockGetSessions = vi.fn();
const mockStartSession = vi.fn();
const mockDeleteSession = vi.fn();

vi.mock('../../src/lib/api.ts', () => ({
  getGame: (...args) => mockGetGame(...args),
  getSessions: (...args) => mockGetSessions(...args),
  startSession: (...args) => mockStartSession(...args),
  deleteSession: (...args) => mockDeleteSession(...args),
}));

import SetupPage from '../../src/routes/games/[gameId]/setup/+page.svelte';

describe('SetupPage', () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it('test_continue_list_renders_active_sessions', async () => {
    mockGetGame.mockResolvedValue({
      id: 'checkers',
      name: 'Checkers',
    });

    mockGetSessions.mockResolvedValue([
      { id: 1, game_id: 'checkers', started_at: '2026-09-01T10:00:00Z', finished_at: null },
      { id: 2, game_id: 'checkers', started_at: '2026-09-02T14:30:00Z', finished_at: null },
      { id: 3, game_id: 'checkers', started_at: '2026-08-30T08:00:00Z', finished_at: '2026-08-31T12:00:00Z' },
    ]);

    render(SetupPage, {
      props: { data: { gameId: 'checkers' } },
    });

    await waitFor(() => {
      const continueList = screen.getByTestId('continue-list');
      const rows = continueList.querySelectorAll('tbody tr');
      expect(rows.length).toBe(2);
    });
  });

  it('test_player_name_defaults_to_ryan', async () => {
    mockGetGame.mockResolvedValue({
      id: 'checkers',
      name: 'Checkers',
    });

    mockGetSessions.mockResolvedValue([]);

    render(SetupPage, {
      props: { data: { gameId: 'checkers' } },
    });

    await waitFor(() => {
      const nameInput = screen.getByLabelText('Player Name');
      expect(nameInput.value).toBe('Ryan');
    });
  });

  it('test_min_max_players_hidden_when_not_in_config', async () => {
    mockGetGame.mockResolvedValue({
      id: 'checkers',
      name: 'Checkers',
    });

    mockGetSessions.mockResolvedValue([]);

    render(SetupPage, {
      props: { data: { gameId: 'checkers' } },
    });

    await waitFor(() => {
      expect(screen.queryByLabelText('Min Players')).toBeNull();
      expect(screen.queryByLabelText('Max Players')).toBeNull();
    });
  });

  it('test_min_max_players_shown_when_in_config', async () => {
    mockGetGame.mockResolvedValue({
      id: 'chess',
      name: 'Chess',
      min_players: 2,
      max_players: 4,
    });

    mockGetSessions.mockResolvedValue([]);

    render(SetupPage, {
      props: { data: { gameId: 'chess' } },
    });

    await waitFor(() => {
      expect(screen.getByLabelText('Min Players')).toBeTruthy();
      expect(screen.getByLabelText('Max Players')).toBeTruthy();
    });
  });

  it('test_color_picker_not_rendered', async () => {
    mockGetGame.mockResolvedValue({
      id: 'checkers',
      name: 'Checkers',
    });

    mockGetSessions.mockResolvedValue([]);

    render(SetupPage, {
      props: { data: { gameId: 'checkers' } },
    });

    await waitFor(() => {
      expect(screen.queryByLabelText('Color')).toBeNull();
    });
  });

  it('test_start_calls_api_without_color', async () => {
    mockGetGame.mockResolvedValue({
      id: 'game-1',
      name: 'Chess',
    });

    mockGetSessions.mockResolvedValue([]);

    mockStartSession.mockResolvedValue({
      game_id: 'game-1',
      session_id: 1,
      player_turn: 'player_1',
    });

    render(SetupPage, {
      props: { data: { gameId: 'game-1' } },
    });

    await waitFor(() => {
      const startButton = screen.getByRole('button', { name: /Start Game/i });
      startButton.click();
    });

    await waitFor(() => {
      expect(mockStartSession).toHaveBeenCalledWith('game-1', 'Ryan', expect.anything(), expect.anything());
    });
  });
});
