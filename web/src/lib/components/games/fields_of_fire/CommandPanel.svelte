<script>
  // Command controls for the Friendly Command phase. Every button is driven by
  // the server's legal moves, so the UI cannot offer a move the rules reject.
  import { createEventDispatcher } from 'svelte';
  import { movementAction } from '$lib/stores/fofCommand';
  export let legalMoves = [];
  export let activated = [];
  export let hqLabels = {};
  export let phaseName = null;
  export let hqOrder = [];
  export let pools = {};
  export let lastFire = null;
  export let canUndo = false;
  export let dispatchMove = (move) => {};

  const dispatch = createEventDispatcher();

  let selectedCommander = null;
  function toggleCommander(id) {
    selectedCommander = selectedCommander === id ? null : id;
  }

  // Short labels so the command box fits the footer.
  function abbr(label) {
    return String(label)
      .replace('Battalion HQ', 'BN HQ')
      .replace('Company HQ', 'CO HQ')
      .replace('Company Executive Officer', 'CO XO')
      .replace('Company First Sergeant', 'CO 1SG')
      .replace('Platoon HQ', 'PLT HQ');
  }

  $: activateMoves = legalMoves.filter(m => m.type === 'activate_hq');
  $: readyIds = new Set(activateMoves.map(m => m.hq_id));
  $: hqRows = hqOrder.map(id => ({
    id,
    label: abbr(hqLabels[id] || id),
    state: activated.includes(id) ? 'done' : readyIds.has(id) ? 'ready' : 'waiting',
    move: activateMoves.find(m => m.hq_id === id),
    pool: pools[id] ?? 0,
    draw: legalMoves.find(m => m.type === 'draw_commands' && m.hq_id === id),
    spend: legalMoves.find(m => m.type === 'spend_command' && m.hq_id === id),
  }));
  $: advanceMove = legalMoves.find(m => m.type === 'advance_phase');
  $: commandStripMoves = [
    ...new Map(
      (legalMoves || [])
        .filter(m => {
          if ([
            'draw_commands', 'spend_command', 'advance_phase', 'move_unit', 'move_stack',
            'place_unit', 'place_vof', 'infiltrate', 'fire',
          ].includes(m.type)) return false;
          if (selectedCommander && m.originator_hq_id !== selectedCommander) return false;
          return true;
        })
        .map(m => [m.move_id, m])
    ).values(),
  ];
  $: if (legalMoves) selectedCommander = null;
  $: visible = phaseName === 'friendly_command' || phaseName === 'mutual_combat';
  // 6.4: fire is offered per VOF-marked card in Mutual Combat.
  $: fireMoves = legalMoves.filter(m => m.type === 'fire');

  // VOF placement (6.2.1): the server only offers placements in line of sight.
  $: vofMoves = legalMoves.filter(m => m.type === 'place_vof');
  $: vofOrigins = [...new Set(vofMoves.map(m => m.from_position))].sort((a, b) => a - b);
  let vofOrigin = null;
  let vofTarget = null;
  let vofRating = null;
  $: if (!vofOrigins.includes(vofOrigin)) vofOrigin = vofOrigins[0] ?? null;
  $: vofTargets = [...new Set(vofMoves.filter(m => m.from_position === vofOrigin).map(m => m.position))].sort((a, b) => a - b);
  $: if (!vofTargets.includes(vofTarget)) vofTarget = vofTargets[0] ?? null;
  $: vofRatings = vofMoves
    .filter(m => m.from_position === vofOrigin && m.position === vofTarget)
    .map(m => m.rating);
  $: if (!vofRatings.includes(vofRating)) vofRating = vofRatings[0] ?? null;
  $: selectedVof = vofMoves.find(m => m.from_position === vofOrigin && m.position === vofTarget && m.rating === vofRating);

  // Action categories sourced from the config (4.2.1-4.2.4).
  const ACTION_CATEGORY = {
    'activate_a_subordinate_hq_or_staff': 'cmd_ctrl',
    'exhort': 'cmd_ctrl',
    'deploy_pyrotechnic': 'cmd_ctrl',
    'reconstitute_a_plt_hq': 'cmd_ctrl',
    'reconstitute_the_co_hq': 'cmd_ctrl',
    'create_a_runner': 'cmd_ctrl',
    'dispatch_a_runner': 'cmd_ctrl',
    'dismiss_a_runner': 'cmd_ctrl',
    'activate_for_at_combat_&_vehicle_movement': 'cmd_ctrl',
    'switch_radio_phone_to_a_different_network': 'cmd_ctrl',
    'repair_a_cut_phone_line': 'cmd_ctrl',
    'designate_a_new_tactical_control': 'cmd_ctrl',
    'move_to_an_adjacent_card': 'movement',
    'move_a_platoon_to_an_adjacent_card': 'movement',
    'attempt_to_infiltrate_an_adjacent_card': 'movement',
    'attempt_to_have_a_platoon_infiltrate_an_adjacent_card': 'movement',
    'attempt_to_seek_cover': 'movement',
    'move_within_a_card': 'movement',
    'attempt_to_infiltrate_within_a_card': 'movement',
    'pick_up_load_unload_embark': 'movement',
    'attempt_to_remove_a_pinned_marker': 'rally',
    'attempt_to_convert_a_paralyzed_team_to_a_litter_team': 'rally',
    'attempt_to_convert_a_litter_team_to_a_fire_team': 'rally',
    'attempt_to_convert_a_fire_team_to_an_assault_team': 'rally',
    'convert_an_assault_team_to_a_fire_team': 'rally',
    'attempt_to_flip_a_unit_with_a_fire_team_side_to_front': 'rally',
    'detach_team': 'rally',
    'supplement_squad': 'rally',
    'attempt_to_reconstitute_squad': 'rally',
    'flip_a_unit_with_a_fire_team_side_to_its_fire_team_side': 'rally',
    'attempt_to_spot': 'combat',
    'attempt_to_concentrate_fire': 'combat',
    'attempt_to_have_a_platoon_concentrate_fire': 'combat',
    'attempt_to_make_a_grenade_attack': 'combat',
    'attempt_to_throw_a_demolition_charge': 'combat',
    'place_a_demolition_charge': 'combat',
    'flamethrower_attack': 'combat',
    'attempt_to_have_a_platoon_make_a_grenade_attack': 'combat',
    'attempt_to_call_for_fire_from_an_off_map_firing_agency_includes_air_strikes_and_attack_helicopters': 'combat',
    'call_for_indirect_fire_from_an_on_map_mortar': 'combat',
    'cease_fire': 'combat',
    'shift_fire': 'combat',
    'fire_fpf_fpl': 'combat',
  };
  const CATEGORY_ORDER = ['cmd_ctrl', 'movement', 'rally', 'combat'];
  const CATEGORY_LABELS = {
    'cmd_ctrl': 'Command & Control',
    'movement': 'Movement',
    'rally': 'Rally',
    'combat': 'Combat',
  };

  let selectedCategory = null;
  $: commandCategories = (() => {
    const byCat = new Map();
    for (const move of commandStripMoves) {
      const cat = ACTION_CATEGORY[move.type] || 'combat';
      if (!byCat.has(cat)) byCat.set(cat, []);
      byCat.get(cat).push(move);
    }
    return CATEGORY_ORDER.filter(k => byCat.has(k)).map(k => {
      const byType = new Map();
      for (const m of byCat.get(k)) {
        if (!byType.has(m.type)) byType.set(m.type, []);
        byType.get(m.type).push(m);
      }
      return {
        key: k,
        label: CATEGORY_LABELS[k],
        groups: [...byType.entries()].map(([type, moves]) => ({ type, moves })),
      };
    });
  })();

  // Movement action: click button → board highlights eligible units → click unit → board highlights destinations → click destination
  let moveActionType = null;
  let selectedMoveUnit = null;
  let selectedMoveDest = null;

  function isMovementAction(type) {
    return type === 'move_to_an_adjacent_card' || type === 'move_a_platoon_to_an_adjacent_card';
  }

  function startMoveSelection(type) {
    moveActionType = type;
    selectedMoveUnit = null;
    selectedMoveDest = null;
    movementAction.set({
      type,
      step: 'select_unit',
      selectedUnitId: null,
      originatorId: selectedCommander,
    });
  }

  function commandActionLabel(move) {
    if (move.type === 'activate_hq') return `Act ${abbr(hqLabels[move.hq_id] || move.hq_id)}`;
    return String(move.type || move.move_id || 'Action')
      .replace(/_/g, ' ')
      .replace(/\b\w/g, char => char.toUpperCase());
  }
</script>

{#if phaseName === 'friendly_higher_hq_event' && advanceMove}
  <section class="command-panel" aria-label="Higher HQ Event controls">
    <div class="cp-row">
      <span class="cp-label">HQ Event (T2+)</span>
      <button type="button" class="cp-btn cp-next" on:click={() => dispatchMove(advanceMove)}>Continue</button>
      <button type="button" class="cp-btn cp-exit" on:click={() => dispatch('exit')}>Exit</button>
    </div>
  </section>
{/if}

{#if visible}
  <section class="command-panel" aria-label="Command controls">
    <div class="cp-row cp-order">
      <span class="cp-label">Order:</span>
      {#each hqRows as row (row.id)}
        <div class="cp-hq-group">
          <button
            type="button"
            class="cp-btn cp-hq cp-{row.state}"
            class:cp-expanded={selectedCommander === row.id}
            disabled={row.state === 'waiting'}
            title={row.state === 'waiting' ? 'Waiting: an earlier HQ must activate first' : row.state === 'done' ? (row.pool > 0 ? 'Click to use a command' : (row.draw ? 'Click to draw commands' : 'Already activated this turn')) : (row.id === hqOrder[0] || activated.length === 0) ? 'Click to activate (free)' : 'Click a commander to activate'}
            on:click={() => {
              // The first HQ in the activation chain activates for free directly:
              // BN HQ when it is on the map, otherwise the CO HQ. All later
              // activations go through a commander's action strip.
              const isFirstActivation = row.id === hqOrder[0] || activated.length === 0;
              if (row.state === 'ready' && row.move && isFirstActivation) { dispatchMove(row.move); selectedCommander = null; }
              else if (row.state === 'done' && row.pool > 0) { toggleCommander(row.id); }
              else if (row.state === 'done' && row.pool === 0 && row.draw) { dispatchMove(row.draw); selectedCommander = null; }
            }}
          >
            {row.label}
            <small>{row.state === 'done' ? (row.pool > 0 ? `${row.pool} Available` : (row.draw ? 'Draw' : 'finished')) : row.state === 'ready' ? 'Ready' : 'finished'}</small>
          </button>
        </div>
      {/each}
      <div class="cp-exit-group">
        <button type="button" class="cp-btn cp-exit" on:click={() => dispatch('exit')}>Exit</button>
        {#if advanceMove}
          <button type="button" class="cp-btn cp-next" on:click={() => dispatchMove(advanceMove)}>End Cmd</button>
        {/if}
        <button type="button" class="cp-btn cp-undo" disabled={!canUndo} on:click={() => dispatch('undo')}>Undo</button>
        </div>
      </div>
    {#if selectedCommander !== null}
      <div class="cp-command-strip">
        {#each commandCategories as category}
          <div class="cp-category">
            <button type="button" class="cp-cat-btn" class:cp-expanded={selectedCategory === category.key} on:click={() => selectedCategory = selectedCategory === category.key ? null : category.key} aria-expanded={selectedCategory === category.key}>
              {category.label}
            </button>
            {#if selectedCategory === category.key}
              <div class="cp-category-actions cp-cols-3">
                {#each category.groups as group (group.type)}
                  <div class="cp-cmd-group">
                    {#if isMovementAction(group.type)}
                      <button type="button" class="cp-btn cp-cmd" on:click={() => startMoveSelection(group.type)}>
                        {commandActionLabel(group.moves[0])}
                      </button>
                    {:else}
                      <button type="button" class="cp-btn cp-cmd" on:click={() => {
                        const selected = group.moves[0];
                        if (selected) { dispatchMove(selected); selectedCommander = null; }
                      }}>{commandActionLabel(group.moves[0])}</button>
                    {/if}
                  </div>
                {/each}
              </div>
            {/if}
          </div>
        {/each}
      </div>
    {/if}
      {#if phaseName === 'mutual_combat'}
      <div class="cp-row cp-fire">
        <span class="cp-label">Fire:</span>
        {#each fireMoves as fire (fire.position)}
          <button type="button" class="cp-btn" on:click={() => dispatchMove(fire)}>Card {fire.position}</button>
        {/each}
        {#if fireMoves.length === 0}
          <span class="cp-label">No VOF target</span>
        {/if}
      </div>
      {#if lastFire}
        <div class="cp-row cp-lastdraw">
          <span class="cp-label">Last fire:</span>
          <strong>card {lastFire.position}</strong>
          <span>net {lastFire.net_modifier}, result <strong class="cp-pool">{lastFire.result}</strong></span>
        </div>
      {/if}
    {/if}
  </section>
{/if}

<style>
  .command-panel {
    background: #222217;
    border: 1px solid #62624d;
    border-radius: 8px;
    padding: 0.55rem 0.75rem;
    margin: 0 auto 0.75rem;
    max-width: 900px;
    color: #eee;
    font-size: 0.8rem;
    box-sizing: border-box;
  }

  .cp-row {
    display: flex;
    flex-wrap: wrap;
    align-items: flex-start;
    gap: 0.5rem;
    margin-bottom: 0.35rem;
  }

  .cp-pool {
    color: #ffd700;
  }

  .cp-label {
    color: #b7b79f;
  }

  .cp-btn {
    padding: 0.2rem 0.45rem;
    border: 1px solid #887a2d;
    border-radius: 4px;
    background: #51471d;
    color: #ffe66c;
    font-size: 0.68rem;
    font-weight: 700;
    line-height: 1.1;
    white-space: nowrap;
    cursor: pointer;
  }

  .cp-exit {
    background: #7a1f1f;
    border-color: #c04a4a;
    color: #fff;
    margin-left: auto;
  }

  .cp-btn:hover {
    background: #6b5f25;
  }

  .cp-next {
    background: #296341;
    border-color: #55a675;
    color: #fff;
  }

  .cp-hq {
    background: #3a3a2a;
    border-color: #888;
    color: #eee;
  }

  .cp-hq small {
    display: block;
    font-size: 0.6rem;
    font-weight: 400;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .cp-ready {
    background: #ffd700;
    border-color: #fff0a3;
    color: #1a1a0a;
  }

  .cp-done {
    background: #2d4a2d;
    border-color: #3d6b3d;
    color: #8fbf8f;
  }

  .cp-exit-group {
    display: flex;
    flex-direction: column;
    gap: 0.35rem;
    align-items: stretch;
    margin-left: auto;
  }
  .cp-undo {
    background: #6c757d;
    border-color: #8a8a8a;
    color: #fff;
  }

  .cp-undo:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }
  .cp-command-strip {
    width: 100%;
    margin-top: 0.15rem;
    box-sizing: border-box;
  }

  .cp-command-list {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    padding: 0.4rem;
    margin-top: 0;
    background: #5a4a2a;
    border: 1px solid #887a2d;
    border-radius: 4px;
  }

  .cp-cmd {
    background: #7a6a3a;
    border-color: #b8a050;
    color: #fff;
  }

  .cp-cmd:hover {
    background: #8a7a4a;
  }

  .cp-expanded {
    box-shadow: 0 0 0 2px #ffd700;
  }
  .cp-waiting {
    opacity: 0.5;
    cursor: not-allowed;
  }

  /* Unslop pass */
  .command-panel {
    background: var(--fof-surface);
    border: 1px solid var(--fof-border);
    border-radius: var(--fof-radius-md);
    color: var(--fof-text);
    font-family: var(--fof-font);
    font-size: 0.8rem;
    box-shadow: none;
  }

  .cp-row {
    gap: var(--fof-space-1);
    margin-bottom: var(--fof-space-1);
  }

  .cp-label {
    color: var(--fof-muted);
    font-size: 0.75rem;
  }

  .cp-pool {
    color: var(--fof-accent);
    font-family: var(--fof-mono);
    font-variant-numeric: tabular-nums;
  }

  .cp-btn {
    border-radius: var(--fof-radius-sm);
    border: 1px solid var(--fof-border-strong);
    background: var(--fof-surface-2);
    color: var(--fof-text);
    font-size: 0.7rem;
    font-weight: 500;
    transition: background-color var(--fof-dur-fast) var(--fof-ease), border-color var(--fof-dur-fast) var(--fof-ease), color var(--fof-dur-fast) var(--fof-ease);
  }

  .cp-btn:hover {
    background: var(--fof-surface-3);
    border-color: var(--fof-accent);
  }

  .cp-hq {
    background: var(--fof-surface-2);
    border-color: var(--fof-border-strong);
    color: var(--fof-text);
  }

  .cp-hq small {
    text-transform: none;
    letter-spacing: 0;
    font-size: 0.65rem;
    color: var(--fof-muted);
  }

  .cp-ready {
    background: var(--fof-accent);
    border-color: var(--fof-accent);
    color: var(--fof-accent-text);
  }

  .cp-done {
    background: var(--fof-surface-3);
    border-color: var(--fof-border-strong);
    color: var(--fof-success);
  }

  .cp-exit {
    background: var(--fof-danger);
    border-color: var(--fof-danger);
    color: var(--fof-text);
  }

  .cp-next {
    background: var(--fof-success);
    border-color: var(--fof-success);
    color: var(--fof-text);
  }

  .cp-undo {
    background: var(--fof-surface-3);
    border-color: var(--fof-border-strong);
    color: var(--fof-text-2);
  }

  .cp-undo:disabled {
    opacity: 0.45;
  }

  .cp-command-list {
    background: var(--fof-surface-2);
    border: 1px solid var(--fof-border-strong);
    border-radius: var(--fof-radius-sm);
  }

  .cp-cmd {
    background: var(--fof-surface-3);
    border-color: var(--fof-border-strong);
    color: var(--fof-text);
  }

  .cp-expanded {
    box-shadow: 0 0 0 2px var(--fof-accent);
  }

  .cp-waiting {
    opacity: 0.45;
  }

  select {
    background: var(--fof-surface-2);
    color: var(--fof-text);
    border: 1px solid var(--fof-border-strong);
    border-radius: var(--fof-radius-sm);
    font-family: var(--fof-font);
  }

  button:focus-visible,
  select:focus-visible {
    outline: 2px solid var(--fof-accent);
    outline-offset: 2px;
  }

  /* Consistent command-bar buttons — no more unstyled white squares */
  .cp-cat-btn {
    width: 100%;
    padding: 0.28rem 0.45rem;
    border: 1px solid var(--fof-border-strong);
    border-radius: var(--fof-radius-sm);
    background: var(--fof-surface-2);
    color: var(--fof-text);
    font-family: var(--fof-font);
    font-size: 0.68rem;
    font-weight: 600;
    text-align: left;
    cursor: pointer;
    transition: background-color var(--fof-dur-fast) var(--fof-ease), border-color var(--fof-dur-fast) var(--fof-ease);
  }

  .cp-cat-btn:hover {
    background: var(--fof-surface-3);
    border-color: var(--fof-accent);
  }

  .cp-cat-btn[aria-expanded="true"] {
    background: var(--fof-surface-3);
    border-color: var(--fof-accent);
  }

  .cp-move-unit,
  .cp-move-dest,
  .cp-back,
  .cp-cmd {
    padding: 0.25rem 0.4rem;
    font-size: 0.66rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .cp-category-actions {
    gap: var(--fof-space-1);
    padding: var(--fof-space-1);
  }

  .cp-cmd-group {
    display: flex;
    flex-direction: column;
    gap: var(--fof-space-1);
  }

  .cp-move-selector {
    display: flex;
    flex-direction: column;
    gap: var(--fof-space-1);
  }
</style>
