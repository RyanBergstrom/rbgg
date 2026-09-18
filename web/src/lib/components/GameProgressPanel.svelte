<script>
  import { createEventDispatcher } from 'svelte';
  import { IS_DEV, tracePhase } from '$lib/dev';

  export let game = null;
  export let screenState = null;
  export let pendingMove = null;
  export let canUndo = false;

  const dispatch = createEventDispatcher();

  $: phase = screenState?.phase || null;
  $: currentPlayer = screenState?.current_player || game?.state?.player_turn || null;
  $: winner = screenState?.winner || game?.state?.winner || null;
  $: confirmRequired = phase?.confirm_required || false;
  $: showConfirm = (pendingMove !== null) || confirmRequired;

  $: if (phase) {
    tracePhase('GameProgressPanel', 'phase updated', {
      phase_name: phase.phase_name,
      confirm_required: phase.confirm_required,
      currentPlayer, winner
    });
  }

  function getPlayerName(playerId) {
    if (!playerId) return 'Unknown';
    if (playerId === 'player_1') return 'Red';
    if (playerId === 'player_2') return 'Black';
    return playerId;
  }

  function getPlayerColor(playerId) {
    if (playerId === 'player_1') return '#cc0000';
    if (playerId === 'player_2') return '#222222';
    return '#666';
  }

  function handleConfirm() {
    tracePhase('GameProgressPanel', 'confirm clicked');
    dispatch('confirm');
  }

  function handleUndo() {
    tracePhase('GameProgressPanel', 'undo clicked');
    dispatch('undo');
  }

  function handleExit() {
    tracePhase('GameProgressPanel', 'exit clicked');
    dispatch('exit');
  }

  function handleSettings() {
    tracePhase('GameProgressPanel', 'settings clicked');
    dispatch('settings');
  }
</script>

<div class="game-progress-panel">
  {#if IS_DEV}<div class="panel-name-debug">GameProgressPanel</div>{/if}

  <div class="panel-row">
    <div class="panel-left">
      <button class="settings-button" on:click={handleSettings} title="Settings">
        <svg xmlns="http://www.w3.org/2000/svg" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <circle cx="12" cy="12" r="3"></circle>
          <path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path>
        </svg>
      </button>
      {#if winner}
        <span class="player-dot" style="background: {getPlayerColor(winner)}"></span>
        <strong>{getPlayerName(winner)} wins!</strong>
      {:else if currentPlayer}
        <span class="player-dot" style="background: {getPlayerColor(currentPlayer)}"></span>
        <span>{getPlayerName(currentPlayer)}'s turn</span>
      {/if}

      {#if phase && !winner}
        <span class="phase-status">
          <span class="phase-name">{phase.phase_name}</span>
          {#if phase.phase_text}
            <span class="phase-text"> — {phase.phase_text}</span>
          {/if}
        </span>
      {/if}
    </div>

    <div class="panel-right">
      {#if confirmRequired || pendingMove}
        <button class="confirm-button" on:click={handleConfirm} disabled={!pendingMove && !confirmRequired}>
          {pendingMove ? 'Submit Move' : (phase?.confirm_name || 'Confirm')}
        </button>
      {/if}
      {#if canUndo || pendingMove}
        <button class="undo-button" on:click={handleUndo} disabled={!pendingMove && !canUndo}>
          Undo
        </button>
      {/if}
      <button class="exit-button" on:click={handleExit}>
        Exit
      </button>
    </div>
  </div>
</div>

<style>
  .game-progress-panel {
    padding: 0.5rem 1rem;
    background: #f5f5f5;
    margin: 0;
    border-top: 2px dashed #aaa;
    border-bottom: none;
    min-height: 3.5rem;
    box-sizing: border-box;
  }

  .panel-name-debug {
    font-size: 0.7rem;
    color: #999;
    font-family: monospace;
    position: absolute;
    top: 2px;
    left: 4px;
  }

  .panel-row {
    display: flex;
    align-items: center;
    justify-content: space-between;
    height: 100%;
    gap: 1rem;
  }

  .panel-left {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.95rem;
    font-weight: 500;
    min-width: 0;
    overflow: hidden;
  }

  .settings-button {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 36px;
    height: 36px;
    padding: 0;
    background: transparent;
    border: 1px solid #ccc;
    border-radius: 6px;
    color: #666;
    cursor: pointer;
    transition: all 0.15s;
    flex-shrink: 0;
  }

  .settings-button:hover {
    background: #e0e0e0;
    color: #333;
    border-color: #999;
  }

  .panel-right {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    flex-shrink: 0;
  }

  .player-dot {
    width: 12px;
    height: 12px;
    border-radius: 50%;
    display: inline-block;
    border: 1px solid #999;
    flex-shrink: 0;
  }

  .phase-status {
    font-size: 0.85rem;
    color: #555;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .phase-name {
    font-weight: 600;
    color: #333;
  }

  .phase-text {
    color: #666;
  }

  .confirm-button {
    padding: 0.35rem 1rem;
    background: #4a90e2;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
    white-space: nowrap;
  }

  .confirm-button:hover:not(:disabled) {
    background: #357abd;
  }

  .confirm-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .undo-button {
    padding: 0.35rem 0.75rem;
    background: #6c757d;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
    white-space: nowrap;
  }

  .undo-button:hover:not(:disabled) {
    background: #5a6268;
  }

  .undo-button:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .exit-button {
    padding: 0.35rem 0.75rem;
    background: #dc3545;
    color: white;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
    white-space: nowrap;
  }

  .exit-button:hover {
    background: #c82333;
  }
</style>
