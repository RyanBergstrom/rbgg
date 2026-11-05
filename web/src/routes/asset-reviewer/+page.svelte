<script>
  import { onMount } from 'svelte';
  import {
    getAssetReviewCsv,
    validateAssetReviewRow,
    updateAssetReviewFields,
    updateAssetReviewRow,
    getAssetReviewImageUrl,
    API_BASE,
  } from '$lib/api';

  // State for game folder selection (populated from config folders)
  let availableGames = [];
  let selectedGameId = '';

  // State for CSV/JSON file selection
  let selectedCsvName = '';
  let isJsonFile = false;

  // State for CSV loading (legacy support)
  let csvHeaders = [];
  let csvRows = [];
  let currentCsvName = '';
  let currentIndex = 0;
  let validatedHeader = '';
  let fileNameHeader = '';

  // State for image display
  let selectedImageUrl = '';
  let selectedImageName = '';
  let imageLoadError = '';

  // Property editing state
  let showLibrary = false;
  let notice = '';
  let loadError = '';
  let busy = false;

$: currentRow = csvRows.length > 0 ? csvRows[currentIndex] : null;

  // Initialize from API config folders
  async function initAssetReview() {
    loadError = '';
    busy = true;
    try {
      // Read game folders from the config directory
      const result = await fetch(`${API_BASE}/asset-review/config-games`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });
      if (!result.ok) throw new Error('Failed to fetch config games');
      const data = await result.json();
      availableGames = data.games || [];
     
      if (!availableGames.length) {
        loadError = 'No game folders with config files found in C:\\Dev\\rbgg\\api\\configs';
        busy = false;
        return;
      }

      // Select first game and its first config file
      selectedGameId = availableGames[0].id;
      selectedCsvName = availableGames[0].first_config ?? '';
      isJsonFile = selectedCsvName?.endsWith('.json') ?? false;
      busy = false;
      notice = `Config root: C:\\Dev\\rbgg\\api\\configs\\${selectedGameId}`;
    } catch (error) {
      loadError = `Cannot reach the asset-review config API: ${error.message}`;
      busy = false;
    }
  }

  // Load a CSV file (legacy)
  async function loadSelectedCsv() {
    try {
      const result = await getAssetReviewCsv(selectedGameId, selectedCsvName);
      csvHeaders = result.fields;
      csvRows = result.rows;
      currentCsvName = result.csv_name;
      currentIndex = 0;
      validatedHeader = csvHeaders.find((name) => name.trim().toLowerCase() === 'validated') ?? '';
      fileNameHeader = csvHeaders.find((name) => name.trim().toLowerCase() === 'file name') ?? '';
      showLibrary = false;
      loadError = '';
      updateJumpInput();
      
      // Always start at first record (not just first unvalidated)
      if (csvRows.length) {
        await loadCurrentRecord(csvRows[0]);
      } else {
        clearCurrentRecord();
      }
    } catch (error) {
      loadError = error.message || 'Could not load the selected config file.';
    }
  }

  // Load a JSON config file (counters.json)
    async function loadSelectedJson() {
      try {
        // Fetch the JSON file from the API
        const result = await fetchAssetReviewJson(selectedCsvName);
        if (!result) throw new Error('JSON file not found');
       
        csvRows = result.records || [];
        csvHeaders = [];
        currentCsvName = result.csv_name || selectedCsvName;
        currentIndex = 0;
        validatedHeader = ''; // JSON has no validated column - show all records
        fileNameHeader = 'file_name'; // JSON uses file_name
        showLibrary = false;
        loadError = '';
        updateJumpInput();
        
        // Always start at first record
        if (csvRows.length) {
          await loadCurrentRecord(csvRows[0]);
        } else {
          clearCurrentRecord();
        }
      } catch (error) {
        loadError = error.message || 'Could not load the selected JSON config.';
      }
    }

  // Fetch JSON config from the API
  async function fetchAssetReviewJson(csvName) {
    try {
      const result = await fetch(`${API_BASE}/asset-review/${selectedGameId}/config/${csvName}`, {
        method: 'GET',
        headers: { 'Content-Type': 'application/json' }
      });
      if (!result.ok) {
        const text = await result.text();
        throw new Error(`HTTP ${result.status}: ${text}`);
      }
      return await result.json();
    } catch (error) {
      console.error('Failed to fetch JSON config:', error);
      return null;
    }
  }

  // Load current record data (for both CSV and JSON)
  async function loadCurrentRecord(row) {
    // Determine the image filename from the row
    let filename = '';
    if (fileNameHeader && row[fileNameHeader]) {
      filename = row[fileNameHeader];
    } else if (row.file_name) {
      filename = row.file_name;
    } else if (row.path) {
      filename = row.path.split(/[\\/]/).at(-1) ?? '';
    } else if (row.image && typeof row.image === 'object' && row.image.filename) {
      filename = row.image.filename;
    } else if (row.image && typeof row.image === 'string') {
      filename = row.image;
    }
    
    selectedImageName = filename?.split(/[\\/]/).at(-1) ?? '';
    
    if (selectedGameId && filename) {
      selectedImageUrl = getAssetReviewImageUrl(selectedGameId, filename);
      imageLoadError = '';
      notice = '';
      return;
    }
    
    notice = 'Select a config file to load image preview.';
  }

  // Clear current record state
  function clearCurrentRecord() {
    selectedImageUrl = '';
    selectedImageName = '';
    imageLoadError = '';
    notice = '';
    csvRows = [];
    csvHeaders = [];
    currentIndex = 0;
  }

// Jump to a specific record by number (1-based)
  let jumpInput = '';
  // Update jump input when current index changes
  function updateJumpInput() {
    jumpInput = String(currentIndex + 1);
  }
  function jumpToRecord() {
    const num = parseInt(jumpInput, 10);
    if (isNaN(num) || num < 1 || num > csvRows.length) {
      loadError = `Enter a number between 1 and ${csvRows.length}`;
      return;
    }
    busy = true;
    currentIndex = num - 1;
    if (csvRows.length > 0) {
      loadCurrentRecord(csvRows[currentIndex]);
    }
    busy = false;
    loadError = '';
    updateJumpInput();
  }
  async function advance() {
    if (busy) return;
    busy = true;
    currentIndex = currentIndex + 1;
    
    if (currentIndex >= csvRows.length) {
      currentIndex = csvRows.length - 1;
      if (csvRows.length > 0) {
        notice = 'Showing last record.';
      }
    }
    
    if (csvRows.length > 0) {
      await loadCurrentRecord(csvRows[currentIndex]);
    }
    
    busy = false;
    updateJumpInput();
  }

  // Go to previous record
  function goToPreviousRecord() {
    if (currentIndex <= 0 || busy) return;
    busy = true;
    currentIndex -= 1;
    if (csvRows.length > 0) {
      loadCurrentRecord(csvRows[currentIndex]);
    }
    busy = false;
    updateJumpInput();
  }

  // Edit a property field
  async function editProperty(header, value) {
    if (!currentRow || (header === validatedHeader && !isJsonFile)) return;
    const previousValue = currentRow[header] ?? '';
    csvRows = csvRows.map((row, index) => index === currentIndex ? { ...row, [header]: value } : row);
    const saved = await saveCurrentRow({ [header]: value });
    if (!saved) {
      csvRows = csvRows.map((row, index) => index === currentIndex ? { ...row, [header]: previousValue } : row);
      return;
    }
    if (header === fileNameHeader && !isJsonFile) await loadCurrentImage(value);
  }

  // Save current row updates
  async function saveCurrentRow(updates) {
    try {
      if (isJsonFile) {
        const res = await fetch(`${API_BASE}/asset-review/${encodeURIComponent(selectedGameId)}/${encodeURIComponent(currentCsvName)}/rows/${currentIndex}`, {
          method: 'PATCH',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ updates })
        });
        if (!res.ok) {
          const text = await res.text();
          throw new Error(`HTTP ${res.status}: ${text}`);
        }
        notice = 'Config record updated in place.';
        return true;
      }
      await updateAssetReviewRow(selectedGameId, currentCsvName, currentIndex, updates);
      notice = 'Config record updated in place.';
      return true;
    } catch (error) {
      loadError = `Could not save config record: ${error.message}`;
      return false;
    }
  }

// Skip current record
  function skipCurrent() {
    advance();
  }
  async function validateCurrent() {
    if (!currentRow || busy) return;
    busy = true;
    let saved = false;
    try {
      await validateAssetReviewRow(selectedGameId, currentCsvName, currentIndex, true);
      saved = true;
    } catch (error) {
      loadError = `Could not save CSV: ${error.message}`;
    }
    if (!saved) {
      busy = false;
      return;
    }
    csvRows = csvRows.map((row, index) => index === currentIndex
      ? { ...row, [validatedHeader]: '1' }
      : row);
    await advance();
    busy = false;
  }

  // Add new property column
  async function addProperty() {
    const name = window.prompt('New property / CSV/JSON column name:')?.trim();
    if (!name) return;
    // For JSON, we just add to the headers that are displayed
    if (isJsonFile) {
      if (csvHeaders.some((header) => header.toLowerCase() === name.toLowerCase())) {
        loadError = `The JSON config already has a " ${name} " column.`;
        return;
      }
      csvHeaders.push(name);
      // Initialize new column in all rows
      csvRows = csvRows.map((row) => ({ ...row, [name]: '' }));
      loadError = '';
    } else {
      if (csvHeaders.some((header) => header.toLowerCase() === name.toLowerCase())) {
        loadError = `The CSV already has a " ${name} " column.`;
        return;
      }
      try {
        const result = await updateAssetReviewFields(selectedGameId, currentCsvName, [name], []);
        csvHeaders = result.fields;
        // Initialize new column in all rows
        csvRows = csvRows.map((row) => ({ ...row, [name]: '' }));
        loadError = '';
      } catch (error) {
        loadError = `Could not add property: ${error.message}`;
      }
    }
  }

  // Format property value for display (handle different types)
  function formatPropertyValue(value) {
    if (value === null || value === undefined) return '';
    if (typeof value === 'boolean') return value ? 'Yes' : 'No';
    if (typeof value === 'number') return String(value);
    if (typeof value === 'object') return JSON.stringify(value).substring(0, 200);
    return String(value).substring(0, 500);
  }

  // JSON syntax highlighting helper
  function getHighlightedJson(text) {
    if (!text) return '';
    let escaped = text
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;");
    let highlighted = escaped.replace(
      /("(?:\\u[a-zA-Z0-9]{4}|\\[^u]|[^\\"])*")(\s*:)?|\b(true|false|null)\b|(-?\d+(?:\.\d*)?(?:[eE][+\-]?\d+)?)/g,
      function (match, stringVal, colon, booleanVal, numberVal) {
        if (stringVal) {
          if (colon) {
            return `<span class="json-key">${stringVal}</span><span class="json-colon">${colon}</span>`;
          }
          return `<span class="json-string">${stringVal}</span>`;
        }
        if (booleanVal) {
          return `<span class="json-boolean">${booleanVal}</span>`;
        }
        if (numberVal) {
          return `<span class="json-number">${numberVal}</span>`;
        }
        return match;
      }
    );
    return highlighted + (text.endsWith('\n') ? ' ' : '');
  }

  // JSON editor state
  let jsonTextValue = '';

  function saveJsonEditor() {
    try {
      const parsed = JSON.parse(jsonTextValue);
      csvRows = csvRows.map((row, index) => index === currentIndex ? parsed : row);
      saveCurrentRow(parsed);
    } catch (e) {
      loadError = `Invalid JSON: ${e.message}`;
    }
  }

  onMount(async () => {
    await initAssetReview();
  });

  $: if (isJsonFile && currentRow) jsonTextValue = JSON.stringify(currentRow, null, 2);

</script>

<!-- Header -->
<main>
  <header class="topbar">
    <div class="brand"><span class="brand-mark">AR</span><div><p class="eyebrow">LOCAL WORKSPACE</p><h1>Asset Review Desk</h1></div></div>
    <div class="toolbar">
      {#if showLibrary}
        <section class="library-picker">
          <div><p class="eyebrow">LOCAL CONFIG LIBRARY</p><h2>Select a game folder and config</h2><p class="picker-hint">Choose a listed game folder. Its configs are searched in that folder.</p></div>
          <div class="select-group">
            <label>Game folder</label>
            <select bind:value={selectedGameId} onchange={() => { selectedCsvName = availableGames.find((game) => game.id === selectedGameId)?.first_config ?? ''; isJsonFile = selectedCsvName?.endsWith('.json') ?? false; }}>
              {#each availableGames as game}
                <option value={game.id}>{game.id}</option>
              {/each}
            </select>
          </div>
          {#if selectedGameId}
            <div class="select-group">
              <label>Config file</label>
              <select bind:value={selectedCsvName} onchange={() => { isJsonFile = selectedCsvName?.endsWith('.json') ?? false; }}>
                {#each (availableGames.find((game) => game.id === selectedGameId)?.csv_files ?? []).concat(availableGames.find((game) => game.id === selectedGameId)?.json_files ?? []) as csv}
                  <option value={csv}>{csv}</option>
                {/each}
              </select>
            </div>
          {/if}
          <button class="button primary" onclick={() => isJsonFile ? loadSelectedJson() : loadSelectedCsv()} disabled={!selectedCsvName}>Open Config</button>
          <button class="button secondary" onclick={() => showLibrary = false}>Cancel</button>
        </section>
      {/if}
      
      {#if csvRows.length}
        <span class="file-label" title={currentCsvName}>{currentCsvName}</span>
        {#if !isJsonFile}
          <button class="button secondary" onclick={showLibrary = true}>Change Config</button>
        {/if}
        {#if isJsonFile}
          <button class="button secondary" onclick={showLibrary = true}>Change JSON</button>
        {/if}
      {/if}
    </div>
  </header>

  {#if csvRows.length}
    {#if csvRows.length > 0}
        <div class="progress-row">
          <button class="button nav-arrow" onclick={goToPreviousRecord} disabled={busy || currentIndex <= 0}>←</button>
          <input type="number" class="jump-input" bind:value={jumpInput} onkeydown={(e) => { if (e.key === 'Enter') jumpToRecord(); }} placeholder={String(currentIndex + 1)} min="1" max={csvRows.length} />
          <span>/ {csvRows.length}</span>
          <button class="button nav-arrow" onclick={advance} disabled={busy || currentIndex >= csvRows.length - 1}>→</button>
          <div class="progress-track"><div class="progress-fill" style="width: ${Math.round((currentIndex / (csvRows.length - 1)) * 100)}%;"></div></div>
        </div>
      {/if}
    
    <section class="workspace">
  <aside class="record-panel">
        <div class="panel-heading"><div><p class="eyebrow">RECORD {currentIndex + 1} OF {csvRows.length}</p><h2>Properties</h2></div></div>
        {#if currentRow}
          {#if isJsonFile}
            <div class="json-editor-container">
              <pre aria-hidden="true" class="json-highlight"><code class="language-json">{@html getHighlightedJson(jsonTextValue)}</code></pre>
              <textarea
                class="json-textarea"
                bind:value={jsonTextValue}
                spellcheck="false"
                onscroll={(event) => {
                  const pre = event.currentTarget.parentElement.querySelector('pre');
                  if (pre) {
                    pre.scrollTop = event.currentTarget.scrollTop;
                    pre.scrollLeft = event.currentTarget.scrollLeft;
                  }
                }}
                onblur={saveJsonEditor}
                aria-label="JSON record editor"
              ></textarea>
            </div>
          {:else}
            <div class="properties">
              {#each csvHeaders as header}
                <div class="property-row">
                  <span class="property-marker" aria-hidden="true">×</span>
                  <label for={`prop-${header}`}>{header}</label>
                  <textarea
                    class="property-value"
                    id={`prop-${header}`}
                    value={formatPropertyValue(csvRows[currentIndex][header] ?? '')}
                    rows={Math.max(1, Math.min(3, Math.ceil(String(csvRows[currentIndex][header] ?? '').length / 30)))}
                    disabled={false}
                    oninput={(event) => editProperty(header, event.currentTarget.value)}
                    onblur={(event) => editProperty(header, event.currentTarget.value)}
                    aria-label={`${header} value`}
                  ></textarea>
                </div>
              {/each}
            </div>
          {/if}
        {/if}
      </aside>

      <section class="preview-panel" aria-label="Image preview">
        <div class="preview-heading"><div><p class="eyebrow">IMAGE COMPARISON</p><h2>{selectedImageName || 'No filename in this record'}</h2></div>{#if selectedImageName}<span class="image-badge">MATCHED</span>{/if}</div>
        <div class="filename-actions"><span class="filename-label">{selectedImageName || 'No image filename'}</span><button class="button secondary" onclick={() => showLibrary = true}>Select different config</button></div>
        <div class="image-stage">
          {#if selectedImageUrl}
            <img class="preview-image" src={selectedImageUrl} alt={`Preview of ${selectedImageName || selectedImageName}`} />
          {:else}
            <div class="no-image"><div class="image-icon">▧</div><strong>{imageLoadError ? 'Image unavailable' : 'Image not loaded'}</strong><span>{imageLoadError || 'Choose a game folder and config. Images are searched in that game folder and its subfolders.'}</span></div>
          {/if}
        </div>
        <div class="preview-actions"><div class="image-path">{selectedImageName ? `Previewing: ${selectedImageName}` : selectedImageName}</div></div>
        <div class="decision-row"><div><p class="eyebrow">REVIEW DECISION</p><p class="decision-note">Edit properties and images to review accuracy. Navigate with Previous/Next.</p></div><div class="decision-buttons"><button class="button skip" onclick={skipCurrent} disabled={busy}>Skip →</button><button class="button validate" onclick={validateCurrent} disabled={busy || !currentRow}>✓ &nbsp; Validated</button></div></div>
      </section>
    </section>
  {:else}
    <section class="welcome">
      <div class="welcome-card"><div class="welcome-icon">▧</div><p class="eyebrow">CONFIG + IMAGE REVIEW</p><h2>Review each record<br />against its artwork.</h2><p>Load a config file with <strong>File Name</strong> and other properties from the local game library.</p><button class="button primary large" onclick={() => showLibrary = true}>Load a config file</button><div class="requirements"><span>✓ Config changes save directly</span><span>✓ Images load from game folders</span><span>✓ Add and edit metadata</span></div></div>
    </section>
  {/if}
</main>

<style>
  :global(*) { box-sizing: border-box; }
  :global(body) { margin: 0; background: #f4f6fa; color: #172033; font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; }
  main { min-height: 100vh; padding: 0 36px 38px; }
  .topbar { min-height: 92px; display: flex; align-items: center; justify-content: space-between; gap: 20px; border-bottom: 1px solid #e1e6ef; }
  .library-picker { display:flex; align-items:end; gap:14px; flex-wrap:wrap; margin:20px 0; padding:18px; background:white; border:1px solid #e4e8f0; border-radius:12px; box-shadow:0 5px 22px #1a2c5010; }
  .library-picker > div { flex:1 1 100%; }
  .library-picker label { display:grid; gap:6px; color:#68738a; font-size:11px; font-weight:700; }
  .library-picker select { min-width:200px; padding:10px 12px; border:1px solid #dce2ec; border-radius:8px; background:white; color:#202b40; font:inherit; }
  .brand, .toolbar, .panel-heading, .preview-heading, .preview-actions, .decision-row, .decision-buttons, .record-nav { display: flex; align-items: center; }
  .brand { gap: 13px; }
  .brand-mark { display: grid; place-items: center; width: 42px; height: 42px; border-radius: 12px; background: #254de5; color: white; font-weight: 800; letter-spacing: -.04em; }
  h1, h2, p { margin: 0; }
  h1 { font-size: 19px; letter-spacing: -.02em; }
  .eyebrow { color: #7b8497; font-size: 10px; font-weight: 800; letter-spacing: .13em; margin-bottom: 5px; }
  .toolbar { gap: 10px; }
  .file-label { max-width: 210px; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #64708a; font-size: 13px; }
  .button { border: 1px solid transparent; border-radius: 9px; padding: 10px 14px; cursor: pointer; font: inherit; font-size: 13px; font-weight: 700; transition: .15s ease; }
  .button:disabled { opacity: .45; cursor: not-allowed; }
  .primary { background: #254de5; color: white; box-shadow: 0 3px 8px #254de52a; }
  .primary:hover:not(:disabled) { background: #173cc9; transform: translateY(-1px); }
  .secondary { background: white; border-color: #dce2ec; color: #38445b; }
  .secondary:hover:not(:disabled) { border-color: #9ba9c0; background: #fafbfe; }
  .hidden-input { display: none; }
.nav-arrow { padding: 6px 12px; font-size: 16px; }
  .jump-input { width: 60px; padding: 6px 8px; border: 1px solid #dce2ec; border-radius: 6px; text-align: center; font: inherit; font-size: 12px; }
  .progress-track { width: 180px; height: 6px; border-radius: 10px; background: #e3e8f1; overflow: hidden; }
  .progress-fill { height: 100%; border-radius: inherit; background: #254de5; transition: width .25s ease; }
  .workspace { display: grid; grid-template-columns: minmax(640px, 800px) minmax(0, 1fr); gap: 20px; min-height: min(800px, calc(100vh - 165px)); }
  .record-panel, .preview-panel { background: white; border: 1px solid #e4e8f0; border-radius: 15px; box-shadow: 0 5px 22px #1a2c5010; }
  .record-panel { padding: 20px 16px 12px; display: flex; flex-direction: column; }
  .panel-heading { justify-content: space-between; padding-bottom: 12px; border-bottom: 1px solid #edf0f5; }
  .panel-heading h2, .preview-heading h2 { font-size: 17px; letter-spacing: -.025em; }
  .icon-button { flex: 0 0 25px; width: 25px; height: 25px; padding: 0; border: 0; background: transparent; cursor: pointer; font: inherit; line-height: 1; }
  .icon-button.add { width: 30px; height: 30px; flex-basis: 30px; border-radius: 8px; background: #e9efff; color: #254de5; font-size: 22px; }
  .property-marker { color: #98a2b4; font-size: 16px; font-weight: 700; line-height: 1.5; text-align: center; }
  .properties { overflow: auto; flex: 1; }
  .property-row { display: grid; grid-template-columns: auto 1fr; align-items: start; gap: 8px; padding: 8px 0; border-bottom: 1px solid #f0f2f6; }
  .property-row label { color: #748097; font-size: 12px; font-weight: 650; line-height: 1.5; overflow-wrap: anywhere; }
  .property-value { width:100%; min-height:40px; max-height:120px; padding:6px; border:1px solid transparent; border-radius:6px; background:transparent; color:#202b40; font:inherit; font-size:13px; line-height:1.5; overflow-wrap:anywhere; white-space:pre-wrap; resize:vertical; overflow-y:auto; }
  .json-editor-container {
    position: relative;
    flex: 1;
    min-height: 400px;
    border: 1px solid #e4e8f0;
    border-radius: 8px;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 11px;
    line-height: 1.4;
    background: #1e1e1e;
    overflow: hidden;
  }
  .json-editor-container textarea,
  .json-editor-container pre {
    position: absolute;
    top: 0;
    left: 0;
    width: 100%;
    height: 100%;
    margin: 0;
    padding: 12px;
    box-sizing: border-box;
    white-space: pre-wrap;
    word-break: break-word;
    overflow: auto;
    font-family: inherit;
    font-size: inherit;
    line-height: inherit;
  }
  .json-editor-container pre {
    background: #1e1e1e;
    color: #d4d4d4;
    pointer-events: none;
  }
  .json-editor-container .json-textarea {
    background: transparent;
    color: transparent;
    caret-color: #fff;
    resize: none;
    border: none;
    outline: none;
    font-family: 'Consolas', 'Monaco', 'Courier New', monospace;
    font-size: 11px;
    line-height: 1.4;
  }
  .json-editor-container textarea::-webkit-scrollbar,
  .json-editor-container pre::-webkit-scrollbar {
    width: 8px;
    height: 8px;
  }
  .json-editor-container textarea::-webkit-scrollbar-thumb,
  .json-editor-container pre::-webkit-scrollbar-thumb {
    background: #424242;
    border-radius: 4px;
  }
  :global(.json-colon) { color: #d4d4d4; }
  :global(.json-key) { color: #9cdcfe; }
  :global(.json-string) { color: #ce9178; }
  :global(.json-number) { color: #b5cea8; }
  :global(.json-boolean) { color: #569cd6; }
  :global(.json-null) { color: #569cd6; }
  .empty-value { color: #b0b7c4; }
  .record-nav { justify-content: space-between; gap: 10px; padding-top: 10px; }
  .hint { padding-top: 8px; color: #929bad; font-size: 11px; line-height: 1.5; }
  .preview-panel { padding: 20px; display: flex; flex-direction: column; min-width: 0; }
  .preview-heading { min-height: 40px; justify-content: space-between; gap: 12px; }
  .preview-heading h2 { max-width: 55vw; overflow-wrap: anywhere; }
  .image-badge { border-radius: 99px; background: #eaf7f0; color: #208150; padding: 6px 9px; font-size: 9px; font-weight: 850; letter-spacing: .1em; }
  .image-stage { flex: 0 0 450px; margin: 20px 0 13px; display: grid; place-items: start; overflow: hidden; border: 1px solid #e9edf4; border-radius: 11px; background-color: #f8f9fc; height: 450px; }
  .preview-image { width: auto; height: auto; max-width: 100%; max-height: 100%; object-fit: contain; display: block; margin: auto; }
  .no-image { display: flex; flex-direction: column; align-items: center; gap: 6px; max-width: 360px; padding: 20px; text-align: center; color: #7c879b; }
  .image-icon { margin-bottom: 3px; color: #99a8c5; font-size: 45px; }
  .no-image strong { color: #46536d; font-size: 14px; }
  .no-image span { font-size: 12px; line-height: 1.5; }
  .preview-actions { justify-content: space-between; gap: 15px; padding-bottom: 12px; border-bottom: 1px solid #edf0f5; }
  .filename-actions { display:flex; align-items:center; justify-content:space-between; gap:12x; margin-top:8px; padding:8px 12px; border:1px solid #e9edf4; border-radius:9px; background:#fafbfe; }
  .filename-label { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; color:#46536d; font-size:12px; font-weight:650; }
  .image-path { min-width: 0; overflow: hidden; text-overflow: ellipsis; white-space: nowrap; color: #778198; font-size: 12px; }
  .decision-row { justify-content: space-between; gap: 15px; padding-top: 12px; }
  .decision-note { color: #788399; font-size: 12px; line-height: 1.45; }
  .decision-buttons { flex: 0 0 auto; gap: 6px; }
  .skip { background: white; border-color: #dce2ec; color: #566178; }
  .validate { background: #16834d; color: white; box-shadow: 0 3px 8px #16834d26; }
  .validate:hover:not(:disabled) { background: #0f7040; transform: translateY(-1px); }
  .welcome { min-height: calc(100vh - 130px); display: grid; place-items: center; }
  .welcome-card { width: min(100%, 510px); padding: 48px; text-align: center; border: 1px solid #e4e8f0; border-radius: 18px; background: white; box-shadow: 0 12px 44px #1a2c5010; }
  .welcome-icon { display: grid; place-items: center; width: 66px; height: 66px; margin: 0 auto 25px; border-radius: 18px; background: #edf1ff; color: #254de5; font-size: 32px; }
  .welcome-card h2 { margin: 8px 0 13px; font-size: clamp(25px, 4vw, 35px); line-height: 1.15; letter-spacing: -.045em; }
  .welcome-card > p:not(.eyebrow) { margin: 0 auto 23px; max-width: 390px; color: #748097; font-size: 14px; line-height: 1.7; }
  .large { padding: 13px 21px; }
  .requirements { display: flex; justify-content: center; flex-wrap: wrap; gap: 10px 17px; margin-top: 27px; color: #8792a7; font-size: 10px; }
  .toast { position: fixed; right: 22px; bottom: 20px; z-index: 5; display: flex; align-items: gap: 18px; max-width: min(520px, calc(100vw - 30px)); padding: 13px 16px; border: 1px solid #d9e2f5; border-radius: 10px; background: #fff; box-shadow: 0 7px 25px #1a2c5020; color: #3b4a64; font-size: 12px; }
  .toast.error { border-color: #f2c5c8; color: #a42b35; }
  .toast button { border: 0; background: transparent; color: inherit; font-size: 18px; cursor: pointer; }
  @media (max-width: 860px) { main { padding: 0 18px 25px; } .workspace { grid-template-columns: 1fr; } .record-panel { max-height: 470px; } .image-stage { min-height: 300px; } .preview-image { max-height: 50vh; } }
  @media (max-width: 560px) { main { padding: 0 12px 20px; } .topbar { align-items: flex-start; flex-direction: column; padding: 17px 0; } .toolbar { width: 100%; flex-wrap: wrap; } .file-label { flex: 1; } .progress-track { flex: 1; } .workspace { gap: 12px; } .record-panel, .preview-panel { padding: 16px; } .decision-row { align-items: flex-start; flex-direction: column; } .decision-buttons { width: 100%; } .decision-buttons .button { flex: 1; } .welcome-card { padding: 32px 22px; } }
</style>