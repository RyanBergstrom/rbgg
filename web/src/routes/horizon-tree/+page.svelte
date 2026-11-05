<script>
  let input = '';
  let records = [];
  let summaries = [];
  let error = '';
  let selected = null;

  function parseInput(value) {
    const trimmed = value.trim();
    if (!trimmed) return [];
    try {
      return JSON.parse(trimmed);
    } catch {
      // The simulator prints Python repr dictionaries. This intentionally
      // supports the diagnostic shape, not arbitrary Python execution.
      const normalized = (text) => text
        .replace(/None/g, 'null')
        .replace(/True/g, 'true')
        .replace(/False/g, 'false')
        .replace(/'/g, '"');
      try {
        return JSON.parse(normalized(trimmed));
      } catch {
        const objects = [];
        let depth = 0;
        let start = -1;
        let quote = '';
        let escaped = false;
        for (let index = 0; index < trimmed.length; index += 1) {
          const character = trimmed[index];
          if (quote) {
            if (escaped) escaped = false;
            else if (character === '\\') escaped = true;
            else if (character === quote) quote = '';
            continue;
          }
          if (character === '"' || character === "'") {
            quote = character;
          } else if (character === '{') {
            if (depth === 0) start = index;
            depth += 1;
          } else if (character === '}') {
            depth -= 1;
            if (depth === 0 && start >= 0) {
              objects.push(JSON.parse(normalized(trimmed.slice(start, index + 1))));
              start = -1;
            }
          }
        }
        if (!objects.length) throw new Error('Expected JSON or diagnostic dictionaries');
        return objects;
      }
    }
  }

  function loadTree() {
    try {
      const parsed = parseInput(input);
      const values = Array.isArray(parsed) ? parsed : [parsed];
      summaries = values.filter((record) => record && record.record_type === 'root_summary');
      records = values.filter((record) => record && Array.isArray(record.path));
      selected = records[0] || null;
      error = records.length ? '' : 'No diagnostic path records were found.';
    } catch (err) {
      records = [];
      selected = null;
      error = `Could not parse the pasted diagnostics: ${err.message}`;
    }
  }

  function clearTree() {
    input = '';
    records = [];
    summaries = [];
    selected = null;
    error = '';
  }

  function label(record) {
    const last = record.path?.at(-1)?.action;
    if (!last) return record.leaf_type || 'leaf';
    if (last.type === 'draw') return `draw: ${last.source}`;
    return `${last.type || 'move'}: ${last.card || last.move_id}`;
  }

  function groups() {
    const grouped = new Map();
    for (const record of records) {
      const root = record.path?.[0]?.move_id || 'root';
      if (!grouped.has(root)) grouped.set(root, []);
      grouped.get(root).push(record);
    }
    const summaryByMove = new Map(summaries.map((summary) => [summary.move, summary]));
    return [...grouped.entries()].map(([root, items]) => {
      const ordered = [...items].sort((a, b) => Number(b.value) - Number(a.value));
      const top = ordered.slice(0, 5);
      const bottom = ordered.slice(-5).reverse();
      const unique = [...new Map([...top, ...bottom].map((record) => [JSON.stringify(record.path), record])).values()];
      return {
        root,
        items: unique,
        totalSamples: items.length,
        summary: summaryByMove.get(root),
      };
    });
  }
</script>

<svelte:head>
  <title>Horizon Tree Explorer</title>
  <meta name="description" content="Explore hybrid MCTS horizon diagnostics." />
</svelte:head>

<main>
  <section class="hero">
    <div>
      <p class="eyebrow">RBGG / SEARCH TOOLS</p>
      <h1>Horizon Tree Explorer</h1>
      <p class="subtitle">Paste the diagnostic records from <strong>--explain</strong> to inspect paths, leaf values, and horizon contributions.</p>
    </div>
    <a href="/" class="back">Back to games</a>
  </section>

  <section class="workspace">
    <div class="input-card">
      <div class="card-heading">
        <div>
          <h2>Paste diagnostics</h2>
          <p>Accepts JSON or Python-style dictionary records printed by the simulator.</p>
        </div>
        <div class="actions">
          <button class="secondary" onclick={clearTree}>Clear</button>
          <button onclick={loadTree}>Build tree</button>
        </div>
      </div>
      <textarea bind:value={input} placeholder="Paste one or more diagnostic dictionaries here..."></textarea>
      {#if error}<p class="error">{error}</p>{/if}
    </div>

    {#if records.length}
      <div class="summary">
        <span><b>{records.length}</b> leaf records</span>
        <span><b>{new Set(records.map((record) => record.path?.[0]?.move_id)).size}</b> root actions</span>
        <span>max depth <b>{Math.max(...records.map((record) => record.depth || 0))}</b></span>
      </div>

      <div class="layout">
        <section class="tree-card">
          <div class="card-heading"><div><h2>Search paths</h2><p>Choose a root branch, then inspect its explored continuations.</p></div></div>
          {#each groups() as group}
            <div class="branch">
              <button class:selected={selected?.path?.[0]?.move_id === group.root} class="root-node" onclick={() => selected = group.items[0]}>
                <span class="chevron">›</span><span>{group.root}</span><span class="count">{group.summary?.visits ?? group.totalSamples} visits · avg {Number(group.summary?.average_value ?? (group.items.reduce((sum, item) => sum + Number(item.value), 0) / Math.max(1, group.items.length))).toFixed(3)}</span>
              </button>
              <div class="branch-leaves">
                <div class="range-label">TOP 5 / BOTTOM 5 OF {group.totalSamples} SAMPLED LEAVES</div>
                {#each group.items as record}
                  <button class:selected={selected === record} class="leaf" onclick={() => selected = record}>
                    <span class="depth">d{record.depth}</span>
                    <span class="path-label">{record.path.map((step) => step.action?.card || step.action?.source || step.move_id).join(' → ')}</span>
                    <span class="leaf-value">{Number(record.value).toFixed(3)}</span>
                  </button>
                {/each}
              </div>
            </div>
          {/each}
        </section>

        <aside class="details-card">
          {#if selected}
            <div class="card-heading"><div><h2>Leaf detail</h2><p>{selected.leaf_type} evaluation at depth {selected.depth}</p></div></div>
            <div class="metric"><span>Leaf value</span><strong>{Number(selected.value).toFixed(4)}</strong></div>
            <h3>Path</h3>
            <ol class="path-list">
              {#each selected.path as step, index}
                <li><span>{index + 1}</span><div><b>{step.action?.type || 'move'}</b><small>{step.action?.card || step.action?.source || step.move_id}</small></div></li>
              {/each}
            </ol>
            {#if selected.horizon}
              <h3>Horizon components</h3>
              <div class="components">
                {#each Object.entries(selected.horizon.contributions || {}) as [name, value]}
                  <div class="component"><div><span>{name.replaceAll('_', ' ')}</span><b>{Number(selected.horizon[name] || 0).toFixed(3)}</b></div><div class="bar"><i style={`width:${Math.max(0, Math.min(100, Number(value) * 100))}%`}></i></div><small>contribution {Number(value).toFixed(4)}</small></div>
                {/each}
              </div>
            {/if}
          {:else}
            <div class="empty"><span>◈</span><p>Select a path to inspect its horizon evaluation.</p></div>
          {/if}
        </aside>
      </div>
      {#if summaries.length}
        <section class="summary-card">
          <div class="card-heading"><div><h2>Why the move won</h2><p>Root-level evidence from the complete search; diagnostic samples are a bounded explanation sample.</p></div></div>
          <div class="table-wrap"><table><thead><tr><th>Move</th><th>Selected</th><th>Visits</th><th>One-ply</th><th>Avg value</th><th>Selection</th><th>Samples</th><th>Sample range</th></tr></thead><tbody>{#each summaries as summary}<tr class:selected-row={summary.selected}><td>{summary.move}</td><td>{summary.selected ? 'YES' : ''}</td><td>{summary.visits}</td><td>{Number(summary.one_ply_value || 0).toFixed(3)}</td><td>{Number(summary.average_value || 0).toFixed(3)}</td><td>{Number(summary.selection_score || 0).toFixed(3)}</td><td>{summary.diagnostic_samples}</td><td>{summary.sample_min === undefined ? '—' : `${Number(summary.sample_min).toFixed(3)}–${Number(summary.sample_max).toFixed(3)}`}</td></tr>{/each}</tbody></table></div>
        </section>
      {/if}
    {/if}
  </section>
</main>

<style>
  :global(*) { box-sizing: border-box; }
  :global(body) { margin: 0; background: #08111f; }
  main { min-height: 100vh; padding: 42px clamp(18px, 5vw, 76px) 80px; color: #e8f0f7; font-family: Inter, ui-sans-serif, system-ui, -apple-system, sans-serif; background: radial-gradient(circle at 85% 0%, #173354 0, transparent 34%), #08111f; }
  .hero { max-width: 1400px; margin: 0 auto 30px; display: flex; align-items: end; justify-content: space-between; gap: 24px; }
  .eyebrow { color: #63d9bd; font-size: 11px; letter-spacing: .18em; font-weight: 800; margin: 0 0 12px; }
  h1 { margin: 0; font-size: clamp(32px, 5vw, 58px); letter-spacing: -.05em; line-height: .98; }
  .subtitle { color: #91a5b8; max-width: 650px; line-height: 1.6; margin: 16px 0 0; }
  .back { color: #8ce2ce; text-decoration: none; border: 1px solid #234359; padding: 10px 15px; border-radius: 10px; white-space: nowrap; }
  .workspace { max-width: 1400px; margin: auto; }
  .input-card, .tree-card, .details-card { background: rgba(13, 29, 47, .88); border: 1px solid #1d3a52; border-radius: 18px; box-shadow: 0 18px 55px rgba(0,0,0,.18); }
  .input-card { padding: 22px; }
  .card-heading { display: flex; justify-content: space-between; gap: 18px; align-items: center; }
  h2 { margin: 0; font-size: 19px; letter-spacing: -.02em; }
  h3 { margin: 27px 0 12px; font-size: 12px; text-transform: uppercase; color: #7c9bb2; letter-spacing: .12em; }
  .card-heading p { margin: 6px 0 0; color: #7892a6; font-size: 13px; }
  textarea { width: 100%; min-height: 180px; margin-top: 20px; resize: vertical; border-radius: 12px; border: 1px solid #294a62; background: #07101c; color: #dcebf4; padding: 15px; font: 12px/1.55 ui-monospace, SFMono-Regular, Consolas, monospace; outline: none; }
  textarea:focus { border-color: #63d9bd; box-shadow: 0 0 0 3px rgba(99,217,189,.12); }
  button { border: 0; border-radius: 9px; color: #06121c; background: #63d9bd; padding: 10px 15px; font-weight: 750; cursor: pointer; }
  button:hover { filter: brightness(1.08); } button.secondary { color: #a7bfd0; background: #12283b; border: 1px solid #294a62; }
  .actions { display: flex; gap: 8px; } .error { color: #ff9a9a; margin: 12px 0 0; font-size: 13px; }
  .summary { display: flex; gap: 10px; flex-wrap: wrap; margin: 18px 0; } .summary span { border: 1px solid #24445b; background: #0d2032; color: #88a2b4; border-radius: 999px; padding: 8px 12px; font-size: 12px; } .summary b { color: #dffaf3; }
  .layout { display: grid; grid-template-columns: minmax(0, 1.25fr) minmax(330px, .75fr); gap: 18px; align-items: start; }
  .tree-card, .details-card { padding: 22px; } .branch { margin-top: 16px; } .root-node, .leaf { width: 100%; display: flex; align-items: center; gap: 10px; text-align: left; background: #10263a; border: 1px solid #204259; color: #d7e7ef; padding: 11px 13px; } .root-node.selected, .leaf.selected { background: #16463f; border-color: #63d9bd; } .chevron { color: #63d9bd; font-size: 20px; } .count { margin-left: auto; color: #7b9bad; font-size: 11px; } .branch-leaves { border-left: 1px solid #28465a; margin-left: 15px; padding-left: 12px; } .leaf { border-radius: 0; border-top: 0; background: transparent; font-weight: 500; } .leaf:first-child { border-radius: 8px 8px 0 0; } .leaf:last-child { border-radius: 0 0 8px 8px; } .depth { color: #63d9bd; font: 11px ui-monospace, monospace; } .path-label { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; } .leaf-value { margin-left: auto; color: #f6d58b; font: 12px ui-monospace, monospace; }
  .details-card { position: sticky; top: 18px; min-height: 360px; } .metric { display: flex; justify-content: space-between; align-items: center; background: #091725; border: 1px solid #203d53; padding: 16px; border-radius: 12px; margin-top: 20px; color: #91a9b8; } .metric strong { color: #8ce2ce; font-size: 26px; } .path-list { list-style: none; margin: 0; padding: 0; } .path-list li { display: flex; gap: 12px; align-items: center; padding: 9px 0; border-bottom: 1px solid #193347; } .path-list li > span { color: #63d9bd; font: 12px ui-monospace, monospace; } .path-list b, .path-list small { display: block; } .path-list small { color: #91a9b8; margin-top: 3px; } .components { display: grid; gap: 12px; } .component > div:first-child { display: flex; justify-content: space-between; font-size: 13px; } .component b { color: #f6d58b; font: 12px ui-monospace, monospace; } .component small { color: #718b9c; font-size: 11px; } .bar { height: 6px; background: #11283a; border-radius: 99px; margin: 6px 0 4px; overflow: hidden; } .bar i { display: block; height: 100%; background: linear-gradient(90deg, #63d9bd, #81b8ff); border-radius: inherit; }
  .empty { min-height: 310px; display: grid; place-content: center; text-align: center; color: #6d8799; } .empty span { color: #63d9bd; font-size: 40px; } .empty p { max-width: 190px; line-height: 1.5; }
  .range-label { padding: 12px 8px 5px; color: #6f8da0; font-size: 10px; letter-spacing: .1em; font-weight: 800; }
  .summary-card { margin-top: 18px; padding: 22px; background: rgba(13, 29, 47, .88); border: 1px solid #1d3a52; border-radius: 18px; overflow: hidden; } .table-wrap { overflow-x: auto; margin-top: 18px; } table { width: 100%; border-collapse: collapse; font: 12px ui-monospace, SFMono-Regular, Consolas, monospace; } th, td { padding: 11px 10px; border-bottom: 1px solid #1b384d; text-align: right; white-space: nowrap; } th:first-child, td:first-child { text-align: left; } th { color: #7d9aab; font-size: 10px; text-transform: uppercase; letter-spacing: .08em; } td { color: #c7d9e3; } tr.selected-row td { color: #8ce2ce; background: rgba(99,217,189,.08); }
  @media (max-width: 850px) { .hero { align-items: start; flex-direction: column; } .layout { grid-template-columns: 1fr; } .details-card { position: static; } }
</style>
