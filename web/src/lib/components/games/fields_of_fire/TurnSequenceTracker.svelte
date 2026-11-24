<script>
  // Turn sequence (rulebook section 3), shown as a collapsible left column.
  // Each phase is a row from top to bottom. The current phase opens by default,
  // and any row can be opened or closed. Setup and game over are not shown.
  export let sequence = [];
  export let currentPhase = null;
  export let turn = 1;
  export let durationTurns = null;

  const HIDDEN = ['setup', 'game_over'];

  let collapsed = false;
  // User overrides per phase: true = open, false = closed. Missing = default.
  let overrides = {};

  $: phases = sequence.filter(step => !HIDDEN.includes(step.phase));
  $: currentIndex = phases.findIndex(step => step.phase === currentPhase);
  $: current = currentIndex >= 0 ? phases[currentIndex] : null;

  function isOpen(step) {
    if (step.phase in overrides) return overrides[step.phase];
    return step.phase === currentPhase;
  }

  function toggle(step) {
    overrides = { ...overrides, [step.phase]: !isOpen(step) };
  }
</script>

<aside class="turn-tracker" class:collapsed aria-label="Turn sequence">
  <div class="tt-top">
    {#if !collapsed}
      <div class="tt-title">
        <strong>Turn {turn}{durationTurns ? ` of ${durationTurns}` : ''}</strong>
      </div>
    {/if}
    <button
      type="button"
      class="tt-collapse"
      aria-expanded={!collapsed}
      title={collapsed ? 'Show turn sequence' : 'Hide turn sequence'}
      on:click={() => (collapsed = !collapsed)}
    >
      {collapsed ? '▶' : '◀'}
    </button>
  </div>

  {#if !collapsed}
    <ol class="tt-phases">
      {#each phases as step, index (step.phase)}
        {@const open = isOpen(step)}
        <li
          class="tt-phase"
          class:done={index < currentIndex}
          class:current={index === currentIndex}
          aria-current={index === currentIndex ? 'step' : undefined}
        >
          <button type="button" class="tt-row" aria-expanded={open} on:click={() => toggle(step)}>
            <span class="tt-marker">{index < currentIndex ? '✓' : index + 1}</span>
            <span class="tt-label">{step.label}</span>
            {#if step.rule && step.rule !== '—'}<span class="tt-rule">{step.rule}</span>{/if}
            <span class="tt-chevron">{open ? '▾' : '▸'}</span>
          </button>

          {#if open && step.segments && step.segments.length}
            <div class="tt-segments">
              <strong>This phase:</strong>
              <ul>
                {#each step.segments as segment}
                  <li>{segment.label} <span class="tt-rule">{segment.rule}</span></li>
                {/each}
              </ul>
            </div>
          {/if}
        </li>
      {/each}
    </ol>
  {/if}
</aside>

<style>
  .turn-tracker {
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
  }

  .turn-tracker.collapsed {
    width: 2.2rem;
    padding: 0.4rem 0.2rem;
  }

  .tt-top {
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 0.4rem;
    margin-bottom: 0.4rem;
  }

  .tt-title strong {
    color: #ffd700;
  }

  .tt-collapse {
    background: #51471d;
    color: #ffe66c;
    border: 1px solid #887a2d;
    border-radius: 5px;
    padding: 0.2rem 0.45rem;
    cursor: pointer;
    font-size: 0.75rem;
  }

  .tt-phases {
    list-style: none;
    margin: 0;
    padding: 0;
    display: flex;
    flex-direction: column;
    gap: 0.3rem;
  }

  .tt-phase {
    border: 1px solid #555;
    border-radius: 6px;
    background: #2a2a1a;
    color: #aaa;
  }

  .tt-phase.done {
    color: #8fbf8f;
    border-color: #3d6b3d;
  }

  .tt-phase.current {
    color: #1a1a0a;
    background: #ffd700;
    border-color: #fff0a3;
    font-weight: 700;
  }

  .tt-row {
    width: 100%;
    display: grid;
    grid-template-columns: 1.3rem minmax(0, 1fr) auto auto;
    align-items: center;
    gap: 0.35rem;
    padding: 0.35rem 0.45rem;
    background: transparent;
    border: none;
    color: inherit;
    font: inherit;
    text-align: left;
    cursor: pointer;
  }

  .tt-marker {
    display: grid;
    place-items: center;
    width: 1.2rem;
    height: 1.2rem;
    border-radius: 50%;
    background: #3a3a2a;
    font-size: 0.68rem;
  }

  .tt-phase.current .tt-marker {
    background: #1a1a0a;
    color: #ffd700;
  }

  .tt-label {
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }

  .tt-rule {
    font-family: monospace;
    font-size: 0.65rem;
    color: #b7b79f;
    white-space: nowrap;
  }

  .tt-phase.current .tt-rule {
    color: #3a3212;
  }

  .tt-chevron {
    font-size: 0.7rem;
  }

  .tt-segments {
    padding: 0.3rem 0.5rem 0.5rem 0.5rem;
    font-size: 0.72rem;
    color: #1a1a0a;
    border-top: 1px solid rgba(0, 0, 0, 0.2);
  }

  .tt-phase:not(.current) .tt-segments {
    color: #ddd;
  }

  .tt-segments ul {
    margin: 0.2rem 0 0;
    padding-left: 1rem;
  }

  .tt-segments li {
    margin-bottom: 0.15rem;
  }
</style>
