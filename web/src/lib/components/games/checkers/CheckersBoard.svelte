<script>
  import { createEventDispatcher } from 'svelte';
  import { IS_DEV, traceRender, traceMove } from '$lib/dev';

  export let game = null;
  export let gameId = 'checkers';
  export let legalMoves = [];
  export let screenState = null;
  export let pendingMove = null;

  const dispatch = createEventDispatcher();

  const EMPTY = 0;
  const RED = 1;
  const RED_KING = 2;
  const BLACK = 3;
  const BLACK_KING = 4;

  let cells = [];
  let boardSize = 8;
  let selectedPiece = null;
  let highlightedMoves = [];
  let currentPlayerId = 'player_1';
  let winner = null;
  let phase = null;

  $: {
    if (screenState?.panels) {
      const mainBoard = screenState.panels.find(p => p.id === 'main_board');
      const boardComp = mainBoard?.components?.find(c => c.id === 'board');
      cells = boardComp?.grid?.cells || [];
      boardSize = boardComp?.grid?.rows || 8;
      currentPlayerId = screenState.current_player || 'player_1';
      winner = screenState.winner || null;
      legalMoves = screenState.legal_moves || [];
      phase = screenState.phase || null;
      selectedPiece = null;
      highlightedMoves = [];
      console.log('[debug:CheckersBoard] using screenState.panels', {
        cellCount: cells.length,
        firstCell: cells[0]?.[0],
        currentPlayerId, winner,
      });
      traceRender('CheckersBoard', 'screenState updated', {
        currentPlayerId, winner, phase: phase?.phase_name,
        confirmRequired: phase?.confirm_required, legalMoveCount: legalMoves.length
      });
    } else if (game?.state?.game_data?.board) {
      const board = game.state.game_data.board;
      cells = board.map((row, r) =>
        row.map((val, c) => ({
          color: (r + c) % 2 === 1 ? '#b58863' : '#f0d9b5',
          piece: val === RED ? { id: `r${r}c${c}`, type: 'red', color: '#cc0000', king: false }
            : val === RED_KING ? { id: `r${r}c${c}`, type: 'red', color: '#cc0000', king: true }
            : val === BLACK ? { id: `r${r}c${c}`, type: 'black', color: '#222222', king: false }
            : val === BLACK_KING ? { id: `r${r}c${c}`, type: 'black', color: '#222222', king: true }
            : null
        }))
      );
      boardSize = game.state.game_data.board_size || 8;
      currentPlayerId = game?.state?.player_turn || 'player_1';
      winner = game?.state?.winner || null;
      console.log('[debug:CheckersBoard] using game.state fallback', {
        cellCount: cells.length,
        firstCell: cells[0]?.[0],
        currentPlayerId, winner,
      });
    } else {
      cells = Array.from({ length: 8 }, (_, r) =>
        Array.from({ length: 8 }, (_, c) => ({
          color: (r + c) % 2 === 1 ? '#b58863' : '#f0d9b5',
          piece: null
        }))
      );
    }
  }

  function getPieceAt(row, col) {
    return cells[row]?.[col]?.piece || null;
  }

  const HUMAN_PLAYER = 'player_1';

  $: isBoardLocked = !!winner || currentPlayerId !== HUMAN_PLAYER || pendingMove !== null;

  function isSelectable(row, col) {
    if (isBoardLocked) return false;
    const piece = getPieceAt(row, col);
    if (!piece) return false;
    if (currentPlayerId === 'player_1') {
      return piece.type === 'red';
    }
    return piece.type === 'black';
  }

  function getMovesForPiece(row, col) {
    return legalMoves.filter(m =>
      m.from_row === row && m.from_col === col
    );
  }

  function handleCellClick(row, col) {
    if (isBoardLocked) return;

    if (selectedPiece) {
      const targetMove = highlightedMoves.find(m =>
        m.to_row === row && m.to_col === col
      );
      if (targetMove) {
        traceMove('CheckersBoard', 'selecting move', targetMove);
        dispatch('select-move', targetMove);
        selectedPiece = null;
        highlightedMoves = [];
        return;
      }
    }

    if (isSelectable(row, col)) {
      const moves = getMovesForPiece(row, col);
      if (moves.length > 0) {
        selectedPiece = { row, col };
        highlightedMoves = moves;
      }
    } else {
      selectedPiece = null;
      highlightedMoves = [];
    }
  }

  function isHighlighted(row, col) {
    return highlightedMoves.some(m => m.to_row === row && m.to_col === col);
  }

  function pieceSymbol(piece) {
    if (!piece) return '';
    if (piece.type === 'red') return piece.king ? '👑' : '🔴';
    return piece.king ? '♛' : '⚫';
  }
</script>

<div class="checkers-board">
  {#if IS_DEV}<div class="panel-name-debug">CheckersBoard</div>{/if}

  {#if winner}
    <div class="winner-banner">
      {winner === 'player_1' ? 'Red' : 'Black'} wins!
    </div>
  {/if}

  <div class="board-grid" style="grid-template-columns: repeat({boardSize}, 1fr);">
    {#each cells as row, r}
      {#each row as cell, c}
        {@const isPendingSource = pendingMove?.from_row === r && pendingMove?.from_col === c}
        {@const isPendingDest = pendingMove?.to_row === r && pendingMove?.to_col === c}
        {@const piece = isPendingDest && pendingMove ? cells[pendingMove.from_row]?.[pendingMove.from_col]?.piece : isPendingSource ? null : cell.piece}
        <button
          class="cell"
          class:dark={cell.color === '#b58863'}
          class:selected={selectedPiece?.row === r && selectedPiece?.col === c}
          class:highlighted={isHighlighted(r, c)}
          class:selectable={isSelectable(r, c)}
          class:locked={isBoardLocked}
          style="background: {cell.color}"
          on:click={() => handleCellClick(r, c)}
          disabled={isBoardLocked}
        >
          {#if piece}
            <span class="piece" class:king={piece.king} style="color: {piece.color}">
              {pieceSymbol(piece)}
            </span>
          {/if}
          {#if isHighlighted(r, c)}
            <span class="move-dot"></span>
          {/if}
        </button>
      {/each}
    {/each}
  </div>

  <div class="board-info">
    {#if isBoardLocked && !winner}
      <span class="waiting">Waiting for opponent...</span>
    {:else}
      <span>Your turn — {currentPlayerId === 'player_1' ? 'Red' : 'Black'}</span>
    {/if}
    {#if phase}
      <span class="phase-info"> | {phase.phase_name}</span>
    {/if}
  </div>
</div>

<style>
  .checkers-board {
    width: 100%;
    padding: 1rem;
    box-sizing: border-box;
    background: #2c2c2c;
  }

  .panel-name-debug {
    font-size: 0.7rem;
    color: #999;
    font-family: monospace;
    margin-bottom: 0.5rem;
  }

  .winner-banner {
    background: #ffd700;
    color: #333;
    text-align: center;
    padding: 0.5rem;
    border-radius: 4px;
    font-weight: bold;
    margin-bottom: 0.5rem;
  }

  .board-grid {
    display: grid;
    gap: 0;
    max-width: 480px;
    margin: 0 auto;
    border: 2px solid #555;
  }

  .cell {
    aspect-ratio: 1;
    display: flex;
    align-items: center;
    justify-content: center;
    border: none;
    cursor: pointer;
    position: relative;
    font-size: 1.5rem;
    padding: 0;
    transition: background 0.15s;
  }

  .cell.selectable:hover {
    outline: 2px solid #ffd700;
    outline-offset: -2px;
    z-index: 1;
  }

  .cell.selected {
    outline: 3px solid #4a90e2;
    outline-offset: -3px;
    z-index: 1;
  }

  .cell.highlighted {
    background: rgba(74, 144, 226, 0.4) !important;
  }

  .cell.locked, .cell:disabled {
    cursor: default;
  }

  .piece {
    font-size: 1.6rem;
    line-height: 1;
    z-index: 2;
  }

  .piece.king {
    filter: drop-shadow(0 0 2px gold);
  }

  .move-dot {
    position: absolute;
    width: 12px;
    height: 12px;
    border-radius: 50%;
    background: rgba(255, 215, 0, 0.7);
    z-index: 3;
  }

  .board-info {
    text-align: center;
    margin-top: 0.5rem;
    color: #ccc;
    font-size: 0.85rem;
  }

  .phase-info {
    color: #999;
  }

  .waiting {
    color: #999;
    font-style: italic;
  }
</style>
