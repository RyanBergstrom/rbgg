<script>
  import { createEventDispatcher, onDestroy } from 'svelte';
  import { IS_DEV } from '$lib/dev';
  import { API_BASE } from '$lib/api';
  import { fofCommand } from '$lib/stores/fofCommand';
import { eligibleMoveUnits, validMoveDestinations, movementAction as movementActionStore } from '$lib/stores/fofCommand';
  import TurnSequenceTracker from './TurnSequenceTracker.svelte';

  export let game = null;
  export let legalMoves = [];
  export let screenState = null;
  export let auditEntries = [];
  export let actionInProgress = false;
  export let deployment_zones = [];
  export let scenario_id = null;
  let gameId = 'fields_of_fire';
  let pendingMove = null;
  let lastSelectedMove = null;

  const dispatch = createEventDispatcher();

  // Publish the command state so the footer can render the command controls.
  $: fofCommand.set({
    legalMoves,
    pool: commandPool,
    pools: commandPools,
    lastDraw: lastCommandDraw,
    lastFire: screenState?.last_fire_result ?? null,
    activated: commandActivated,
    hqLabels,
    hqOrder,
    phaseName: phase?.phase_name || phase,
    dispatchMove: (move) => dispatch('select-move', move),
  });
  onDestroy(() => fofCommand.set(null));

  // Movement action derived stores for board highlighting
  $: eligibleUnitIds = $eligibleMoveUnits;
  $: validDestIds = $validMoveDestinations;

  let mapCards = [];
  let units = [];
  let unitsByCard = {};
  let stacksByCard = {};
  let markers = [];
  let vofMarkers = [];
  let pcMarkers = [];
  let currentPlayerId = 'player_1';
  let phase = null;
  let winner = null;
  let turnNumber = 1;
  let setupStatus = { complete: false, reason: '', placed: 0, total: 0 };
  let availableSetupUnits = [];
  let popupIdx = null;
  let popupStackId = null;
  let focusedStack = null;
  let movingSelection = null;
  let moveSelectionError = '';
  let hoveredStack = null;
  let hoverTimer = null;
  let discardHovered = false;
  let discardHoverTimer = null;
  function startDiscardHover() {
    clearDiscardHover();
    discardHoverTimer = window.setTimeout(() => {
      discardHovered = true;
      discardHoverTimer = null;
    }, 1000);
  }
  function clearDiscardHover() {
    if (discardHoverTimer !== null) {
      window.clearTimeout(discardHoverTimer);
      discardHoverTimer = null;
    }
    discardHovered = false;
  }
  let popupPos = { x: 0, y: 0 };
  let terrainDecks = [];
  let cardLayout = [];
  let gridRows = 3;
  let gridCols = 4;
  let turnSequence = [];
  $: actionDeck = (screenState?.game_data || game?.state?.game_data || {}).action_deck || null;
  $: cardsLeft = actionDeck?.draw_pile?.length ?? 0;
  $: discardPile = actionDeck?.discard || [];
  $: discardCount = discardPile.length;
  $: topDiscardId = discardPile.length ? discardPile[discardPile.length - 1] : null;
  $: topDiscardNum = topDiscardId ? (parseInt((topDiscardId.match(/(\d+)$/) || [])[1] || '0', 10)) : 0;
  $: topDiscard = screenState?.game_data?.top_discard || null;
  $: topDiscardUrl = topDiscard?.image_url
    ? (topDiscard.image_url.startsWith('http') ? topDiscard.image_url : `${API_BASE.replace(/\/api\/v1\/?$/, '')}${topDiscard.image_url}`)
    : (topDiscardNum > 0 ? `${API_BASE}/img/fof/cards/Action Cards Draw/A${String(topDiscardNum).padStart(2, '0')}.jpg` : null);
  let auditCollapsed = false;
  function formatAuditTime(ts) {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
  let durationTurns = null;
  let commandPool = 0;
  let commandActivated = [];
  let commandPools = {};
  let lastCommandDraw = null;
  let hqLabels = {};
  let hqOrder = [];

  function getCardImageUrl(cardId) {
    if (!cardId) return null;
    // Check for deployment zones
    if (cardId.startsWith('DZ_')) {
      const camp = scenario_id || '';
      if (camp.includes('heartbreak')) return `${API_BASE}/img/fof/cards/Card Back - Heartbreak Ridge.png`;
      if (camp.includes('naktong')) return `${API_BASE}/img/fof/cards/Card Back - Naktong River.png`;
      if (camp.includes('vietnam')) return `${API_BASE}/img/fof/cards/Card Back - Vietnam.jpg`;
      // Default to normandy
      return `${API_BASE}/img/fof/cards/Card Back - Normandy.jpg`;
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
      return `${API_BASE}/img/fof/cards/${encodeURIComponent(cardMap[cardId])}`;
    }
    // Try common patterns
    return `${API_BASE}/img/fof/cards/${encodeURIComponent(cardId + ' Open Fields.jpg')}`;
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
      pcMarkers = gd.pc_markers || [];
      currentPlayerId = screenState.current_player || gd.current_player || 'player_1';
      winner = screenState.winner || gd.winner || null;
      turnSequence = screenState.game_data?.turn_sequence || [];
      turnNumber = gd.turn || 1;
      durationTurns = screenState.game_data?.duration_turns ?? null;
      commandPool = gd.company?.command?.commands_pool ?? 0;
      commandActivated = gd.company?.command?.activated ?? [];
      commandPools = gd.company?.command?.pool_by_hq ?? {};
      lastCommandDraw = screenState.game_data?.last_command_draw ?? null;
      hqOrder = [
        gd.company?.command?.bn_hq,
        gd.company?.command?.co_hq,
        ...(gd.company?.command?.plt_hqs || []),
        ...(gd.company?.command?.co_staff || []),
      ].filter(Boolean);
      hqLabels = {
        ...Object.fromEntries((gd.company?.units || []).map(u => [u.id, getUnitDisplayName(u)])),
        bn_hq_1: 'Battalion HQ',
      };
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
      pcMarkers = gd.pc_markers || [];
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
      pcMarkers = [];
      terrainDecks = [];
      cardLayout = [];
    }
  }

  // Compute setup status
  $: {
    if (phase?.phase_name === 'setup') {
      const requiredUnits = units.filter(u => u.setup_required !== false);
      const placedUnits = requiredUnits.filter(u => u.position !== null && u.position !== undefined);
      availableSetupUnits = requiredUnits.filter(u =>
        (u.position === null || u.position === undefined) &&
        legalMoves.some(move => move.type === 'place_unit' && move.unit_id === u.id)
      );
      setupStatus = {
        complete: placedUnits.length === requiredUnits.length && (mapCards.length === 0 || !mapCards.every(c => c === null)),
        reason: placedUnits.length < requiredUnits.length ? `${requiredUnits.length - placedUnits.length} units remaining` : 'All units placed',
        placed: placedUnits.length,
        total: requiredUnits.length
      };
    } else {
      availableSetupUnits = [];
      setupStatus = { complete: true, reason: '', placed: units.length, total: units.length };
    }
  }

  // Build this from the reactive units array rather than calling a helper
  // inside the each block; Svelte otherwise cannot track that helper's
  // dependency and newly placed counters do not appear until a page reload.
  $: {
    const groupedUnits = {};
    const groupedStacks = {};
    for (const [fallbackOrder, unit] of units.entries()) {
      if (unit.position === null || unit.position === undefined) continue;
      (groupedUnits[unit.position] ||= []).push({ unit, fallbackOrder });
      const stackId = unit.stack_id || `legacy-stack-${unit.position}`;
      const stackKey = `${unit.position}:${stackId}`;
      const stack = groupedStacks[stackKey] ||= { position: unit.position, stackId, entries: [] };
      stack.entries.push({ unit, fallbackOrder });
    }
    unitsByCard = Object.fromEntries(Object.entries(groupedUnits).map(([position, entries]) => [
      position,
      entries
        .sort((a, b) => (a.unit.stack_order ?? a.fallbackOrder) - (b.unit.stack_order ?? b.fallbackOrder))
        .map(entry => entry.unit)
    ]));
    stacksByCard = {};
    for (const stack of Object.values(groupedStacks)) {
      stack.units = stack.entries
        .sort((a, b) => (a.unit.stack_order ?? a.fallbackOrder) - (b.unit.stack_order ?? b.fallbackOrder))
        .map(entry => entry.unit);
      delete stack.entries;
      (stacksByCard[stack.position] ||= []).push(stack);
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
    if (phaseName === 'setup' && !isStagingCard(idx)) return;

    if (movingSelection) {
      submitStackMove(idx, stackId);
      return;
    }

    // Setup phase: choose any card as a destination for a new stack.
    if (phaseName === 'setup') {
      focusedStack = null;
      popupIdx = idx;
      popupStackId = createStackId(idx);
      positionPopup(event.currentTarget);
      return;
    }

    // Gameplay phase: find legal move for this card
    const move = getLegalMoveForCard(idx);
    if (move) {
      dispatch('select-move', move);
    }
  }

  function placeUnitAtPopup(unitId) {
    if (popupIdx === null) return;
    const move = legalMoves.find(m => m.type === 'place_unit' && m.unit_id === unitId);
    if (move) {
      const moveWithPosition = { ...move, position: popupIdx, stack_id: popupStackId };
      dispatch('select-move', moveWithPosition);
    }
    popupIdx = null;
    popupStackId = null;
  }

  function createStackId(position) {
    const suffix = typeof crypto !== 'undefined' && crypto.randomUUID
      ? crypto.randomUUID()
      : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
    return `stack-${position}-${suffix}`;
  }

  function positionPopup(anchor) {
    const cardRect = anchor.getBoundingClientRect();
    if (focusedStack !== null && phase?.phase_name === 'setup') {
      const popupWidth = Math.min(760, window.innerWidth - 32);
      const popupHeight = Math.min(520, window.innerHeight * 0.72);
      const x = Math.max(16, Math.min(
        cardRect.left + cardRect.width / 2 - popupWidth / 2,
        window.innerWidth - popupWidth - 16
      ));
      let y = cardRect.top - popupHeight - 12;
      if (y < 16) y = cardRect.bottom + 12;
      y = Math.max(16, Math.min(y, window.innerHeight - popupHeight - 16));
      popupPos = { x, y };
      return;
    }
    const containerEl = document.querySelector('.fof-board');
    const containerRect = containerEl ? containerEl.getBoundingClientRect() : { left: 0, top: 0, width: window.innerWidth, height: window.innerHeight };
    const desiredWidth = focusedStack !== null && phase?.phase_name === 'setup' ? 760 : 400;
    const popupWidth = Math.min(desiredWidth, containerRect.width - 16);
    const popupHeight = Math.min(520, containerRect.height * 0.78);
    const centerX = cardRect.left - containerRect.left + cardRect.width / 2;
    let x = centerX - popupWidth / 2;
    let y = cardRect.top - containerRect.top - popupHeight - 12;
    x = Math.max(8, Math.min(x, containerRect.width - popupWidth - 8));
    if (y < 8) y = Math.min(cardRect.bottom - containerRect.top + 12, containerRect.height - popupHeight - 8);
    popupPos = { x: Math.max(8, x), y: Math.max(8, y) };
  }

  function handleCounterClick(event, idx, stackId) {
    event.stopPropagation();
    if (winner || actionInProgress) return;
    if (phase?.phase_name === 'setup' && !isStagingCard(idx)) return;
    if (movingSelection) {
      submitStackMove(idx, stackId);
      return;
    }
    
    // Check if we're in movement action mode
    const $movementAction = $movementActionStore;
    if ($movementAction.type && $movementAction.step === 'select_unit') {
      // Find the unit ID from the clicked counter
      const unitId = event.currentTarget.getAttribute('data-unit-id');
      if (unitId) {
        movementActionStore.set({
          type: $movementAction.type,
          step: 'select_destination',
          selectedUnitId: unitId,
          originatorId: $movementAction.originatorId,
        });
      }
      return;
    }
    
    popupIdx = null;
    focusedStack = { position: idx, stackId };
    positionPopup(event.currentTarget);
  }

  function handleCounterKeydown(event, idx) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      handleCounterClick(event, idx);
    }
  }

  function beginMoveSelection(selection) {
    if (selection.type === 'move_unit' && !selection.stackId) {
      selection.stackId = createStackId(selection.fromPosition);
    }
    movingSelection = selection;
    moveSelectionError = '';
    popupIdx = null;
    focusedStack = null;
  }

  function submitStackMove(destination, destStackId = null) {
    if (!movingSelection) return;
    const { type, unitId, unitIds, fromPosition, stackId } = movingSelection;
    const move = legalMoves.find(candidate => {
      if (candidate.type !== type || candidate.from_position !== fromPosition || candidate.to_position !== destination) return false;
      if (type === 'move_unit') return candidate.unit_id === unitId;
      return Array.isArray(candidate.unit_ids) && candidate.unit_ids.length === unitIds.length &&
        unitIds.every(id => candidate.unit_ids.includes(id));
    });
    if (move) {
      const targetStackId = destStackId || stackId;
      dispatch('select-move', { ...move, stack_id: targetStackId });
      movingSelection = null;
      moveSelectionError = '';
    } else {
      moveSelectionError = 'That destination exceeds the stacking limit or is otherwise unavailable.';
    }
  }

  function startStackHover(position, stackId) {
    clearStackHover();
    hoverTimer = window.setTimeout(() => {
      hoveredStack = { position, stackId };
      hoverTimer = null;
    }, 1000);
  }

  function clearStackHover() {
    if (hoverTimer !== null) {
      window.clearTimeout(hoverTimer);
      hoverTimer = null;
    }
    hoveredStack = null;
  }

  function cancelPopup() {
    popupIdx = null;
    popupStackId = null;
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

  function getUnitDisplayName(unit) {
    const names = {
      co_hq_1: 'Company HQ',
      co_xo: 'Company Executive Officer',
      co_1sg: 'Company First Sergeant',
      hmg_50cal: '.50 cal HMG Team',
      arty_fo: 'Artillery Forward Observer'
    };
    if (names[unit.id]) return names[unit.id];
    let match = unit.id?.match(/^plt_hq_(\d+)$/);
    if (match) return `${match[1]}${match[1] === '1' ? 'st' : match[1] === '2' ? 'nd' : 'rd'} Platoon HQ`;
    match = unit.id?.match(/^squad_(\d+)_(\d+)$/);
    if (match) return `${match[1]}/${match[2]} Rifle Squad`;
    match = unit.id?.match(/^mortar_team_(\d+)$/);
    if (match) return `${match[1]}/Mtr 60mm Team`;
    match = unit.id?.match(/^lmg_(\d+)$/);
    if (match) return `${match[1]}/LMG Team`;
    match = unit.id?.match(/^at_team_(\d+)$/);
    if (match) return `${match[1]}/AT Bazooka Team`;
    return unit.name || unit.id || unit.type || 'Unit';
  }

  function getUnitCounterImage(unit) {
    let asset = null;
    if (unit.counter_image) {
      asset = unit.counter_image;
    } else if (unit.id === 'co_hq_1') {
      asset = 'Tokens/Markers/HQ CO HQ.png';
    } else if (unit.id === 'co_xo') {
      asset = 'Tokens/Markers/HQ CO XO.png';
    } else if (unit.id === 'co_1sg') {
      asset = 'Tokens/Markers/HQ CO 1SGT.png';
    } else if (unit.id === 'hmg_50cal') {
      asset = 'Tokens/Markers/Weapon_HMG50-1.png';
    } else if (unit.id === 'arty_fo') {
      asset = 'Tokens/Markers/Observer_Arty FO.png';
    } else {
      let match = unit.id?.match(/^plt_hq_(\d+)$/);
      if (match) asset = `Tokens/Markers/HQ ${match[1]} PLT.png`;
      match = unit.id?.match(/^squad_(\d+)_(\d+)$/);
      if (match) asset = `Tokens/Markers/2nd_${match[1]}-${match[2]}.png`;
      match = unit.id?.match(/^mortar_team_(\d+)$/);
      if (match) asset = `Tokens/Markers/Weapon_Mtr-${match[1]}b.png`;
      match = unit.id?.match(/^lmg_(\d+)$/);
      if (match) asset = `Tokens/Markers/Weapon_LMG-${match[1]}.png`;
      match = unit.id?.match(/^at_team_(\d+)$/);
      if (match) asset = `Tokens/Markers/Weapon_AT-${match[1]}.png`;
    }
    return asset
      ? `${API_BASE}/img/fof/counters/${encodeURIComponent(asset.split('/').pop())}`
      : null;
  }

  function getUnitSetupDetails(unit) {
    return [
      unit.experience,
      unit.steps ? `${unit.steps} ${unit.steps === 1 ? 'step' : 'steps'}` : null,
      unit.ammo ? `${unit.ammo} ammo` : null,
      unit.weapon
    ].filter(Boolean).join(' · ');
  }

  function isStagingCard(position) {
    const card = mapCards[position];
    const cardId = typeof card === 'string' ? card : card?.id;
    return deployment_zones.includes(position) || String(cardId || '').startsWith('DZ_');
  }

  function getUnitSteps(unit) {
    if (['vehicle', 'tank', 'truck', 'apc'].includes(String(unit.type || '').toLowerCase())) return 0;
    const steps = Number(unit.steps ?? unit.step_count ?? 1);
    return Number.isFinite(steps) ? Math.max(0, steps) : 1;
  }

  function canAddUnitToCard(unit, position) {
    if (isStagingCard(position)) return true;
    const stack = (unitsByCard[position] || []).filter(item =>
      !['casualty', 'dead', 'removed', 'destroyed', 'wrecked'].includes(String(item.status || '').toLowerCase()) && !item.embarked_in
    );
    const steps = stack.reduce((total, item) => total + getUnitSteps(item), 0);
    const vehicleTypes = ['vehicle', 'tank', 'truck', 'apc'];
    const vehicles = stack.filter(item => vehicleTypes.includes(String(item.type || '').toLowerCase())).length +
      (game?.state?.game_data?.company?.vehicles || screenState?.game_data?.company?.vehicles || [])
        .filter(vehicle => vehicle.position === position && !['wrecked', 'brewed_up', 'destroyed'].includes(String(vehicle.status || '').toLowerCase())).length;
    const isVehicle = vehicleTypes.includes(String(unit.type || '').toLowerCase());
    return steps + getUnitSteps(unit) <= 16 && vehicles + (isVehicle ? 1 : 0) <= 4;
  }

  function addUnitToStack(unitId) {
    if (focusedStack === null) return;
    const move = legalMoves.find(candidate => candidate.type === 'place_unit' && candidate.unit_id === unitId);
    if (move) dispatch('select-move', { ...move, position: focusedStack.position, stack_id: focusedStack.stackId });
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
<div class="fof-layout">
  <div class="fof-sidebar">
  <TurnSequenceTracker
    sequence={turnSequence}
    currentPhase={phase?.phase_name || phase}
    turn={turnNumber}
    durationTurns={durationTurns}
  />
    <div class="draw-pile-panel">
      <div class="dp-count">{cardsLeft}</div>
      <div class="dp-label">Cards remaining</div>
      <div class="dp-pile" role="img" aria-label="Last played card" on:mouseenter={startDiscardHover} on:mouseleave={clearDiscardHover}>
        {#if topDiscardUrl}
          <img src={topDiscardUrl} alt="Last played card" class="dp-card-img" />
        {:else}
          <div class="dp-card dp-card-back"></div>
        {/if}
        {#if discardHovered && topDiscardUrl}
          <div class="dp-hover-preview">
            <img src={topDiscardUrl} alt="Last played card" />
          </div>
        {/if}
      </div>
      <div class="dp-discard">Discard {discardCount}</div>
    </div>
    <div class="audit-panel" class:collapsed={auditCollapsed}>
      <div class="ap-top">
        {#if !auditCollapsed}
          <div class="ap-title"><strong>Activity log ({auditEntries.length})</strong></div>
        {/if}
        <button
          type="button"
          class="ap-collapse"
          aria-expanded={!auditCollapsed}
          title={auditCollapsed ? 'Show audit log' : 'Hide audit log'}
          on:click={() => (auditCollapsed = !auditCollapsed)}
        >
          {auditCollapsed ? '▶' : '◀'}
        </button>
      </div>
      {#if !auditCollapsed}
        <div class="ap-body">
          {#if auditEntries.length === 0}
            <div class="ap-empty">No activity yet</div>
          {:else}
            {#each auditEntries as entry (entry.id)}
              <div class="ap-entry">
                <span class="ap-time">{formatAuditTime(entry.timestamp)}</span>
                <span class="ap-text">{entry.text}</span>
              </div>
            {/each}
          {/if}
        </div>
      {/if}
    </div>
  </div>

<div class="fof-main">
  {#if IS_DEV}<div class="panel-name-debug">FieldsOfFireBoard</div>{/if}

  {#if winner}
    <div class="winner-banner">
      Mission complete - {winner} wins.
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
  {#if phase?.phase_name === 'setup' || focusedStack !== null || movingSelection}
    <div class="setup-panel">
      {#if phase?.phase_name === 'setup'}
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
      {/if}

      {#if movingSelection}
        <div class="moving-stack-banner">
          {#if movingSelection.type === 'move_stack'}
            Moving {movingSelection.unitIds.length} counters together — choose a destination card.
          {:else}
            Moving {getUnitDisplayName(units.find(unit => unit.id === movingSelection.unitId) || {})} — choose a destination card.
          {/if}
          <button type="button" class="cancel-move-btn" on:click={() => { movingSelection = null; moveSelectionError = ''; }}>Cancel move</button>
        </div>
        {#if moveSelectionError}<div class="move-selection-error">{moveSelectionError}</div>{/if}
      {/if}

      {#if popupIdx !== null && phase?.phase_name === 'setup'}
        <div class="unit-popup" style="left: {popupPos.x}px; top: {popupPos.y}px;">
          <div class="popup-header">
            <div class="popup-title">
              <span>Choose a counter for a new stack on card {popupIdx + 1}</span>
              <small>{availableSetupUnits.length} available</small>
            </div>
            <button class="cancel-btn" on:click={cancelPopup}>Cancel</button>
          </div>
          <div class="available-unit-list">
            {#each availableSetupUnits as unit (unit.id)}
              <button class="available-unit-option" type="button" on:click={() => placeUnitAtPopup(unit.id)}>
                {#if getUnitCounterImage(unit)}
                  <img class="counter-thumbnail" src={getUnitCounterImage(unit)} alt={getUnitDisplayName(unit)} />
                {:else}
                  <span class="counter-fallback">{unit.type}</span>
                {/if}
                <span class="unit-option-details">
                  <strong>{getUnitDisplayName(unit)}</strong>
                  <small>{getUnitSetupDetails(unit) || unit.type}</small>
                </span>
                <span class="place-arrow" aria-hidden="true">＋</span>
              </button>
            {:else}
              <p class="no-units-available">No unplaced counters are currently available.</p>
            {/each}
          </div>
        </div>
      {/if}

      {#if focusedStack !== null}
        {@const focusedUnits = stacksByCard[focusedStack.position]?.find(stack => stack.stackId === focusedStack.stackId)?.units || []}
        <div class="unit-popup stack-popup setup-stack-popup" style="left: {popupPos.x}px; top: {popupPos.y}px;">
          <div class="popup-header">
            <div class="popup-title">
              <span>Stack on card {focusedStack.position + 1}</span>
              <small>{focusedUnits.length} counters in this stack</small>
            </div>
            <button type="button" class="cancel-btn" on:click={() => (focusedStack = null)}>Close</button>
          </div>
          <div class="setup-stack-content">
            <section class="setup-stack-column current-stack-column">
              <h3>In this stack</h3>
              <div class="stack-member-list">
                {#each focusedUnits as unit (unit.id)}
                  <div class="stack-member-row">
                    {#if getUnitCounterImage(unit)}
                      <img class="counter-thumbnail" src={getUnitCounterImage(unit)} alt={getUnitDisplayName(unit)} />
                    {:else}
                      <span class="counter-fallback">{unit.type}</span>
                    {/if}
                    <span class="unit-option-details">
                      <strong>{getUnitDisplayName(unit)}</strong>
                      <small>{getUnitSetupDetails(unit) || unit.type}</small>
                    </span>
                    <button
                      type="button"
                      class="stack-action-btn move-counter-btn"
                      on:click={() => beginMoveSelection({ type: 'move_unit', unitId: unit.id, fromPosition: focusedStack.position, stackId: focusedStack.stackId })}
                    >Move</button>
                  </div>
                {/each}
              </div>
              {#if focusedUnits.length > 1}
                {@const groupMove = legalMoves.find(move => move.type === 'move_stack' && move.from_position === focusedStack.position && (move.stack_id === focusedStack.stackId || (!move.stack_id && move.unit_ids.every(id => focusedUnits.some(unit => unit.id === id)))))}
                {#if groupMove}
                  <button
                    type="button"
                    class="move-whole-stack-btn"
                    on:click={() => beginMoveSelection({ type: 'move_stack', unitIds: groupMove.unit_ids, fromPosition: focusedStack.position, stackId: focusedStack.stackId })}
                  >Move entire stack</button>
                {/if}
              {/if}
            </section>

            <section class="setup-stack-column remaining-units-column">
              <h3>Remaining to place <span>{availableSetupUnits.length}</span></h3>
              <div class="stack-add-section">
                {#each availableSetupUnits as unit (unit.id)}
                  <button type="button" class="available-unit-option" on:click={() => addUnitToStack(unit.id)}>
                    {#if getUnitCounterImage(unit)}
                      <img class="counter-thumbnail" src={getUnitCounterImage(unit)} alt={getUnitDisplayName(unit)} />
                    {:else}
                      <span class="counter-fallback">{unit.type}</span>
                    {/if}
                    <span class="unit-option-details">
                      <strong>{getUnitDisplayName(unit)}</strong>
                      <small>{getUnitSetupDetails(unit) || unit.type}</small>
                    </span>
                    <span class="place-arrow" aria-hidden="true">＋</span>
                  </button>
                {:else}
                  <p class="no-units-available">All required counters have been placed.</p>
                {/each}
              </div>
            </section>
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
        {@const stacksAt = stacksByCard[idx] || []}
        <button
          class="map-card"
          class:empty={card === null || card === undefined}
          class:deployment-zone={dz}
          class:has-legal-moves={hasLegalMoves(idx)}
          class:placing-target={popupIdx === idx}
          class:stack-focused={focusedStack?.position === idx}
          class:hovered-card={hoveredStack?.position === idx}
          class:move-destination={validDestIds?.has(idx)}
          class:legal-destination={validDestIds?.has(idx)}
          on:click={(e) => handleCardClick(e, idx)}
          disabled={!!winner || actionInProgress || (phase?.phase_name === 'setup' && !isStagingCard(idx))}
        >
          {#if dz}
            <div class="deployment-overlay"></div>
          {/if}
          {#if hasLegalMoves(idx) && phase?.phase_name !== 'setup'}
            <div class="legal-move-overlay"></div>
          {/if}
          {#if popupIdx === idx}
            <div class="placement-target-badge">Place here</div>
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
          {#if pcMarkers.some(p => p.position === idx && !p.resolved)}
            {@const pc = pcMarkers.find(p => p.position === idx)}
            <div class="pc-marker-badge" title="Potential Contact {pc.letter}">PC {pc.letter || '?'}</div>
          {/if}
          {#if stacksAt.length}
            <div class="card-stacks" aria-label={`${unitsByCard[idx]?.length || 0} units in ${stacksAt.length} stacks`}>
              {#each stacksAt as stack (stack.stackId)}
                {@const stackUnits = stack.units}
                <div
                  class="unit-counter-stack"
                  role="img"
                  class:stack-focused={focusedStack?.position === idx && focusedStack?.stackId === stack.stackId}
                  style="width: {48 + Math.min(Math.max(stackUnits.length - 1, 0), 8) * 2}px; height: {48 + Math.min(Math.max(stackUnits.length - 1, 0), 8) * 2}px;"
                  aria-label={`${stackUnits.length} counters in stack`}
                  on:mouseenter={() => startStackHover(idx, stack.stackId)}
                  on:mouseleave={clearStackHover}
                >
                  {#each stackUnits as unit, unitIndex (unit.id)}
                    {@const depth = stackUnits.length - unitIndex - 1}
                    <span
                      class="unit-counter-tile"
                      role="button"
                      tabindex="0"
                      class:selected-counter={movingSelection?.unitId === unit.id || movingSelection?.unitIds?.includes(unit.id)}
                      class:move-eligible={eligibleUnitIds?.has(unit.id)}
                      data-unit-id={unit.id}
                      style="left: {depth * 2}px; top: {depth * 2}px; z-index: {unitIndex + 1};"
                      title={`${getUnitDisplayName(unit)}${getUnitSetupDetails(unit) ? ` · ${getUnitSetupDetails(unit)}` : ''}`}
                      on:click={(event) => handleCounterClick(event, idx, stack.stackId)}
                      on:keydown={(event) => handleCounterKeydown(event, idx, stack.stackId)}
                      aria-label={`Select ${getUnitDisplayName(unit)} in stack`}
                    >
                      {#if getUnitCounterImage(unit)}
                        <img class="map-counter-image" src={getUnitCounterImage(unit)} alt={getUnitDisplayName(unit)} />
                      {:else}
                        <span class="counter-fallback">{getUnitDisplayName(unit)}</span>
                      {/if}
                    </span>
                  {/each}
                  {#if hoveredStack?.position === idx && hoveredStack?.stackId === stack.stackId}
                    <div class="stack-hover-preview">
                      <strong>{stackUnits.length} counters in this stack</strong>
                      <div class="hover-counter-grid">
                        {#each [...stackUnits].reverse() as unit (unit.id)}
                          <div class="hover-counter-item" title={getUnitDisplayName(unit)}>
                            {#if getUnitCounterImage(unit)}
                              <img src={getUnitCounterImage(unit)} alt={getUnitDisplayName(unit)} />
                            {/if}
                            <small>{getUnitDisplayName(unit)}</small>
                          </div>
                        {/each}
                      </div>
                    </div>
                  {/if}
                </div>
              {/each}
            </div>
          {/if}
        </button>
      {/each}
      {/each}
    </div>
  </div>

  <div class="bottom-bar">
    <div class="markers">
      <strong>Markers:</strong> {markers.length} | <strong>VOF:</strong> {vofMarkers.length}
    </div>
  </div>
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

  .fof-layout {
    display: flex;
    gap: 0.75rem;
    align-items: flex-start;
  }

  .draw-pile-panel {
    background: #222217;
    border: 1px solid #62624d;
    border-radius: 8px;
    padding: 0.5rem;
    color: #eee;
    box-sizing: border-box;
    width: 250px;
    flex: 0 0 auto;
    align-self: flex-start;
    font-size: 0.78rem;
    text-align: center;
  }

  .dp-count {
    font-size: 1.6rem;
    font-weight: bold;
    color: #ffd700;
    line-height: 1;
  }

  .dp-label {
    font-size: 0.7rem;
    color: #b7b79f;
    margin-bottom: 0.4rem;
  }

  .dp-pile {
    position: relative;
    margin: 0 auto 0.4rem;
    width: 150px;
    aspect-ratio: 3 / 4;
    display: flex;
    align-items: center;
    justify-content: center;
  }

  .dp-card-img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    border: 1px solid #887a2d;
    border-radius: 6px;
    box-shadow: 0 2px 4px rgba(0,0,0,0.5);
  }

  .dp-card-back {
    width: 100%;
    height: 100%;
    background: #3a3a2a;
    border: 1px solid #887a2d;
    border-radius: 6px;
  }

  .dp-hover-preview {
    position: absolute;
    top: 0;
    left: 100%;
    margin-left: 0.5rem;
    z-index: 100;
    background: #1a1a0a;
    border: 2px solid #ffd700;
    border-radius: 8px;
    padding: 0.4rem;
    box-shadow: 0 6px 20px rgba(0,0,0,0.7);
  }

  .dp-hover-preview img {
    width: 260px;
    height: auto;
    display: block;
    border-radius: 4px;
  }
  .fof-sidebar {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    flex: 0 0 auto;
    align-self: flex-start;
  }

  .audit-panel {
    background: #222217;
    border: 1px solid #62624d;
    border-radius: 8px;
    padding: 0.5rem;
    color: #eee;
    box-sizing: border-box;
    width: 250px;
    flex: 0 0 auto;
    align-self: flex-start;
    font-size: 0.78rem;
    max-height: 220px;
    overflow-y: auto;
  }

  .audit-panel.collapsed {
    width: 2.2rem;
    padding: 0.4rem 0.2rem;
  }

  .ap-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.4rem;
    margin-bottom: 0.4rem;
  }

  .ap-title {
    font-size: 0.78rem;
  }

  .ap-collapse {
    background: transparent;
    border: 1px solid #62624d;
    color: #eee;
    border-radius: 4px;
    cursor: pointer;
    padding: 0.1rem 0.3rem;
    font-size: 0.7rem;
  }

  .ap-body {
    overflow-y: visible;
    padding: 0.2rem 0;
  }

  .ap-entry {
    display: flex;
    gap: 0.4rem;
    margin-bottom: 0.3rem;
    line-height: 1.3;
    word-break: break-word;
  }

  .ap-time {
    color: #888;
    flex-shrink: 0;
  }

  .ap-text {
    color: #ddd;
  }

  .ap-empty {
    color: #666;
    font-style: italic;
  }

  .bottom-bar {
    margin-top: 0.75rem;
    border-top: 1px solid #62624d;
    padding-top: 0.6rem;
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
    width: min(380px, calc(100vw - 32px));
    max-height: min(440px, 70vh);
    display: flex;
    flex-direction: column;
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.5);
  }

  .stack-popup {
    gap: 0.4rem;
  }

  .setup-stack-popup {
    position: fixed;
    width: min(760px, calc(100vw - 32px));
    max-height: min(520px, 72vh);
    box-sizing: border-box;
  }

  .setup-stack-content {
    display: grid;
    grid-template-columns: minmax(0, 0.85fr) minmax(0, 1.15fr);
    gap: 0.7rem;
    flex: 1 1 auto;
    min-height: 0;
    overflow: hidden;
  }

  .setup-stack-column {
    display: flex;
    flex-direction: column;
    min-width: 0;
    min-height: 0;
    padding: 0.55rem;
    border: 1px solid #62624d;
    border-radius: 6px;
    background: #222217;
  }

  .setup-stack-column h3 {
    display: flex;
    justify-content: space-between;
    gap: 0.5rem;
    margin: 0 0 0.45rem;
    color: #ffd700;
    font-size: 0.82rem;
  }

  .setup-stack-column h3 span {
    color: #f3f0d7;
  }

  .current-stack-column .stack-member-list,
  .remaining-units-column .stack-add-section {
    flex: 1 1 auto;
    min-height: 0;
    max-height: none;
    overflow-x: hidden;
    overflow-y: auto;
    overscroll-behavior: contain;
  }

  .setup-stack-column .stack-member-row {
    grid-template-columns: 52px minmax(0, 1fr);
    padding: 0.4rem;
  }

  .setup-stack-column .stack-member-row .counter-thumbnail,
  .setup-stack-column .stack-member-row .counter-fallback {
    width: 48px;
    height: 48px;
  }

  .unit-popup .popup-header {
    display: flex;
    justify-content: space-between;
    align-items: flex-start;
    gap: 0.75rem;
    margin-bottom: 0.5rem;
  }

  .popup-title {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .unit-popup .popup-header span {
    font-size: 0.8rem;
    color: #ffd700;
    font-weight: 600;
  }

  .popup-title small {
    color: #b7b79f;
    font-size: 0.68rem;
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

  .available-unit-list {
    overflow-y: auto;
    min-height: 0;
    display: grid;
    gap: 0.4rem;
    padding-right: 0.2rem;
  }

  .stack-member-list {
    display: grid;
    gap: 0.35rem;
    max-height: 180px;
    overflow-y: auto;
  }

  .stack-member-row {
    display: grid;
    grid-template-columns: 48px minmax(0, 1fr) auto;
    align-items: center;
    gap: 0.55rem;
    padding: 0.3rem;
    border: 1px solid #555;
    border-radius: 6px;
    background: #353526;
  }

  .stack-action-btn,
  .move-whole-stack-btn,
  .cancel-move-btn {
    border: 1px solid #887a2d;
    border-radius: 5px;
    padding: 0.35rem 0.55rem;
    background: #51471d;
    color: #ffe66c;
    font-size: 0.68rem;
    font-weight: 700;
    cursor: pointer;
  }

  .move-whole-stack-btn {
    width: 100%;
    padding: 0.55rem;
    background: #296341;
    border-color: #55a675;
    color: #fff;
  }

  .stack-add-section {
    display: grid;
    gap: 0.35rem;
    min-height: 0;
    padding-top: 0.5rem;
  }

  .stack-add-section > strong {
    color: #ffd700;
    font-size: 0.72rem;
  }

  .stack-add-section .available-unit-option {
    grid-template-columns: 38px minmax(0, 1fr) 20px;
    padding: 0.25rem 0.35rem;
  }

  .stack-add-section .counter-thumbnail,
  .stack-add-section .counter-fallback {
    width: 36px;
    height: 36px;
  }

  .moving-stack-banner {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.75rem;
    margin-top: 0.6rem;
    border: 1px solid #f3d54b;
    border-radius: 6px;
    padding: 0.5rem 0.65rem;
    background: #3a3212;
    color: #ffe66c;
    font-size: 0.75rem;
    font-weight: 700;
  }

  .move-selection-error {
    margin-top: 0.3rem;
    color: #ff9a8b;
    font-size: 0.72rem;
  }

  .available-unit-option {
    display: grid;
    grid-template-columns: 48px minmax(0, 1fr) 20px;
    align-items: center;
    gap: 0.6rem;
    width: 100%;
    min-width: 0;
    box-sizing: border-box;
    padding: 0.35rem 0.45rem;
    border: 1px solid #555;
    border-radius: 6px;
    background: #3a3a2a;
    color: #eee;
    text-align: left;
    cursor: pointer;
  }

  .available-unit-option:hover {
    border-color: #ffd700;
    background: #4a4a32;
  }

  .counter-thumbnail,
  .counter-fallback {
    width: 44px;
    height: 44px;
    object-fit: contain;
    border-radius: 4px;
    background: #555;
  }

  .counter-fallback {
    display: grid;
    place-items: center;
    color: #fff;
    font-size: 0.55rem;
    text-align: center;
  }

  .unit-option-details {
    min-width: 0;
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
  }

  .unit-option-details strong {
    overflow: hidden;
    color: #f3f0d7;
    font-size: 0.75rem;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .unit-option-details small {
    color: #b7b79f;
    font-size: 0.65rem;
    text-transform: capitalize;
  }

  .place-arrow {
    color: #ffd700;
    font-size: 1.1rem;
    text-align: center;
  }

  .no-units-available {
    margin: 0;
    padding: 0.6rem;
    color: #ccc;
    font-size: 0.75rem;
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
    overflow: visible;
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
    border: 3px solid #ffe14d;
    box-shadow: 0 0 0 4px rgba(255, 225, 77, 0.65), 0 0 18px rgba(255, 225, 77, 0.75);
    z-index: 4;
  }

  .map-card.stack-focused {
    border: 3px solid #42f0c4;
    box-shadow: 0 0 0 4px rgba(66, 240, 196, 0.52), 0 0 18px rgba(66, 240, 196, 0.8);
    z-index: 4;
  }

  .map-card.hovered-card {
    z-index: 10;
  }

  .map-card.move-destination {
    cursor: copy;
    border-color: #ffe14d;
  }

  .map-card.move-destination:hover:not(:disabled) {
    border: 3px solid #ffe14d;
    box-shadow: 0 0 0 4px rgba(255, 225, 77, 0.6), 0 0 18px rgba(255, 225, 77, 0.75);
  }

  .map-card.move-destination:not(.legal-destination) {
    cursor: not-allowed;
    filter: saturate(0.55) brightness(0.72);
  }

  .map-card.move-destination.legal-destination {
    border-color: #b7ff5f;
  }

  .map-card.move-destination.legal-destination:hover:not(:disabled) {
    border: 3px solid #b7ff5f;
    box-shadow: 0 0 0 4px rgba(183, 255, 95, 0.58), 0 0 18px rgba(183, 255, 95, 0.75);
  }

  .map-card:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  @media (max-width: 600px) {
    .setup-stack-popup {
      max-height: min(560px, 76vh);
    }

    .setup-stack-content {
      grid-template-columns: minmax(0, 1fr);
      grid-template-rows: minmax(110px, 0.75fr) minmax(150px, 1.25fr);
    }

    .setup-stack-column {
      padding: 0.4rem;
    }

    .setup-stack-column .stack-member-row {
      grid-template-columns: 42px minmax(0, 1fr);
    }

    .setup-stack-column .stack-member-row .counter-thumbnail,
    .setup-stack-column .stack-member-row .counter-fallback {
      width: 38px;
      height: 38px;
    }
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

  .pc-marker-badge {
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
    background: rgba(30, 80, 180, 0.9);
    color: #fff;
    font-size: 1.4rem;
    font-weight: bold;
    padding: 8px 14px;
    border-radius: 6px;
    z-index: 2;
    border: 2px solid #fff;
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

  .placement-target-badge {
    position: absolute;
    top: 5px;
    left: 5px;
    z-index: 5;
    padding: 4px 6px;
    border: 1px solid #fff0a3;
    border-radius: 4px;
    background: rgba(36, 31, 8, 0.92);
    color: #ffe14d;
    font-size: 0.62rem;
    font-weight: 900;
    letter-spacing: 0.04em;
    pointer-events: none;
  }

  .unit-counter-stack {
    position: relative;
    flex: 0 0 auto;
    overflow: visible;
    pointer-events: none;
  }

  .card-stacks {
    position: absolute;
    z-index: 3;
    left: 2px;
    bottom: 4px;
    display: flex;
    flex-wrap: wrap;
    align-items: flex-end;
    gap: 3px;
    max-width: calc(100% - 8px);
    max-height: 78%;
    overflow: visible;
  }

  .unit-counter-tile {
    position: absolute;
    width: 44px;
    height: 44px;
    overflow: hidden;
    border: 1px solid rgba(255, 255, 255, 0.9);
    border-radius: 4px;
    background: #d7d1a3;
    box-shadow: 0 2px 5px rgba(0, 0, 0, 0.8);
    cursor: pointer;
    pointer-events: auto;
  }

  .unit-counter-tile.selected-counter {
    outline: 3px solid #ffe14d;
    outline-offset: 1px;
  }

  .unit-counter-tile.move-eligible {
    box-shadow: 0 0 0 3px #ffd700, 0 0 10px rgba(255, 215, 0, 0.6);
    border-color: #ffd700;
    transform: scale(1.05);
    z-index: 100;
  }

  .unit-counter-tile.move-eligible:hover {
    box-shadow: 0 0 0 4px #ffd700, 0 0 15px rgba(255, 215, 0, 0.8);
    transform: scale(1.1);
  }

  .stack-hover-preview {
    position: absolute;
    left: 0;
    bottom: calc(100% + 8px);
    z-index: 100;
    width: min(400px, 90vw);
    max-height: 375px;
    overflow: auto;
    padding: 0.65rem;
    border: 2px solid #ffe14d;
    border-radius: 8px;
    background: rgba(25, 27, 21, 0.98);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.8);
  }

  .stack-hover-preview > strong {
    display: block;
    margin-bottom: 0.5rem;
    color: #ffe66c;
    font-size: 0.75rem;
  }

  .hover-counter-grid {
    display: flex;
    flex-wrap: wrap;
    gap: 0.4rem;
  }

  .hover-counter-item {
    display: grid;
    justify-items: center;
    gap: 0.2rem;
    width: 84px;
    color: #f2f0db;
    text-align: center;
  }

  .hover-counter-item img {
    width: 95px;
    height: 95px;
    border: 1px solid #c8c0a0;
    border-radius: 4px;
    background: #ddd6b1;
    object-fit: contain;
  }

  .hover-counter-item small {
    font-size: 0.62rem;
    line-height: 1.15;
  }

  .map-counter-image {
    display: block;
    width: 100%;
    height: 100%;
    object-fit: contain;
  }

  .counter-overflow {
    display: grid;
    place-items: center;
    width: 34px;
    aspect-ratio: 1;
    border-radius: 3px;
    background: #ffe14d;
    color: #25210d;
    font-size: 0.8rem;
    font-weight: 900;
  }

  .board-info {
    text-align: center;
    margin-top: 0.5rem;
    color: #ccc;
    font-size: 0.8rem;
  }

  /* Unslop pass */
  .fof-board {
    background: var(--fof-bg);
    padding: var(--fof-space-4);
  }

  .fof-layout {
    gap: var(--fof-space-3);
    min-height: 0;
  }

  .fof-main {
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .fof-sidebar,
  .draw-pile-panel,
  .audit-panel {
    width: 170px;
    background: var(--fof-surface);
    border: 1px solid var(--fof-border);
    border-radius: var(--fof-radius-md);
    padding: var(--fof-space-2);
    color: var(--fof-text);
    box-shadow: none;
  }

  .draw-pile-panel,
  .audit-panel {
    width: 170px;
  }

  .dp-count {
    color: var(--fof-accent);
    font-family: var(--fof-mono);
    font-variant-numeric: tabular-nums;
  }

  .dp-label,
  .dp-discard {
    color: var(--fof-muted);
    font-size: 0.7rem;
  }

  .dp-card-img,
  .dp-card-back {
    border-color: var(--fof-border-strong);
    border-radius: var(--fof-radius-sm);
    box-shadow: none;
  }

  .dp-hover-preview {
    background: var(--fof-surface-2);
    border: 1px solid var(--fof-border-strong);
    border-radius: var(--fof-radius-md);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
  }

  .ap-title,
  .ap-text {
    color: var(--fof-text);
  }

  .ap-time {
    color: var(--fof-muted);
    font-family: var(--fof-mono);
  }

  .ap-empty {
    color: var(--fof-muted);
    font-style: normal;
  }

  .ap-collapse {
    background: transparent;
    border: 1px solid var(--fof-border-strong);
    color: var(--fof-text-2);
    border-radius: var(--fof-radius-sm);
  }

  .info-bar {
    color: var(--fof-text-2);
    font-size: 0.8rem;
    font-family: var(--fof-mono);
  }

  .winner-banner {
    background: var(--fof-surface-2);
    color: var(--fof-text);
    border: 1px solid var(--fof-accent);
    border-radius: var(--fof-radius-sm);
    font-weight: 500;
  }

  .setup-panel,
  .unit-popup,
  .setup-stack-column {
    background: var(--fof-surface);
    border: 1px solid var(--fof-border-strong);
    border-radius: var(--fof-radius-md);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
  }

  .setup-stack-column h3 {
    color: var(--fof-accent);
  }

  .setup-stack-column h3 span {
    color: var(--fof-text);
  }

  .unit-popup .popup-header span {
    color: var(--fof-accent);
    font-weight: 500;
  }

  .popup-title small,
  .dp-label {
    color: var(--fof-muted);
  }

  .cancel-btn {
    background: transparent;
    color: var(--fof-accent);
    border: 1px solid var(--fof-accent);
    border-radius: var(--fof-radius-sm);
  }

  .cancel-btn:hover {
    background: var(--fof-accent);
    color: var(--fof-accent-text);
  }

  .available-unit-option {
    background: var(--fof-surface-2);
    border: 1px solid var(--fof-border);
    border-radius: var(--fof-radius-sm);
    color: var(--fof-text);
    transition: border-color var(--fof-dur-fast) var(--fof-ease), background-color var(--fof-dur-fast) var(--fof-ease);
  }

  .available-unit-option:hover {
    border-color: var(--fof-accent);
    background: var(--fof-surface-3);
  }

  .unit-option-details strong {
    color: var(--fof-text);
  }

  .unit-option-details small {
    color: var(--fof-muted);
  }

  .place-arrow {
    color: var(--fof-accent);
  }

  .map-container {
    width: 100%;
    max-width: none;
    flex: 1;
    min-height: 0;
    display: flex;
    flex-direction: column;
  }

  .map-grid {
    background: var(--fof-surface-2);
    border: 1px solid var(--fof-border);
    border-radius: var(--fof-radius-md);
    gap: var(--fof-space-3);
    padding: var(--fof-space-3);
    flex: 1;
    min-height: 0;
  }

  .map-card {
    border: 1px solid var(--fof-border);
    background: var(--fof-surface-3);
    border-radius: var(--fof-radius-sm);
    transition: border-color var(--fof-dur-fast) var(--fof-ease);
  }

  .map-card:hover:not(:disabled) {
    border-color: var(--fof-accent);
  }

  .map-card.empty {
    background: var(--fof-surface);
  }

  .map-card.deployment-zone {
    border-color: var(--fof-text-2);
  }

  .map-card.has-legal-moves {
    box-shadow: 0 0 0 2px var(--fof-accent);
  }

  .map-card.placing-target {
    border: 2px solid var(--fof-accent);
    box-shadow: 0 0 0 2px var(--fof-accent);
  }

  .map-card.move-destination {
    box-shadow: inset 0 0 0 4px #27ae60, 0 0 20px rgba(39, 174, 96, 0.5);
    border-color: #27ae60;
    background: rgba(39, 174, 96, 0.1);
    transition: box-shadow 0.15s ease, border-color 0.15s ease, background 0.15s ease;
  }

  .map-card.move-destination:hover {
    box-shadow: inset 0 0 0 5px #27ae60, 0 0 30px rgba(39, 174, 96, 0.7);
  }

  .map-card.move-destination.legal-destination {
    border-color: #27ae60;
  }

  .map-card.move-destination:not(.legal-destination) {
    filter: saturate(0.5) brightness(0.7);
  }

  .map-card:disabled {
    opacity: 0.55;
  }

  .deployment-overlay {
    background: rgba(184, 148, 31, 0.12);
  }

  .legal-move-overlay {
    background: rgba(184, 148, 31, 0.10);
  }

  .card-label {
    color: var(--fof-text-2);
    font-size: 0.7rem;
  }

  .empty-card {
    color: var(--fof-muted);
  }

  .pc-marker-badge {
    background: var(--fof-surface-3);
    color: var(--fof-text);
    border: 1px solid var(--fof-border-strong);
    border-radius: var(--fof-radius-sm);
    font-family: var(--fof-mono);
  }

  .elevation,
  .cover {
    background: rgba(0, 0, 0, 0.55);
    color: var(--fof-accent);
    border-radius: 3px;
    font-family: var(--fof-mono);
  }

  .progress-bar {
    background: var(--fof-surface-3);
    border-radius: var(--fof-radius-sm);
  }

  .progress-fill {
    background: var(--fof-accent);
    transition: width var(--fof-dur-fast) var(--fof-ease);
  }

  .moving-stack-banner {
    background: var(--fof-surface-2);
    border: 1px solid var(--fof-warning);
    color: var(--fof-text);
    border-radius: var(--fof-radius-sm);
  }

  .move-selection-error {
    color: var(--fof-danger);
  }

  .stack-member-row {
    background: var(--fof-surface-2);
    border: 1px solid var(--fof-border);
    border-radius: var(--fof-radius-sm);
  }

  .stack-action-btn,
  .move-whole-stack-btn,
  .cancel-move-btn {
    border-radius: var(--fof-radius-sm);
    transition: background-color var(--fof-dur-fast) var(--fof-ease);
  }

  .move-whole-stack-btn {
    background: var(--fof-success);
    border-color: var(--fof-success);
    color: var(--fof-text);
  }

  .counter-thumbnail,
  .counter-fallback {
    border-radius: var(--fof-radius-sm);
    background: var(--fof-surface-3);
  }

  .bottom-bar {
    border-top: 1px solid var(--fof-border);
    color: var(--fof-text-2);
  }

  .markers {
    font-family: var(--fof-mono);
    font-size: 0.75rem;
  }

  .unit-counter-tile {
    border-radius: 4px;
  }

  .stack-hover-preview {
    background: var(--fof-surface);
    border: 1px solid var(--fof-border-strong);
    border-radius: var(--fof-radius-md);
    box-shadow: 0 4px 12px rgba(0, 0, 0, 0.35);
  }

  .hover-counter-item small {
    color: var(--fof-muted);
    font-size: 0.65rem;
  }

  .placement-target-badge {
    background: var(--fof-accent);
    color: var(--fof-accent-text);
    border-radius: var(--fof-radius-sm);
    font-size: 0.65rem;
    letter-spacing: 0;
    text-transform: none;
  }

  .unit-popup .popup-header {
    gap: var(--fof-space-2);
  }

  .no-units-available {
    color: var(--fof-muted);
  }

  button:focus-visible,
  .map-card:focus-visible,
  .available-unit-option:focus-visible {
    outline: 2px solid var(--fof-accent);
    outline-offset: 2px;
  }

  @media (max-width: 640px) {
    .fof-layout {
      flex-direction: column;
    }

    .fof-sidebar,
    .draw-pile-panel,
    .audit-panel {
      width: 100%;
    }

    .map-container {
      max-width: 100%;
    }

    .setup-stack-content {
      grid-template-columns: 1fr;
    }
  }
</style>
