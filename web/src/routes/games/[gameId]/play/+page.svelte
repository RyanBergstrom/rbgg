<script>
  import { onMount, onDestroy } from 'svelte';
  import { getGame, getSessions, getLegalMoves, getAiMove, makeMove, startSession, confirmTurn, undoMove, debugLoadState, loadSession } from '$lib/api';
  import GameProgressPanel from '$lib/components/GameProgressPanel.svelte';
  import DebugPanel from '$lib/components/DebugPanel.svelte';
  import SettingsPanel from '$lib/components/SettingsPanel.svelte';
  import { settings } from '$lib/stores/settings';
  import { traceApi, traceState, traceMove, tracePhase } from '$lib/dev';

  export let data;

  let gameId = data?.gameId || '{gameId}';
  let game = null;
  let sessions = [];
  let legalMoves = [];
  let screenState = null;
  let loading = true;
  let error = null;
  let aiInterval = null;
  let aiInProgress = false;
  let pendingMove = null;
  let canUndo = false;
  let showSettings = false;

  let BoardComponent = null;
  let debugMode = data?.debug || false;

  const HUMAN_PLAYER = 'player_1';

  $: currentPlayer = screenState?.current_player || game?.state?.player_turn || null;
  $: isHumanTurn = currentPlayer === HUMAN_PLAYER && !screenState?.winner && !game?.state?.winner;
  $: isAiTurn = currentPlayer && currentPlayer !== HUMAN_PLAYER && !screenState?.winner && !game?.state?.winner;

  $: if (currentPlayer) {
    tracePhase('play:page', 'turn state', { currentPlayer, isHumanTurn, isAiTurn });
  }

  async function loadBoardComponent(type) {
    try {
      // Convert snake_case to PascalCase for component filename
      // e.g., "lost_cities" -> "LostCities", "checkers" -> "Checkers"
      const componentName = type
        .split('_')
        .map(part => part.charAt(0).toUpperCase() + part.slice(1))
        .join('');
      const mod = await import(`$lib/components/games/${type}/${componentName}Board.svelte`);
      BoardComponent = mod.default;
    } catch (e) {
      console.warn(`No board component for game type: ${type}`, e);
      BoardComponent = null;
    }
  }

  function updateScreenState(result) {
    if (result?.screen_state) {
      traceState('play:page', 'screenState from response', {
        phase: result.screen_state.phase,
        currentPlayer: result.screen_state.current_player,
        winner: result.screen_state.winner,
        legalMoveCount: result.screen_state.legal_moves?.length,
      });
      screenState = result.screen_state;
    } else {
      traceApi('play:page', 'no screen_state in response', Object.keys(result || {}));
    }
  }

  async function refreshState() {
    game = await getGame(gameId);
    updateScreenState(game);
    const movesResult = await getLegalMoves(gameId);
    updateScreenState(movesResult);
    legalMoves = movesResult?.legal_moves || [];
  }

  $: confirmRequired = screenState?.phase?.confirm_required || false;

  async function handleBoardSelect(event) {
    const move = event.detail;
    traceMove('play:page', 'move selected locally', move);

    if (!confirmRequired) {
      // Phase doesn't require confirm — submit immediately
      try {
        traceMove('play:page', 'auto-submitting move (no confirm required)', { phase: screenState?.phase?.phase_name });
        const result = await makeMove(gameId, move);
        traceMove('play:page', 'auto-submit result', {
          status: result?.status,
          phase: result?.screen_state?.phase?.phase_name,
        });
        updateScreenState(result);
        pendingMove = null;
        canUndo = true;
        await refreshState();
      } catch (e) {
        traceMove('play:page', 'auto-submit error', e.message);
      }
    } else {
      pendingMove = move;
    }
  }

  async function handleUndo() {
    traceMove('play:page', 'undo requested', { canUndo, pendingMove });
    try {
      const result = await undoMove(gameId);
      traceMove('play:page', 'undo result', {
        status: result?.status,
        phase: result?.screen_state?.phase?.phase_name,
      });
      updateScreenState(result);
      pendingMove = null;
      canUndo = false;
      await refreshState();
    } catch (e) {
      traceMove('play:page', 'undo error', e.message);
    }
  }

  function handleExit() {
    window.location.href = `/games/${gameId}/setup`;
  }

  function handleSettings() {
    showSettings = true;
  }

  async function handleConfirm() {
    tracePhase('play:page', 'confirm requested', { hasPendingMove: !!pendingMove });
    try {
      if (pendingMove) {
        const result = await makeMove(gameId, pendingMove);
        traceMove('play:page', 'move submitted', {
          status: result?.status,
          confirmRequired: result?.screen_state?.phase?.confirm_required,
          phase: result?.screen_state?.phase?.phase_name,
        });
        updateScreenState(result);
        pendingMove = null;
        canUndo = false;
        await refreshState();
      }
      if (screenState?.phase?.confirm_required) {
        const result = await confirmTurn(gameId);
        tracePhase('play:page', 'confirm response', {
          status: result?.status,
          phase: result?.screen_state?.phase?.phase_name,
          currentPlayer: result?.screen_state?.current_player,
        });
        updateScreenState(result);
        canUndo = false;
        await refreshState();
      }
    } catch (e) {
      tracePhase('play:page', 'confirm error', e.message);
    }
  }

  function handleDebugLoadState(event) {
    const newState = event.detail;
    traceState('play:page', 'debug: loading injected screen state', {
      phase: newState?.phase,
      currentPlayer: newState?.current_player,
      winner: newState?.winner,
    });
    screenState = newState;
    if (newState?.legal_moves) {
      legalMoves = newState.legal_moves;
    }
    const serialized = JSON.stringify(newState);
    localStorage.setItem(`rbgg:debug:${gameId}`, serialized);
    console.log('[debug] saved to localStorage:', {
      key: `rbgg:debug:${gameId}`,
      size: serialized.length,
      hasPanels: !!newState?.panels,
      panelIds: newState?.panels?.map(p => p.id),
    });
    // Sync game_data to backend so get_legal_moves uses the pasted board
    debugLoadState(gameId, newState?.game_data, newState?.current_player_index, newState?.winner)
      .then(() => console.log('[debug] synced game_data to backend'))
      .catch(e => console.warn('[debug] failed to sync to backend:', e));
  }

  function handleDebugClearState() {
    localStorage.removeItem(`rbgg:debug:${gameId}`);
    window.location.reload();
  }

  function startAiTurnLoop() {
    if (aiInterval) {
      clearInterval(aiInterval);
    }
    traceApi('play:page', 'AI turn loop started');

    aiInterval = setInterval(async () => {
      if (!isAiTurn || aiInProgress || screenState?.winner || game?.state?.winner) {
        traceApi('play:page', 'AI turn loop skipping', { isAiTurn, aiInProgress, winner: screenState?.winner });
        if (!isAiTurn || screenState?.winner || game?.state?.winner) {
          clearInterval(aiInterval);
          aiInterval = null;
        }
        return;
      }
      try {
        aiInProgress = true;
        const moveData = await getAiMove(gameId, sessions[0]?.id);
        traceMove('play:page', 'AI move response', {
          hasMove: !!moveData.move,
          status: moveData.status,
        });

        updateScreenState(moveData);
        await refreshState();

        if (moveData.winner || screenState?.winner || game?.state?.winner) {
          clearInterval(aiInterval);
          aiInterval = null;
        }
      } catch (e) {
        clearInterval(aiInterval);
        aiInterval = null;
        traceMove('play:page', 'AI turn error', e.message);
      } finally {
        aiInProgress = false;
      }
    }, 1000);
  }

  $: if (isAiTurn && !aiInterval && !aiInProgress && !loading) {
    canUndo = false;
    startAiTurnLoop();
  }

  $: if (isHumanTurn && aiInterval) {
    traceApi('play:page', 'stopping AI loop — human turn');
    clearInterval(aiInterval);
    aiInterval = null;
    aiInProgress = false;
  }

  onMount(async () => {
    traceApi('play:page', 'mount', { gameId });
    settings.load();

    const urlParams = new URLSearchParams(window.location.search);
    const sessionIdParam = urlParams.get('sessionId');

    if (sessionIdParam) {
      const sessionId = parseInt(sessionIdParam, 10);
      if (!isNaN(sessionId)) {
        try {
          traceApi('play:page', 'loading session from URL', { sessionId });
          const loaded = await loadSession(sessionId);
          game = loaded;
          updateScreenState(loaded);
          sessions = await getSessions(gameId);
          const movesResult = await getLegalMoves(gameId);
          updateScreenState(movesResult);
          legalMoves = movesResult?.legal_moves || [];
          if (loaded?.type) {
            await loadBoardComponent(loaded.type);
          }
          window.history.replaceState({}, '', `/games/${gameId}/play`);
        } catch (e) {
          error = e.message;
        }
        loading = false;
        return;
      }
    }

    const cachedDebug = localStorage.getItem(`rbgg:debug:${gameId}`);
    if (cachedDebug) {
      traceApi('play:page', 'restoring debug state from localStorage');
      try {
        const debugState = JSON.parse(cachedDebug);
        console.log('[debug] restored from localStorage:', {
          hasPanels: !!debugState?.panels,
          panelIds: debugState?.panels?.map(p => p.id),
          currentPlayer: debugState?.current_player,
          legalMoveCount: debugState?.legal_moves?.length,
        });
        screenState = debugState;
        if (debugState?.legal_moves) {
          legalMoves = debugState.legal_moves;
        }
        // Sync cached debug game_data to backend
        await debugLoadState(gameId, debugState?.game_data, debugState?.current_player_index, debugState?.winner);
        console.log('[debug] synced cached debug state to backend');
        game = await getGame(gameId);
        console.log('[debug] after getGame:', {
          screenStateHasPanels: !!screenState?.panels,
          gameHasBoard: !!game?.state?.game_data?.board,
          gameHasScreenState: !!game?.screen_state,
        });
        if (game?.type) {
          await loadBoardComponent(game.type);
        }
        sessions = await getSessions(gameId);
      } catch (e) {
        error = e.message;
      }
      loading = false;
      return;
    }

    try {
      game = await getGame(gameId);
      updateScreenState(game);

      sessions = await getSessions(gameId);

      if (!game?.state) {
        traceApi('play:page', 'no active state — starting new session');
        const sessionResult = await startSession(gameId, 'Player One', 2, 2, 'default', '#cc0000');
        updateScreenState(sessionResult);
        sessions = await getSessions(gameId);
        game = await getGame(gameId);
        updateScreenState(game);
      }

      const movesResult = await getLegalMoves(gameId);
      updateScreenState(movesResult);
      legalMoves = movesResult?.legal_moves || [];

      if (game?.type) {
        await loadBoardComponent(game.type);
      }
    } catch (e) {
      error = e.message;
    }
    loading = false;
  });

  onDestroy(() => {
    if (aiInterval) {
      clearInterval(aiInterval);
    }
  });
</script>

<div class="game-container">
  {#if error}
    <div class="error-state">
      <h2>Error</h2>
      <p>{error}</p>
      <button on:click={() => window.location.reload()}>Retry</button>
    </div>
  {:else}
    {#if BoardComponent}
      <svelte:component
        this={BoardComponent}
        {gameId}
        {legalMoves}
        {game}
        {screenState}
        {pendingMove}
        on:select-move={handleBoardSelect}
      />
    {:else if loading}
      <div class="loading-panel">Loading game board...</div>
    {:else}
      <div class="placeholder-panel">
        <h2>{game?.name || gameId}</h2>
        <p>Game type: {game?.type || 'unknown'}</p>
        <p>No board component registered for this game.</p>
      </div>
    {/if}

    {#if screenState?.winner || game?.state?.winner}
      <div class="game-over-banner">
        <h2>Player {screenState?.winner || game?.state?.winner} wins!</h2>
        <p>Final stats recorded</p>
      </div>
    {/if}

    {#if debugMode}
      <DebugPanel {screenState} on:load-state={handleDebugLoadState} on:clear-state={handleDebugClearState} />
    {/if}
  {/if}
</div>

<GameProgressPanel
  {game}
  {screenState}
  {pendingMove}
  {canUndo}
  on:confirm={handleConfirm}
  on:undo={handleUndo}
  on:exit={handleExit}
  on:settings={handleSettings}
/>

{#if showSettings}
  <SettingsPanel on:close={() => showSettings = false} />
{/if}

<style>
  .game-container {
    display: flex;
    flex-direction: column;
    gap: 0;
    padding: 0;
    padding-bottom: 70px;
    width: 100%;
    min-height: 100vh;
    box-sizing: border-box;
  }

  :global(.game-progress-panel) {
    position: fixed;
    bottom: 0;
    left: 0;
    right: 0;
    z-index: 100;
  }

  .error-state {
    padding: 2rem;
    border: 1px solid #e74c3c;
    border-radius: 4px;
    background: #fdf2f2;
    margin: 1rem;
  }

  .game-over-banner {
    background: #d4edda;
    border: 1px solid #c3e6cb;
    border-radius: 4px;
    padding: 1rem;
    margin: 1rem;
    text-align: center;
  }

  .game-over-banner h2 {
    margin-top: 0;
  }

  .placeholder-panel {
    width: 100%;
    padding: 1rem;
    box-sizing: border-box;
    background: #f0f0f0;
  }

  .loading-panel {
    width: 100%;
    padding: 2rem;
    text-align: center;
    color: #666;
  }
</style>
