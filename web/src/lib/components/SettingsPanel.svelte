<script>
  import { createEventDispatcher, onMount } from 'svelte';
  import { settings } from '$lib/stores/settings';

  const dispatch = createEventDispatcher();

  let localSettings = { ...$settings };
  let saved = false;

  onMount(() => {
    localSettings = { ...$settings };
  });

  function handleSave() {
    settings.save(localSettings);
    saved = true;
    setTimeout(() => { saved = false; }, 2000);
  }

  function handleReset() {
    settings.reset();
    localSettings = { hover_zoom_percent: 150 };
  }

  function handleClose() {
    dispatch('close');
  }

  function handleBackdropClick(e) {
    if (e.target === e.currentTarget) {
      handleClose();
    }
  }

  function handleKeydown(e) {
    if (e.key === 'Escape') {
      handleClose();
    }
  }
</script>

<svelte:window on:keydown={handleKeydown} />

<div class="settings-overlay" on:click={handleBackdropClick}>
  <div class="settings-modal">
    <div class="settings-header">
      <h2>Settings</h2>
      <button class="close-btn" on:click={handleClose}>×</button>
    </div>

    <div class="settings-body">
      <table class="settings-table">
        <thead>
          <tr>
            <th>Setting</th>
            <th>Value</th>
            <th>Description</th>
          </tr>
        </thead>
        <tbody>
          <tr>
            <td class="setting-name">Hover Zoom</td>
            <td class="setting-control">
              <div class="range-wrapper">
                <input 
                  type="range" 
                  min="100" 
                  max="300" 
                  step="10"
                  bind:value={localSettings.hover_zoom_percent}
                />
                <span class="range-value">{localSettings.hover_zoom_percent}%</span>
              </div>
            </td>
            <td class="setting-desc">Card enlargement on hover (100% = no zoom, 300% = 3x size)</td>
          </tr>
        </tbody>
      </table>
    </div>

    <div class="settings-footer">
      <button class="btn-reset" on:click={handleReset}>Reset to Defaults</button>
      <div class="footer-right">
        {#if saved}
          <span class="saved-indicator">Saved!</span>
        {/if}
        <button class="btn-cancel" on:click={handleClose}>Cancel</button>
        <button class="btn-save" on:click={handleSave}>Save</button>
      </div>
    </div>
  </div>
</div>

<style>
  .settings-overlay {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.7);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 5000;
    backdrop-filter: blur(4px);
  }

  .settings-modal {
    background: #1e1e2e;
    border-radius: 12px;
    width: 90%;
    max-width: 600px;
    max-height: 80vh;
    display: flex;
    flex-direction: column;
    box-shadow: 0 20px 60px rgba(0, 0, 0, 0.5);
    border: 1px solid #333;
  }

  .settings-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1.25rem 1.5rem;
    border-bottom: 1px solid #333;
  }

  .settings-header h2 {
    margin: 0;
    font-size: 1.25rem;
    color: #eee;
    font-weight: 600;
  }

  .close-btn {
    background: none;
    border: none;
    color: #888;
    font-size: 1.5rem;
    cursor: pointer;
    padding: 0;
    width: 32px;
    height: 32px;
    display: flex;
    align-items: center;
    justify-content: center;
    border-radius: 6px;
    transition: all 0.15s;
  }

  .close-btn:hover {
    background: #333;
    color: #fff;
  }

  .settings-body {
    padding: 1.5rem;
    overflow-y: auto;
    flex: 1;
  }

  .settings-table {
    width: 100%;
    border-collapse: collapse;
  }

  .settings-table th {
    text-align: left;
    padding: 0.75rem 1rem;
    background: #16161e;
    color: #aaa;
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    border-bottom: 1px solid #333;
  }

  .settings-table td {
    padding: 1rem;
    border-bottom: 1px solid #2a2a3a;
    color: #ccc;
    font-size: 0.9rem;
  }

  .setting-name {
    font-weight: 600;
    color: #eee;
    white-space: nowrap;
  }

  .setting-control {
    min-width: 200px;
  }

  .range-wrapper {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .range-wrapper input[type="range"] {
    flex: 1;
    height: 6px;
    -webkit-appearance: none;
    appearance: none;
    background: #333;
    border-radius: 3px;
    outline: none;
  }

  .range-wrapper input[type="range"]::-webkit-slider-thumb {
    -webkit-appearance: none;
    appearance: none;
    width: 18px;
    height: 18px;
    background: #4a90e2;
    border-radius: 50%;
    cursor: pointer;
    transition: background 0.15s;
  }

  .range-wrapper input[type="range"]::-webkit-slider-thumb:hover {
    background: #5aa0f2;
  }

  .range-wrapper input[type="range"]::-moz-range-thumb {
    width: 18px;
    height: 18px;
    background: #4a90e2;
    border-radius: 50%;
    cursor: pointer;
    border: none;
  }

  .range-value {
    min-width: 48px;
    text-align: right;
    font-weight: 600;
    color: #4a90e2;
    font-variant-numeric: tabular-nums;
  }

  .setting-desc {
    color: #888;
    font-size: 0.8rem;
    line-height: 1.4;
  }

  .settings-footer {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 1rem 1.5rem;
    border-top: 1px solid #333;
    background: #16161e;
    border-radius: 0 0 12px 12px;
  }

  .footer-right {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .saved-indicator {
    color: #4caf50;
    font-size: 0.85rem;
    font-weight: 500;
    animation: fadeIn 0.2s;
  }

  @keyframes fadeIn {
    from { opacity: 0; transform: translateY(4px); }
    to { opacity: 1; transform: translateY(0); }
  }

  button {
    padding: 0.5rem 1rem;
    border-radius: 6px;
    font-size: 0.85rem;
    font-weight: 500;
    cursor: pointer;
    transition: all 0.15s;
    border: none;
  }

  .btn-reset {
    background: #333;
    color: #aaa;
  }

  .btn-reset:hover {
    background: #444;
    color: #fff;
  }

  .btn-cancel {
    background: #333;
    color: #ccc;
  }

  .btn-cancel:hover {
    background: #444;
    color: #fff;
  }

  .btn-save {
    background: #4a90e2;
    color: white;
  }

  .btn-save:hover {
    background: #5aa0f2;
  }
</style>
