<script>
  import { createEventDispatcher } from 'svelte';

  export let screenState = null;
  export let legalMoves = [];
  export let pendingMove = null;
  export let actionInProgress = false;
  export let lastSelectedMove = null;

  const dispatch = createEventDispatcher();
  const HUMAN_PLAYER = 'player_1';
  let showReferenceIds = false;
  let selectedBuildingSite = null;
  const ACTION_TYPES = ['line_expansion', 'buses', 'passengers', 'buildings', 'clock', 'vrrooomm', 'starting_player'];
  const SINGLE_SLOT_ACTIONS = new Set(['buses', 'clock', 'starting_player']);
  // Row/column positions are measured directly from the board artwork's pixel grid
  // (web/static/bus-game-board.png, 1728x1296) so rendered markers land inside the
  // printed slot squares. The four 6-slot rows share one column grid; single-slot
  // rows use their own checkbox position. Values verified against live rendered
  // marker vs. printed-box-border pixel measurements (2026-10-17).
  const SIX_SLOT_LEFT_X = 79.15;
  const SIX_SLOT_PITCH_X = 2.305;
  const ACTION_ROWS = {
    line_expansion: { y: 17.75, reverse: true },
    buses: { y: 24.07, right: true },
    passengers: { y: 54.94 },
    buildings: { y: 65.05, reverse: true },
    clock: { y: 75.15 },
    vrrooomm: { y: 88.66 },
    starting_player: { y: 93.6, right: true }
  };

  $: data = screenState?.game_data || {};
  $: clockTypes = ['house', 'office', 'pub'];
  $: clockName = ({ house: 'House', office: 'Office', pub: 'Pub' })[data.clock] || 'House';
  $: clockStoneCount = Math.max(0, Number(data.time_stones_remaining) || 0);
  $: totalClockStones = Object.keys(data.players || {}).length === 3 ? 4 : 5;
  $: availableMoves = screenState?.legal_moves?.length ? screenState.legal_moves : legalMoves;
  $: isHumanTurn = screenState?.current_player === HUMAN_PLAYER && !screenState?.winner;
  $: canInteract = isHumanTurn && !actionInProgress;
  $: selectedMove = pendingMove || lastSelectedMove;
  $: selectedMoveId = selectedMove?.move_id || null;
  $: selectableActions = availableMoves.filter(move => move.type === 'select_action');
  $: selectableSites = availableMoves.filter(move => move.type === 'setup_building');
  $: selectableEdges = availableMoves.filter(move => move.type?.startsWith('setup_') && move.edge_id);
  $: routeMoves = availableMoves.filter(move => move.edge_id && (move.type?.startsWith('setup_') || move.type === 'line_expand'));
  $: resolutionMoves = availableMoves.filter(move => !['select_action', 'pass_action_selection', 'setup_building'].includes(move.type) && !move.type?.startsWith('setup_'));

  function choose(move) {
    if (canInteract && !pendingMove) {
      selectedBuildingSite = null;
      dispatch('select-move', move);
    }
  }

  function chooseWithKeyboard(event, move) {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault();
      choose(move);
    }
  }

  function actionLabel(action) {
    return action.replace('_', ' ');
  }

  function actionSlotCount(action) {
    return SINGLE_SLOT_ACTIONS.has(action) ? 1 : 6;
  }

  function buildingMoves(siteId) {
    return [
      ...selectableSites.filter(move => move.site_id === siteId),
      ...resolutionMoves.filter(move => move.type === 'build' && move.site_id === siteId),
    ];
  }

  function chooseBuildingSite(siteId) {
    if (!canInteract || pendingMove) return;
    const moves = buildingMoves(siteId);
    if (moves.length === 1) {
      choose(moves[0]);
      return;
    }
    selectedBuildingSite = siteId;
  }

  function actionSlotStyle(action, index) {
    const row = ACTION_ROWS[action];
    const single = SINGLE_SLOT_ACTIONS.has(action);
    const x = single
      ? (row.right ? 95.85 : 79.57)
      : (row.reverse ? SIX_SLOT_LEFT_X + (5 - index) * SIX_SLOT_PITCH_X : SIX_SLOT_LEFT_X + index * SIX_SLOT_PITCH_X);
    return `left: ${x}%; top: ${row.y}%;`;
  }

  function moveLabel(move) {
    if (move.type === 'line_expand') return `Extend line: ${move.edge_id}`;
    if (move.type === 'buy_bus') return 'Buy bus';
    if (move.type === 'place_passenger') return `Place passenger at ${move.station}`;
    if (move.type === 'build') return `Build ${move.building_type} at ${move.site_id}`;
    if (move.type === 'clock_stop') return 'Stop time';
    if (move.type === 'clock_advance') return 'Advance clock';
    if (move.type === 'transport') return `Transport ${move.passenger_id} to ${move.destination_site}`;
    if (move.type === 'complete_resolution') return 'Complete action';
    return actionLabel(move.type);
  }

  function siteStyle(site) {
    return `left: ${site.x}%; top: ${site.y}%;`;
  }

  function passengerStyle(location) {
    const siteId = location?.startsWith('building:') ? location.slice('building:'.length) : null;
    const crossing = siteId ? data.topology?.building_sites?.[siteId]?.crossing : location;
    const mapNode = node(crossing);
    return mapNode ? `left: ${mapNode.x}%; top: ${mapNode.y}%;` : '';
  }

  function node(id) {
    return data.topology?.nodes?.[id];
  }

  function routeColor(playerId) {
    return ({ player_1: '#cc0000', player_2: '#3b8d3b', player_3: '#1d70b8', player_4: '#e0a800', player_5: '#333333' })[playerId] || '#ffffff';
  }

  // When multiple players' routes share the same street edge (allowed by the
  // rules as a "parallel" use), drawing every route line on the exact same
  // coordinates makes them visually indistinguishable (only the last-drawn
  // color shows). Offset each occupant's line perpendicular to the edge so
  // all colors remain visible side by side.
  const ROUTE_OFFSET_STEP = 0.55;

  function routeLineCoords(from, to, occupants, playerId) {
    const count = occupants.length;
    if (count <= 1) {
      return { x1: from.x, y1: from.y, x2: to.x, y2: to.y };
    }
    const index = occupants.indexOf(playerId);
    const dx = to.x - from.x;
    const dy = to.y - from.y;
    const length = Math.hypot(dx, dy) || 1;
    const normalX = -dy / length;
    const normalY = dx / length;
    const offset = (index - (count - 1) / 2) * ROUTE_OFFSET_STEP;
    return {
      x1: from.x + normalX * offset,
      y1: from.y + normalY * offset,
      x2: to.x + normalX * offset,
      y2: to.y + normalY * offset,
    };
  }

  function playerLabel(playerId) {
    return ({ player_1: 'Red', player_2: 'Green', player_3: 'Blue', player_4: 'Yellow', player_5: 'Black' })[playerId] || playerId;
  }

  function referenceId(value) {
    return value.replace('building_', '').replace('_', '').toUpperCase();
  }

  // Debug function to find action move with detailed logging
  function debugActionMove(action, index, slot) {
    const candidates = selectableActions;
    const targetAction = action;
    const targetSlot = slot;
    
    // Log the search parameters
    console.log('[debugActionMove] Searching for:', { action: targetAction, slot: targetSlot, index });
    console.log('[debugActionMove] selectableActions:', JSON.stringify(candidates.map(c => ({ action_type: c.action_type, slot: c.slot, move_id: c.move_id }))));
    
    for (const candidate of candidates) {
      const actionMatch = candidate.action_type === targetAction;
      const slotMatch = candidate.slot === targetSlot;
      console.log('[debugActionMove] Checking candidate:', {
        candidateAction: candidate.action_type,
        candidateSlot: candidate.slot,
        candidateMoveId: candidate.move_id,
        actionMatch,
        slotMatch,
        actionType: typeof candidate.action_type,
        targetActionType: typeof targetAction,
        slotType: typeof candidate.slot,
        targetSlotType: typeof targetSlot,
        actionEqual: candidate.action_type == targetAction,
        slotEqual: candidate.slot == targetSlot
      });
      if (actionMatch && slotMatch) {
        console.log('[debugActionMove] FOUND MATCH:', candidate.move_id);
        return candidate;
      }
    }
    console.log('[debugActionMove] NO MATCH FOUND');
    return undefined;
  }

  // Precomputed per-edge occupant lists (player IDs in stable `data.players`
  // order) so overlapping "parallel" routes can be offset consistently.
  $: edgeOccupants = Object.entries(data.players || {}).reduce((map, [playerId, player]) => {
    for (const edgeId of player.route_edges || []) {
      (map[edgeId] ||= []).push(playerId);
    }
    return map;
  }, {});
</script>

<main class="bus-board" aria-label="Bus game board">
  <header>
    <h1>🚌 Bus</h1>
    <p>{screenState?.phase?.phase_text || 'Loading game…'}</p>
  </header>

  <section class="status" aria-live="polite">
    <span>Round {data.round_number || 0}</span>
    <div class="clock-display" role="img" aria-label={`Clock currently demands ${clockName}; ${clockStoneCount} of ${totalClockStones} time stones remain`}>
      <strong>Clock</strong>
      <div class="clock-types" aria-hidden="true">
        {#each clockTypes as type}
          <span class:current={data.clock === type} class="clock-type">{type}</span>
        {/each}
      </div>
      <span class="clock-current">Now: {clockName}</span>
      <div class="clock-stones" aria-label={`${clockStoneCount} time stones remain on the clock`}>
        {#each Array(totalClockStones) as _, index}
          <span class:available={index < clockStoneCount} class="clock-stone" aria-hidden="true">◆</span>
        {/each}
        <small>{clockStoneCount} remaining</small>
      </div>
    </div>
    <button class="reference-toggle" type="button" aria-pressed={showReferenceIds} on:click={() => showReferenceIds = !showReferenceIds}>
      {showReferenceIds ? 'Hide map IDs' : 'Show map IDs'}
    </button>
  </section>

  {#if selectedMove}
    <section class="pending-move" aria-live="polite">
      <strong>{pendingMove ? 'Selected' : actionInProgress ? 'Submitting' : 'Last action'}: {moveLabel(selectedMove)}</strong>
      {#if pendingMove}
        <span>This choice has not been committed yet.</span>
        <button type="button" disabled={actionInProgress} on:click={() => dispatch('confirm')}>Confirm Action</button>
        <button type="button" disabled={actionInProgress} on:click={() => dispatch('cancel-pending-move')}>Cancel</button>
      {/if}
    </section>
  {/if}

  <section class="city" aria-label="City map">
    <svg class="route-map" viewBox="0 0 100 100" preserveAspectRatio="none" role="group" aria-label="Bus route and station controls">
      {#each Object.entries(data.topology?.edges || {}) as [edgeId, ends]}
        {@const from = node(ends[0])}
        {@const to = node(ends[1])}
        {#if from && to}
          <line class="street" x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
          {#if showReferenceIds}
            <text class="edge-reference" x={(from.x + to.x) / 2} y={(from.y + to.y) / 2}>{edgeId}</text>
          {/if}
        {/if}
      {/each}
      {#each Object.entries(data.players || {}) as [playerId, player]}
        {#each player.route_edges || [] as edgeId}
          {@const ends = data.topology?.edges?.[edgeId]}
          {@const from = ends && node(ends[0])}
          {@const to = ends && node(ends[1])}
          {#if from && to}
            {@const coords = routeLineCoords(from, to, edgeOccupants[edgeId] || [playerId], playerId)}
            <line class="route" style={`stroke: ${routeColor(playerId)}`} x1={coords.x1} y1={coords.y1} x2={coords.x2} y2={coords.y2} />
          {/if}
        {/each}
        {#each player.route_ends || [] as crossingId}
          {@const routeEnd = node(crossingId)}
          {#if routeEnd}
            <circle class="route-end" style={`fill: ${routeColor(playerId)}`} cx={routeEnd.x} cy={routeEnd.y} r="1.12" />
          {/if}
        {/each}
      {/each}
      {#each routeMoves as move}
        {@const ends = data.topology?.edges?.[move.edge_id]}
        {@const from = ends && node(ends[0])}
        {@const to = ends && node(ends[1])}
        {#if from && to}
          <g class="legal-route" role="button" tabindex="0" aria-label={`Build route segment ${move.edge_id}`}
            on:click={() => choose(move)} on:keydown={(event) => chooseWithKeyboard(event, move)}>
            <line class="legal-route-hitbox" x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
            <line class="legal-route-highlight" x1={from.x} y1={from.y} x2={to.x} y2={to.y} />
          </g>
        {/if}
      {/each}
      {#each Object.entries(data.topology?.nodes || {}) as [nodeId, mapNode]}
        {@const move = mapNode.station && resolutionMoves.find(candidate => candidate.type === 'place_passenger' && candidate.station === nodeId)}
        {#if move}
          <g class="legal-station" role="button" tabindex="0" aria-label={`Place passenger at ${nodeId}`}
            on:click={() => choose(move)} on:keydown={(event) => chooseWithKeyboard(event, move)}>
            <circle class="station-station-hitbox" cx={mapNode.x} cy={mapNode.y} r="2" />
            <circle class="station legal-station-marker" cx={mapNode.x} cy={mapNode.y} r="0.88" />
          </g>
        {:else}
          <circle class:station={mapNode.station} cx={mapNode.x} cy={mapNode.y} r="0.72" />
        {/if}
        {#if showReferenceIds}
          <text class="node-reference" x={mapNode.x} y={mapNode.y - 1.15}>{nodeId}</text>
        {/if}
      {/each}
    </svg>
    {#each Object.entries(data.topology?.building_sites || {}) as [siteId, site]}
      {@const building = data.buildings?.[siteId]}
      {@const move = selectableSites.find(candidate => candidate.site_id === siteId) || resolutionMoves.find(candidate => candidate.type === 'build' && candidate.site_id === siteId)}
      <button class="site" class:legal={!!move} class:reference-id={showReferenceIds} class:built={!!building}
        style={`${siteStyle(site)}${building ? ` --building-color: ${routeColor(building.owner_id)}` : ''}`}
        disabled={!move || !canInteract} on:click={() => chooseBuildingSite(siteId)}
        aria-label={`${siteId}, zone ${site.zone}${building ? `, ${building.type}, built by ${playerLabel(building.owner_id)}` : ', empty'}`}>
        {showReferenceIds ? referenceId(siteId) : building?.type === 'house' ? '⌂' : building?.type === 'office' ? '⌨' : building?.type === 'pub' ? '🍺' : site.zone}
      </button>
    {/each}
    {#each Object.entries(data.passengers || {}) as [passengerId, location]}
      <span class="passenger" style={passengerStyle(location)} aria-label={`Passenger ${passengerId}`}>♟</span>
    {/each}

    {#each ACTION_TYPES as action}
      {#each Array(actionSlotCount(action)) as _, index}
        {@const slot = String.fromCharCode(65 + index)}
        {@const move = debugActionMove(action, index, slot)}
        {@const owner = data.action_spaces?.[action]?.[index] || null}
        <button class="board-action-slot" class:legal={!!move} class:occupied={!!owner} class:selected={!!move && selectedMoveId === move.move_id}
          disabled={!move || !canInteract} on:click={() => choose(move)} style={`${actionSlotStyle(action, index)}${owner ? ` --marker-color: ${routeColor(owner)};` : ''}`}
          aria-label={`${actionLabel(action)} slot ${slot}${owner ? ` occupied by ${playerLabel(owner)}` : ''}`}>
          {#if owner}<span class="marker-token">{playerLabel(owner).charAt(0)}</span>{/if}
        </button>
      {/each}
    {/each}
  </section>

  {#each availableMoves.filter(move => move.type === 'pass_action_selection') as move}
    <section class="pass-action" aria-label="Action selection"><button on:click={() => choose(move)} disabled={!canInteract}>Pass action selection</button></section>
  {/each}

  {#if selectedBuildingSite && !pendingMove}
    <section class="building-type-picker" aria-label={`Choose building type for ${selectedBuildingSite}`}>
      <h2>Choose building type</h2>
      <p>{showReferenceIds ? referenceId(selectedBuildingSite) : selectedBuildingSite}</p>
      {#each buildingMoves(selectedBuildingSite) as move}
        <button class="legal" on:click={() => choose(move)} disabled={!canInteract}>{move.building_type}</button>
      {/each}
      <button on:click={() => selectedBuildingSite = null}>Cancel</button>
    </section>
  {/if}

  {#if selectableEdges.length}
    <section class="legal-list" aria-label="Legal route segments">
      <h2>Legal route segments (or select one on the map)</h2>
      {#each selectableEdges as move}
        <button class="legal" on:click={() => choose(move)} disabled={!canInteract}>{move.edge_id}</button>
      {/each}
    </section>
  {/if}

  {#if resolutionMoves.length}
    <section class="resolution-list" aria-label="Required action resolution">
      <h2>Complete current action</h2>
      {#each resolutionMoves as move}
        <button class="legal" on:click={() => choose(move)} disabled={!canInteract}>{moveLabel(move)}</button>
      {/each}
    </section>
  {/if}

  <section class="players" aria-label="Player status">
    {#each Object.entries(data.players || {}) as [playerId, player]}
      <article class:current={screenState?.current_player === playerId}>
        <strong>{playerLabel(playerId)}{playerId === HUMAN_PLAYER ? ' (You)' : ''}</strong>
        <span> Score {player.score} ({player.adjusted_score} adjusted); buses {player.buses}; stones {player.time_stones}; markers {player.action_markers}</span>
        <small> Route ends: {player.route_ends?.join(', ') || 'not placed'}</small>
      </article>
    {/each}
  </section>

  {#if data.game_over && data.final_ranking?.length}
    <section class="final-ranking" aria-label="Final ranking">
      <h2>Final ranking</h2>
      <ol>
        {#each data.final_ranking as playerId}
          {@const player = data.players[playerId]}
          <li>{playerId === HUMAN_PLAYER ? 'You' : playerLabel(playerId)}: {player.adjusted_score} adjusted score</li>
        {/each}
      </ol>
    </section>
  {/if}
</main>

<style>
  .bus-board { min-height: calc(100vh - 70px); padding: 1rem; color: #14212b; background: #d8e0e5; font-family: system-ui, sans-serif; }
  header { display: flex; justify-content: space-between; align-items: baseline; max-width: 1280px; margin: auto; }
  h1 { margin: 0; color: #1a2730; } header p { margin: 0; font-weight: 600; }
  .status, .players { display: flex; flex-wrap: wrap; gap: .75rem; max-width: 1280px; margin: .75rem auto; }
  .status span, .players article { padding: .45rem .7rem; background: rgba(255,255,255,.8); border-radius: .4rem; }
  .clock-display { display:grid; grid-template-columns:auto 1fr; align-items:center; gap:.2rem .65rem; min-width:19rem; padding:.4rem .65rem; border:2px solid #51462f; border-radius:.5rem; background:linear-gradient(135deg,#fff9e7,#e7d5a8); box-shadow:inset 0 0 0 2px rgba(255,255,255,.65); }
  .clock-display > strong { grid-row:span 3; color:#3d3424; font-size:1.05rem; }
  .clock-types, .clock-stones { display:flex; align-items:center; gap:.35rem; }
  .status .clock-type { padding:.12rem .4rem; border:1px solid #887b61; border-radius:1rem; color:#554c3b; background:#fffdf5; text-transform:capitalize; font-size:.78rem; }
  .status .clock-type.current { border:2px solid #a83224; background:#f8d5c8; color:#6d1e16; font-weight:900; box-shadow:0 0 0 2px rgba(168,50,36,.18); }
  .status .clock-current { padding:0 !important; background:transparent !important; color:#3d3424; font-size:.82rem; font-weight:800; }
  .status .clock-stone { padding:0; background:transparent; color:#b7b0a0; font-size:.8rem; text-shadow:0 1px 0 #fff; }
  .status .clock-stone.available { color:#176b9a; text-shadow:0 1px 0 #fff,0 0 3px rgba(23,107,154,.3); }
  .clock-stones small { margin-left:.2rem; color:#3d3424; font-size:.72rem; font-weight:700; }
  .pending-move { display:flex; align-items:center; flex-wrap:wrap; gap:.65rem; max-width:1280px; margin:.75rem auto; padding:.65rem .8rem; border:3px solid #e3af00; border-radius:.4rem; background:#fff5aa; }.pending-move button { padding:.4rem .8rem; border:2px solid #26343e; border-radius:.3rem; background:#fff; font-weight:800; cursor:pointer; }
  .reference-toggle { border: 1px solid #26343e; border-radius: .3rem; background: #fff; color:#14212b; font-weight:700; cursor:pointer; }
  .players article.current { outline: 3px dotted #d9a300; }
  .city { aspect-ratio: 4 / 3; max-width: 1280px; margin: auto; position: relative; border: 4px solid #40484e; background: #d7c9a8 url('/bus-game-board.png') center / contain no-repeat; overflow: hidden; }
  .route-map { position:absolute; inset:0; width:100%; height:100%; background: radial-gradient(circle at 50% 50%, rgba(255,255,255,.05), transparent 50%); }
  .street { stroke: #4a5258; stroke-width: .46; stroke-linecap: round; }
  .route { stroke-width: .26; stroke-linecap: round; }
  .route-end { stroke:#fff; stroke-width:.24; pointer-events:none; }
  .edge-reference, .node-reference { fill:#111; stroke:#fff; stroke-width:.12; paint-order:stroke; font-family:ui-monospace, monospace; font-size:1.05px; font-weight:800; text-anchor:middle; pointer-events:none; }
  .legal-route { cursor:pointer; }.legal-route:focus { outline:none; }.legal-route-hitbox { stroke:transparent; stroke-width:2.8; }.legal-route-highlight { stroke:#f6d300; stroke-width:.72; stroke-dasharray:1 1; stroke-linecap:round; pointer-events:none; }
  .legal-station { cursor:pointer; }.legal-station:focus { outline:none; }.station-station-hitbox { fill:transparent; stroke:transparent; }.legal-station-marker { stroke:#f6d300; stroke-width:.45; }
  circle { fill: #ecf0f1; stroke: #28323a; stroke-width: .18; }
  circle.station { fill: #ffe600; stroke-width: .32; }
  .site { position: absolute; z-index: 1; transform: translate(-50%, -50%); width: 2.5rem; height: 2.5rem; border-radius:50%; border: 3px solid #26343e; background: #fff; font-size: 1.2rem; }.site.built { background: var(--building-color); border-color: #fff; box-shadow: 0 0 0 3px var(--building-color), 0 2px 7px rgba(0,0,0,.5); color: #fff; text-shadow: 0 1px 2px #000; opacity: 1; }.site.reference-id { font-size:clamp(.45rem, .8vw, .7rem); }
  .passenger { position:absolute; z-index:2; transform:translate(-50%, -52%); color:#c01f36; font-size:1.7rem; line-height:1; text-shadow:0 1px 1px #fff; pointer-events:none; }
  .board-action-slot { position:absolute; z-index:3; transform:translate(-50%, -50%); width:2%; height:2.3%; padding:0; border:0; border-radius:.15rem; background:transparent; color:#17232c; font-size:clamp(.4rem, 1vw, .8rem); font-weight:900; cursor:default; display:flex; align-items:center; justify-content:center; }
  .board-action-slot.legal { cursor:pointer; outline:none; }
  .board-action-slot.legal:hover, .board-action-slot.legal:focus-visible { background:rgba(255, 224, 0, .35); outline:2px solid rgba(255, 180, 0, .9); outline-offset:1px; }
  .board-action-slot.selected { background:rgba(37, 99, 235, .3); outline:2px solid #2563eb; outline-offset:1px; }
  .marker-token { display:flex; align-items:center; justify-content:center; width:92%; height:92%; border-radius:.12rem; background:var(--marker-color, #8799a5); color:#fff; border:2px solid #17232c; box-shadow:0 1px 3px rgba(0,0,0,.45); line-height:1; }
  .legal { outline: 3px dotted #f6d300; outline-offset: 2px; cursor: pointer; } button:disabled { cursor: default; opacity: .7; }
  .pass-action { max-width:1280px; margin:.75rem auto; }.pass-action button { padding:.6rem .8rem; border:2px solid #29333a; background:#fff; border-radius:.35rem; font-weight:700; }
  .building-type-picker { position:absolute; z-index:5; left:50%; top:50%; transform:translate(-50%, -50%); min-width:12rem; padding:1rem; border:3px solid #26343e; border-radius:.45rem; background:#fff8b8; box-shadow:0 3px 12px rgba(0,0,0,.35); text-align:center; }.building-type-picker h2, .building-type-picker p { margin:.1rem 0 .6rem; }.building-type-picker button { margin:.2rem; padding:.35rem .6rem; }
  .action.pass { background:#fff; }.legal-list, .resolution-list { max-width:1280px; margin:auto; }.legal-list h2, .resolution-list h2 { font-size:1rem; }
  .legal-list button, .resolution-list button { margin: 0 .5rem .5rem 0; padding:.3rem .5rem; }
  .final-ranking { max-width:1280px; margin:.75rem auto; padding:.75rem 1rem; border:3px solid #26343e; background:#ffe920; border-radius:.35rem; }.final-ranking h2 { margin:0; }.final-ranking ol { margin:.4rem 0 0; }
</style>