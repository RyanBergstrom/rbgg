<script>
  import { createEventDispatcher } from 'svelte';

  export let screenState = null;

  const dispatch = createEventDispatcher();

  let jsonInput = '';
  let statusMessage = '';
  let statusType = '';

  function handleLoad() {
    statusMessage = '';
    statusType = '';

    let parsed;
    try {
      parsed = JSON.parse(jsonInput);
    } catch (e) {
      statusMessage = `Invalid JSON: ${e.message}`;
      statusType = 'error';
      return;
    }

    dispatch('load-state', parsed);
    statusMessage = 'State loaded';
    statusType = 'success';
  }

  function handleCopyCurrent() {
    if (!screenState) {
      statusMessage = 'No current state to copy';
      statusType = 'error';
      return;
    }

    const json = JSON.stringify(screenState, null, 2);
    navigator.clipboard.writeText(json).then(() => {
      statusMessage = 'Current state copied to clipboard';
      statusType = 'success';
    }).catch(() => {
      jsonInput = json;
      statusMessage = 'Current state placed in textarea (clipboard blocked)';
      statusType = 'success';
    });
  }

  function handleFormat() {
    try {
      const parsed = JSON.parse(jsonInput);
      jsonInput = JSON.stringify(parsed, null, 2);
      statusMessage = 'Formatted';
      statusType = 'success';
    } catch (e) {
      statusMessage = `Invalid JSON: ${e.message}`;
      statusType = 'error';
    }
  }

  function handleClear() {
    dispatch('clear-state');
    statusMessage = 'Debug state cleared — page will reload with real state';
    statusType = 'success';
  }
</script>

<div class="debug-panel">
  <div class="debug-header">
    <span class="debug-title">Debug Panel</span>
    <div class="debug-actions">
      <button class="debug-btn danger" on:click={handleClear}>Clear</button>
      <button class="debug-btn secondary" on:click={handleCopyCurrent}>Copy Current</button>
      <button class="debug-btn secondary" on:click={handleFormat}>Format</button>
      <button class="debug-btn primary" on:click={handleLoad}>Load State</button>
    </div>
  </div>

  <textarea
    class="debug-textarea"
    bind:value={jsonInput}
    placeholder="Paste screen state JSON here..."
    spellcheck="false"
  ></textarea>

  {#if statusMessage}
    <div class="debug-status {statusType}">{statusMessage}</div>
  {/if}
</div>

<style>
  .debug-panel {
    padding: 0.5rem 1rem 1rem;
    border-top: 2px dashed #e74c3c;
    background: #fff8f8;
    box-sizing: border-box;
    flex-shrink: 0;
  }

  .debug-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 0.5rem;
  }

  .debug-title {
    font-size: 0.8rem;
    font-weight: 700;
    color: #e74c3c;
    font-family: monospace;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .debug-actions {
    display: flex;
    gap: 0.4rem;
  }

  .debug-btn {
    padding: 0.3rem 0.7rem;
    border: none;
    border-radius: 3px;
    cursor: pointer;
    font-size: 0.75rem;
    font-weight: 600;
    font-family: monospace;
  }

  .debug-btn.primary {
    background: #e74c3c;
    color: white;
  }

  .debug-btn.primary:hover {
    background: #c0392b;
  }

  .debug-btn.secondary {
    background: #eee;
    color: #333;
  }

  .debug-btn.secondary:hover {
    background: #ddd;
  }

  .debug-btn.danger {
    background: #fff;
    color: #e74c3c;
    border: 1px solid #e74c3c;
  }

  .debug-btn.danger:hover {
    background: #fdf2f2;
  }

  .debug-textarea {
    width: 100%;
    height: 120px;
    font-family: monospace;
    font-size: 0.8rem;
    line-height: 1.4;
    padding: 0.5rem;
    border: 1px solid #ccc;
    border-radius: 3px;
    resize: vertical;
    box-sizing: border-box;
    background: #fff;
    color: #333;
  }

  .debug-textarea::placeholder {
    color: #aaa;
  }

  .debug-status {
    margin-top: 0.4rem;
    font-size: 0.75rem;
    font-family: monospace;
    padding: 0.2rem 0.5rem;
    border-radius: 3px;
  }

  .debug-status.success {
    color: #27ae60;
    background: #eafaf1;
  }

  .debug-status.error {
    color: #e74c3c;
    background: #fdf2f2;
  }
</style>
