<script>
  import { onMount } from 'svelte';
  import { getGames } from '../lib/api';

  const API_BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000/api/v1';

  let games = [];
  let loading = true;
  let error = null;

  function getCoverUrl(game) {
    if (!game.cover_image) return null;
    return `${API_BASE}/img/${game.cover_image}`;
  }

  onMount(async () => {
    try {
      games = await getGames();
    } catch (e) {
      error = e.message;
    }
    loading = false;
  });
</script>

<main>
  {#if error}
    <div class="error-state">
      <h2>Error</h2>
      <p>{error}</p>
      <button onclick="window.location.reload()">Retry</button>
    </div>
  {:else if games.length === 0}
    <div class="empty-state" data-testid="empty-state">
      <h2>No games found</h2>
      <p>There are no games available at this time.</p>
    </div>
  {:else}
    <div class="page-header">
      <h1>Start</h1>
    </div>
    <div class="tile-grid">
      {#each games as game}
        <a href={`/games/${game.id}/setup`} class="tile">
          {#if getCoverUrl(game)}
            <img src={getCoverUrl(game)} alt="{game.name} cover" class="tile-image" />
          {:else}
            <div class="tile-placeholder">
              <span class="placeholder-icon">&#9823;</span>
            </div>
          {/if}
          <div class="tile-label">
            <span class="tile-name">{game.name}</span>
          </div>
        </a>
      {/each}
    </div>
  {/if}
</main>

<style>
  main {
    min-height: 100vh;
    background: #1a1a2e;
    color: #eee;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
    padding: 2rem;
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

  .error-state button {
    padding: 0.5rem 1.5rem;
    background: #4a90e2;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    margin-top: 0.5rem;
  }

  .error-state button:hover {
    background: #357abd;
  }

  .empty-state {
    padding: 4rem 2rem;
    text-align: center;
    color: #888;
  }

  .empty-state h2 {
    margin: 0 0 0.5rem;
    font-size: 1.5rem;
    color: #aaa;
  }

  .empty-state p {
    margin: 0;
    font-size: 0.95rem;
  }

  .page-header {
    margin-bottom: 1.5rem;
  }

  .page-header h1 {
    margin: 0;
    font-size: 2.2rem;
    font-weight: 700;
    color: #eee;
  }

  .tile-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(180px, 1fr));
    gap: 1rem;
  }

  .tile {
    position: relative;
    aspect-ratio: 1;
    border-radius: 8px;
    overflow: hidden;
    background: #16213e;
    border: 1px solid rgba(255,255,255,0.08);
    text-decoration: none;
    color: inherit;
    display: block;
    transition: transform 0.15s ease, box-shadow 0.15s ease;
  }

  .tile:hover {
    transform: scale(1.03);
    box-shadow: 0 8px 24px rgba(0,0,0,0.4);
  }

  .tile-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
    display: block;
  }

  .tile-placeholder {
    width: 100%;
    height: 100%;
    display: flex;
    align-items: center;
    justify-content: center;
    background: linear-gradient(135deg, #16213e 0%, #0f3460 100%);
  }

  .placeholder-icon {
    font-size: 3rem;
    color: #4a90e2;
  }

  .tile-label {
    position: absolute;
    bottom: 0;
    left: 0;
    right: 0;
    padding: 0.75rem 1rem;
    background: linear-gradient(to top, rgba(26,26,46,0.95) 0%, rgba(26,26,46,0.6) 60%, transparent 100%);
  }

  .tile-name {
    font-size: 1rem;
    font-weight: 600;
    color: #eee;
    text-shadow: 0 1px 4px rgba(0,0,0,0.5);
  }

  @media (max-width: 480px) {
    .tile-grid {
      grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
      gap: 0.75rem;
    }

    .page-header h1 {
      font-size: 1.8rem;
    }
  }
</style>
