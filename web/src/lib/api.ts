/**
 * API wrapper for the rbgg backend.
 * Provides typed fetch helpers for the Svelte frontend.
 */
const BASE_URL = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api/v1';

export const API_BASE = BASE_URL;

export class ApiError extends Error {
  status;
  code;

  constructor(message, status, code = 'API_ERROR') {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
  }
}

async function request(url, options = {}, timeoutMs = 30000) {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const response = await fetch(url, { ...options, signal: controller.signal });
    let payload = null;
    try {
      payload = await response.json();
    } catch {
      payload = null;
    }
    if (!response.ok) {
      const error = payload?.error || payload?.detail || {};
      const message = typeof error === 'string' ? error : error.message || `Request failed (${response.status})`;
      throw new ApiError(message, response.status, typeof error === 'object' ? error.code : 'API_ERROR');
    }
    return payload;
  } catch (error) {
    if (error.name === 'AbortError') {
      throw new ApiError('Request timed out. Please retry.', 408, 'REQUEST_TIMEOUT');
    }
    throw error;
  } finally {
    clearTimeout(timeout);
  }
}

export async function getGames() {
  const res = await fetch(`${BASE_URL}/games/`);
  if (!res.ok) throw new Error('Failed to fetch games');
  return res.json();
}

export async function getAssetReviewGames() {
    return request(`${BASE_URL}/asset-review/config-games`);
  }

export async function getAssetReviewCsv(gameId, csvName) {
  return request(`${BASE_URL}/asset-review/${encodeURIComponent(gameId)}/${encodeURIComponent(csvName)}`);
}

export async function validateAssetReviewRow(gameId, csvName, rowIndex, validated = true) {
  return request(`${BASE_URL}/asset-review/${encodeURIComponent(gameId)}/${encodeURIComponent(csvName)}/rows/${rowIndex}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ validated }),
  });
}

export async function updateAssetReviewRow(gameId, csvName, rowIndex, updates) {
  return request(`${BASE_URL}/asset-review/${encodeURIComponent(gameId)}/${encodeURIComponent(csvName)}/rows/${rowIndex}`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ updates }),
  });
}

export async function updateAssetReviewFields(gameId, csvName, add = [], remove = []) {
  return request(`${BASE_URL}/asset-review/${encodeURIComponent(gameId)}/${encodeURIComponent(csvName)}/fields`, {
    method: 'PATCH',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ add, remove }),
  });
}

export function getAssetReviewImageUrl(gameId, imagePath) {
  const safePath = imagePath.split(/[\\/]+/).map(encodeURIComponent).join('/');
  return `${BASE_URL}/asset-review/${encodeURIComponent(gameId)}/images/${safePath}`;
}

export async function getGame(gameId, sessionId = null) {
  const query = sessionId ? `?session_id=${sessionId}` : '';
  const res = await fetch(`${BASE_URL}/games/${gameId}${query}`);
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

export async function startSession(gameId, playerName, playerCount, difficulty, scenarioId = null) {
  const body = { playerName, playerCount, difficulty };
  if (scenarioId) {
    body.scenarioId = scenarioId;
  }
  const res = await fetch(`${BASE_URL}/moves/start-session/${gameId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error('Failed to start session');
  return res.json();
}

export async function getLegalMoves(sessionId) {
  return request(`${BASE_URL}/moves/legal-moves`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ session_id: sessionId }),
  });
}

export async function makeMove(sessionId, move) {
  return request(`${BASE_URL}/moves/${sessionId}/move`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(move),
  });
}

export async function getAiMove(sessionId, provider = 'mcts', aiDifficulty = 'hard') {
  const body: { sessionId: number; provider: string; aiDifficulty?: string } = { sessionId, provider };
  if (provider === 'ppo') body.aiDifficulty = aiDifficulty;
  return request(`${BASE_URL}/moves/ai`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  }, 120000);
}

export async function confirmTurn(sessionId) {
  return request(`${BASE_URL}/moves/confirm/${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function undoMove(sessionId) {
  return request(`${BASE_URL}/moves/undo/${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
}

export async function debugLoadState(sessionId, gameData, currentPlayerIndex, winner) {
  return request(`${BASE_URL}/moves/debug-load/${sessionId}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      game_data: gameData,
      current_player_index: currentPlayerIndex,
      winner,
    }),
  });
}

export async function loadSession(sessionId) {
  const res = await fetch(`${BASE_URL}/sessions/${sessionId}/load`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
  });
  if (!res.ok) throw new Error(`Failed to load session ${sessionId}`);
  return res.json();
}
