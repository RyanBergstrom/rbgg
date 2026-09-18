/**
 * API wrapper for the rbgg backend.
 * Provides typed fetch helpers for the Svelte frontend.
 */
const BASE_URL = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api/v1';

export async function getGames() {
  const res = await fetch(`${BASE_URL}/games/`);
  if (!res.ok) throw new Error('Failed to fetch games');
  return res.json();
}

export async function getGame(gameId) {
  const res = await fetch(`${BASE_URL}/games/${gameId}`);
  if (!res.ok) throw new Error(`Failed to fetch game ${gameId}`);
  return res.json();
}

export async function getSessions(gameId) {
  const res = await fetch(`${BASE_URL}/sessions/filter?game_id=${gameId}`);
  if (!res.ok) throw new Error(`Failed to fetch sessions for game ${gameId}`);
  return res.json();
}

export async function deleteSession(sessionId) {
  const res = await fetch(`${BASE_URL}/sessions/${sessionId}`, {
    method: 'DELETE',
  });
  if (!res.ok) throw new Error(`Failed to delete session ${sessionId}`);
  return res.json();
}

export async function startSession(gameId, playerName, minPlayers, maxPlayers, difficulty) {
  const res = await fetch(`${BASE_URL}/moves/start-session/${gameId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ playerName, minPlayers, maxPlayers, difficulty }),
  });
  if (!res.ok) throw new Error('Failed to start session');
  return res.json();
}

export async function getLegalMoves(gameId) {
  const res = await fetch(`${BASE_URL}/moves/legal-moves`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ game_id: gameId }),
  });
  if (!res.ok) throw new Error(`Failed to fetch legal moves for game ${gameId}`);
  return res.json();
}

export async function makeMove(gameId, move) {
  const res = await fetch(`${BASE_URL}/moves/${gameId}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(move),
  });
  if (!res.ok) throw new Error('Failed to make move');
  return res.json();
}

export async function getAiMove(gameId, sessionId) {
  const res = await fetch(`${BASE_URL}/moves/ai`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ gameId, sessionId }),
  });
  if (!res.ok) throw new Error('Failed to get AI move');
  return res.json();
}

export async function confirmTurn(gameId) {
  const res = await fetch(`${BASE_URL}/moves/confirm/${gameId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Failed to confirm turn');
  return res.json();
}

export async function undoMove(gameId) {
  const res = await fetch(`${BASE_URL}/moves/undo/${gameId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Failed to undo move');
  return res.json();
}

export async function debugLoadState(gameId, gameData, currentPlayerIndex, winner) {
  const res = await fetch(`${BASE_URL}/moves/debug-load/${gameId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_data: gameData,
      current_player_index: currentPlayerIndex,
      winner,
    }),
  });
  if (!res.ok) throw new Error(`Failed to load debug state for game ${gameId}`);
  return res.json();
}

export async function startNewGame(gameId) {
  const res = await fetch(`${BASE_URL}/sessions/${gameId}/start`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error('Failed to start new game');
  return res.json();
}

export async function loadSession(sessionId) {
  const res = await fetch(`${BASE_URL}/sessions/${sessionId}/load`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`Failed to load session ${sessionId}`);
  return res.json();
}
