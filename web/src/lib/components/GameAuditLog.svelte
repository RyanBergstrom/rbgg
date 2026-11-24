<script>
  import { onMount } from 'svelte';
  export let entries = [];
  let expanded = false;
  let container;

  onMount(() => { console.log('GameAuditLog mounted, entries:', entries.length); });

  $: if (expanded && container) {
    setTimeout(() => { container.scrollTop = container.scrollHeight; }, 0);
  }

  function formatTime(ts) {
    const d = new Date(ts);
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
  }
</script>

<div class="audit-log" class:expanded>
  <button class="audit-toggle" on:click={() => expanded = !expanded}>
    {expanded ? '▾' : '▸'} Audit Log ({entries.length})
  </button>
  {#if expanded}
    <div class="audit-body" bind:this={container}>
      {#if entries.length === 0}
        <div class="audit-empty">No activity yet.</div>
      {:else}
        {#each entries as entry (entry.id)}
          <div class="audit-entry">
            <span class="audit-time">{formatTime(entry.timestamp)}</span>
            <span class="audit-text">{entry.text}</span>
          </div>
        {/each}
      {/if}
    </div>
  {/if}
</div>

<style>
  .audit-log {
    position: fixed;
    top: 1rem;
    right: 1rem;
    width: 300px;
    max-width: 90vw;
    z-index: 9999;
    font-size: 0.75rem;
    font-family: monospace;
  }
  .audit-toggle {
    width: 100%;
    text-align: left;
    padding: 0.45rem 0.7rem;
    background: #1f3a5f;
    color: #fff;
    border: 1px solid #4a90e2;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.8rem;
    font-weight: 600;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
  }
  .audit-body {
    max-height: 40vh;
    overflow-y: auto;
    background: #1a1a1a;
    color: #ddd;
    border: 1px solid #4a90e2;
    border-top: none;
    border-radius: 0 0 6px 6px;
    padding: 0.4rem 0.6rem;
  }
  .audit-entry {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
    line-height: 1.3;
  }
  .audit-time {
    color: #888;
    flex-shrink: 0;
  }
  .audit-text {
    word-break: break-word;
  }
  .audit-empty {
    color: #666;
    font-style: italic;
  }
</style>
"