<script>
  import { createEventDispatcher } from 'svelte';
  import { IS_DEV } from '$lib/dev';
  import { API_BASE } from '$lib/api';

  export let game = null;
  export let legalMoves = [];
  export let screenState = null;
  export let actionInProgress = false;
  export let deployment_zones = [];
  export let scenario_id = null;
  let gameId = 'fields_of_fire';
  let pendingMove = null;
  let lastSelectedMove = null;

  const dispatch = createEventDispatcher();

  let mapCards = [];
  let units = [];
  let markers = [];
  let vofMarkers = [];
  let currentPlayerId = 'player_1';
  let phase = null;
  let winner = null;
  let setupStatus = { complete: false, reason: '', placed: 0, total: 0 };
  let selectedUnitType = null;
  let popupIdx = null;
  let popupPos = { x: 0, y: 0 };
  let terrainDecks = [];
  let cardLayout = [];
  let gridRows = 3;
  let gridCols = 4;

  function getCardImageUrl(cardId) {
    if (!cardId) return null;
    // Check for deployment zones
    if (cardId.startsWith('DZ_')) {
      const camp = scenario_id || '';
      if (camp.includes('heartbreak')) return `${API_BASE}/img/fof/Shared Assets/Card Backs/Card Back - Heartbreak Ridge.png`;
      if (camp.includes('naktong')) return `${API_BASE}/img/fof/Shared Assets/Card Backs/Card Back - Naktong River.png`;
      if (camp.includes('vietnam')) return `${API_BASE}/img/fof/Shared Assets/Card Backs/Card Back - Vietnam.jpg`;
      // Default to normandy
      return `${API_BASE}/img/fof/Shared Assets/Card Backs/Card Back - Normandy.jpg`;
    }
    // Map known cards to their actual filenames
    const cardMap = {
      'N41': 'N41 Open Fields.jpg',
      'N10': 'N10 Orchard Grove.jpg',
      'N17': 'N17 Woods.jpg',
      'N01': 'N01 Orchard Grove.jpg',
      'N09': 'N09 Plowed Fields.jpg',
      'N18': 'N18 Woods.jpg',
      'N19': 'N19 Woods.jpg',
      'N42': 'N42 Open Fields.jpg',
      'N43': 'N43 Open Fields.jpg',
      'N44': 'N44 Open Fields.jpg'
    };
    if (cardMap[cardId]) {
      return `${API_BASE}/img/fof/Cards/Starter 1 Terrain/${encodeURIComponent(cardMap[cardId])}`;
    }
    // Try common patterns
    return `${API_BASE}/img/fof/Cards/Starter 1 Terrain/${encodeURIComponent(cardId + ' Open Fields.jpg')}`;
  }

  function getRandomCardFromDecks() {
    if (!terrainDecks || terrainDecks.length === 0) return null;
    // Simple random selection - in a real scenario this would be more complex
    const deckName = terrainDecks[0];
    // For now return null and let backend handle, or use a placeholder
    return null;
  }

  $: {
    if (screenState?.game_data) {
      const gd = screenState.game_data;
      mapCards = gd.map?.cards || [];
      terrainDecks = gd.map?.decks || [];
      cardLayout = gd.map?.card_layout || [];
      gridRows = gd.map?.rows || gridRows;
      gridCols = gd.map?.cols || gridCols;
      units = gd.company?.units || [];
      markers = gd.markers || [];
      vofMarkers = gd.vof_markers || [];
      currentPlayerId = screenState.current_player || gd.current_player || 'player_1';
      winner = screenState.winner || gd.winner || null;
      legalMoves = screenState.legal_moves || legalMoves;
      // Handle phase as string or object
      const rawPhase = screenState.phase || gd.phase;
      phase = typeof rawPhase === 'string' ? { phase_name: rawPhase, confirm_required: screenState.phase?.confirm_required || false } : (rawPhase || null);
      deployment_zones = gd.deployment_zones || deployment_zones;
      scenario_id = gd.scenario_id || scenario_id;
    } else if (game?.state?.game_data) {
      const gd = game.state.game_data;
      mapCards = gd.map?.cards || [];
      terrainDecks = gd.map?.decks || [];
      cardLayout = gd.map?.card_layout || [];
      gridRows = gd.map?.rows || gridRows;
      gridCols = gd.map?.cols || gridCols;
      units = gd.company?.units || [];
      markers = gd.markers || [];
      vofMarkers = gd.vof_markers || [];
      currentPlayerId = game?.state?.player_turn || 'player_1';
      winner = game?.state?.winner || null;
      phase = gd.phase ? { phase_name: gd.phase, confirm_required: false } : null;
      deployment_zones = gd.deployment_zones || deployment_zones;
      scenario_id = gd.scenario_id || scenario_id;
    } else {
      mapCards = [];
      units = [];
      markers = [];
      vofMarkers = [];
      terrainDecks = [];
      cardLayout = [];
    }
  }

  // Compute setup status
  $: {
    if (phase?.phase_name === 'setup') {
      const placedUnits = units.filter(u => u.position !== null && u.position !== undefined);
      setupStatus = {
        complete: placedUnits.length === units.length && (mapCards.length === 0 || !mapCards.every(c => c === null)),
        reason: placedUnits.length < units.length ? `${units.length - placedUnits.length} units remaining` : 'All units placed',
        placed: placedUnits.length,
        total: units.length
      };
    } else {
      setupStatus = { complete: true, reason: '', placed: units.length, total: units.length };
    }
  }

  function getCardAtPosition(row, col) {
    // Check card_layout first (has position info)
    if (cardLayout && Array.isArray(cardLayout)) {
      const found = cardLayout.find(c => c && typeof c === 'object' && c.row === row && c.col === col);
      if (found && found.id) {
        if (found.deployment_zone && !found.id.startsWith('DZ_')) {
          // Assign deployment zone card based on scenario
          const camp = scenario_id || '';
          let dzId = 'DZ_NORMANDY';
          if (camp.includes('heartbreak')) dzId = 'DZ_HEARTBREAK';
          else if (camp.includes('naktong')) dzId = 'DZ_NAKTONG';
          else if (camp.includes('vietnam')) dzId = 'DZ_VIETNAM';
          return { id: dzId, fromLayout: true, image: getCardImageUrl(dzId), deployment_zone: true };
        }
        return { id: found.id, fromLayout: true, image: getCardImageUrl(found.id), deployment_zone: found.deployment_zone };
      }
      if (found && found.id === null) {
        return null;
      }
    }
    // Fall back to mapCards array indexed by row*cols + col
    const gd = screenState?.game_data || game?.state?.game_data || {};
    const rows = gd.map?.rows || 3;
    const cols = gd.map?.cols || 4;
    const idx = row * cols + col;
    if (mapCards && mapCards[idx]) {
      const card = mapCards[idx];
      if (typeof card === 'string') {
        return { id: card, fromLayout: false, image: getCardImageUrl(card) };
      }
      if (typeof card === 'object') {
        if (card.image) return card;
        if (card.id) return { ...card, image: card.image || getCardImageUrl(card.id) };
        return card;
      }
    }
    return null;
  }

  function getUnitsAtCard(idx) {
    return units.filter(u => u.position === idx);
  }

  function hasLegalMoves(idx) {
    return legalMoves.some(m => m.position === idx);
  }

  function getLegalMoveForCard(idx, moveType = null) {
    if (moveType) {
      return legalMoves.find(m => m.position === idx && m.type === moveType);
    }
    return legalMoves.find(m => m.position === idx);
  }

  // Find a legal move by type
  function getLegalMoveByType(type) {
    return legalMoves.find(m => m.type === type);
  }

  function handleCardClick(event, idx) {
    if (winner || actionInProgress) return;

    const phaseName = phase?.phase_name || phase;

    // Setup phase: place units
    if (phaseName === 'setup') {
      const renderRow = Math.floor(idx / gridCols);
      const colIdx = idx % gridCols;
      // Check cardLayout for deployment_zone flag (mapCards only stores ID strings)
      const layoutCard = cardLayout?.find(c => c && typeof c === 'object' && c.row === renderRow && c.col === colIdx);
      const isDZ = layoutCard?.deployment_zone ||
        (layoutCard?.id && String(layoutCard.id).startsWith('DZ_')) ||
        (deployment_zones && deployment_zones.includes(idx));

      if (!isDZ) return;

      // Show compact unit type selector popup above the clicked tile
      popupIdx = idx;
      const cardEl = event.currentTarget;
      const cardRect = cardEl.getBoundingClientRect();
      const containerEl = document.querySelector('.fof-board');
      const containerRect = containerEl ? containerEl.getBoundingClientRect() : { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
      const popupWidth = 220;
      const popupHeight = 140;
      // Center popup's center on card's center, relative to container
      let cardCenterX = cardRect.left - containerRect.left + cardRect.width / 2;
      let x = cardCenterX - popupWidth / 2;
      let y = cardRect.top - containerRect.top - popupHeight - 50;
      // Clamp to container edges with 8px margin
      if (x < 8) x = 8;
      if (x + popupWidth > containerRect.width - 8) x = containerRect.width - popupWidth - 8;
      if (y < 8) {
        y = cardRect.bottom - containerRect.top + 50;
        if (y + popupHeight > containerRect.height - 8) y = containerRect.height - popupHeight - 8;
      }
      popupPos = { x: Math.max(8, x), y: Math.max(8, y) };
      return;
    }

    // Gameplay phase: find legal move for this card
    const move = getLegalMoveForCard(idx);
    if (move) {
      dispatch('select-move', move);
    }
  }

  function placeUnitAtPopup(unitType) {
    if (popupIdx === null) return;
    const move = legalMoves.find(m =>
      m.type === 'place_unit' &&
      m.unit_id && m.unit_id.includes(unitType)
    );
    if (move) {
      const moveWithPosition = { ...move, position: popupIdx };
      dispatch('select-move', moveWithPosition);
    }
    popupIdx = null;
  }

  function cancelPopup() {
    popupIdx = null;
  }

  function getCardImage(card) {
    if (!card) return null;
    if (typeof card === 'object') {
      if (card.image) return card.image;
      if (card.id) return getCardImageUrl(card.id);
      // Check if it's a string card id
      return null;
    }
    if (typeof card === 'string') {
      return getCardImageUrl(card);
    }
    return null;
  }

  function getUnitLabel(unit) {
    return unit.type || unit.id || '?';
  }

  function getUnitColor(unit) {
    const colors = {
      squad: '#4a90e2',
      hq: '#e74c3c',
      weapon_team: '#27ae60',
      mortar_team: '#8e44ad',
      at_team: '#f39c12',
      vehicle: '#95a5a6',
      helicopter: '#1abc9c'
    };
    return colors[unit.type] || '#888';
  }
</script>

<div class="fof-board">
  {#if IS_DEV}<div class="panel-name-debug">FieldsOfFireBoard</div>{/if}

  {#if winner}
    <div class="winner-banner">
      Mission complete - {winner} wins!
    </div>
  {/if}

  <div class="info-bar">
    <span>Player: {currentPlayerId}</span>
    {#if phase}
      <span> | Phase: {phase.phase_name || phase}</span>
    {/if}
    {#if scenario_id}
      <span> | Scenario: {scenario_id}</span>
    {/if}
    <span> | Units: {units.length}</span>
    {#if phase?.phase_name === 'setup'}
      <span> | Placed: {setupStatus.placed}/{setupStatus.total}</span>
    {/if}
  </div>

  <!-- Setup Phase: Unit Type Selection Panel -->
  {#if phase?.phase_name === 'setup'}
    <div class="setup-panel">
      <div class="setup-status">
        <div class="progress-bar">
          <div class="progress-fill" style="width: {setupStatus.total > 0 ? (setupStatus.placed / setupStatus.total * 100) : 0}%"></div>
        </div>
        <span class="setup-text">
          {setupStatus.placed}/{setupStatus.total} units placed
          {#if !setupStatus.complete}
            — {setupStatus.reason}
          {/if}
        </span>
      </div>

      {#if popupIdx !== null}
        <div class="unit-popup" style="left: {popupPos.x}px; top: {popupPos.y}px;">
          <div class="popup-header">
            <span>Place unit at {popupIdx}</span>
            <button class="cancel-btn" on:click={cancelPopup}>Cancel</button>
          </div>
          <div class="unit-type-buttons compact">
            <button class="unit-type-btn" class:selected={selectedUnitType === 'squad'} on:click={() => placeUnitAtPopup('squad')}>Squad</button>
            <button class="unit-type-btn" class:selected={selectedUnitType === 'hq'} on:click={() => placeUnitAtPopup('hq')}>HQ</button>
            <button class="unit-type-btn" class:selected={selectedUnitType === 'weapon_team'} on:click={() => placeUnitAtPopup('weapon_team')}>Weapon Team</button>
            <button class="unit-type-btn" class:selected={selectedUnitType === 'mortar_team'} on:click={() => placeUnitAtPopup('mortar_team')}>Mortar Team</button>
            <button class="unit-type-btn" class:selected={selectedUnitType === 'at_team'} on:click={() => placeUnitAtPopup('at_team')}>AT Team</button>
            <button class="unit-type-btn" class:selected={selectedUnitType === 'vehicle'} on:click={() => placeUnitAtPopup('vehicle')}>Vehicle</button>
            <button class="unit-type-btn" class:selected={selectedUnitType === 'helicopter'} on:click={() => placeUnitAtPopup('helicopter')}>Helicopter</button>
          </div>
        </div>
      {/if}
    </div>
  {/if}

                  <!-- Map Grid -->
  <div class="map-container">
    <div class="map-grid" style="grid-template-columns: repeat({gridCols}, 1fr); --fof-cols: {gridCols}; --fof-card-height: 150px;">
    {#each Array(gridRows) as _, rowIdx}
      {@const renderRow = gridRows - 1 - rowIdx}
      {#each Array(gridCols) as _, colIdx}
        {@const idx = renderRow * gridCols + colIdx}
        {@const card = mapCards[idx]}
        {@const c = typeof card === 'object' ? card : (typeof card === 'string' ? { id: card } : null)}
        {@const dz = c?.deployment_zone || (c?.id && String(c.id).startsWith('DZ_')) || (deployment_zones && deployment_zones.includes(idx))}
        <button
          class="map-card"
          class:empty={card === null || card === undefined}
          class:deployment-zone={dz}
          class:has-legal-moves={hasLegalMoves(idx)}
          class:placing-target={popupIdx === idx}
          on:click={(e) => handleCardClick(e, idx)}
          disabled={!!winner || actionInProgress}
        >
          {#if dz}
            <div class="deployment-overlay"></div>
          {/if}
          {#if hasLegalMoves(idx) && phase?.phase_name !== 'setup'}
            <div class="legal-move-overlay"></div>
          {/if}
          {#if card}
            {@const img = c?.image || (c?.id ? getCardImageUrl(c.id) : getCardImage(card))}
            {#if img}
              <img src={img} alt={c?.name || c?.type || c?.id || 'terrain'} class="card-image" />
            {:else}
              <div class="card-label">{c?.name || c?.type || c?.id || idx}</div>
            {/if}
            {#if c?.elevation && !dz}
              <span class="elevation">?{c.elevation}</span>
            {/if}
            {#if c?.cover_high && !dz}
              <span class="cover">C{c.cover_high}</span>
            {/if}
          {:else}
            <div class="empty-card">-</div>
          {/if}
          {#each getUnitsAtCard(idx) as unit, uIdx}
            <div
              class="unit-marker"
              style="background: {getUnitColor(unit)}; bottom: {4 + uIdx * 16}px; left: 4px;"
              title={unit.id || unit.type}
            >
              {getUnitLabel(unit)}
            </div>
          {/each}
        </button>
      {/each}
      {/each}
    </div>
  </div>

  <div class="board-info">
    <div class="markers">
      <strong>Markers:</strong> {markers.length} | <strong>VOF:</strong> {vofMarkers.length}
    </div>
  </div>
</div>

<style>
  .fof-board {
    width: 100%;
    padding: 1rem;
    box-sizing: border-box;
    background: #3a3a2a;
    position: relative;
  }

  .panel-name-debug {
    font-size: 0.7rem;
    color: #999;
    font-family: monospace;
    margin-bottom: 0.5rem;
  }

  .winner-banner {
    background: #8b7355;
    color: #fff;
    text-align: center;
    padding: 0.5rem;
    border-radius: 4px;
    font-weight: bold;
    margin-bottom: 0.5rem;
  }

  .info-bar {
    text-align: center;
    margin-bottom: 0.5rem;
    color: #ddd;
    font-size: 0.85rem;
  }

  .setup-panel {
    background: #2a2a1a;
    border: 1px solid #555;
    border-radius: 8px;
    padding: 1rem;
    margin-bottom: 1rem;
    max-width: 800px;
    margin-left: auto;
    margin-right: auto;
  }

  .setup-status {
    margin-bottom: 0.75rem;
  }

  .progress-bar {
    width: 100%;
    height: 8px;
    background: #1a1a0a;
    border-radius: 4px;
    overflow: hidden;
    margin-bottom: 0.5rem;
  }

  .progress-fill {
    height: 100%;
    background: #27ae60;
    transition: width 0.3s ease;
  }

  .setup-text {
    font-size: 0.8rem;
    color: #ccc;
  }

  .unit-type-buttons {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
  }

  .unit-type-btn {
    padding: 0.4rem 0.8rem;
    background: #4a4a3a;
    color: #ddd;
    border: 1px solid #666;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.75rem;
    transition: all 0.15s ease;
  }

  .unit-type-btn:hover {
    background: #5a5a4a;
    border-color: #ffd700;
  }

  .unit-type-btn.selected {
    background: #27ae60;
    color: #fff;
    border-color: #27ae60;
  }

  .cancel-btn {
    padding: 0.4rem 0.8rem;
    background: #c0392b;
    color: #fff;
    border: 1px solid #c0392b;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.75rem;
  }

  .unit-popup {
    position: absolute;
    background: #2a2a1a;
    border: 2px solid #ffd700;
    border-radius: 8px;
    padding: 0.75rem;
    z-index: 200;
    min-width: 220px;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  }

  .unit-popup .popup-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 0.5rem;
  }

  .unit-popup .popup-header span {
    font-size: 0.8rem;
    color: #ffd700;
    font-weight: 600;
  }

  .unit-popup .cancel-btn {
    padding: 0.25rem 0.6rem;
    background: transparent;
    color: #ffd700;
    border: 1px solid #ffd700;
    cursor: pointer;
    font-size: 0.7rem;
  }

  .unit-popup .cancel-btn:hover {
    background: #ffd700;
    color: #2a2a1a;
  }

  .unit-popup .unit-type-buttons.compact {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 0.4rem;
    margin-bottom: 0;
  }

  .unit-popup .unit-type-btn {
    padding: 0.5rem;
    font-size: 0.7rem;
  }

  .map-container {
    position: relative;
    width: 100%;
    max-width: 800px;
    margin: 0 auto;
  }

  .map-grid {
    display: grid;
    grid-template-columns: repeat(var(--fof-cols, 4), 1fr);
    gap: calc(var(--fof-card-height, 150px) * 0.2);
    max-width: 800px;
    margin: 0 auto;
    background: #2a2a1a;
    padding: calc(var(--fof-card-height, 150px) * 0.2);
  }

  .map-card {
    aspect-ratio: 3/4;
    border: 1px solid #555;
    background: #4a4a3a;
    cursor: pointer;
    position: relative;
    padding: 0;
    overflow: hidden;
  }

  .map-card.empty {
    background: #2a2a1a;
  }

  .map-card:hover:not(:disabled) {
    border-color: #ffd700;
  }

  .map-card.deployment-zone {
    border-color: #4a90e2;
  }

  .map-card.has-legal-moves {
    box-shadow: 0 0 0 2px rgba(255, 215, 0, 0.5);
  }

  .map-card.placing-target {
    cursor: crosshair;
    border-color: #27ae60;
  }

  .map-card:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .deployment-overlay {
    position: absolute;
    inset: 0;
    background: rgba(74, 144, 226, 0.2);
    pointer-events: none;
    z-index: 1;
  }

  .legal-move-overlay {
    position: absolute;
    inset: 0;
    background: rgba(255, 215, 0, 0.15);
    pointer-events: none;
    z-index: 1;
  }

  .card-image {
    width: 100%;
    height: 100%;
    object-fit: cover;
  }

  .card-label {
    font-size: 0.6rem;
    color: #ddd;
    padding: 0.2rem;
    text-align: center;
  }

  .empty-card {
    color: #666;
    text-align: center;
    padding-top: 50%;
  }

  .elevation, .cover {
    position: absolute;
    top: 2px;
    right: 2px;
    background: rgba(0,0,0,0.7);
    color: #ffd700;
    font-size: 0.5rem;
    padding: 1px 3px;
    border-radius: 2px;
    z-index: 2;
  }

  .cover {
    top: 12px;
    color: #87ceeb;
  }

  .unit-marker {
    position: absolute;
    width: 14px;
    height: 14px;
    border-radius: 3px;
    color: #fff;
    font-size: 0.5rem;
    font-weight: bold;
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 3;
    border: 1px solid rgba(255,255,255,0.3);
  }

  .board-info {
    text-align: center;
    margin-top: 0.5rem;
    color: #ccc;
    font-size: 0.8rem;
  }
</style>
