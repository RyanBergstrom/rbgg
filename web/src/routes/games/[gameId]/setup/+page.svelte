<script>
  import { onMount } from 'svelte';
  import { getGame, getSessions, startSession, deleteSession } from '$lib/api';
  import { buildGameHistory } from '$lib/game-history';

  const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api/v1';

  export let data;
  let gameId = data?.gameId || '{gameId}';
  let game = null;
  let sessions = [];
  let loading = true;
  let error = null;
  let newPlayerName = 'Ryan';
  let playerCount = gameId === 'bus' ? 3 : 2;
  let selectedDifficulty = '';
  let selectedCampaign = '';
  let selectedScenario = '';

  let activeSessions = [];
  let gameHistory = buildGameHistory([], gameId);
  let campaignData = null;


  $: coverImageUrl = game?.cover_image ? `${API_BASE}/img/${game.cover_image}` : null;

  onMount(async () => {
    try {
      game = await getGame(gameId);
      sessions = await getSessions(gameId);
      activeSessions = sessions.filter(s => !s.finished_at && !s.winner && !s.result_summary_json);
      gameHistory = buildGameHistory(sessions, gameId);
      if (game?.min_players) playerCount = game.min_players;
      if (game?.difficulty) {
        selectedDifficulty = game.difficulty.default
          || Object.keys(game.difficulty).find(k => k !== 'default')
          || '';
      }
      if (gameId === 'fields_of_fire') {
        try {
          const res = await fetch(`${API_BASE}/games/fields_of_fire/scenarios`);
          if (res.ok) {
            campaignData = await res.json();
            const camps = campaignData?.campaigns || {};
            const campKeys = Object.keys(camps);
            if (campKeys.length > 0 && !selectedCampaign) {
              selectedCampaign = campKeys[0];
            }
            const firstCamp = camps[selectedCampaign];
            const scenariosInCamp = firstCamp?.scenarios ? Object.keys(firstCamp.scenarios) : [];
            if (scenariosInCamp.length > 0 && !selectedScenario) {
              selectedScenario = scenariosInCamp[0];
            }
          }
        } catch (e) {
          // ignore
        }
      }
    } catch (e) {
      error = e.message;
    }
    loading = false;
  });

  $: if (gameId === 'fields_of_fire' && campaignData?.campaigns && selectedCampaign) {
    const camp = campaignData.campaigns[selectedCampaign];
    const scenariosInCamp = camp?.scenarios ? Object.keys(camp.scenarios) : [];
    if (scenariosInCamp.length > 0 && !scenariosInCamp.includes(selectedScenario)) {
      selectedScenario = scenariosInCamp[0];
    } else if (scenariosInCamp.length === 0) {
      selectedScenario = '';
    }
  }

  function handleStartNewGame() {
    localStorage.removeItem(`rbgg:debug:${gameId}`);
    startSession(gameId, newPlayerName, parseInt(playerCount), selectedDifficulty, selectedScenario || null)
      .then((session) => {
        window.location.href = `/games/${gameId}/play?sessionId=${session.session_id}`;
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

            {#if gameId === 'fields_of_fire'}
              <div class="form-group">
                <label for="campaign">Campaign</label>
                <select id="campaign" bind:value={selectedCampaign}>
                  {#if campaignData?.campaigns}
                    {#each Object.entries(campaignData.campaigns) as [campId, camp]}
                      <option value={campId}>{camp.name || campId}</option>
                    {/each}
                  {:else}
                    <option value="training">Training Missions</option>
                    <option value="normandy">Normandy</option>
                    <option value="naktong">Naktong River</option>
                    <option value="heartbreak">Heartbreak Ridge</option>
                    <option value="vietnam">Vietnam</option>
                  {/if}
                </select>
              </div>

              <div class="form-group">
                <label for="scenario">Scenario/Mission</label>
                <select id="scenario" bind:value={selectedScenario}>
                  {#if campaignData?.campaigns && selectedCampaign && campaignData.campaigns[selectedCampaign]?.scenarios}
                    {#each Object.entries(campaignData.campaigns[selectedCampaign].scenarios) as [scenId, scen]}
                      <option value={scenId}>{scen.name || scenId}</option>
                    {/each}
                  {:else}
                    <option value="">Select a scenario...</option>
                    <option value="training_1">Basic Training - Movement</option>
                    <option value="pac_run1">PAC Run 1: Activation & Movement</option>
                    <option value="pac_run2">PAC Run 2: Attacking an Enemy Position</option>
                    <option value="pac_run3">PAC Run 3: Potential Contact</option>
                    <option value="cac_run1">CAC Run 1: Assaulting a Known Position</option>
                    <option value="cac_run2">CAC Run 2: Potential Contact System</option>
                    <option value="cac_run3">CAC Run 3: Adding Communications</option>
                  {/if}
                </select>
              </div>
            {/if}

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


            {#if game?.min_players || gameId === 'bus'}
              <div class="form-group">
                <label for="player-count">Number of Players</label>
                <input
                  id="player-count"
                  type="number"
                  bind:value={playerCount}
                  min={game?.min_players || 3}
                  max={game?.max_players || (gameId === 'bus' ? 5 : 2)}
                  step="1"
                  aria-describedby="player-count-help"
                />
                <small id="player-count-help">Choose from {game?.min_players || 3} to {game?.max_players || (gameId === 'bus' ? 5 : 2)} players.</small>
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

        <section class="card history-card" data-testid="game-history">
          <h2 class="card-title">{game?.name || gameId} History</h2>
          <div class="history-stats" aria-label="All-time completed game statistics">
            <div class="stat-tile"><span>Completed</span><strong>{gameHistory.gamesPlayed}</strong></div>
            <div class="stat-tile"><span>Wins</span><strong>{gameHistory.wins}</strong></div>
            <div class="stat-tile"><span>Losses</span><strong>{gameHistory.losses}</strong></div>
            <div class="stat-tile"><span>Win rate</span><strong>{gameHistory.gamesPlayed ? `${gameHistory.winRate}%` : '—'}</strong></div>
          </div>

          {#if gameHistory.gamesPlayed === 0}
            <p class="history-empty">Completed games will appear here. Games still in progress are not included.</p>
          {:else}
            <h3 class="history-subtitle">Record against each bot</h3>
            <div class="history-table-wrap">
              <table class="history-table" data-testid="opponent-records">
                <thead>
                  <tr><th>Opponent</th><th>Games</th><th>W–L–D</th><th>Win rate</th></tr>
                </thead>
                <tbody>
                  {#each gameHistory.opponents as opponent (opponent.name)}
                    <tr>
                      <td>{opponent.name}</td>
                      <td>{opponent.games}</td>
                      <td>{opponent.wins}–{opponent.losses}–{opponent.draws}</td>
                      <td>{Math.round((opponent.wins / opponent.games) * 100)}%</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>

            <h3 class="history-subtitle">Completed games</h3>
            <div class="history-table-wrap">
              <table class="history-table" data-testid="completed-games">
                <thead>
                  <tr><th>Finished</th><th>Result</th><th>Opponents</th><th>Your score</th></tr>
                </thead>
                <tbody>
                  {#each gameHistory.history as entry (entry.id)}
                    <tr>
                      <td>{entry.date ? new Date(entry.date).toLocaleDateString() : '—'}</td>
                      <td><span class="result-pill" class:result-win={entry.result === 'Win'} class:result-loss={entry.result === 'Loss'}>{entry.result}</span></td>
                      <td>{entry.opponents.join(', ') || '—'}</td>
                      <td>{entry.score ?? '—'}</td>
                    </tr>
                  {/each}
                </tbody>
              </table>
            </div>
          {/if}
        </section>
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

  .history-card { margin-top: 1.5rem; }
  .history-stats { display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: .75rem; }
  .stat-tile { display: flex; flex-direction: column; gap: .35rem; padding: 1rem; border-radius: 8px; background: #0f3460; }
  .stat-tile span { color: #9ab0c7; font-size: .75rem; font-weight: 600; text-transform: uppercase; letter-spacing: .04em; }
  .stat-tile strong { color: #f4f7fb; font-size: 1.5rem; }
  .history-empty { margin: 1rem 0 0; color: #aab7c5; }
  .history-subtitle { margin: 1.5rem 0 .5rem; color: #d7e2ef; font-size: .95rem; }
  .history-table-wrap { overflow-x: auto; }
  .history-table { width: 100%; border-collapse: collapse; }
  .history-table th, .history-table td { padding: .7rem .75rem; border-bottom: 1px solid rgba(255,255,255,.07); text-align: left; white-space: nowrap; }
  .history-table th { color: #8fa0b5; font-size: .72rem; letter-spacing: .04em; text-transform: uppercase; }
  .history-table td { color: #e1e7ef; font-size: .88rem; }
  .result-pill { display: inline-block; padding: .18rem .5rem; border-radius: 999px; background: #485569; font-size: .75rem; font-weight: 700; }
  .result-win { background: rgba(39,174,96,.2); color: #7ce0a5; }
  .result-loss { background: rgba(231,76,60,.16); color: #ff9a91; }

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

  @media (max-width: 600px) {
    .history-stats { grid-template-columns: repeat(2, minmax(0, 1fr)); }
    .history-card { padding: 1rem; }
  }
</style>
