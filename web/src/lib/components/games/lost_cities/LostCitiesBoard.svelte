<script>
  import { createEventDispatcher } from 'svelte';
  import { IS_DEV, traceRender, traceMove } from '$lib/dev';
  import CardImage from '$lib/components/CardImage.svelte';

  export let game = null;
  export let gameId = 'lost_cities';
  export let legalMoves = [];
  export let screenState = null;
  export let pendingMove = null;

  const dispatch = createEventDispatcher();

  const COLORS = ['blue', 'yellow', 'red', 'white', 'green'];
  const COLOR_DISPLAY = {
    blue: 'Blue (Himalayas)',
    yellow: 'Yellow (Desert)',
    red: 'Red (Volcanoes)',
    white: 'White (Neptune\'s Realm)',
    green: 'Green (Rain Forest)',
  };
  const COLOR_HEX_MAP = {
    blue: '#3498db',
    yellow: '#f1c40f',
    red: '#e74c3c',
    white: '#ecf0f1',
    green: '#2ecc71',
  };

  let gameData = null;
  let currentPlayerId = 'player_1';
  let winner = null;
  let phase = null;
  let isBoardLocked = false;
  let hoverZoom = true;

  let selectedCard = null;
  let selectedHandIndex = null;

  $: {
    if (screenState?.game_data) {
      gameData = screenState.game_data;
      currentPlayerId = screenState.current_player || gameData?.current_player || 'player_1';
      winner = screenState.winner || null;
      phase = screenState.phase || null;
      legalMoves = screenState.legal_moves || [];
      hoverZoom = screenState.config?.hover_zoom !== false;
      isBoardLocked = !!winner || currentPlayerId !== 'player_1' || pendingMove !== null;
      traceRender('LostCitiesBoard', 'screenState updated', {
        currentPlayerId, winner, phase: phase?.phase_name,
        legalMoveCount: legalMoves.length,
        handSize: gameData?.player_hands?.player_1?.length,
      });
    } else if (game?.state?.game_data) {
      gameData = game.state.game_data;
      currentPlayerId = game?.state?.player_turn || 'player_1';
      winner = game?.state?.winner || null;
      legalMoves = game?.state?.legal_moves || [];
      isBoardLocked = !!winner || currentPlayerId !== 'player_1' || pendingMove !== null;
    } else {
      gameData = null;
    }
  }

  $: currentPhase = gameData?.current_phase || null;
  $: isPlayPhase = currentPhase === 'play_a_card' && !isBoardLocked;
  $: isDrawPhase = currentPhase === 'draw_a_card' && !isBoardLocked;

  $: sortedHand = (() => {
    const hand = gameData?.player_hands?.player_1;
    if (!hand) return [];
    const colorOrder = { blue: 0, yellow: 1, red: 2, white: 3, green: 4 };
    const COLOR_SHORT = { b: 'blue', y: 'yellow', r: 'red', w: 'white', g: 'green' };
    return hand.map((card, idx) => ({ card, origIdx: idx }))
      .sort((a, b) => {
        const aParts = a.card.card.split('_');
        const bParts = b.card.card.split('_');
        const aColor = colorOrder[COLOR_SHORT[aParts[0]]] ?? 99;
        const bColor = colorOrder[COLOR_SHORT[bParts[0]]] ?? 99;
        if (aColor !== bColor) return aColor - bColor;
        const aVal = aParts[1] === 'i' ? -1 : parseInt(aParts[1]);
        const bVal = bParts[1] === 'i' ? -1 : parseInt(bParts[1]);
        return aVal - bVal;
      });
  })();

  function clearSelection() {
    selectedCard = null;
    selectedHandIndex = null;
  }

  function handleCardClick(cardObj, idx) {
    if (isBoardLocked || isDrawPhase) return;
    if (selectedHandIndex === idx) {
      clearSelection();
      return;
    }
    selectedCard = cardObj;
    selectedHandIndex = idx;
    console.log('[LC] card selected', { card: cardObj.card, color: cardObj.color, legalMoveCount: legalMoves.length });
  }

  $: expeditionDestinations = (() => {
    if (!selectedCard || !isPlayPhase) return {};
    const map = {};
    for (const color of COLORS) {
      map[color] = legalMoves.some(m =>
        m.type === 'play_expedition' &&
        m.card === selectedCard.card &&
        m.color === color
      );
    }
    console.log('[LC] expeditionDestinations computed', { card: selectedCard.card, map });
    return map;
  })();

  $: discardDestinations = (() => {
    if (!selectedCard || !isPlayPhase) return {};
    const map = {};
    for (const color of COLORS) {
      map[color] = legalMoves.some(m =>
        m.type === 'discard' &&
        m.card === selectedCard.card &&
        m.color === color
      );
    }
    return map;
  })();

  function handleExpeditionClick(color) {
    if (!isPlayPhase || !selectedCard) return;
    const move = legalMoves.find(m =>
      m.type === 'play_expedition' &&
      m.card === selectedCard.card &&
      m.color === color
    );
    if (move) {
      clearSelection();
      traceMove('LostCitiesBoard', 'play expedition', move);
      dispatch('select-move', move);
    }
  }

  function handleDiscardPileClick(color) {
    if (isDrawPhase) {
      handleDraw(`${color}_discard`);
      return;
    }
    if (!isPlayPhase || !selectedCard) return;
    const move = legalMoves.find(m =>
      m.type === 'discard' &&
      m.card === selectedCard.card &&
      m.color === color
    );
    if (move) {
      clearSelection();
      traceMove('LostCitiesBoard', 'discard', move);
      dispatch('select-move', move);
    }
  }

  function handleDrawPileClick() {
    if (!isDrawPhase) return;
    handleDraw('draw_pile');
  }

  function handleDraw(source) {
    const move = legalMoves.find(m => m.type === 'draw' && m.source === source);
    if (move) {
      clearSelection();
      traceMove('LostCitiesBoard', 'draw', move);
      dispatch('select-move', move);
    }
  }

  function isDiscardSourceLegal(color) {
    if (!isDrawPhase) return false;
    return legalMoves.some(m => m.type === 'draw' && m.source === `${color}_discard`);
  }

  function isDrawPileLegal() {
    if (!isDrawPhase) return false;
    return legalMoves.some(m => m.type === 'draw' && m.source === 'draw_pile');
  }

  function cardStr(card) {
    if (!card) return '';
    if (typeof card === 'object') return card.card || '';
    return card;
  }

  function formatCardValue(card) {
    const s = cardStr(card);
    if (!s) return '';
    const parts = s.split('_');
    if (parts[1] === 'i') return '🤝';
    return parts[1];
  }

  function getExpeditionScore(cards) {
    if (!cards || cards.length === 0) return 0;
    let investmentCount = 0;
    let numberedSum = 0;
    let hasNumbered = false;
    for (const card of cards) {
      const s = cardStr(card);
      const parts = s.split('_');
      if (parts[1] === 'i') {
        investmentCount++;
      } else {
        numberedSum += parseInt(parts[1]);
        hasNumbered = true;
      }
    }
    let base = hasNumbered ? numberedSum - 20 : -20;
    const multiplier = 1 + investmentCount;
    let score = base * multiplier;
    if (cards.length >= 8) score += 20;
    return score;
  }

  function getCardImage(card) {
    if (!card) return '';
    if (typeof card === 'object') return card.image || '';
    const parts = card.split('_');
    const color = parts[0];
    const value = parts[1];
    if (value === 'i') {
      return `/api/v1/img/lost_cities/cards/${color}_i.jpg`;
    }
    return `/api/v1/img/lost_cities/cards/${color}_${value}.jpg`;
  }

  function getCardBack() {
    return `/api/v1/img/lost_cities/cards/card_backs.jpg`;
  }

  function getBaseImage(color) {
    const COLOR_SHORT = { blue: 'b', yellow: 'y', red: 'r', white: 'w', green: 'g' };
    return `/api/v1/img/lost_cities/cards/${COLOR_SHORT[color] || color}_base.jpg`;
  }
</script>

<div class="lost-cities-board">
  {#if IS_DEV}<div class="panel-name-debug">LostCitiesBoard</div>{/if}

  {#if winner}
    <div class="winner-banner">
      {winner === 'player_1' ? 'You win!' : 'AI wins!'} 
      {#if gameData?.scores}
        (You: {gameData.scores.player_1} | AI: {gameData.scores.player_2})
      {/if}
    </div>
  {/if}

  <div class="board-grid">
    <!-- Header row with color labels -->
    <div class="grid-row grid-header">
      <div class="grid-label">AI Expeditions</div>
      {#each COLORS as color}
        <div class="grid-label">{color}</div>
      {/each}
      <div class="grid-label">Draw</div>
    </div>

    <!-- Player 2 (AI) Expeditions -->
    <div class="grid-row">
      <div class="row-label">AI</div>
      {#each COLORS as color}
        <div class="grid-cell">
          <div class="card-slot expedition-slot ai" style="--color: {COLOR_HEX_MAP[color]}">
            <div class="expedition-cards">
              {#if gameData?.expeditions?.player_2?.[color]?.length}
                {#each gameData.expeditions.player_2[color] as card, idx}
                  <div class="expedition-card ai-card" style="z-index: {idx}">
                    <CardImage 
                      src="{getCardImage(card)}" 
                      alt="{COLOR_DISPLAY[color]} {formatCardValue(card)}"
                      hoverZoom={hoverZoom}
                    />
                  </div>
                {/each}
              {/if}
            </div>
          </div>
          <div class="expedition-score">
            {#if gameData?.expeditions?.player_2?.[color]}
              {getExpeditionScore(gameData.expeditions.player_2[color])}
            {/if}
          </div>
        </div>
      {/each}
      <div class="grid-cell draw-cell">
        <div 
          class="card-slot draw-pile-slot game-slot" 
          class:legal-destination={isDrawPileLegal()}
          on:click={handleDrawPileClick}
        >
          <div class="pile-cards draw-pile-cards">
            {#if gameData?.draw_pile?.count > 0}
              <div class="draw-top">
                <CardImage src="{gameData.draw_pile.image}" alt="Draw pile" hoverZoom={false} />
              </div>
              <span class="pile-count">{gameData.draw_pile.count}</span>
            {:else}
              <div class="empty-pile"></div>
            {/if}
          </div>
        </div>
        <div class="draw-label">Draw Pile</div>
      </div>
    </div>

    <!-- Discard Piles -->
    <div class="grid-row">
      <div class="row-label">Discard</div>
      {#each COLORS as color}
        <div class="grid-cell">
          <div 
            class="card-slot discard-slot game-slot" 
            class:legal-destination={discardDestinations[color]}
            class:legal-draw={isDiscardSourceLegal(color)}
            on:click={() => handleDiscardPileClick(color)}
          >
            <div class="pile-cards">
              {#if gameData?.discard_piles?.[color]?.top_card}
                <CardImage 
                  src="{gameData.discard_piles[color].top_card.image}" 
                  alt="{color} discard"
                  hoverZoom={hoverZoom}
                />
              {:else}
                <div class="empty-pile" style="background-image: url('{getBaseImage(color)}')"></div>
              {/if}
              {#if gameData?.discard_piles?.[color]?.count > 1}
                <span class="pile-count">{gameData.discard_piles[color].count}</span>
              {/if}
            </div>
          </div>
        </div>
      {/each}
      <div class="grid-cell"></div>
    </div>

    <!-- Player 1 (Human) Expeditions -->
    <div class="grid-row">
      <div class="row-label">You</div>
      {#each COLORS as color}
        <div class="grid-cell">
          <div 
            class="card-slot expedition-slot game-slot" 
            class:legal-destination={expeditionDestinations[color]}
            style="--color: {COLOR_HEX_MAP[color]}"
            on:click={() => handleExpeditionClick(color)}
          >
            <div class="expedition-cards">
              {#if gameData?.expeditions?.player_1?.[color]?.length}
                {#each gameData.expeditions.player_1[color] as card, idx}
                  <div class="expedition-card" style="z-index: {idx}">
                    <CardImage 
                      src="{getCardImage(card)}" 
                      alt="{COLOR_DISPLAY[color]} {formatCardValue(card)}"
                      hoverZoom={hoverZoom}
                    />
                  </div>
                {/each}
              {/if}
            </div>
          </div>
          <div class="expedition-score">
            {#if gameData?.expeditions?.player_1?.[color]}
              {getExpeditionScore(gameData.expeditions.player_1[color])}
            {/if}
          </div>
        </div>
      {/each}
      <div class="grid-cell"></div>
    </div>
  </div>

  <!-- Player Hand -->
  <div class="hand-area">
    <div class="hand-label">
      Your Hand 
      {#if isPlayPhase}
        <span class="phase-indicator">
          {#if selectedCard}
            Playing {selectedCard.card} — click a destination
          {:else}
            Click a card to play
          {/if}
        </span>
      {:else if isDrawPhase}
        <span class="phase-indicator">Draw a card from the pile or a discard</span>
      {/if}
    </div>
    <div class="hand-cards">
      {#if sortedHand.length}
        {#each sortedHand as item, idx}
          <div 
            class="hand-card game-card" 
            class:playable={isPlayPhase && legalMoves.some(m => m.type === 'play_expedition' && m.card === item.card.card) || legalMoves.some(m => m.type === 'discard' && m.card === item.card.card)}
            class:selected={selectedHandIndex === item.origIdx}
            on:click={() => handleCardClick(item.card, item.origIdx)}
          >
            {#if item.card.face_up !== false}
              <CardImage src="{item.card.image}" alt="{formatCardValue(item.card.card)}" hoverZoom={hoverZoom} />
            {:else}
              <CardImage src="{getCardBack()}" alt="Card back" hoverZoom={false} />
            {/if}
          </div>
        {/each}
      {/if}
    </div>
  </div>

  <div class="board-info">
    {#if isBoardLocked && !winner}
      <span class="waiting">Waiting for opponent...</span>
    {:else}
      <span>Your turn — Round {gameData?.round || 1}</span>
    {/if}
    {#if phase}
      <span class="phase-info"> | {phase.phase_name || phase}</span>
    {/if}
    {#if gameData?.scores}
      <span class="score-info">Score: You {gameData.scores.player_1} | AI {gameData.scores.player_2}</span>
    {/if}
    {#if gameData?.current_scores}
      <span class="current-score">This round: You {gameData.current_scores.player_1} | AI {gameData.current_scores.player_2}</span>
    {/if}
  </div>
</div>

<style>
  .lost-cities-board {
    width: 100%;
    padding: 1rem;
    box-sizing: border-box;
    background: #1a1a2e;
    color: #eee;
    font-family: system-ui, sans-serif;
  }

  .panel-name-debug {
    font-size: 0.7rem;
    color: #666;
    font-family: monospace;
    margin-bottom: 0.5rem;
  }

  .winner-banner {
    background: linear-gradient(135deg, #ffd700, #ffaa00);
    color: #333;
    text-align: center;
    padding: 1rem;
    border-radius: 8px;
    font-weight: bold;
    font-size: 1.2rem;
    margin-bottom: 1rem;
    box-shadow: 0 4px 12px rgba(255, 215, 0, 0.3);
  }

  .board-grid {
    display: grid;
    grid-template-columns: 100px repeat(5, 1fr) 120px;
    gap: 0.5rem;
    max-width: 900px;
    margin: 0 auto;
    padding: 0.5rem;
    background: rgba(255,255,255,0.02);
    border-radius: 8px;
  }

  .grid-row {
    display: contents;
  }

  .grid-header {
    display: contents;
  }

  .grid-header .grid-label {
    font-size: 0.65rem;
    color: #888;
    text-align: center;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    padding-bottom: 0.25rem;
    border-bottom: 1px solid #333;
  }

  .row-label {
    font-size: 0.75rem;
    font-weight: bold;
    color: #aaa;
    display: flex;
    align-items: center;
    justify-content: center;
    text-align: center;
  }

  .grid-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
  }

  .card-slot {
    width: 100%;
    aspect-ratio: 2/3;
    border-radius: 6px;
    border: 2px solid #444;
    position: relative;
    transition: all 0.2s;
  }

  .expedition-slot {
    border: 2px dashed var(--color);
    background: rgba(255, 255, 255, 0.01);
    aspect-ratio: unset;
    height: 250px;
  }

  .expedition-base {
    width: 100%;
    height: 100%;
    background-size: cover;
    background-position: center;
    border-radius: 4px;
  }

  .expedition-cards {
    position: absolute;
    width: 100%;
    height: 100%;
    top: 0;
    left: 0;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: flex-start;
    pointer-events: none;
  }

  .expedition-card {
    width: 80px;
    aspect-ratio: 2/3;
    border-radius: 4px;
    box-shadow: 0 2px 6px rgba(0,0,0,0.4);
    transition: transform 0.2s;
    margin-top: -100px;
    overflow: hidden;
  }

  .expedition-card:first-child {
    margin-top: 0;
  }

  .expedition-card.ai-card {
  }

  .expedition-card:hover {
    transform: translateY(-4px) scale(1.02);
    z-index: 100 !important;
  }

  .expedition-score {
    font-size: 0.7rem;
    font-weight: bold;
    color: #ffd700;
    text-shadow: 0 1px 2px #000;
  }

  .discard-slot {
    aspect-ratio: unset;
    height: 120px;
    width: 80px;
  }

  .discard-slot:hover {
    border-color: #ffd700;
    transform: scale(1.02);
  }

  .discard-slot .pile-cards {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    height: 100%;
  }

  .discard-slot .empty-pile {
    width: 100%;
    height: 100%;
  }

  .draw-cell {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.25rem;
  }

  .draw-pile-slot {
    cursor: pointer;
  }

  .draw-pile-slot:hover {
    border-color: #ffd700;
    transform: scale(1.02);
  }

  .draw-pile-cards {
    width: 100%;
    height: 100%;
    background: linear-gradient(135deg, #2c3e50, #1a1a2e);
    border: 2px dashed #555;
    border-radius: 4px;
    display: flex;
    flex-direction: column;
    align-items: center;
    justify-content: center;
    position: relative;
  }

  .draw-top {
    width: 80px;
    aspect-ratio: 2/3;
    border-radius: 4px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.5);
    overflow: hidden;
  }

  .draw-label {
    font-size: 0.65rem;
    color: #888;
    text-align: center;
    text-transform: uppercase;
  }

  .pile-cards {
    width: 100%;
    height: 100%;
    background-size: cover;
    background-position: center;
    border-radius: 4px;
    position: relative;
  }

  .empty-pile {
    width: 100%;
    height: 100%;
    background-size: cover;
    background-position: center;
    border-radius: 4px;
    opacity: 0.5;
  }

  .pile-count {
    position: absolute;
    bottom: 4px;
    right: 4px;
    background: rgba(0,0,0,0.8);
    color: #ffd700;
    padding: 2px 6px;
    border-radius: 10px;
    font-size: 0.65rem;
    font-weight: bold;
  }

  .hand-area {
    margin-top: 1rem;
    padding: 1rem;
    background: rgba(0,0,0,0.3);
    border-radius: 8px;
    border: 1px solid #333;
    max-width: 900px;
    margin-left: auto;
    margin-right: auto;
  }

  .hand-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    margin-bottom: 0.5rem;
    font-weight: bold;
    color: #ffd700;
  }

  .phase-indicator {
    font-size: 0.8rem;
    font-weight: normal;
    animation: pulse 1.5s infinite;
  }

  @keyframes pulse {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.6; }
  }

  .hand-cards {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
    justify-content: center;
    min-height: 120px;
  }

  .hand-card {
    position: relative;
    width: 80px;
    aspect-ratio: 2/3;
    border-radius: 6px;
    box-shadow: 0 4px 12px rgba(0,0,0,0.4);
    transition: all 0.2s;
    background: #1a1a2e;
    cursor: pointer;
  }

  .board-info {
    display: flex;
    flex-wrap: wrap;
    gap: 1rem;
    justify-content: center;
    margin-top: 1rem;
    padding: 0.5rem;
    color: #ccc;
    font-size: 0.85rem;
  }

  .waiting {
    color: #999;
    font-style: italic;
  }

  .phase-info {
    color: #999;
  }

  .score-info {
    font-weight: bold;
    color: #ffd700;
  }

  .current-score {
    color: #888;
    font-size: 0.8rem;
  }

  @media (max-width: 900px) {
    .board-grid {
      grid-template-columns: 70px repeat(5, 1fr) 90px;
      gap: 0.25rem;
    }

    .hand-card {
      width: 65px;
    }

    .expedition-slot {
      height: 190px;
    }

    .expedition-card {
      width: 65px;
      margin-top: -83px;
    }

    .draw-top {
      width: 65px;
    }

    .discard-slot {
      height: 98px;
      width: 65px;
    }
  }
</style>