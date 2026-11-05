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
  let sessionId = data?.sessionId || null;
  let game = null;
  let sessions = [];
  let legalMoves = [];
  let screenState = null;
  let loading = true;
  let debugMode = false;
  let error = null;
  let aiInterval = null;
  let aiInProgress = false;
  let aiProvider = 'ppo';
  let aiProviderUsed = null;
  let aiDifficulty = 'hard';
  let pendingMove = null;
  let canUndo = false;
  let showSettings = false;
  let actionInProgress = false;
  let actionError = null;
  let lastSelectedMove = null;
  let selectedMoveTimeout = null;
  let BoardComponent = null;

  function getLegalMoveByType(type) {
    return (legalMoves || []).find(m => m.type === type);
  }

  $: setupComplete = (() => {
    if (gameId !== 'fields_of_fire') return false;
    const gd = screenState?.game_data || game?.state?.game_data || {};
    const units = gd.company?.units || [];
    const placed = units.filter(u => u.position !== null && u.position !== undefined);
    return placed.length === units.length && units.length > 0;
  })();

  const HUMAN_PLAYER = 'player_1';
  const HOT_SEAT_GAME = 'twilight_struggle';
  $: isHotSeatGame = gameId === HOT_SEAT_GAME;

  $: currentPlayer = screenState?.current_player || game?.state?.player_turn || null;
  $: isHumanTurn = (isHotSeatGame || currentPlayer === HUMAN_PLAYER) && !screenState?.winner && !game?.state?.winner;
  $: isAiTurn = !isHotSeatGame && currentPlayer && currentPlayer !== HUMAN_PLAYER && !screenState?.winner && !game?.state?.winner;

  $: if (currentPlayer) {
    tracePhase('play:page', 'turn state', { currentPlayer, isHumanTurn, isAiTurn });
  }

  async function loadBoardComponent(type) {
    try {
      console.log('loadBoardComponent called with type:', type, 'BoardComponent before:', BoardComponent);
      if (type === 'fields_of_fire') {
        try {
          console.log('Attempting FOF direct import...');
          const mod = await import('$lib/components/games/fields_of_fire/FieldsOfFireBoard.svelte');
          console.log('FOF module loaded:', Object.keys(mod));
          if (typeof BoardComponent !== 'undefined') {
            BoardComponent = mod.default;
            console.log('BoardComponent set to:', BoardComponent);
          }
          return;
        } catch (e2) {
          console.error('Failed to load FOF board directly:', e2);
        }
      }
      // Convert snake_case to PascalCase for component filename
      // e.g., "lost_cities" -> "LostCities", "checkers" -> "Checkers"
      const componentName = type
        .split('_')
        .map(part => part.charAt(0).toUpperCase() + part.slice(1))
        .join('');
      const mod = await import(`$lib/components/games/${type}/${componentName}Board.svelte`);
      if (typeof BoardComponent !== 'undefined') {
        BoardComponent = mod.default;
      }
    } catch (e) {
      console.error(`Error loading board component for type ${type}:`, e);
      if (typeof BoardComponent !== 'undefined') {
        BoardComponent = null;
      }
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

  function handleAiProviderChange() {
    localStorage.setItem('rbgg:lost-cities-ai-provider-v2', aiProvider);
    aiProviderUsed = null;
  }

  function syncSessionUrl(activeSessionId) {
    if (!activeSessionId || typeof window === 'undefined') return;
    const nextUrl = new URL(window.location.href);
    nextUrl.searchParams.set('sessionId', String(activeSessionId));
    window.history.replaceState({}, '', `${nextUrl.pathname}${nextUrl.search}`);
  }

  async function refreshState() {
    game = await getGame(gameId, sessionId);
    updateScreenState(game);
    const movesResult = await getLegalMoves(sessionId);
    updateScreenState(movesResult);
    legalMoves = movesResult?.legal_moves || [];
  }

  $: confirmRequired = screenState?.phase?.confirm_required || false;
  // In Bus, action selection and each resolution choice commit real game
  // resources/positions. Keep setup friction-free, but stage all live-round
  // moves until the player explicitly confirms them.
  $: busLivePlay = gameId === 'bus' && (screenState?.game_data?.round_number || 0) > 0;
  $: requiresMoveConfirmation = confirmRequired || busLivePlay;

  function showSelectedMove(move) {
    lastSelectedMove = move;
    if (selectedMoveTimeout) clearTimeout(selectedMoveTimeout);
    selectedMoveTimeout = setTimeout(() => {
      lastSelectedMove = null;
      selectedMoveTimeout = null;
    }, 1500);
  }

  async function handleBoardSelect(event) {
    if (actionInProgress) return;
    const move = event.detail;
    traceMove('play:page', 'move selected locally', move);
    actionError = null;

    // Defend against stale click targets: only submit a move that is still
    // present in the most recently known legal-move set. A board overlay can
    // briefly hold on to moves from a prior render pass.
    const currentLegalMoves = screenState?.legal_moves?.length ? screenState.legal_moves : legalMoves;
    const isStillLegal = currentLegalMoves.some((candidate) => candidate.move_id === move.move_id);
    if (!isStillLegal) {
      traceMove('play:page', 'stale move rejected before submit', move);
      actionError = 'That action is no longer available. The board has been refreshed.';
      try {
        await refreshState();
      } catch (e) {
        actionError = e.message || 'Unable to refresh the board. Please retry.';
      }
      return;
    }

    if (!requiresMoveConfirmation) {
      // Phase doesn't require confirm — submit immediately
      actionInProgress = true;
      showSelectedMove(move);
      try {
        traceMove('play:page', 'auto-submitting move (no confirm required)', { phase: screenState?.phase?.phase_name });
        const result = await makeMove(sessionId, move);
        traceMove('play:page', 'auto-submit result', {
          status: result?.status,
          phase: result?.screen_state?.phase?.phase_name,
        });
        updateScreenState(result);
        pendingMove = null;
        canUndo = true;
      } catch (e) {
        actionError = e.message || 'Unable to submit move. Please retry.';
        traceMove('play:page', 'auto-submit error', e.message);
        try {
          await refreshState();
        } catch (refreshErr) {
          traceMove('play:page', 'refresh after error failed', refreshErr.message);
        }
      } finally {
        actionInProgress = false;
      }
    } else {
      pendingMove = move;
      showSelectedMove(move);
    }
  }

  async function handleStartMission() {
    const move = getLegalMoveByType('start_mission');
    if (move) {
      actionInProgress = true;
      actionError = null;
      try {
        const result = await makeMove(sessionId, move);
        updateScreenState(result);
        await refreshState();
      } catch (e) {
        actionError = e.message || 'Unable to start mission.';
      } finally {
        actionInProgress = false;
      }
    }
  }

  function handleExit() {
    window.location.href = `/games/${gameId}/setup`;
  }

  function handleSettings() {
    showSettings = true;
  }

  async function handleConfirm() {
    if (actionInProgress) return;
    actionInProgress = true;
    actionError = null;
    tracePhase('play:page', 'confirm requested', { hasPendingMove: !!pendingMove });
    try {
      if (pendingMove) {
        const result = await makeMove(sessionId, pendingMove);
        traceMove('play:page', 'move submitted', {
          status: result?.status,
          confirmRequired: result?.screen_state?.phase?.confirm_required,
          phase: result?.screen_state?.phase?.phase_name,
        });
        updateScreenState(result);
        pendingMove = null;
        canUndo = false;
      }
      if (screenState?.phase?.confirm_required) {
        const result = await confirmTurn(sessionId);
        tracePhase('play:page', 'confirm response', {
          status: result?.status,
          phase: result?.screen_state?.phase?.phase_name,
          currentPlayer: result?.screen_state?.current_player,
        });
        updateScreenState(result);
        canUndo = false;
      }
    } catch (e) {
      actionError = e.message || 'Unable to complete turn. Please retry.';
      tracePhase('play:page', 'confirm error', e.message);
    } finally {
      actionInProgress = false;
    }
  }

  function handleCancelPendingMove() {
    if (actionInProgress) return;
    pendingMove = null;
    actionError = null;
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
    debugLoadState(sessionId, newState?.game_data, newState?.current_player_index, newState?.winner)
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
        const moveData = await getAiMove(
          sessionId,
          gameId === 'lost_cities' ? aiProvider : undefined,
          aiDifficulty,
        );
        traceMove('play:page', 'AI move response', {
          hasMove: !!moveData.move,
          status: moveData.status,
          requestedProvider: aiProvider,
          actualProvider: moveData.ai_provider,
        });
        aiProviderUsed = moveData.ai_provider || null;

        updateScreenState(moveData);
        if (moveData.winner || screenState?.winner || game?.state?.winner) {
          clearInterval(aiInterval);
          aiInterval = null;
        }
      } catch (e) {
        error = e.message || 'Unable to calculate the AI move. Please retry.';
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
    if (gameId === 'lost_cities') {
      const requestedProvider = urlParams.get('aiProvider');
      const savedProvider = localStorage.getItem('rbgg:lost-cities-ai-provider-v2');
      aiProvider = ['ppo', 'mcts'].includes(requestedProvider ?? '')
        ? requestedProvider
        : (['ppo', 'mcts'].includes(savedProvider ?? '') ? savedProvider : 'ppo');
      localStorage.setItem('rbgg:lost-cities-ai-provider-v2', aiProvider);

      const requestedDifficulty = urlParams.get('aiDifficulty');
      const savedDifficulty = localStorage.getItem('rbgg:lost-cities-ai-difficulty');
      aiDifficulty = ['easy', 'medium', 'hard'].includes(requestedDifficulty ?? '')
        ? requestedDifficulty
        : (['easy', 'medium', 'hard'].includes(savedDifficulty ?? '') ? savedDifficulty : 'hard');
      localStorage.setItem('rbgg:lost-cities-ai-difficulty', aiDifficulty);
    }
    const sessionIdParam = urlParams.get('sessionId');

    if (sessionIdParam) {
      const requestedSessionId = parseInt(sessionIdParam, 10);
      if (!isNaN(requestedSessionId)) {
        try {
          traceApi('play:page', 'loading session from URL', { sessionId: requestedSessionId });
          sessionId = requestedSessionId;
          const loaded = await loadSession(sessionId);
          game = loaded;
          updateScreenState(loaded);
          sessions = await getSessions(gameId);
          const movesResult = await getLegalMoves(sessionId);
          updateScreenState(movesResult);
          legalMoves = movesResult?.legal_moves || [];
          if (loaded?.type) {
            await loadBoardComponent(loaded.type);
          }
          syncSessionUrl(sessionId);
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
        await debugLoadState(sessionId, debugState?.game_data, debugState?.current_player_index, debugState?.winner);
        console.log('[debug] synced cached debug state to backend');
        game = await getGame(gameId, sessionId);
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
      game = await getGame(gameId, sessionId);
      updateScreenState(game);

      sessions = await getSessions(gameId);

      if (!game?.state) {
        traceApi('play:page', 'no active state — starting new session');
        const sessionResult = await startSession(gameId, 'Player One', 2, 'default');
        sessionId = sessionResult.session_id;
        syncSessionUrl(sessionId);
        updateScreenState(sessionResult);
        sessions = await getSessions(gameId);
        game = await getGame(gameId, sessionId);
        updateScreenState(game);
      }

      const movesResult = await getLegalMoves(sessionId);
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
    if (selectedMoveTimeout) {
      clearTimeout(selectedMoveTimeout);
    }
  });
</script>

<div class="game-container">
  {#if gameId === 'lost_cities' && $settings.show_ai_controls !== false}
    <label class="ai-provider-control">
      AI opponent
      <select bind:value={aiProvider} on:change={handleAiProviderChange}>
        <option value="ppo">Trained PPO model (default)</option>
        <option value="mcts">MCTS</option>
      </select>
    </label>
    {#if aiProviderUsed}
      <p class="ai-provider-status" role="status">
        Last AI turn used {aiProviderUsed.toUpperCase()}.
        {#if aiProviderUsed !== aiProvider}
          Requested {aiProvider.toUpperCase()}; check the API logs for a PPO fallback reason.
        {/if}
      </p>
    {/if}
    {#if aiProvider === 'ppo'}
      <label class="ai-provider-control">
        Model difficulty
        <select bind:value={aiDifficulty} on:change={() => localStorage.setItem('rbgg:lost-cities-ai-difficulty', aiDifficulty)}>
          <option value="hard">Hard — strongest choices</option>
          <option value="medium">Medium — occasional random move</option>
          <option value="easy">Easy — more random moves</option>
        </select>
      </label>
    {/if}
  {/if}
  {#if error}
    <div class="error-state">
      <h2>Error</h2>
      <p>{error}</p>
      <button on:click={() => window.location.reload()}>Retry</button>
    </div>
  {:else}
    {#if actionError}
      <div class="action-error-banner" role="alert">
        <span>{actionError}</span>
        <button type="button" on:click={() => actionError = null}>Dismiss</button>
      </div>
    {/if}
    {#if typeof BoardComponent !== 'undefined' && BoardComponent}
      <svelte:component
        this={BoardComponent}
        {gameId}
        {legalMoves}
        {game}
        {screenState}
        {pendingMove}
        {actionInProgress}
        {lastSelectedMove}
        on:select-move={handleBoardSelect}
        on:confirm={handleConfirm}
        on:cancel-pending-move={handleCancelPendingMove}
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
  gameId={gameId}
  setupComplete={setupComplete}
  on:confirm={handleConfirm}
  on:undo={handleUndo}
  on:exit={handleExit}
  on:settings={handleSettings}
  on:start-mission={handleStartMission}
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

  .ai-provider-control {
    display: flex;
    align-items: center;
    justify-content: flex-end;
    gap: 0.5rem;
    padding: 0.5rem 1rem;
    color: #334155;
    font-size: 0.9rem;
  }

  .ai-provider-control select {
    padding: 0.35rem 0.55rem;
    border: 1px solid #94a3b8;
    border-radius: 0.35rem;
    background: white;
    color: inherit;
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

  .action-error-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    max-width: 1280px;
    margin: 0.75rem auto;
    padding: 0.6rem 0.9rem;
    border: 1px solid #e74c3c;
    border-radius: 0.35rem;
    background: #fdf2f2;
    color: #8a2a21;
    font-size: 0.9rem;
  }

  .action-error-banner button {
    padding: 0.3rem 0.7rem;
    border: 1px solid #e74c3c;
    border-radius: 0.3rem;
    background: white;
    color: #8a2a21;
    cursor: pointer;
    flex-shrink: 0;
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
