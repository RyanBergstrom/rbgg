<script>
  import { onMount } from 'svelte';
  import { getGame, getSessions, startSession, deleteSession } from '$lib/api';

  const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api/v1';

  export let data;
  let gameId = data?.gameId || '{gameId}';
  let game = null;
  let sessions = [];
  let loading = true;
  let error = null;
  let newPlayerName = 'Ryan';
  let newMinPlayers = 2;
  let newMaxPlayers = 4;
  let selectedDifficulty = '';

  let activeSessions = [];

  $: coverImageUrl = game?.cover_image ? `${API_BASE}/img/${game.cover_image}` : null;

  onMount(async () => {
    try {
      game = await getGame(gameId);
      sessions = await getSessions(gameId);
      activeSessions = sessions.filter(s => !s.finished_at);
      if (game?.min_players) newMinPlayers = game.min_players;
      if (game?.max_players) newMaxPlayers = game.max_players;
      if (game?.difficulty) {
        selectedDifficulty = game.difficulty.default
          || Object.keys(game.difficulty).find(k => k !== 'default')
          || '';
      }
    } catch (e) {
      error = e.message;
    }
    loading = false;
  });

  function handleStartNewGame() {
    localStorage.removeItem(`rbgg:debug:${gameId}`);
    startSession(gameId, newPlayerName, parseInt(newMinPlayers), parseInt(newMaxPlayers), selectedDifficulty)
      .then(() => {
        window.location.href = `/games/${gameId}/play`;
      })
      .catch(e => {
        error = e.message;
      });
  }

  async function handleDeleteSession(sessionId) {
    if (!confirm('Are you sure you want to delete this session?')) return;
    try {
      await deleteSession(sessionId);
      activeSessions = activeSessions.filter(s => s.id !== sessionId);
    } catch (e) {
      error = e.message;
    }
  }

  function handleExit() {
    window.location.href = '/';
  }
</script>

<div class="setup-page">
  {#if error}
    <div class="error-state">
      <h2>Error</h2>
      <p>{error}</p>
      <button class="retry-btn" on:click={() => window.location.reload()}>Retry</button>
    </div>
  {:else}
    <div class="setup-container">
      {#if coverImageUrl}
        <div class="cover-hero">
          <img src={coverImageUrl} alt="{game?.name || gameId} cover" class="cover-image" />
          <div class="cover-overlay">
            <h1 class="cover-title">{game?.name || gameId}</h1>
          </div>
        </div>
      {:else}
        <div class="text-hero">
          <h1>{game?.name || gameId}</h1>
        </div>
      {/if}

      <div class="content-area">
        <div class="top-bar">
          <button class="exit-button" on:click={handleExit}>
            <span class="exit-icon">&larr;</span> Exit
          </button>
        </div>

        <div class="cards-row">
          {#if activeSessions.length > 0}
            <div class="card continue-card">
              <h2 class="card-title">Continue Game</h2>
              <table class="continue-table" data-testid="continue-list">
                <thead>
                  <tr>
                    <th>Game ID</th>
                    <th>Started</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {#each activeSessions as session}
                    <tr>
                      <td class="session-id">{session.game_id}</td>
                      <td>{new Date(session.started_at).toLocaleDateString()}</td>
                      <td class="actions-cell">
                        <button class="delete-btn" on:click={() => handleDeleteSession(session.id)}>
                          Delete
                        </button>
                        <a href={`/games/${gameId}/play?sessionId=${session.id}`} class="load-link">Load</a>
                      </td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}

          <div class="card new-game-card">
            <h2 class="card-title">New Game</h2>

            <div class="form-group">
              <label for="player-name">Player Name</label>
              <input
                id="player-name"
                type="text"
                bind:value={newPlayerName}
                placeholder="Enter your name"
                minlength="1"
                maxlength="20"
              />
            </div>

            {#if game?.min_players}
              <div class="form-group">
                <label for="min-players">Min Players</label>
                <input
                  id="min-players"
                  type="number"
                  bind:value={newMinPlayers}
                  min={game.min_players}
                  max="8"
                  placeholder={String(game.min_players)}
                />
              </div>
            {/if}

            {#if game?.max_players}
              <div class="form-group">
                <label for="max-players">Max Players</label>
                <input
                  id="max-players"
                  type="number"
                  bind:value={newMaxPlayers}
                  min={game.min_players || 2}
                  max="8"
                  placeholder={String(game.max_players)}
                />
              </div>
            {/if}

            {#if game?.difficulty}
              <div class="form-group">
                <label for="difficulty">Difficulty</label>
                <select id="difficulty" bind:value={selectedDifficulty}>
                  {#each Object.entries(game.difficulty).filter(([key]) => key !== 'default') as [key, value]}
                    <option value={key}>{key.charAt(0).toUpperCase() + key.slice(1)}</option>
                  {/each}
                </select>
              </div>
            {/if}

            <button class="start-button"
                    on:click={handleStartNewGame}
                    disabled={!newPlayerName.trim()}>
              Start Game
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .setup-page {
    min-height: 100vh;
    background: #1a1a2e;
    color: #eee;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }

  .error-state {
    max-width: 500px;
    margin: 4rem auto;
    padding: 2rem;
    background: #2a1a1a;
    border: 1px solid #c0392b;
    border-radius: 8px;
    text-align: center;
  }

  .error-state h2 {
    color: #e74c3c;
    margin-top: 0;
  }

  .retry-btn {
    padding: 0.5rem 1.5rem;
    background: #4a90e2;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    margin-top: 0.5rem;
  }

  .retry-btn:hover {
    background: #357abd;
  }

  .cover-hero {
    position: relative;
    width: 100%;
    height: 280px;
    overflow: hidden;
  }

  .cover-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .cover-overlay {
    position: absolute;
    inset: 0;
    background: linear-gradient(to top, rgba(26,26,46,0.95) 0%, rgba(26,26,46,0.4) 50%, transparent 100%);
    display: flex;
    align-items: flex-end;
    padding: 2rem 2.5rem;
  }

  .cover-title {
    margin: 0;
    font-size: 2.2rem;
    font-weight: 700;
    text-shadow: 0 2px 8px rgba(0,0,0,0.5);
  }

  .text-hero {
    padding: 2.5rem;
    text-align: center;
    background: linear-gradient(135deg, #16213e 0%, #0f3460 100%);
    border-bottom: 2px solid rgba(255,255,255,0.1);
  }

  .text-hero h1 {
    margin: 0;
    font-size: 2.2rem;
    font-weight: 700;
  }

  .content-area {
    max-width: 900px;
    margin: 0 auto;
    padding: 1.5rem 2rem 3rem;
  }

  .top-bar {
    display: flex;
    justify-content: flex-end;
    margin-bottom: 1.5rem;
  }

  .exit-button {
    display: inline-flex;
    align-items: center;
    gap: 0.4rem;
    padding: 0.5rem 1rem;
    background: transparent;
    color: #ccc;
    border: 1px solid #555;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
    transition: all 0.15s ease;
  }

  .exit-button:hover {
    background: rgba(220, 53, 69, 0.15);
    border-color: #dc3545;
    color: #dc3545;
  }

  .exit-icon {
    font-size: 1rem;
  }

  .cards-row {
    display: flex;
    flex-direction: column;
    gap: 1.5rem;
  }

  .card {
    background: #16213e;
    border: 1px solid rgba(255,255,255,0.08);
    border-radius: 10px;
    padding: 1.5rem;
  }

  .card-title {
    margin: 0 0 1rem;
    font-size: 1.1rem;
    font-weight: 600;
    color: #ddd;
    padding-bottom: 0.75rem;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }

  .continue-table {
    width: 100%;
    border-collapse: collapse;
  }

  .continue-table th {
    text-align: left;
    font-size: 0.75rem;
    font-weight: 600;
    color: #888;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid rgba(255,255,255,0.08);
  }

  .continue-table td {
    padding: 0.75rem;
    font-size: 0.9rem;
    border-bottom: 1px solid rgba(255,255,255,0.05);
    vertical-align: middle;
  }

  .continue-table tbody tr:hover {
    background: rgba(255,255,255,0.03);
  }

  .session-id {
    font-family: 'SF Mono', 'Fira Code', monospace;
    font-size: 0.85rem;
    color: #4a90e2;
  }

  .actions-cell {
    display: flex;
    gap: 0.5rem;
    align-items: center;
  }

  .delete-btn {
    padding: 0.3rem 0.7rem;
    background: transparent;
    color: #e74c3c;
    border: 1px solid #e74c3c;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 500;
    transition: all 0.15s ease;
  }

  .delete-btn:hover {
    background: rgba(231, 76, 60, 0.15);
  }

  .load-link {
    display: inline-block;
    padding: 0.3rem 0.7rem;
    background: #4a90e2;
    color: white;
    border: none;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 500;
    text-decoration: none;
    transition: background 0.15s ease;
  }

  .load-link:hover {
    background: #357abd;
  }

  .form-group {
    margin-bottom: 1rem;
  }

  .form-group label {
    display: block;
    font-size: 0.8rem;
    font-weight: 600;
    color: #aaa;
    margin-bottom: 0.4rem;
    text-transform: uppercase;
    letter-spacing: 0.03em;
  }

  .form-group input {
    width: 100%;
    padding: 0.6rem 0.75rem;
    background: #0f3460;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px;
    color: #eee;
    font-size: 0.9rem;
    box-sizing: border-box;
    transition: border-color 0.15s ease;
  }

  .form-group input:focus {
    outline: none;
    border-color: #4a90e2;
    box-shadow: 0 0 0 2px rgba(74, 144, 226, 0.2);
  }

  .form-group input::placeholder {
    color: #555;
  }

  .form-group select {
    width: 100%;
    padding: 0.6rem 0.75rem;
    background: #0f3460;
    border: 1px solid rgba(255,255,255,0.12);
    border-radius: 6px;
    color: #eee;
    font-size: 0.9rem;
    box-sizing: border-box;
    transition: border-color 0.15s ease;
    cursor: pointer;
  }

  .form-group select:focus {
    outline: none;
    border-color: #4a90e2;
    box-shadow: 0 0 0 2px rgba(74, 144, 226, 0.2);
  }

  .form-group select option {
    background: #0f3460;
    color: #eee;
  }

  .start-button {
    width: 100%;
    padding: 0.75rem;
    background: #27ae60;
    color: white;
    border: none;
    border-radius: 6px;
    cursor: pointer;
    font-size: 1rem;
    font-weight: 600;
    margin-top: 0.5rem;
    transition: background 0.15s ease;
  }

  .start-button:hover:not(:disabled) {
    background: #219a52;
  }

  .start-button:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
</style>
