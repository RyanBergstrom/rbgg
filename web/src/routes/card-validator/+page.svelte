<script>
  import { onMount } from 'svelte';
  import {
    getAssetReviewGames,
    getAssetReviewJson,
    updateAssetReviewJsonRow,
    syncAssetReviewJsonRecord,
    getAssetReviewImageUrl,
    API_BASE,
  } from '$lib/api';

  // Game & Config selection state
  let availableGames = [];
  let selectedGameId = 'fof';
  let availableJsonFiles = [];
  let selectedJsonName = 'cards.json';
  let cardRegions = null;
  let rawRevision = null;
  let finalRevision = null;

  // Final filename derived dynamically from loaded filename
  $: finalJsonName = getFinalJsonName(selectedJsonName);
  $: isViewingFinalDirectly = Boolean(selectedJsonName?.endsWith('-final.json'));

  function getFinalJsonName(name) {
    if (!name) return '';
    if (name.endsWith('-final.json')) return name;
    const base = name.replace(/\.json$/i, '');
    return `${base}-final.json`;
  }

  function getRecordKey(rec) {
    return rec?.image?.filename || rec?.id || '';
  }

  function getRegionHotspotStyle(group, regionName, deck = activeRecord?.deck) {
    const region = group === 'terrain'
      ? cardRegions?.terrain?.[deck]?.[regionName] || cardRegions?.terrain?.default?.[regionName]
      : cardRegions?.[group]?.[regionName];
    const box = region?.hotspot;
    if (!box) return '';
    return `top:${box.y * 100}%;left:${box.x * 100}%;width:${box.width * 100}%;height:${box.height * 100}%`;
  }

  function getActiveCropRegion() {
    if (!activeRecord || !cardRegions) return null;
    const terrainKeys = {
      tl_cover: 'cover',
      tc_name: 'terrain_name_and_vehicle',
      tr_num: 'card_number_and_burst',
      tr_elev: 'elevation',
      br_elev: 'elevation',
      bl_cap: 'cover_capacity',
      bc_draw: 'cover_draw',
    };
    const actionKeys = {
      act_cmd: 'commands',
      act_init: 'initiative',
      act_num: 'card_number',
      act_attempt: 'header',
      act_icons: 'attempt_icons',
      act_at: 'anti_tank',
      act_hit: 'hit_effects',
      act_rn: 'random_numbers',
    };
    const key = activeRecord.card_type === 'terrain'
      ? terrainKeys[activeFieldHighlight]
      : actionKeys[activeFieldHighlight];
    if (!key) return null;
    const group = activeRecord.card_type === 'terrain'
      ? (cardRegions.terrain?.[activeRecord.deck] || cardRegions.terrain?.default)
      : cardRegions.action;
    return group?.[key]?.crop || null;
  }

  function getFieldProvenance(section, field) {
    if (!activeRecord) return 'Unknown';
    const key = getRecordKey(activeRecord);
    const details = activeRecord[section] || {};
    if (details.verified_fields?.includes(field)) return 'Verified';
    if (activeRecord.classification?.reviewed && finalMap.has(key)) return 'Verified';
    const suggestion = rawLoadedMap.get(key)?.[section] || {};
    if (Object.prototype.hasOwnProperty.call(suggestion, field) && suggestion[field] !== details[field]) {
      return 'Edited';
    }
    return 'Suggested';
  }

  // Maps for raw loaded records vs final file records
  let rawLoadedMap = new Map();
  let finalMap = new Map();

  // Records state
  let records = [];
  let loading = true;
  let loadError = '';
  let statusMessage = '';
  let savingId = null;

  // Filters & Search
  let searchQuery = '';
  let selectedDeck = 'all';
  let selectedExpansion = 'all';
  let selectedCardType = 'all';
  let filterReviewed = 'all'; // all, reviewed, unreviewed
  let viewMode = 'grid'; // grid | table

  // Pagination
  let pageSize = 48;
  let currentPage = 1;

  // Detail Modal / Inspector
  let activeIndex = null;
  let activeRecord = null;
  let zoomLevel = 1.5;
  let activeFieldHighlight = null; // 'tl_cover' | 'tc_name' | 'tr_num' | 'bl_cap' | 'bc_draw' | 'br_move' | 'borders' | null

  const KNOWN_VEHICLE_ACCESS = [
    'Prohibited (No)',
    'Allowed (Yes)',
    'Tracked Only',
    'Road Only',
    'Unknown',
  ];

  const KNOWN_DECKS = [
    'Action Deck',
    'Normandy Terrain',
    'Korea Terrain',
    'Vietnam Terrain',
    'Peleliu Terrain',
    'Ardennes Terrain',
    'Chosin Reservoir Terrain',
    'Hue Terrain',
    'Heartbreak Ridge Terrain',
    'Falklands - Goose Green Terrain',
    'Fire Support Areas',
    'Staging Areas',
    'Card Backs / Aids',
  ];

  const KNOWN_EXPANSIONS = [
    'Volume I',
    'Volume II',
    'Volume III',
    'Base / Shared',
    'Unknown',
  ];

  const KNOWN_CARD_TYPES = [
    { value: 'terrain', label: 'Terrain (Map Grid)' },
    { value: 'action', label: 'Action (Action Deck)' },
    { value: 'fsa', label: 'FSA (Fire Support Area)' },
    { value: 'staging_area', label: 'Staging Area' },
    { value: 'utility', label: 'Utility / Reference / Back' },
  ];

  const KNOWN_PURPOSES = [
    'Map Terrain Grid',
    'Initiative, Combat Draw & Action Attempts',
    'Elevation Overlay',
    'Fire Support Base',
    'Off-map Staging',
    'Rule Aid / Reference',
    'Deck Reshuffle',
    'Card Back',
  ];

  const KNOWN_TERRAIN_CATEGORIES = [
    'Open',
    'Forest / Woods',
    'Rough / Hill',
    'Urban / Building',
    'Water / Marsh',
    'Linear Obstacle',
    'Special',
  ];

  onMount(async () => {
    await initGames();
  });

  async function initGames() {
    loading = true;
    loadError = '';
    try {
      const data = await getAssetReviewGames();
      availableGames = data.games || [];
      const fofGame = availableGames.find((g) => g.id === 'fof');
      if (fofGame) {
        selectedGameId = 'fof';
        availableJsonFiles = fofGame.json_files || [];
        if (availableJsonFiles.includes('cards.json')) {
          selectedJsonName = 'cards.json';
        } else if (availableJsonFiles.length) {
          selectedJsonName = availableJsonFiles[0];
        }
      } else if (availableGames.length) {
        selectedGameId = availableGames[0].id;
        availableJsonFiles = availableGames[0].json_files || [];
        selectedJsonName = availableJsonFiles[0] || '';
      }
      if (selectedGameId && selectedJsonName) {
        await loadRecords();
      } else {
        loading = false;
        loadError = 'No JSON config files found in api/configs.';
      }
    } catch (err) {
      loading = false;
      loadError = `Failed to load games: ${err.message}`;
    }
  }

  async function onGameChange() {
    const game = availableGames.find((g) => g.id === selectedGameId);
    availableJsonFiles = game ? game.json_files || [] : [];
    selectedJsonName = availableJsonFiles.includes('cards.json')
      ? 'cards.json'
      : availableJsonFiles[0] || '';
    await loadRecords();
  }

  async function loadRecords() {
    if (!selectedGameId || !selectedJsonName) return;
    loading = true;
    loadError = '';
    statusMessage = '';
    try {
      const res = await getAssetReviewJson(selectedGameId, selectedJsonName);
      const loadedRecords = Array.isArray(res.records) ? res.records : [];
      rawRevision = res.revision || null;
      finalRevision = isViewingFinalDirectly ? (res.revision || null) : null;

      if (selectedGameId === 'fof') {
        try {
          const regionResponse = await getAssetReviewJson(selectedGameId, 'card_regions.json');
          cardRegions = regionResponse.records || null;
        } catch (regionError) {
          console.warn('Card region map unavailable; using built-in overlay styles.', regionError);
          cardRegions = null;
        }
      }

      rawLoadedMap = new Map();
      for (const r of loadedRecords) {
        const key = getRecordKey(r);
        if (key) {
          rawLoadedMap.set(key, JSON.parse(JSON.stringify(r)));
        }
      }

      finalMap = new Map();
      if (!isViewingFinalDirectly && finalJsonName) {
        try {
          const finalRes = await getAssetReviewJson(selectedGameId, finalJsonName);
          finalRevision = finalRes.revision || null;
          const finalRecords = Array.isArray(finalRes.records) ? finalRes.records : [];
          for (const fr of finalRecords) {
            const fKey = getRecordKey(fr);
            if (fKey) {
              finalMap.set(fKey, JSON.parse(JSON.stringify(fr)));
            }
          }
        } catch (finalErr) {
          if (finalErr.status !== 404) {
            console.warn('Could not load final file:', finalErr);
          }
        }
      }

      const merged = loadedRecords.map((rawRec) => {
        const key = getRecordKey(rawRec);
        if (key && finalMap.has(key)) {
          const finalRec = JSON.parse(JSON.stringify(finalMap.get(key)));
          finalRec.classification = finalRec.classification || {};
          if (isViewingFinalDirectly || Boolean(finalRec.classification.reviewed)) {
            return finalRec;
          }
          // Keep the latest classifier suggestion visible until a human confirms it.
          const suggestion = JSON.parse(JSON.stringify(rawRec));
          suggestion.classification = suggestion.classification || {};
          suggestion.classification.reviewed = false;
          return suggestion;
        } else {
          const rec = JSON.parse(JSON.stringify(rawRec));
          rec.classification = rec.classification || {};
          rec.classification.reviewed = isViewingFinalDirectly ? Boolean(rec.classification.reviewed) : false;
          return rec;
        }
      });

      records = merged;
      currentPage = 1;
      closeInspector();

      if (finalMap.size > 0 && !isViewingFinalDirectly) {
        const reviewedCount = [...finalMap.values()].filter((rec) => Boolean(rec.classification?.reviewed)).length;
        statusMessage = `Loaded ${loadedRecords.length} cards. Found ${reviewedCount} reviewed in ${finalJsonName}.`;
      }
    } catch (err) {
      loadError = `Failed to load ${selectedJsonName}: ${err.message}`;
      records = [];
      rawLoadedMap = new Map();
      finalMap = new Map();
    } finally {
      loading = false;
    }
  }

  function getCardImageUrl(rec) {
    if (!rec?.image?.filename) return '';
    return getAssetReviewImageUrl(selectedGameId, rec.image.filename);
  }

  // Unique lists for dropdowns
  $: decks = Array.from(new Set(records.map((r) => r.deck).filter(Boolean))).sort();
  $: expansions = Array.from(new Set(records.map((r) => r.expansion).filter(Boolean))).sort();

  // Summary counts
  $: totalCount = records.length;
  $: terrainCount = records.filter((r) => r.card_type === 'terrain').length;
  $: actionCount = records.filter((r) => r.card_type === 'action').length;
  $: fsaCount = records.filter((r) => r.card_type === 'fsa').length;
  $: stagingCount = records.filter((r) => r.card_type === 'staging_area').length;
  $: utilityCount = records.filter((r) => r.card_type === 'utility').length;
  $: finalCount = isViewingFinalDirectly
    ? records.filter((r) => Boolean(r.classification?.reviewed)).length
    : finalMap.size;

  // Filtered records
  $: filteredRecords = records.filter((rec) => {
    if (selectedDeck !== 'all' && rec.deck !== selectedDeck) return false;
    if (selectedExpansion !== 'all' && rec.expansion !== selectedExpansion) return false;
    if (selectedCardType !== 'all' && rec.card_type !== selectedCardType) return false;

    const isRev = Boolean(rec.classification?.reviewed);
    if (filterReviewed === 'reviewed' && !isRev) return false;
    if (filterReviewed === 'unreviewed' && isRev) return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchId = rec.id?.toLowerCase().includes(q);
      const matchName = rec.name?.toLowerCase().includes(q);
      const matchFile = rec.image?.filename?.toLowerCase().includes(q);
      const matchDeck = rec.deck?.toLowerCase().includes(q);
      const matchPurpose = rec.purpose?.toLowerCase().includes(q);
      const matchTerrain = rec.terrain_details?.terrain_name?.toLowerCase().includes(q);
      const matchVeh = rec.terrain_details?.vehicle_access?.toLowerCase().includes(q);
      const matchNum = rec.terrain_details?.card_number?.toLowerCase().includes(q);
      const matchNotes = rec.classification?.notes?.toLowerCase().includes(q);
      if (!matchId && !matchName && !matchFile && !matchDeck && !matchPurpose && !matchTerrain && !matchVeh && !matchNum && !matchNotes) {
        return false;
      }
    }
    return true;
  });

  // Paginated records
  $: totalPages = pageSize === 'all' ? 1 : Math.ceil(filteredRecords.length / Number(pageSize)) || 1;
  $: pageRecords = pageSize === 'all'
    ? filteredRecords
    : filteredRecords.slice((currentPage - 1) * Number(pageSize), currentPage * Number(pageSize));

  function setPage(p) {
    if (p >= 1 && p <= totalPages) {
      currentPage = p;
      window.scrollTo({ top: 0, behavior: 'smooth' });
    }
  }

  // Quick Validate / Unvalidate Toggle
  async function toggleValidated(rec) {
    const key = getRecordKey(rec);
    const targetSyncId = rec.image?.filename || rec.id;
    if (!key) return;

    const isCurrentlyValidated = Boolean(rec.classification?.reviewed);
    const newValidated = !isCurrentlyValidated;

    const realIndex = records.findIndex((r) => getRecordKey(r) === key);
    if (realIndex === -1) return;

    savingId = key;

    try {
      if (newValidated) {
        rec.classification = rec.classification || {};
        rec.classification.reviewed = true;
        rec.classification.reviewed_at = new Date().toISOString();
        for (const section of ['terrain_details', 'action_details']) {
          const details = rec[section];
          if (details) {
            details.verified_fields = Object.keys(details).filter((field) => field !== 'verified_fields');
          }
        }

        const recordToSave = JSON.parse(JSON.stringify(rec));
        const targetJsonName = isViewingFinalDirectly ? selectedJsonName : finalJsonName;
        const revision = isViewingFinalDirectly ? rawRevision : finalRevision;
        const syncResult = await syncAssetReviewJsonRecord(selectedGameId, targetJsonName, 'upsert', recordToSave, targetSyncId, revision);
        if (isViewingFinalDirectly) rawRevision = syncResult.revision || rawRevision;
        else finalRevision = syncResult.revision || finalRevision;

        finalMap.set(key, recordToSave);
        records[realIndex] = recordToSave;
        records = [...records];

        if (activeRecord && getRecordKey(activeRecord) === key) {
          activeRecord = JSON.parse(JSON.stringify(recordToSave));
        }

        statusMessage = `Validated and added "${targetSyncId}" to ${finalJsonName}`;
      } else {
        const targetJsonName = isViewingFinalDirectly ? selectedJsonName : finalJsonName;
        const revision = isViewingFinalDirectly ? rawRevision : finalRevision;
        const syncResult = await syncAssetReviewJsonRecord(selectedGameId, targetJsonName, 'delete', null, targetSyncId, revision);
        if (isViewingFinalDirectly) rawRevision = syncResult.revision || rawRevision;
        else finalRevision = syncResult.revision || finalRevision;
        finalMap.delete(key);

        const original = rawLoadedMap.get(key);
        let reverted;
        if (original) {
          reverted = JSON.parse(JSON.stringify(original));
        } else {
          reverted = JSON.parse(JSON.stringify(rec));
        }
        reverted.classification = reverted.classification || {};
        reverted.classification.reviewed = false;
        reverted.classification.reviewed_at = null;

        records[realIndex] = reverted;
        records = [...records];

        if (activeRecord && getRecordKey(activeRecord) === key) {
          activeRecord = JSON.parse(JSON.stringify(reverted));
        }

        statusMessage = `Removed "${targetSyncId}" from ${finalJsonName}. Reverted to ${selectedJsonName} version.`;
      }
    } catch (err) {
      statusMessage = err.status === 409
        ? 'This catalog changed in another edit. Reload the cards before saving again.'
        : `Operation failed for ${targetSyncId}: ${err.message}`;
    } finally {
      savingId = null;
    }
  }

  // Inspector Drawer / Modal
  function openInspector(rec) {
    if (!rec) return;
    const realIdx = records.findIndex((r) => getRecordKey(r) === getRecordKey(rec));
    activeIndex = realIdx !== -1 ? realIdx : records.indexOf(rec);
    activeRecord = JSON.parse(JSON.stringify(rec));
    if (activeRecord) {
      activeRecord.classification = activeRecord.classification || {};
      if (activeRecord.card_type === 'terrain') {
        activeRecord.terrain_details = activeRecord.terrain_details || {};
        activeRecord.terrain_details.borders = activeRecord.terrain_details.borders || { north: 'white', east: 'white', south: 'white', west: 'white' };
      } else if (activeRecord.card_type === 'action') {
        activeRecord.action_details = activeRecord.action_details || {};
      }
    }
  }

  function closeInspector() {
    activeIndex = null;
    activeRecord = null;
    activeFieldHighlight = null;
  }

  function navInspector(direction) {
    if (activeIndex === null || !activeRecord) return;
    const currentKey = getRecordKey(activeRecord);
    const currentInFiltered = filteredRecords.findIndex((r) => getRecordKey(r) === currentKey);

    let nextInFiltered = -1;
    if (currentInFiltered !== -1) {
      nextInFiltered = currentInFiltered + direction;
    } else {
      nextInFiltered = direction > 0 ? 0 : filteredRecords.length - 1;
    }

    if (nextInFiltered >= 0 && nextInFiltered < filteredRecords.length) {
      openInspector(filteredRecords[nextInFiltered]);
    } else if (filteredRecords.length > 0) {
      const clamped = Math.max(0, Math.min(filteredRecords.length - 1, nextInFiltered));
      openInspector(filteredRecords[clamped]);
    } else {
      closeInspector();
    }
  }

  async function saveActiveRecord(advanceNext = false, forceValidate = null) {
    if (activeIndex === null || !activeRecord) return;
    const key = getRecordKey(activeRecord);
    const targetSyncId = activeRecord.image?.filename || activeRecord.id;
    if (!key) return;

    let nextRecordToOpen = null;
    if (advanceNext) {
      const currentInFiltered = filteredRecords.findIndex((r) => getRecordKey(r) === key);
      if (currentInFiltered !== -1 && currentInFiltered + 1 < filteredRecords.length) {
        nextRecordToOpen = filteredRecords[currentInFiltered + 1];
      } else if (currentInFiltered !== -1 && currentInFiltered < filteredRecords.length - 1) {
        nextRecordToOpen = filteredRecords[currentInFiltered];
      } else if (filteredRecords.length > 1) {
        nextRecordToOpen = filteredRecords[0];
      }
    }

    savingId = key;
    try {
      if (forceValidate !== null) {
        activeRecord.classification = activeRecord.classification || {};
        activeRecord.classification.reviewed = forceValidate;
        if (forceValidate && !activeRecord.classification.reviewed_at) {
          activeRecord.classification.reviewed_at = new Date().toISOString();
        } else if (!forceValidate) {
          activeRecord.classification.reviewed_at = null;
        }
      }

      const isVerified = Boolean(activeRecord.classification?.reviewed);
      const updatedRec = JSON.parse(JSON.stringify(activeRecord));
      for (const section of ['terrain_details', 'action_details']) {
        const details = updatedRec[section];
        if (!details) continue;
        const baseline = rawLoadedMap.get(key)?.[section] || {};
        const verified = new Set(details.verified_fields || []);
        for (const field of Object.keys(details)) {
          if (field !== 'verified_fields' && (isVerified || details[field] !== baseline[field])) {
            verified.add(field);
          }
        }
        details.verified_fields = [...verified];
      }

      const targetFinalJsonName = isViewingFinalDirectly ? selectedJsonName : finalJsonName;
      if (isVerified || isViewingFinalDirectly) {
        const revision = isViewingFinalDirectly ? rawRevision : finalRevision;
        const syncResult = await syncAssetReviewJsonRecord(selectedGameId, targetFinalJsonName, 'upsert', updatedRec, targetSyncId, revision);
        if (isViewingFinalDirectly) rawRevision = syncResult.revision || rawRevision;
        else finalRevision = syncResult.revision || finalRevision;
        finalMap.set(key, updatedRec);
        statusMessage = `${isVerified ? 'Validated' : 'Saved'} "${targetSyncId}" to ${targetFinalJsonName}`;
      } else {
        if (finalMap.has(key)) {
          const syncResult = await syncAssetReviewJsonRecord(selectedGameId, targetFinalJsonName, 'delete', null, targetSyncId, finalRevision);
          finalRevision = syncResult.revision || finalRevision;
          finalMap.delete(key);
        }
        statusMessage = `Saved "${targetSyncId}" (unverified)`;
      }

      const targetIdx = records.findIndex((r) => getRecordKey(r) === key);
      const updateIdx = targetIdx !== -1 ? targetIdx : activeIndex;
      records[updateIdx] = updatedRec;
      records = [...records];

      // Unreviewed edits remain classifier suggestions. Verified edits live only
      // in cards-final.json, preventing stale UI state from overwriting them in cards.json.
      if (!isVerified && !isViewingFinalDirectly) {
        const rowResult = await updateAssetReviewJsonRow(selectedGameId, selectedJsonName, updateIdx, updatedRec, rawRevision);
        rawRevision = rowResult.revision || rawRevision;
      }

      if (advanceNext) {
        if (nextRecordToOpen && getRecordKey(nextRecordToOpen) !== key) {
          openInspector(nextRecordToOpen);
        } else {
          navInspector(1);
        }
      }
    } catch (err) {
      statusMessage = err.status === 409
        ? 'This catalog changed in another edit. Reload the cards before saving again.'
        : `Save failed: ${err.message}`;
    } finally {
      savingId = null;
    }
  }

  function handleKeydown(e) {
    if (activeIndex !== null) {
      if (e.key === 'ArrowRight' && !e.target.matches('input, textarea, select')) {
        navInspector(1);
      } else if (e.key === 'ArrowLeft' && !e.target.matches('input, textarea, select')) {
        navInspector(-1);
      } else if (e.key === 'Escape') {
        closeInspector();
      }
    }
  }
</script>

<svelte:window onkeydown={handleKeydown} />

<div class="validator-root">
  <!-- Top Navigation & Controls Header -->
  <header class="top-nav">
    <div class="nav-title-group">
      <a href="/" class="home-btn">&larr; RBGG Home</a>
      <a href="/counter-validator" class="secondary-nav-btn">&#9638; Counter Validator</a>
      <h1>Card Batch Validator</h1>
      <span class="file-tag" title="Loaded source file">{selectedGameId}/{selectedJsonName}</span>
      {#if !isViewingFinalDirectly}
        <span class="final-file-tag" title="Target final file for validated cards">
          Target: {finalJsonName} ({finalCount} validated)
        </span>
      {:else}
        <span class="final-file-tag direct-tag">Viewing Final File Directly</span>
      {/if}
    </div>

    <div class="nav-config-group">
      <label class="config-label">
        Game:
        <select bind:value={selectedGameId} onchange={onGameChange} class="nav-select">
          {#each availableGames as g}
            <option value={g.id}>{g.id}</option>
          {/each}
        </select>
      </label>

      <label class="config-label">
        Config:
        <select bind:value={selectedJsonName} onchange={loadRecords} class="nav-select">
          {#each availableJsonFiles as jf}
            <option value={jf}>{jf}</option>
          {/each}
        </select>
      </label>

      <button onclick={loadRecords} class="reload-btn" title="Reload data and sync with final file">
        &#x21bb; Reload
      </button>

      <div class="view-toggle">
        <button
          class="toggle-btn"
          class:active={viewMode === 'grid'}
          onclick={() => (viewMode = 'grid')}
          title="Grid Gallery View"
        >
          &#9638; Grid
        </button>
        <button
          class="toggle-btn"
          class:active={viewMode === 'table'}
          onclick={() => (viewMode = 'table')}
          title="Dense Table View"
        >
          &#9776; Table
        </button>
      </div>
    </div>
  </header>

  <!-- Summary Audit Bar & Quick Chips -->
  <section class="audit-bar">
    <div
      class="audit-stat"
      role="button"
      tabindex="0"
      onclick={() => { selectedDeck = 'all'; selectedExpansion = 'all'; selectedCardType = 'all'; filterReviewed = 'all'; }}
      onkeydown={(e) => { if (e.key === 'Enter') { selectedDeck = 'all'; selectedExpansion = 'all'; selectedCardType = 'all'; filterReviewed = 'all'; } }}
    >
      <span class="stat-num">{totalCount}</span>
      <span class="stat-lbl">Total Cards</span>
    </div>

    <div
      class="audit-stat category-terrain"
      role="button"
      tabindex="0"
      class:active-chip={selectedCardType === 'terrain'}
      onclick={() => (selectedCardType = selectedCardType === 'terrain' ? 'all' : 'terrain')}
      onkeydown={(e) => { if (e.key === 'Enter') selectedCardType = selectedCardType === 'terrain' ? 'all' : 'terrain'; }}
    >
      <span class="stat-num">&#127958; {terrainCount}</span>
      <span class="stat-lbl">Terrain</span>
    </div>

    <div
      class="audit-stat category-action"
      role="button"
      tabindex="0"
      class:active-chip={selectedCardType === 'action'}
      onclick={() => (selectedCardType = selectedCardType === 'action' ? 'all' : 'action')}
      onkeydown={(e) => { if (e.key === 'Enter') selectedCardType = selectedCardType === 'action' ? 'all' : 'action'; }}
    >
      <span class="stat-num">&#9876; {actionCount}</span>
      <span class="stat-lbl">Action Deck</span>
    </div>

    <div
      class="audit-stat category-fsa"
      role="button"
      tabindex="0"
      class:active-chip={selectedCardType === 'fsa'}
      onclick={() => (selectedCardType = selectedCardType === 'fsa' ? 'all' : 'fsa')}
      onkeydown={(e) => { if (e.key === 'Enter') selectedCardType = selectedCardType === 'fsa' ? 'all' : 'fsa'; }}
    >
      <span class="stat-num">&#128300; {fsaCount}</span>
      <span class="stat-lbl">FSA Areas</span>
    </div>

    <div
      class="audit-stat category-staging"
      role="button"
      tabindex="0"
      class:active-chip={selectedCardType === 'staging_area'}
      onclick={() => (selectedCardType = selectedCardType === 'staging_area' ? 'all' : 'staging_area')}
      onkeydown={(e) => { if (e.key === 'Enter') selectedCardType = selectedCardType === 'staging_area' ? 'all' : 'staging_area'; }}
    >
      <span class="stat-num">&#128652; {stagingCount}</span>
      <span class="stat-lbl">Staging Areas</span>
    </div>

    <div
      class="audit-stat category-utility"
      role="button"
      tabindex="0"
      class:active-chip={selectedCardType === 'utility'}
      onclick={() => (selectedCardType = selectedCardType === 'utility' ? 'all' : 'utility')}
      onkeydown={(e) => { if (e.key === 'Enter') selectedCardType = selectedCardType === 'utility' ? 'all' : 'utility'; }}
    >
      <span class="stat-num">&#128214; {utilityCount}</span>
      <span class="stat-lbl">Utility / Aids</span>
    </div>

    <div
      class="audit-stat stat-reviewed"
      role="button"
      tabindex="0"
      class:active-chip={filterReviewed === 'reviewed'}
      onclick={() => (filterReviewed = filterReviewed === 'reviewed' ? 'all' : 'reviewed')}
      onkeydown={(e) => { if (e.key === 'Enter') filterReviewed = filterReviewed === 'reviewed' ? 'all' : 'reviewed'; }}
      title="Show only records saved to {finalJsonName}"
    >
      <span class="stat-num">✓ {finalCount}</span>
      <span class="stat-lbl">{isViewingFinalDirectly ? 'Reviewed' : 'In Final File'}</span>
    </div>
  </section>

  <!-- Filter & Search Controls Strip -->
  <section class="filters-bar">
    <div class="search-box">
      <input
        type="text"
        bind:value={searchQuery}
        placeholder="Filter by ID, name, deck, or features..."
        class="search-input"
      />
      {#if searchQuery}
        <button class="clear-search" onclick={() => (searchQuery = '')}>&times;</button>
      {/if}
    </div>

    <div class="dropdowns-group">
      <select bind:value={selectedDeck} class="filter-select">
        <option value="all">All Decks ({decks.length})</option>
        {#each decks as d}
          <option value={d}>{d}</option>
        {/each}
      </select>

      <select bind:value={selectedExpansion} class="filter-select">
        <option value="all">All Expansions ({expansions.length})</option>
        {#each expansions as exp}
          <option value={exp}>{exp}</option>
        {/each}
      </select>

      <select bind:value={selectedCardType} class="filter-select">
        <option value="all">All Card Types</option>
        {#each KNOWN_CARD_TYPES as ct}
          <option value={ct.value}>{ct.label}</option>
        {/each}
      </select>

      <select bind:value={filterReviewed} class="filter-select">
        <option value="all">All Review Statuses</option>
        <option value="reviewed">✓ In Final File ({finalCount})</option>
        <option value="unreviewed">○ Not in Final File ({totalCount - finalCount})</option>
      </select>

      <select bind:value={pageSize} onchange={() => (currentPage = 1)} class="filter-select page-size-select">
        <option value={24}>24 / page</option>
        <option value={48}>48 / page</option>
        <option value={96}>96 / page</option>
        <option value={192}>192 / page</option>
        <option value="all">Show All</option>
      </select>
    </div>
  </section>

  <!-- Status / Error Notification -->
  {#if loadError}
    <div class="alert error-alert">{loadError}</div>
  {:else if statusMessage}
    <div class="alert status-alert">{statusMessage}</div>
  {/if}

  <!-- Main Viewer Content -->
  {#if loading}
    <div class="loading-state">
      <div class="spinner"></div>
      <p>Loading {selectedJsonName} &amp; syncing {finalJsonName}...</p>
    </div>
  {:else if filteredRecords.length === 0}
    <div class="empty-state">
      <h2>No cards match the current filters</h2>
      <p>Try clearing your search query or setting dropdowns back to "All".</p>
      <button
        class="action-btn"
        onclick={() => {
          searchQuery = '';
          selectedDeck = 'all';
          selectedExpansion = 'all';
          selectedCardType = 'all';
          filterReviewed = 'all';
        }}
      >
        Reset Filters
      </button>
    </div>
  {:else}
    <!-- Pagination Header -->
    <div class="pagination-bar">
      <span class="paging-info">
        Showing {(currentPage - 1) * Number(pageSize === 'all' ? filteredRecords.length : pageSize) + 1}
        &ndash;
        {Math.min(currentPage * Number(pageSize === 'all' ? filteredRecords.length : pageSize), filteredRecords.length)}
        of {filteredRecords.length} filtered ({totalCount} total, {finalCount} in {finalJsonName})
      </span>

      {#if totalPages > 1}
        <div class="pager-btns">
          <button class="page-nav-btn" disabled={currentPage <= 1} onclick={() => setPage(1)}>&laquo;</button>
          <button class="page-nav-btn" disabled={currentPage <= 1} onclick={() => setPage(currentPage - 1)}>&lsaquo;</button>
          <span class="current-page-badge">{currentPage} / {totalPages}</span>
          <button class="page-nav-btn" disabled={currentPage >= totalPages} onclick={() => setPage(currentPage + 1)}>&rsaquo;</button>
          <button class="page-nav-btn" disabled={currentPage >= totalPages} onclick={() => setPage(totalPages)}>&raquo;</button>
        </div>
      {/if}
    </div>

    <!-- GRID GALLERY VIEW -->
    {#if viewMode === 'grid'}
      <div class="card-grid">
        {#each pageRecords as rec, i (rec.image?.filename || `${rec.id || 'card'}-${i}`)}
          {@const filename = rec.image?.filename || ''}
          {@const id = rec.id || filename}
          {@const isTerrain = rec.card_type === 'terrain'}
          {@const isAction = rec.card_type === 'action'}
          {@const isReviewed = Boolean(rec.classification?.reviewed)}
          {@const imgUrl = getCardImageUrl(rec)}

          <div
            class="card-tile"
            class:card-reviewed={isReviewed}
          >
            <!-- Card Image & Overlay -->
            <div
              class="card-img-container"
              role="button"
              tabindex="0"
              onclick={() => openInspector(rec)}
              onkeydown={(e) => { if (e.key === 'Enter') openInspector(rec); }}
            >
              {#if imgUrl}
                <img
                  src={imgUrl}
                  alt={rec.name || filename}
                  class="card-img"
                  loading="lazy"
                  onerror={(e) => { e.currentTarget.style.display = 'none'; }}
                />
              {:else}
                <div class="card-img-placeholder">&#127183;</div>
              {/if}

              <!-- Badges -->
              <span class="badge type-badge type-{rec.card_type}">
                {rec.card_type}
              </span>
              <span class="badge exp-badge">
                {rec.expansion}
              </span>

              <!-- 4-Edge Directional Border Visual Indicator -->
              {#if isTerrain && rec.terrain_details?.borders}
                <div class="tile-edge-frame" title="Borders: N:{rec.terrain_details.borders.north} E:{rec.terrain_details.borders.east} S:{rec.terrain_details.borders.south} W:{rec.terrain_details.borders.west}">
                  <span class="tile-edge edge-n" class:edge-dark={rec.terrain_details.borders.north === 'dark'} class:edge-black={rec.terrain_details.borders.north === 'black'}></span>
                  <span class="tile-edge edge-e" class:edge-dark={rec.terrain_details.borders.east === 'dark'} class:edge-black={rec.terrain_details.borders.east === 'black'}></span>
                  <span class="tile-edge edge-s" class:edge-dark={rec.terrain_details.borders.south === 'dark'} class:edge-black={rec.terrain_details.borders.south === 'black'}></span>
                  <span class="tile-edge edge-w" class:edge-dark={rec.terrain_details.borders.west === 'dark'} class:edge-black={rec.terrain_details.borders.west === 'black'}></span>
                </div>
              {/if}
            </div>

            <!-- Card Body / Meta -->
            <div class="tile-body">
              <div class="tile-title" title={rec.name}>{rec.name}</div>
              <div class="tile-deck" title={rec.deck}>{rec.deck}</div>
              <div class="tile-id" title={id}>{id}</div>

              <!-- Pill details -->
              <div class="details-row">
                {#if isTerrain && rec.terrain_details}
                  {#if rec.terrain_details.vehicle_access && rec.terrain_details.vehicle_access !== 'Unknown'}
                    <span
                      class="tag-pill veh-pill"
                      class:veh-prohibited={rec.terrain_details.vehicle_access.includes('No')}
                      class:veh-allowed={rec.terrain_details.vehicle_access.includes('Yes')}
                      title="Vehicle Access: {rec.terrain_details.vehicle_access}"
                    >
                      {rec.terrain_details.vehicle_access.includes('No') ? '❌ Tank: No' : '✅ Tank: Yes'}
                    </span>
                  {/if}
                  <span class="tag-pill cov-pill" title="Cover & Concealment (High/Low)">
                    Cov: +{rec.terrain_details.cover_high ?? 0}{rec.terrain_details.cover_low != null ? `/+${rec.terrain_details.cover_low}` : ''}
                  </span>
                  {#if rec.terrain_details.cover_potential != null}
                    <span class="tag-pill cap-pill" title="Cover Capacity (Max Positions Supported)">
                      Cap: {rec.terrain_details.cover_potential}
                    </span>
                  {/if}
                  {#if rec.terrain_details.cover_draw != null}
                    <span class="tag-pill draw-pill" title="Seek Cover Action Card Draw">
                      Draw: {rec.terrain_details.cover_draw}
                    </span>
                  {/if}
                  <span class="tag-pill elev-pill" title="Elevation (Contour Level)">
                    Elev: {rec.terrain_details.elevation ?? 0}
                  </span>
                {:else if isAction && rec.action_details}
                  {#if rec.action_details.card_number}
                    <span class="tag-pill action-pill" title="Card Number">#{rec.action_details.card_number}</span>
                  {/if}
                  {#if rec.action_details.action_attempt}
                    <span class="tag-pill attempt-pill" title="Action Attempt Header: {rec.action_details.action_attempt}">
                      {rec.action_details.action_attempt}
                    </span>
                  {/if}
                  {#if rec.action_details.commands != null}
                    <span class="tag-pill cmd-pill" title="Activated Commands (Helmet)">
                      &#129656; Cmd: {rec.action_details.commands}
                    </span>
                  {/if}
                  {#if rec.action_details.initiative != null}
                    <span class="tag-pill init-pill" title="Initiative Commands (Square Box)">
                      &#127919; Init: {rec.action_details.initiative}
                    </span>
                  {/if}
                  {#if rec.action_details.anti_tank != null}
                    <span class="tag-pill at-pill" title="Anti-Tank Rating (Lower-Right Tank Reticle)">
                      AT: {rec.action_details.anti_tank}
                    </span>
                  {/if}
                  {#if rec.action_details.spot_concentrate_fire}
                    <span class="tag-pill icon-pill" title="Spot or Concentrate Fire">&#127919; Spot</span>
                  {/if}
                  {#if rec.action_details.infiltrate}
                    <span class="tag-pill icon-pill" title="Infiltrate">&#128694; Infil</span>
                  {/if}
                  {#if rec.action_details.grenade}
                    <span class="tag-pill icon-pill" title="Grenade Attack">&#128163; Grenade</span>
                  {/if}
                  {#if rec.action_details.call_for_fire}
                    <span class="tag-pill icon-pill" title="Call for Fire">&#128165; CFF</span>
                  {/if}
                  {#if rec.action_details.battalion_fire_mission}
                    <span class="tag-pill icon-pill" title="Battalion Fire Mission">&#128165;&#128165; Bn CFF</span>
                  {/if}
                  {#if rec.action_details.call_for_fire_short}
                    <span class="tag-pill icon-pill" title="Call for Fire Short!">&#9888;&#65039; Short!</span>
                  {/if}
                  {#if rec.action_details.hq_event}
                    <span class="tag-pill icon-pill" title="Higher HQ Event">&#128223; HQ</span>
                  {/if}
                  {#if rec.action_details.jam}
                    <span class="tag-pill icon-pill" title="Jam! Catastrophic Failure">&#128293; Jam!</span>
                  {/if}
                {:else}
                  <span class="tag-pill purpose-pill">{rec.purpose}</span>
                {/if}
              </div>

              <!-- Tile Actions -->
              <div class="tile-actions">
                <button
                  class="action-btn-sm"
                  class:btn-validated={isReviewed}
                  disabled={savingId === id}
                  onclick={() => toggleValidated(rec)}
                  title={isReviewed ? `Click to unvalidate & remove from ${finalJsonName}` : `Click to validate & add to ${finalJsonName}`}
                >
                  {isReviewed ? '✓ Validated' : 'Validate'}
                </button>
                <button class="action-btn-sm edit-btn" onclick={() => openInspector(rec)}>
                  Inspect &rarr;
                </button>
              </div>
            </div>
          </div>
        {/each}
      </div>

    <!-- DENSE TABLE VIEW -->
    {:else}
      <div class="table-container">
        <table class="cards-table">
          <thead>
            <tr>
              <th style="width: 48px;">Img</th>
              <th>Card ID</th>
              <th>Card Name</th>
              <th>Type</th>
              <th>Deck</th>
              <th>Expansion</th>
              <th>Purpose / Specifics</th>
              <th>Status</th>
              <th style="width: 140px;">Action</th>
            </tr>
          </thead>
          <tbody>
            {#each pageRecords as rec, i (rec.image?.filename || `${rec.id || 'card'}-${i}`)}
              {@const filename = rec.image?.filename || ''}
              {@const id = rec.id || filename}
              {@const isReviewed = Boolean(rec.classification?.reviewed)}
              {@const imgUrl = getCardImageUrl(rec)}

              <tr class:row-reviewed={isReviewed}>
                <td
                  class="table-img-cell"
                  role="button"
                  tabindex="0"
                  onclick={() => openInspector(rec)}
                  onkeydown={(e) => { if (e.key === 'Enter') openInspector(rec); }}
                >
                  {#if imgUrl}
                    <img src={imgUrl} alt={filename} class="table-card-thumb" loading="lazy" />
                  {:else}
                    <div class="table-thumb-placeholder">&#127183;</div>
                  {/if}
                </td>
                <td>
                  <div
                    class="table-id"
                    role="button"
                    tabindex="0"
                    onclick={() => openInspector(rec)}
                    onkeydown={(e) => { if (e.key === 'Enter') openInspector(rec); }}
                  >
                    {rec.id}
                  </div>
                  <div class="table-filename">{filename}</div>
                </td>
                <td>
                  <strong>{rec.name}</strong>
                </td>
                <td>
                  <span class="badge type-badge type-{rec.card_type}">{rec.card_type}</span>
                </td>
                <td>{rec.deck}</td>
                <td>{rec.expansion}</td>
                <td>
                  {#if rec.card_type === 'terrain' && rec.terrain_details}
                    <span>{rec.terrain_details.terrain_category || 'Terrain'} | Cov: +{rec.terrain_details.cover_high ?? 0}{rec.terrain_details.cover_low != null ? `/+${rec.terrain_details.cover_low}` : ''} | Elev: {rec.terrain_details.elevation ?? 0}</span>
                  {:else if rec.card_type === 'action' && rec.action_details}
                    <span>Action #{rec.action_details.card_number || '—'} {rec.action_details.action_attempt ? `(${rec.action_details.action_attempt})` : ''} {rec.action_details.commands != null ? `| Cmd: ${rec.action_details.commands}` : ''} {rec.action_details.initiative != null ? `| Init: ${rec.action_details.initiative}` : ''} {rec.action_details.anti_tank != null ? `| AT: ${rec.action_details.anti_tank}` : ''}</span>
                  {:else}
                    <span>{rec.purpose}</span>
                  {/if}
                </td>
                <td>
                  <span class="status-badge" class:status-reviewed={isReviewed}>
                    {isReviewed ? '✓ In Final' : 'Unreviewed'}
                  </span>
                </td>
                <td>
                  <div class="row-actions">
                    <button
                      class="action-btn-sm"
                      class:btn-validated={isReviewed}
                      disabled={savingId === id}
                      onclick={() => toggleValidated(rec)}
                      title={isReviewed ? `Remove from ${finalJsonName}` : `Add to ${finalJsonName}`}
                    >
                      {isReviewed ? '✓' : 'Validate'}
                    </button>
                    <button class="action-btn-sm edit-btn" onclick={() => openInspector(rec)}>
                      Edit
                    </button>
                  </div>
                </td>
              </tr>
            {/each}
          </tbody>
        </table>
      </div>
    {/if}

    <!-- Bottom Pagination -->
    {#if totalPages > 1}
      <div class="pagination-bar bottom-pager">
        <button class="page-nav-btn" disabled={currentPage <= 1} onclick={() => setPage(currentPage - 1)}>
          &lsaquo; Prev Page
        </button>
        <span class="current-page-badge">Page {currentPage} of {totalPages}</span>
        <button class="page-nav-btn" disabled={currentPage >= totalPages} onclick={() => setPage(currentPage + 1)}>
          Next Page &rsaquo;
        </button>
      </div>
    {/if}
  {/if}

  <!-- INSPECTOR / QUICK EDIT MODAL -->
  {#if activeRecord !== null}
    {@const imgUrl = getCardImageUrl(activeRecord)}
    {@const id = activeRecord.id || activeRecord.image?.filename}

    <div
      class="modal-backdrop"
      role="presentation"
      onclick={closeInspector}
    >
      <div
        class="inspector-dialog"
        role="dialog"
        tabindex="-1"
        onclick={(e) => e.stopPropagation()}
      >
        <!-- Modal Header -->
        <div class="dialog-header">
          <div class="dialog-title-group">
            <div class="dialog-title-row">
              <h2>Inspect: {activeRecord.name}</h2>
              <span class="badge type-badge type-{activeRecord.card_type}">{activeRecord.card_type}</span>
              <span class="badge exp-badge">{activeRecord.expansion}</span>
              {#if finalMap.has(getRecordKey(activeRecord))}
                <span class="status-indicator-badge in-final">✓ In {finalJsonName}</span>
              {:else}
                <span class="status-indicator-badge not-in-final">Loaded File Version</span>
              {/if}
            </div>
            <span class="dialog-filename">{activeRecord.image?.filename}</span>
          </div>

          <div class="dialog-header-actions">
            <button class="nav-arrow-btn" onclick={() => navInspector(-1)} title="Previous card (&larr;)">
              &larr; Prev
            </button>
            <button class="nav-arrow-btn" onclick={() => navInspector(1)} title="Next card (&rarr;)">
              Next &rarr;
            </button>
            <button class="close-btn" onclick={closeInspector}>&times;</button>
          </div>
        </div>

        <!-- Modal Body Grid -->
        <div class="dialog-body">
          <!-- Left Column: Visual Card Preview -->
          <div class="preview-col">
            <div
              class="card-preview-frame"
              style="--zoom: {zoomLevel}; --card-ratio: {(activeRecord.image?.width || 274) / (activeRecord.image?.height || 384)};"
            >
              {#if imgUrl}
                <img src={imgUrl} alt={activeRecord.name || activeRecord.image?.filename} class="preview-card-img" />
              {:else}
                <div class="preview-placeholder">No Card Image Found</div>
              {/if}

              <!-- Interactive Spatial Reticle Hotspots for Terrain Cards -->
              {#if activeRecord.card_type === 'terrain'}
                <!-- Top-Left: Cover & Concealment (+1/+0) -->
                <div
                  class="card-hotspot hotspot-tl-cover"
                  style={getRegionHotspotStyle('terrain', 'cover')}
                  class:highlighted={activeFieldHighlight === 'tl_cover'}
                  title="Top-Left: Cover & Concealment (+High / +Low)"
                >
                  <span class="hotspot-badge">
                    +{activeRecord.terrain_details?.cover_high ?? 0}{activeRecord.terrain_details?.cover_low != null ? `/+${activeRecord.terrain_details.cover_low}` : ''}
                  </span>
                </div>

                <!-- Top-Center: Tank Access & Terrain Name -->
                <div
                  class="card-hotspot hotspot-tc-name"
                  style={getRegionHotspotStyle('terrain', 'terrain_name_and_vehicle')}
                  class:highlighted={activeFieldHighlight === 'tc_name'}
                  title="Top-Center: Vehicle Access & Terrain Name"
                >
                  <span class="hotspot-badge">
                    {activeRecord.terrain_details?.vehicle_access ? (activeRecord.terrain_details.vehicle_access.includes('No') ? 'Tank: NO' : 'Tank: YES') : ''}
                    {activeRecord.terrain_details?.terrain_name || ''}
                  </span>
                </div>

                <!-- Top-Right: Card Number & Burst -->
                <div
                  class="card-hotspot hotspot-tr-cardno"
                  style={getRegionHotspotStyle('terrain', 'card_number_and_burst')}
                  class:highlighted={activeFieldHighlight === 'tr_num'}
                  title="Top-Right: Card Number & Burst Modifier"
                >
                  <span class="hotspot-badge">
                    #{activeRecord.terrain_details?.card_number || '—'} {activeRecord.terrain_details?.burst_modifier ? `(Burst ${activeRecord.terrain_details.burst_modifier > 0 ? '+' : ''}${activeRecord.terrain_details.burst_modifier})` : ''}
                  </span>
                </div>

                {#if activeRecord.deck === 'Normandy Terrain'}
                  <div
                    class="card-hotspot hotspot-tr-elevation"
                    style={getRegionHotspotStyle('terrain', 'elevation')}
                    class:highlighted={activeFieldHighlight === 'tr_elev'}
                    title="Top-Right: Elevation contour badge"
                  >
                    <span class="hotspot-badge">Elev: {activeRecord.terrain_details?.elevation ?? '—'}</span>
                  </div>
                {/if}

                <!-- Bottom-Left: Cover Capacity / Potential -->
                <div
                  class="card-hotspot hotspot-bl-capacity"
                  style={getRegionHotspotStyle('terrain', 'cover_capacity')}
                  class:highlighted={activeFieldHighlight === 'bl_cap'}
                  title="Bottom-Left: Cover Potential / Capacity (Max Cover Positions)"
                >
                  <span class="hotspot-badge">
                    Cap: {activeRecord.terrain_details?.cover_potential ?? '—'}
                  </span>
                </div>

                <!-- Bottom-Center: Seek Cover Draw -->
                <div
                  class="card-hotspot hotspot-bc-draw"
                  style={getRegionHotspotStyle('terrain', 'cover_draw')}
                  class:highlighted={activeFieldHighlight === 'bc_draw'}
                  title="Bottom-Center: Seek Cover Action Card Draw Number"
                >
                  <span class="hotspot-badge">
                    Draw: {activeRecord.terrain_details?.cover_draw ?? '—'}
                  </span>
                </div>

                {#if activeRecord.deck !== 'Normandy Terrain'}
                  <!-- Bottom-Right elevation badge on non-Normandy terrain cards -->
                  <div
                    class="card-hotspot hotspot-br-move"
                    style={getRegionHotspotStyle('terrain', 'elevation')}
                    class:highlighted={activeFieldHighlight === 'br_elev'}
                    title="Bottom-Right: Elevation Contour Level (-2 to +6)"
                  >
                    <span class="hotspot-badge">Elev: {activeRecord.terrain_details?.elevation ?? 0}</span>
                  </div>
                {/if}

                <!-- 4-Edge Directional Borders on Modal Preview -->
                {#if activeRecord.terrain_details?.borders}
                  <div class="modal-border-frame">
                    <div
                      class="modal-edge edge-n"
                      class:edge-dark={activeRecord.terrain_details.borders.north === 'dark'}
                      class:edge-black={activeRecord.terrain_details.borders.north === 'black'}
                      class:highlighted={activeFieldHighlight === 'borders'}
                      title="North: {activeRecord.terrain_details.borders.north}"
                    >
                      <span>N: {activeRecord.terrain_details.borders.north}</span>
                    </div>
                    <div
                      class="modal-edge edge-e"
                      class:edge-dark={activeRecord.terrain_details.borders.east === 'dark'}
                      class:edge-black={activeRecord.terrain_details.borders.east === 'black'}
                      class:highlighted={activeFieldHighlight === 'borders'}
                      title="East: {activeRecord.terrain_details.borders.east}"
                    >
                      <span>E: {activeRecord.terrain_details.borders.east}</span>
                    </div>
                    <div
                      class="modal-edge edge-s"
                      class:edge-dark={activeRecord.terrain_details.borders.south === 'dark'}
                      class:edge-black={activeRecord.terrain_details.borders.south === 'black'}
                      class:highlighted={activeFieldHighlight === 'borders'}
                      title="South: {activeRecord.terrain_details.borders.south}"
                    >
                      <span>S: {activeRecord.terrain_details.borders.south}</span>
                    </div>
                    <div
                      class="modal-edge edge-w"
                      class:edge-dark={activeRecord.terrain_details.borders.west === 'dark'}
                      class:edge-black={activeRecord.terrain_details.borders.west === 'black'}
                      class:highlighted={activeFieldHighlight === 'borders'}
                      title="West: {activeRecord.terrain_details.borders.west}"
                    >
                      <span>W: {activeRecord.terrain_details.borders.west}</span>
                    </div>
                  </div>
                {/if}
              {:else if activeRecord.card_type === 'action' && activeRecord.action_details}
                <!-- Top-Left Helmet: Activated Commands -->
                <div
                  class="card-hotspot hotspot-act-cmd"
                  style={getRegionHotspotStyle('action', 'commands')}
                  class:highlighted={activeFieldHighlight === 'act_cmd'}
                  title="Top-Left: Activated Commands (Helmet Value)"
                >
                  <span class="hotspot-badge">&#129656; Cmd: {activeRecord.action_details.commands ?? '—'}</span>
                </div>

                <!-- Initiative Box: Below Helmet -->
                <div
                  class="card-hotspot hotspot-act-init"
                  style={getRegionHotspotStyle('action', 'initiative')}
                  class:highlighted={activeFieldHighlight === 'act_init'}
                  title="Initiative Commands (Square Box)"
                >
                  <span class="hotspot-badge">&#127919; Init: {activeRecord.action_details.initiative ?? '—'}</span>
                </div>

                <!-- Top-Right: Action Card Number -->
                <div
                  class="card-hotspot hotspot-act-num"
                  style={getRegionHotspotStyle('action', 'card_number')}
                  class:highlighted={activeFieldHighlight === 'act_num'}
                  title="Top-Right: Action Card Number"
                >
                  <span class="hotspot-badge">#{activeRecord.action_details.card_number ?? '—'}</span>
                </div>

                <!-- Top-Center: Attempt Header (Cover / Rally / Contact) -->
                {#if activeRecord.action_details.action_attempt}
                  <div
                    class="card-hotspot hotspot-act-attempt"
                    style={getRegionHotspotStyle('action', 'header')}
                    class:highlighted={activeFieldHighlight === 'act_attempt'}
                    title="Top-Center: Action Attempt Header"
                  >
                    <span class="hotspot-badge">{activeRecord.action_details.action_attempt}</span>
                  </div>
                {/if}

                <!-- Center: Action Attempt Area (Specialty Icons) -->
                <div
                  class="card-hotspot hotspot-act-icons"
                  style={getRegionHotspotStyle('action', 'attempt_icons')}
                  class:highlighted={activeFieldHighlight === 'act_icons'}
                  title="Center: Action Attempt Area Icons"
                >
                  <span class="hotspot-badge">Attempt Area</span>
                </div>

                <!-- Lower-Right: Anti-Tank Number -->
                <div
                  class="card-hotspot hotspot-act-at"
                  style={getRegionHotspotStyle('action', 'anti_tank')}
                  class:highlighted={activeFieldHighlight === 'act_at'}
                  title="Lower-Right: Anti-Tank Number (Tank Reticle)"
                >
                  <span class="hotspot-badge">AT: {activeRecord.action_details.anti_tank ?? '—'}</span>
                </div>

                <!-- Lower-Center: Hit Effects Table -->
                <div
                  class="card-hotspot hotspot-act-hit"
                  style={getRegionHotspotStyle('action', 'hit_effects')}
                  class:highlighted={activeFieldHighlight === 'act_hit'}
                  title="Lower-Center: Hit Effects Table"
                >
                  <span class="hotspot-badge">Hit Effects</span>
                </div>

                <!-- Bottom: Random Number Section (Columns 2-12) -->
                <div
                  class="card-hotspot hotspot-act-rn"
                  style={getRegionHotspotStyle('action', 'random_numbers')}
                  class:highlighted={activeFieldHighlight === 'act_rn'}
                  title="Bottom: Random Number Section (1-N Check Matrix, Columns 2-12)"
                >
                  <span class="hotspot-badge">R#: {activeRecord.action_details.random_number ?? '2-12 Matrix'}</span>
                </div>
              {/if}
            </div>

            <div class="zoom-controls">
              <span>Zoom:</span>
              <button class="zoom-btn" class:active={zoomLevel === 1} onclick={() => (zoomLevel = 1)}>1x</button>
              <button class="zoom-btn" class:active={zoomLevel === 1.5} onclick={() => (zoomLevel = 1.5)}>1.5x</button>
              <button class="zoom-btn" class:active={zoomLevel === 2} onclick={() => (zoomLevel = 2)}>2x</button>
              <button class="zoom-btn" class:active={zoomLevel === 3} onclick={() => (zoomLevel = 3)}>3x</button>
            </div>

            {#if activeFieldHighlight && getActiveCropRegion() && imgUrl}
              {@const crop = getActiveCropRegion()}
              <div class="field-crop-panel" aria-live="polite">
                <span class="field-crop-title">Focused field crop</span>
                <div
                  class="field-crop-window"
                  style={`aspect-ratio:${(activeRecord.image?.width || 274) * crop.width}/${(activeRecord.image?.height || 384) * crop.height}`}
                >
                  <img
                    src={imgUrl}
                    alt="Enlarged crop of the focused card field"
                    style={`width:${100 / crop.width}%;left:${-100 * crop.x / crop.width}%;top:${-100 * crop.y / crop.height}%`}
                  />
                </div>
              </div>
            {/if}

            <div class="card-info-box">
              <h4>Classification Evidence</h4>
              {#if activeRecord.classification?.notes}
                <p class="notes-text">{activeRecord.classification.notes}</p>
              {/if}
            </div>
          </div>

          <!-- Right Column: Editable Schema Properties -->
          <div class="fields-col">
            <!-- SECTION 1: IDENTITY & TAXONOMY -->
            <div class="field-section">
              <div class="section-title-bar">
                <span class="section-badge badge-top">&#127183; Card Identity &amp; Classification</span>
              </div>
              <div class="form-grid-3">
                <label class="form-field">
                  <span class="field-title">Card ID:</span>
                  <input type="text" bind:value={activeRecord.id} class="form-input" />
                </label>

                <label class="form-field">
                  <span class="field-title">Display Name:</span>
                  <input type="text" bind:value={activeRecord.name} class="form-input" />
                </label>

                <label class="form-field">
                  <span class="field-title">Card Type:</span>
                  <select bind:value={activeRecord.card_type} class="form-select">
                    {#each KNOWN_CARD_TYPES as ct}
                      <option value={ct.value}>{ct.label}</option>
                    {/each}
                  </select>
                </label>

                <label class="form-field">
                  <span class="field-title">Deck:</span>
                  <div class="input-with-dropdown">
                    <select
                      class="form-select"
                      value={KNOWN_DECKS.includes(activeRecord.deck) ? activeRecord.deck : '__custom__'}
                      onchange={(e) => {
                        const val = e.currentTarget.value;
                        if (val !== '__custom__') activeRecord.deck = val;
                      }}
                    >
                      {#each KNOWN_DECKS as d}
                        <option value={d}>{d}</option>
                      {/each}
                      <option value="__custom__">Custom / Other &rarr;</option>
                    </select>
                    {#if !KNOWN_DECKS.includes(activeRecord.deck)}
                      <input type="text" bind:value={activeRecord.deck} placeholder="Custom Deck Name" class="form-input custom-input" />
                    {/if}
                  </div>
                </label>

                <label class="form-field">
                  <span class="field-title">Expansion / Volume:</span>
                  <select bind:value={activeRecord.expansion} class="form-select">
                    {#each KNOWN_EXPANSIONS as exp}
                      <option value={exp}>{exp}</option>
                    {/each}
                  </select>
                </label>

                <label class="form-field">
                  <span class="field-title">Purpose / Role:</span>
                  <div class="input-with-dropdown">
                    <select
                      class="form-select"
                      value={KNOWN_PURPOSES.includes(activeRecord.purpose) ? activeRecord.purpose : '__custom__'}
                      onchange={(e) => {
                        const val = e.currentTarget.value;
                        if (val !== '__custom__') activeRecord.purpose = val;
                      }}
                    >
                      {#each KNOWN_PURPOSES as p}
                        <option value={p}>{p}</option>
                      {/each}
                      <option value="__custom__">Custom / Other &rarr;</option>
                    </select>
                    {#if !KNOWN_PURPOSES.includes(activeRecord.purpose)}
                      <input type="text" bind:value={activeRecord.purpose} placeholder="Custom Purpose" class="form-input custom-input" />
                    {/if}
                  </div>
                </label>
              </div>
            </div>

            <!-- SECTION 2: TERRAIN DETAILS (When card_type === 'terrain') -->
            {#if activeRecord.card_type === 'terrain' && activeRecord.terrain_details}
              <!-- TOP BANNER (HEADER) -->
              <div
                class="field-section section-terrain-top"
                class:section-active={activeFieldHighlight === 'tl_cover' || activeFieldHighlight === 'tc_name' || activeFieldHighlight === 'tr_num' || activeFieldHighlight === 'tr_elev'}
              >
                <div class="section-title-bar">
                  <span class="section-badge badge-top">&#128392; Top of Card (Cover Circle, Tank Access, Name &amp; Elevation)</span>
                </div>
                <div class="form-grid-3">
                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'tl_cover')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#8598; Cover High (+): <span class="provenance-chip" class:verified={getFieldProvenance('terrain_details', 'cover_high') === 'Verified'}>{getFieldProvenance('terrain_details', 'cover_high')}</span></span>
                    <input
                      type="number"
                      min="0"
                      max="5"
                      bind:value={activeRecord.terrain_details.cover_high}
                      class="form-input"
                      onfocus={() => (activeFieldHighlight = 'tl_cover')}
                      onblur={() => (activeFieldHighlight = null)}
                    />
                  </label>

                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'tl_cover')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#8598; Cover Low (+) [leave blank if single]: <span class="provenance-chip" class:verified={getFieldProvenance('terrain_details', 'cover_low') === 'Verified'}>{getFieldProvenance('terrain_details', 'cover_low')}</span></span>
                    <input
                      type="number"
                      min="0"
                      max="5"
                      bind:value={activeRecord.terrain_details.cover_low}
                      placeholder="Blank (single value)"
                      class="form-input"
                      onfocus={() => (activeFieldHighlight = 'tl_cover')}
                      onblur={() => (activeFieldHighlight = null)}
                    />
                  </label>

                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'tc_name')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#128668; Vehicle Access (Tank):</span>
                    <select
                      bind:value={activeRecord.terrain_details.vehicle_access}
                      class="form-select"
                      onfocus={() => (activeFieldHighlight = 'tc_name')}
                      onblur={() => (activeFieldHighlight = null)}
                    >
                      {#each KNOWN_VEHICLE_ACCESS as va}
                        <option value={va}>{va}</option>
                      {/each}
                    </select>
                  </label>

                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'tc_name')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#128392; Terrain Name:</span>
                    <input
                      type="text"
                      bind:value={activeRecord.terrain_details.terrain_name}
                      placeholder="e.g. Graveyard, Hill, Canal"
                      class="form-input"
                      onfocus={() => (activeFieldHighlight = 'tc_name')}
                      onblur={() => (activeFieldHighlight = null)}
                    />
                  </label>

                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'tr_num')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#8599; Card Number:</span>
                    <input
                      type="text"
                      bind:value={activeRecord.terrain_details.card_number}
                      placeholder="e.g. 58, 001, N01"
                      class="form-input"
                      onfocus={() => (activeFieldHighlight = 'tr_num')}
                      onblur={() => (activeFieldHighlight = null)}
                    />
                  </label>

                  {#if activeRecord.deck === 'Normandy Terrain'}
                    <label
                      class="form-field"
                      onmouseenter={() => (activeFieldHighlight = 'tr_elev')}
                      onmouseleave={() => (activeFieldHighlight = null)}
                    >
                      <span class="field-title">&#8599; Elevation (Top-Right badge, -2 to +6): <span class="provenance-chip" class:verified={getFieldProvenance('terrain_details', 'elevation') === 'Verified'}>{getFieldProvenance('terrain_details', 'elevation')}</span></span>
                      <input
                        type="number"
                        min="-2"
                        max="6"
                        bind:value={activeRecord.terrain_details.elevation}
                        class="form-input"
                        onfocus={() => (activeFieldHighlight = 'tr_elev')}
                        onblur={() => (activeFieldHighlight = null)}
                      />
                    </label>
                  {/if}

                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'tr_num')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#8599; Burst Modifier (-3 to +3):</span>
                    <input
                      type="number"
                      min="-3"
                      max="3"
                      bind:value={activeRecord.terrain_details.burst_modifier}
                      class="form-input"
                      placeholder="0"
                      onfocus={() => (activeFieldHighlight = 'tr_num')}
                      onblur={() => (activeFieldHighlight = null)}
                    />
                  </label>
                </div>
              </div>

              <!-- BOTTOM TACTICAL BAR (3 ICONS) -->
              <div
                class="field-section section-terrain-bottom"
                class:section-active={activeFieldHighlight === 'bl_cap' || activeFieldHighlight === 'bc_draw' || (activeRecord.deck !== 'Normandy Terrain' && activeFieldHighlight === 'br_elev')}
              >
                <div class="section-title-bar">
                  <span class="section-badge badge-terrain">&#9878; Bottom Icons (Capacity, Card Draw{activeRecord.deck !== 'Normandy Terrain' ? ', Elevation' : ''})</span>
                </div>
                <div class="form-grid-3">
                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'bl_cap')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#8601; Cover Capacity (Positions): <span class="provenance-chip" class:verified={getFieldProvenance('terrain_details', 'cover_potential') === 'Verified'}>{getFieldProvenance('terrain_details', 'cover_potential')}</span></span>
                    <input
                      type="number"
                      min="0"
                      max="4"
                      bind:value={activeRecord.terrain_details.cover_potential}
                      placeholder="e.g. 1, 2, 3"
                      class="form-input"
                      onfocus={() => (activeFieldHighlight = 'bl_cap')}
                      onblur={() => (activeFieldHighlight = null)}
                    />
                  </label>

                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'bc_draw')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#8595; Cover Draw (Action Cards): <span class="provenance-chip" class:verified={getFieldProvenance('terrain_details', 'cover_draw') === 'Verified'}>{getFieldProvenance('terrain_details', 'cover_draw')}</span></span>
                    <input
                      type="number"
                      min="1"
                      max="5"
                      bind:value={activeRecord.terrain_details.cover_draw}
                      placeholder="Cards drawn (e.g. 3)"
                      class="form-input"
                      onfocus={() => (activeFieldHighlight = 'bc_draw')}
                      onblur={() => (activeFieldHighlight = null)}
                    />
                  </label>

                  {#if activeRecord.deck !== 'Normandy Terrain'}
                    <label
                      class="form-field"
                      onmouseenter={() => (activeFieldHighlight = 'br_elev')}
                      onmouseleave={() => (activeFieldHighlight = null)}
                    >
                      <span class="field-title">&#8600; Elevation (-2 to +6):</span>
                      <input
                        type="number"
                        min="-2"
                        max="6"
                        bind:value={activeRecord.terrain_details.elevation}
                        placeholder="e.g. 0, 1, 2"
                        class="form-input"
                        onfocus={() => (activeFieldHighlight = 'br_elev')}
                        onblur={() => (activeFieldHighlight = null)}
                      />
                    </label>
                  {/if}
                </div>
              </div>

              <!-- TERRAIN CATEGORY & DIRECTIONAL BORDERS -->
              <div
                class="field-section section-edges"
                class:section-active={activeFieldHighlight === 'borders'}
              >
                <div class="section-title-bar">
                  <span class="section-badge badge-edges">&#128506; Terrain Features &amp; Directional Borders (FoF Section 5.2.1)</span>
                </div>
                <div class="form-grid-4">
                  <label class="form-field">
                    <span class="field-title">Category:</span>
                    <select bind:value={activeRecord.terrain_details.terrain_category} class="form-select">
                      {#each KNOWN_TERRAIN_CATEGORIES as tc}
                        <option value={tc}>{tc}</option>
                      {/each}
                    </select>
                  </label>

                  <label class="form-field">
                    <span class="field-title">Trafficability:</span>
                    <select bind:value={activeRecord.terrain_details.trafficability} class="form-select">
                      <option value="good">good</option>
                      <option value="fair">fair</option>
                      <option value="poor">poor</option>
                      <option value="impassable">impassable</option>
                    </select>
                  </label>

                  <label class="form-field">
                    <span class="field-title">Landing Zone (LZ):</span>
                    <select bind:value={activeRecord.terrain_details.landing_zone} class="form-select">
                      <option value="None">None</option>
                      <option value="Good">Good</option>
                      <option value="Poor">Poor</option>
                      <option value="LZ-1">LZ-1</option>
                      <option value="LZ-2">LZ-2</option>
                    </select>
                  </label>

                  <label class="form-field">
                    <span class="field-title">Burst Modifier:</span>
                    <input type="number" min="-3" max="3" bind:value={activeRecord.terrain_details.burst_modifier} class="form-input" />
                  </label>
                </div>

                <!-- Borders Grid -->
                <div
                  class="borders-bar"
                  onmouseenter={() => (activeFieldHighlight = 'borders')}
                  onmouseleave={() => (activeFieldHighlight = null)}
                >
                  <span class="sub-bar-title">&#9878; 4-Edge LOS &amp; VOF Directional Borders (Green = Dark / Blocks LOS; Light = White / Open LOS):</span>
                  <div class="borders-grid">
                    <label class="form-field">
                      <span class="field-title">&uarr; North Edge:</span>
                      <select bind:value={activeRecord.terrain_details.borders.north} class="form-select border-select" class:opt-dark={activeRecord.terrain_details.borders.north === 'dark'} class:opt-white={activeRecord.terrain_details.borders.north === 'white'} onfocus={() => (activeFieldHighlight = 'borders')} onblur={() => (activeFieldHighlight = null)}>
                        <option value="white">White / Light (Open LOS)</option>
                        <option value="dark">Dark / Green (Blocks LOS)</option>
                        <option value="black">Black (Impassable)</option>
                      </select>
                    </label>
                    <label class="form-field">
                      <span class="field-title">&rarr; East Edge:</span>
                      <select bind:value={activeRecord.terrain_details.borders.east} class="form-select border-select" class:opt-dark={activeRecord.terrain_details.borders.east === 'dark'} class:opt-white={activeRecord.terrain_details.borders.east === 'white'} onfocus={() => (activeFieldHighlight = 'borders')} onblur={() => (activeFieldHighlight = null)}>
                        <option value="white">White / Light (Open LOS)</option>
                        <option value="dark">Dark / Green (Blocks LOS)</option>
                        <option value="black">Black (Impassable)</option>
                      </select>
                    </label>
                    <label class="form-field">
                      <span class="field-title">&darr; South Edge:</span>
                      <select bind:value={activeRecord.terrain_details.borders.south} class="form-select border-select" class:opt-dark={activeRecord.terrain_details.borders.south === 'dark'} class:opt-white={activeRecord.terrain_details.borders.south === 'white'} onfocus={() => (activeFieldHighlight = 'borders')} onblur={() => (activeFieldHighlight = null)}>
                        <option value="white">White / Light (Open LOS)</option>
                        <option value="dark">Dark / Green (Blocks LOS)</option>
                        <option value="black">Black (Impassable)</option>
                      </select>
                    </label>
                    <label class="form-field">
                      <span class="field-title">&larr; West Edge:</span>
                      <select bind:value={activeRecord.terrain_details.borders.west} class="form-select border-select" class:opt-dark={activeRecord.terrain_details.borders.west === 'dark'} class:opt-white={activeRecord.terrain_details.borders.west === 'white'} onfocus={() => (activeFieldHighlight = 'borders')} onblur={() => (activeFieldHighlight = null)}>
                        <option value="white">White / Light (Open LOS)</option>
                        <option value="dark">Dark / Green (Blocks LOS)</option>
                        <option value="black">Black (Impassable)</option>
                      </select>
                    </label>
                  </div>
                </div>
              </div>

            <!-- SECTION 3: ACTION DETAILS (When card_type === 'action') -->
            {:else if activeRecord.card_type === 'action' && activeRecord.action_details}
              <div class="field-section section-action">
                <div class="section-title-bar">
                  <span class="section-badge badge-action">&#9876; Action Deck Properties (FoF Section 2.8 &amp; 6.4)</span>
                </div>
                <div class="form-grid-3">
                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'act_num')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#8599; Card Number (1-50): <span class="provenance-chip" class:verified={getFieldProvenance('action_details', 'card_number') === 'Verified'}>{getFieldProvenance('action_details', 'card_number')}</span></span>
                    <input
                      type="number"
                      min="1"
                      max="50"
                      bind:value={activeRecord.action_details.card_number}
                      class="form-input"
                      onfocus={() => (activeFieldHighlight = 'act_num')}
                      onblur={() => (activeFieldHighlight = null)}
                    />
                  </label>

                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'act_cmd')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#129656; Activated Commands (Helmet, 1-6): <span class="provenance-chip" class:verified={getFieldProvenance('action_details', 'commands') === 'Verified'}>{getFieldProvenance('action_details', 'commands')}</span></span>
                    <input
                      type="number"
                      min="1"
                      max="6"
                      bind:value={activeRecord.action_details.commands}
                      class="form-input"
                      onfocus={() => (activeFieldHighlight = 'act_cmd')}
                      onblur={() => (activeFieldHighlight = null)}
                    />
                  </label>

                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'act_init')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#127919; Initiative Commands (Box, 0-4): <span class="provenance-chip" class:verified={getFieldProvenance('action_details', 'initiative') === 'Verified'}>{getFieldProvenance('action_details', 'initiative')}</span></span>
                    <input
                      type="number"
                      min="0"
                      max="4"
                      bind:value={activeRecord.action_details.initiative}
                      class="form-input"
                      onfocus={() => (activeFieldHighlight = 'act_init')}
                      onblur={() => (activeFieldHighlight = null)}
                    />
                  </label>

                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'act_attempt')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#128308; Action Attempt Header: <span class="provenance-chip" class:verified={getFieldProvenance('action_details', 'action_attempt') === 'Verified'}>{getFieldProvenance('action_details', 'action_attempt')}</span></span>
                    <select
                      bind:value={activeRecord.action_details.action_attempt}
                      class="form-select"
                      onfocus={() => (activeFieldHighlight = 'act_attempt')}
                      onblur={() => (activeFieldHighlight = null)}
                    >
                      <option value={null}>None (Blank)</option>
                      <option value="Cover">Cover (Seek Cover Check)</option>
                      <option value="Rally">Rally (Unit Morale Check)</option>
                      <option value="Contact">Contact (Potential Contact)</option>
                    </select>
                  </label>

                  <label
                    class="form-field"
                    onmouseenter={() => (activeFieldHighlight = 'act_at')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#128640; Anti-Tank Rating (AT Number): <span class="provenance-chip" class:verified={getFieldProvenance('action_details', 'anti_tank') === 'Verified'}>{getFieldProvenance('action_details', 'anti_tank')}</span></span>
                    <input
                      type="number"
                      min="0"
                      max="9"
                      bind:value={activeRecord.action_details.anti_tank}
                      placeholder="e.g. 7"
                      class="form-input"
                      onfocus={() => (activeFieldHighlight = 'act_at')}
                      onblur={() => (activeFieldHighlight = null)}
                    />
                  </label>

                  <label class="form-field">
                    <span class="field-title">Direction Arrow:</span>
                    <select bind:value={activeRecord.action_details.direction_arrow} class="form-select">
                      <option value={null}>None</option>
                      <option value="N">North (&uarr;)</option>
                      <option value="NE">Northeast (&nearr;)</option>
                      <option value="E">East (&rarr;)</option>
                      <option value="SE">Southeast (&searr;)</option>
                      <option value="S">South (&darr;)</option>
                      <option value="SW">Southwest (&swarr;)</option>
                      <option value="W">West (&larr;)</option>
                      <option value="NW">Northwest (&nwarr;)</option>
                    </select>
                  </label>

                  <label
                    class="form-field full-width"
                    onmouseenter={() => (activeFieldHighlight = 'act_hit')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <span class="field-title">&#128165; Hit Effect Section: <span class="provenance-chip" class:verified={getFieldProvenance('action_details', 'hit_effects') === 'Verified'}>{getFieldProvenance('action_details', 'hit_effects')}</span></span>
                    <input
                      type="text"
                      bind:value={activeRecord.action_details.hit_effects}
                      placeholder="3 values in Vet Line Green order, e.g. CC CC CC"
                      class="form-input"
                      onfocus={() => (activeFieldHighlight = 'act_hit')}
                      onblur={() => (activeFieldHighlight = null)}
                    />
                  </label>

                  {#if activeRecord.action_details.combat_resolution}
                    <label class="form-field full-width">
                      <span class="field-title">&#9876; Direct-Fire Combat Resolution: <span class="provenance-chip" class:verified={getFieldProvenance('action_details', 'combat_resolution') === 'Verified'}>{getFieldProvenance('action_details', 'combat_resolution')}</span></span>
                      <input
                        type="text"
                        bind:value={activeRecord.action_details.combat_resolution}
                        placeholder="e.g. -4 HIT; -3 PIN; 0 MISS"
                        class="form-input"
                      />
                    </label>
                  {/if}
                </div>

                <!-- Center Action Attempt Icons (Section 2.8 / Reference Chart) -->
                <div
                  class="action-icons-box"
                  onmouseenter={() => (activeFieldHighlight = 'act_icons')}
                  onmouseleave={() => (activeFieldHighlight = null)}
                >
                  <span class="sub-bar-title">&#128308; Center Action Attempt Icons (Rulebook Section 2.8 / Reference Card):</span>
                  <div class="action-icon-flags-grid">
                    <label class="icon-toggle-label" class:is-set={activeRecord.action_details.spot_concentrate_fire}>
                      <input type="checkbox" bind:checked={activeRecord.action_details.spot_concentrate_fire} />
                      <span class="icon-flag-name">&#127919; Spot / Concentrate Fire</span>
                      <span class="icon-flag-desc">Crosshair / Target reticle</span>
                    </label>

                    <label class="icon-toggle-label" class:is-set={activeRecord.action_details.infiltrate}>
                      <input type="checkbox" bind:checked={activeRecord.action_details.infiltrate} />
                      <span class="icon-flag-name">&#128694; Infiltrate</span>
                      <span class="icon-flag-desc">3 Infantry silhouettes in wire</span>
                    </label>

                    <label class="icon-toggle-label" class:is-set={activeRecord.action_details.grenade}>
                      <input type="checkbox" bind:checked={activeRecord.action_details.grenade} />
                      <span class="icon-flag-name">&#128163; Grenade Attack</span>
                      <span class="icon-flag-desc">Hand grenade icon</span>
                    </label>

                    <label class="icon-toggle-label" class:is-set={activeRecord.action_details.call_for_fire}>
                      <input type="checkbox" bind:checked={activeRecord.action_details.call_for_fire} />
                      <span class="icon-flag-name">&#128165; Call for Fire / Mine</span>
                      <span class="icon-flag-desc">Single explosion burst</span>
                    </label>

                    <label class="icon-toggle-label" class:is-set={activeRecord.action_details.battalion_fire_mission}>
                      <input type="checkbox" bind:checked={activeRecord.action_details.battalion_fire_mission} />
                      <span class="icon-flag-name">&#128165;&#128165;&#128165; Battalion Fire Mission</span>
                      <span class="icon-flag-desc">Triple explosion bursts</span>
                    </label>

                    <label class="icon-toggle-label" class:is-set={activeRecord.action_details.call_for_fire_short}>
                      <input type="checkbox" bind:checked={activeRecord.action_details.call_for_fire_short} />
                      <span class="icon-flag-name">&#9888;&#65039; Call for Fire Short!</span>
                      <span class="icon-flag-desc">Explosion with 'Short!' text</span>
                    </label>

                    <label class="icon-toggle-label" class:is-set={activeRecord.action_details.hq_event}>
                      <input type="checkbox" bind:checked={activeRecord.action_details.hq_event} />
                      <span class="icon-flag-name">&#128223; Higher HQ Event</span>
                      <span class="icon-flag-desc">Radio handset with 'HQ'</span>
                    </label>

                    <label class="icon-toggle-label" class:is-set={activeRecord.action_details.jam}>
                      <input type="checkbox" bind:checked={activeRecord.action_details.jam} />
                      <span class="icon-flag-name">&#128293; Jam! (Catastrophic Failure)</span>
                      <span class="icon-flag-desc">Reticle with 'Jam!' text</span>
                    </label>
                  </div>
                </div>

                <!-- Random Number Section (1-N Table) -->
                <div
                  class="rn-matrix-box"
                  onmouseenter={() => (activeFieldHighlight = 'act_rn')}
                  onmouseleave={() => (activeFieldHighlight = null)}
                >
                  <div class="rn-header-bar">
                    <span class="sub-bar-title">&#127922; Random Number Section (1-N Check Matrix, Columns 2 through 12):</span>
                    {#if activeRecord.action_details.random_number}
                      <span class="rn-summary-badge">R#: {activeRecord.action_details.random_number}</span>
                    {/if}
                  </div>
                  <div class="rn-table">
                    <div class="rn-row rn-col-labels">
                      <div class="rn-label-col">Column (1-N)</div>
                      {#each [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as col}
                        <div class="rn-cell rn-col-num">{col}</div>
                      {/each}
                    </div>
                    <div class="rn-row rn-col-inputs">
                      <div class="rn-label-col">Result</div>
                      {#if !activeRecord.action_details.random_numbers}
                        <div class="rn-empty" style="grid-column: span 11;">
                          <input
                            type="text"
                            bind:value={activeRecord.action_details.random_number}
                            placeholder="e.g. 1 1 1 2 2 2 2 3 3 3 4"
                            class="form-input"
                            onfocus={() => (activeFieldHighlight = 'act_rn')}
                            onblur={() => (activeFieldHighlight = null)}
                          />
                        </div>
                      {:else}
                        {#each [2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12] as col}
                          <div class="rn-cell">
                            <input
                              type="number"
                              min="1"
                              max={col}
                              bind:value={activeRecord.action_details.random_numbers[String(col)]}
                              class="rn-input"
                              onfocus={() => (activeFieldHighlight = 'act_rn')}
                              onblur={() => (activeFieldHighlight = null)}
                            />
                          </div>
                        {/each}
                      {/if}
                    </div>
                  </div>
                </div>
              </div>
            {/if}

            <!-- NOTES & METADATA -->
            <div class="field-section section-notes">
              <label class="form-field">
                <span class="field-title">Reviewer Notes:</span>
                <input type="text" bind:value={activeRecord.classification.notes} placeholder="Additional notes or clarification" class="form-input" />
              </label>
            </div>
          </div>
        </div>

        <!-- Fixed Modal Footer -->
        <div class="dialog-footer">
          <label class="reviewed-checkbox-label">
            <input
              type="checkbox"
              bind:checked={activeRecord.classification.reviewed}
            />
            In {finalJsonName}
          </label>

          <div class="btn-cluster">
            <button
              class="save-btn"
              disabled={savingId !== null}
              onclick={() => saveActiveRecord(false)}
            >
              {savingId !== null ? 'Saving...' : 'Save Record'}
            </button>
            <button
              class="save-next-btn"
              disabled={savingId !== null}
              onclick={() => saveActiveRecord(true)}
              title="Save changes and advance to next card"
            >
              Save &amp; Next (&rarr;)
            </button>
            <button
              class="validate-btn"
              class:btn-validated={Boolean(activeRecord.classification?.reviewed)}
              disabled={savingId !== null}
              onclick={() => saveActiveRecord(true, !Boolean(activeRecord.classification?.reviewed))}
              title="Validate and advance to next card"
            >
              {Boolean(activeRecord.classification?.reviewed) ? '✓ Validated' : 'Validate & Next'}
            </button>
          </div>
        </div>
      </div>
    </div>
  {/if}
</div>

<style>
  .validator-root {
    min-height: 100vh;
    background: #0f1423;
    color: #e1e7f0;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
    padding: 1.25rem 2rem 4rem;
  }

  .top-nav {
    display: flex;
    justify-content: space-between;
    align-items: center;
    flex-wrap: wrap;
    gap: 1rem;
    padding-bottom: 1.25rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
  }

  .nav-title-group {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .nav-title-group h1 {
    font-size: 1.4rem;
    margin: 0;
    font-weight: 700;
    color: #fff;
  }

  .home-btn,
  .secondary-nav-btn {
    background: #1e293b;
    color: #cbd5e1;
    text-decoration: none;
    font-size: 0.8rem;
    font-weight: 600;
    padding: 0.35rem 0.75rem;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.1);
    transition: all 0.15s ease;
  }

  .home-btn:hover,
  .secondary-nav-btn:hover {
    background: #334155;
    color: #fff;
  }

  .file-tag {
    font-size: 0.75rem;
    font-family: monospace;
    background: #1e293b;
    color: #94a3b8;
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
  }

  .final-file-tag {
    font-size: 0.75rem;
    background: rgba(16, 185, 129, 0.12);
    color: #34d399;
    border: 1px solid rgba(16, 185, 129, 0.3);
    padding: 0.25rem 0.5rem;
    border-radius: 3px;
    font-weight: 600;
  }

  .nav-config-group {
    display: flex;
    align-items: center;
    gap: 0.75rem;
  }

  .config-label {
    font-size: 0.8rem;
    color: #94a3b8;
    display: flex;
    align-items: center;
    gap: 0.35rem;
  }

  .nav-select {
    background: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #fff;
    padding: 0.35rem 0.6rem;
    border-radius: 4px;
    font-size: 0.85rem;
  }

  .reload-btn {
    background: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #cbd5e1;
    padding: 0.35rem 0.75rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
  }

  .reload-btn:hover {
    background: #334155;
    color: #fff;
  }

  .view-toggle {
    display: flex;
    background: #1e293b;
    border-radius: 4px;
    padding: 2px;
  }

  .toggle-btn {
    background: transparent;
    border: none;
    color: #94a3b8;
    padding: 0.3rem 0.6rem;
    border-radius: 3px;
    cursor: pointer;
    font-size: 0.8rem;
  }

  .toggle-btn.active {
    background: #3b82f6;
    color: #fff;
  }

  /* Audit Bar */
  .audit-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.6rem;
    margin: 1rem 0;
  }

  .audit-stat {
    background: #151d30;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 6px;
    padding: 0.4rem 0.8rem;
    display: flex;
    align-items: center;
    gap: 0.5rem;
    cursor: pointer;
    transition: all 0.15s ease;
  }

  .audit-stat:hover {
    border-color: rgba(255, 255, 255, 0.2);
    background: #1a243c;
  }

  .audit-stat.active-chip {
    border-color: #3b82f6;
    background: #1e3a8a;
  }

  .stat-num {
    font-weight: 700;
    font-size: 0.95rem;
    color: #fff;
  }

  .stat-lbl {
    font-size: 0.75rem;
    color: #94a3b8;
  }

  .category-terrain { color: #34d399; }
  .category-action { color: #f87171; }
  .category-fsa { color: #38bdf8; }
  .category-staging { color: #fbbf24; }
  .category-utility { color: #a855f7; }

  /* Filters */
  .filters-bar {
    display: flex;
    flex-wrap: wrap;
    gap: 0.75rem;
    align-items: center;
    background: #131a2c;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    padding: 0.6rem 0.85rem;
    margin-bottom: 1rem;
  }

  .search-box {
    position: relative;
    flex: 1;
    min-width: 240px;
  }

  .search-input {
    width: 100%;
    background: #0c1220;
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #fff;
    padding: 0.45rem 0.75rem;
    border-radius: 4px;
    font-size: 0.85rem;
    box-sizing: border-box;
  }

  .clear-search {
    position: absolute;
    right: 8px;
    top: 50%;
    transform: translateY(-50%);
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 1.1rem;
    cursor: pointer;
  }

  .dropdowns-group {
    display: flex;
    flex-wrap: wrap;
    gap: 0.5rem;
  }

  .filter-select {
    background: #0c1220;
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #e2e8f0;
    padding: 0.45rem 0.65rem;
    border-radius: 4px;
    font-size: 0.85rem;
  }

  /* Alerts */
  .alert {
    padding: 0.6rem 1rem;
    border-radius: 6px;
    margin-bottom: 1rem;
    font-size: 0.85rem;
  }

  .error-alert {
    background: rgba(239, 68, 68, 0.15);
    border: 1px solid #ef4444;
    color: #fca5a5;
  }

  .status-alert {
    background: rgba(16, 185, 129, 0.12);
    border: 1px solid rgba(16, 185, 129, 0.3);
    color: #6ee7b7;
  }

  /* Pagination Bar */
  .pagination-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0;
    font-size: 0.8rem;
    color: #94a3b8;
    margin-bottom: 0.8rem;
  }

  .pager-btns {
    display: flex;
    align-items: center;
    gap: 0.3rem;
  }

  .page-nav-btn {
    background: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
  }

  .page-nav-btn:disabled {
    opacity: 0.4;
    cursor: not-allowed;
  }

  .current-page-badge {
    padding: 0.25rem 0.5rem;
    font-weight: 600;
    color: #fff;
  }

  /* Card Grid (Vertical Card Proportions) */
  .card-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 1rem;
  }

  .card-tile {
    background: #151d30;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: transform 0.15s ease, border-color 0.15s ease;
  }

  .card-tile:hover {
    transform: translateY(-2px);
    border-color: rgba(255, 255, 255, 0.22);
  }

  .card-tile.card-reviewed {
    border-color: rgba(16, 185, 129, 0.4);
    box-shadow: 0 0 10px rgba(16, 185, 129, 0.12);
  }

  .card-img-container {
    position: relative;
    width: 100%;
    aspect-ratio: 2.5 / 3.5;
    background: #0a0e18;
    display: flex;
    align-items: center;
    justify-content: center;
    cursor: pointer;
    overflow: hidden;
  }

  .card-img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }

  .card-img-placeholder {
    font-size: 2.5rem;
    color: #334155;
  }

  /* 4-Edge Directional Border Visual Indicator on Tile */
  .tile-edge-frame {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    pointer-events: none;
  }

  .tile-edge {
    position: absolute;
    background: #e2e8f0;
    box-shadow: 0 0 4px rgba(255, 255, 255, 0.4);
  }

  .tile-edge.edge-n {
    top: 0;
    left: 15%;
    right: 15%;
    height: 4px;
    border-radius: 0 0 2px 2px;
  }

  .tile-edge.edge-s {
    bottom: 0;
    left: 15%;
    right: 15%;
    height: 4px;
    border-radius: 2px 2px 0 0;
  }

  .tile-edge.edge-w {
    top: 15%;
    bottom: 15%;
    left: 0;
    width: 4px;
    border-radius: 0 2px 2px 0;
  }

  .tile-edge.edge-e {
    top: 15%;
    bottom: 15%;
    right: 0;
    width: 4px;
    border-radius: 2px 0 0 2px;
  }

  .tile-edge.edge-dark {
    background: #15803d;
    box-shadow: 0 0 4px rgba(34, 197, 94, 0.6);
  }

  .tile-edge.edge-black {
    background: #000000;
    box-shadow: 0 0 4px rgba(0, 0, 0, 0.8);
  }

  /* Badges */
  .badge {
    position: absolute;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.15rem 0.35rem;
    border-radius: 3px;
    text-transform: uppercase;
    letter-spacing: 0.04em;
  }

  .type-badge {
    top: 0.4rem;
    right: 0.4rem;
    background: #1e293b;
    color: #cbd5e1;
  }

  .type-terrain { background: #064e3b; color: #a7f3d0; border: 1px solid #059669; }
  .type-action { background: #7f1d1d; color: #fecaca; border: 1px solid #dc2626; }
  .type-fsa { background: #0369a1; color: #e0f2fe; border: 1px solid #0284c7; }
  .type-staging_area { background: #854d0e; color: #fef08a; border: 1px solid #eab308; }
  .type-utility { background: #581c87; color: #f3e8ff; border: 1px solid #9333ea; }

  .exp-badge {
    top: 0.4rem;
    left: 0.4rem;
    background: rgba(15, 23, 42, 0.85);
    color: #94a3b8;
    border: 1px solid rgba(255, 255, 255, 0.1);
  }

  .tile-body {
    padding: 0.7rem;
    display: flex;
    flex-direction: column;
    flex: 1;
    gap: 0.3rem;
  }

  .tile-title {
    font-weight: 700;
    font-size: 0.85rem;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tile-deck {
    font-size: 0.72rem;
    color: #38bdf8;
    font-weight: 600;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .tile-id {
    font-size: 0.68rem;
    font-family: monospace;
    color: #64748b;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .details-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.25rem;
    margin: 0.2rem 0;
  }

  .tag-pill {
    font-size: 0.68rem;
    font-weight: 600;
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
    background: #0f172a;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .veh-pill { font-weight: 700; }
  .veh-prohibited {
    background: rgba(239, 68, 68, 0.2);
    color: #f87171;
    border-color: rgba(239, 68, 68, 0.4);
  }
  .veh-allowed {
    background: rgba(34, 197, 94, 0.2);
    color: #4ade80;
    border-color: rgba(34, 197, 94, 0.4);
  }
  .cap-pill { color: #38bdf8; border-color: rgba(56, 189, 248, 0.3); }
  .draw-pill { color: #f59e0b; border-color: rgba(245, 158, 11, 0.3); }
  .move-pill { color: #a78bfa; border-color: rgba(167, 139, 250, 0.3); }

  .cov-pill { color: #34d399; border-color: rgba(52, 211, 153, 0.3); }
  .elev-pill { color: #60a5fa; border-color: rgba(96, 165, 250, 0.3); }
  .cat-pill { color: #facc15; border-color: rgba(250, 204, 21, 0.3); }
  .action-pill { color: #f87171; border-color: rgba(248, 113, 113, 0.3); }
  .cmd-pill { color: #c084fc; border-color: rgba(192, 132, 252, 0.3); }
  .purpose-pill { color: #94a3b8; }

  .tile-actions {
    display: flex;
    gap: 0.35rem;
    margin-top: auto;
    padding-top: 0.4rem;
  }

  .action-btn-sm {
    flex: 1;
    font-size: 0.72rem;
    font-weight: 600;
    padding: 0.3rem 0.4rem;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: #1e293b;
    color: #e2e8f0;
    cursor: pointer;
    transition: all 0.12s ease;
  }

  .action-btn-sm:hover { background: #334155; }

  .action-btn-sm.btn-validated {
    background: #064e3b;
    border-color: #059669;
    color: #6ee7b7;
  }

  .edit-btn { flex: 0.8; background: transparent; }

  /* Dense Table View */
  .table-container {
    overflow-x: auto;
    background: #151d30;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .cards-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.82rem;
    text-align: left;
  }

  .cards-table th {
    background: #0f1423;
    padding: 0.55rem 0.7rem;
    color: #94a3b8;
    font-weight: 600;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .cards-table td {
    padding: 0.45rem 0.7rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .cards-table tr:hover { background: #1a243d; }

  .table-card-thumb {
    width: 32px;
    height: 44px;
    object-fit: cover;
    border-radius: 3px;
    border: 1px solid #334155;
    cursor: pointer;
  }

  .table-id { font-weight: 700; color: #fff; cursor: pointer; }
  .table-filename { font-size: 0.68rem; color: #64748b; font-family: monospace; }
  .status-badge { font-size: 0.72rem; color: #94a3b8; }
  .status-reviewed { color: #34d399; font-weight: 700; }
  .row-actions { display: flex; gap: 0.25rem; }

  /* Widescreen Centered Modal Dialog */
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.82);
    backdrop-filter: blur(4px);
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 1rem;
    z-index: 1000;
  }

  .inspector-dialog {
    width: min(1380px, 96vw);
    height: min(94vh, 840px);
    max-height: 94vh;
    background: #121829;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.85);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .dialog-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1.25rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: #0d1220;
    flex-shrink: 0;
  }

  .dialog-title-group {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .dialog-title-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .dialog-title-group h2 {
    margin: 0;
    font-size: 1.15rem;
    color: #fff;
  }

  .dialog-filename {
    font-size: 0.75rem;
    font-family: monospace;
    color: #64748b;
  }

  .status-indicator-badge {
    font-size: 0.7rem;
    padding: 0.15rem 0.4rem;
    border-radius: 3px;
    font-weight: 600;
  }

  .status-indicator-badge.in-final {
    background: rgba(16, 185, 129, 0.2);
    color: #6ee7b7;
    border: 1px solid rgba(16, 185, 129, 0.4);
  }

  .status-indicator-badge.not-in-final {
    background: #1e293b;
    color: #94a3b8;
  }

  .dialog-header-actions {
    display: flex;
    align-items: center;
    gap: 0.5rem;
  }

  .nav-arrow-btn {
    background: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #e2e8f0;
    padding: 0.35rem 0.7rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.8rem;
  }

  .close-btn {
    background: transparent;
    border: none;
    color: #94a3b8;
    font-size: 1.5rem;
    cursor: pointer;
    line-height: 1;
    padding: 0.2rem 0.5rem;
  }

  .dialog-body {
    flex: 1;
    overflow-y: auto;
    overflow-x: hidden;
    padding: 0.85rem 1.25rem;
    display: grid;
    grid-template-columns: 280px minmax(0, 1fr);
    gap: 1.25rem;
  }

  .preview-col {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.65rem;
    position: sticky;
    top: 0;
    align-self: flex-start;
  }

  .card-preview-frame {
    position: relative;
    width: calc(180px * var(--zoom));
    height: auto;
    aspect-ratio: var(--card-ratio, 0.714);
    max-height: 520px;
    background: #080c14;
    border: 2px solid #334155;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
    overflow: hidden;
  }

  .preview-card-img {
    width: 100%;
    height: 100%;
    object-fit: contain;
    display: block;
  }

  /* Modal Preview Border Overlays */
  .modal-border-frame {
    position: absolute;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    pointer-events: none;
  }

  .modal-edge {
    position: absolute;
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.1rem 0.35rem;
    background: #e2e8f0;
    color: #0f172a;
    border-radius: 2px;
    box-shadow: 0 0 8px rgba(255, 255, 255, 0.4);
    white-space: nowrap;
  }

  .modal-edge.edge-n {
    top: 6px;
    left: 50%;
    transform: translateX(-50%);
  }

  .modal-edge.edge-s {
    bottom: 6px;
    left: 50%;
    transform: translateX(-50%);
  }

  .modal-edge.edge-w {
    left: 6px;
    top: 50%;
    transform: translateY(-50%);
  }

  .modal-edge.edge-e {
    right: 6px;
    top: 50%;
    transform: translateY(-50%);
  }

  .modal-edge.edge-dark {
    background: #15803d;
    color: #f0fdf4;
    box-shadow: 0 0 8px rgba(34, 197, 94, 0.6);
  }

  .modal-edge.edge-black {
    background: #000000;
    color: #f87171;
    border: 1px solid #ef4444;
    box-shadow: 0 0 8px rgba(0, 0, 0, 0.8);
  }

  .modal-edge.highlighted {
    transform: scale(1.15) !important;
    border: 2px solid #38bdf8 !important;
    box-shadow: 0 0 12px #38bdf8 !important;
    z-index: 12;
  }

  /* Interactive Spatial Reticles on Card Preview */
  .card-hotspot {
    position: absolute;
    border: 1px dashed rgba(255, 255, 255, 0.22);
    background: rgba(15, 23, 42, 0.28);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    pointer-events: none;
    border-radius: 4px;
    z-index: 5;
  }

  .hotspot-badge {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
    background: rgba(0, 0, 0, 0.88);
    color: #e2e8f0;
    white-space: nowrap;
    text-shadow: 0 1px 2px #000;
    opacity: 0.88;
    transform: scale(1);
    transition: opacity 0.18s ease, transform 0.18s ease;
    border: 1px solid rgba(255, 255, 255, 0.15);
  }

  .card-hotspot.highlighted .hotspot-badge {
    opacity: 0;
    transform: scale(0.85);
  }

  /* Hotspot Coordinates on Cards */
  .hotspot-tl-cover {
    top: 4%;
    left: 4%;
    width: 29%;
    height: 22%;
    border-color: rgba(52, 211, 153, 0.45);
    border-radius: 50%;
  }

  .hotspot-tc-name {
    top: 5%;
    left: 31%;
    width: 48%;
    height: 22%;
    border-color: rgba(56, 189, 248, 0.45);
  }

  .hotspot-tr-cardno {
    top: 4%;
    right: 4%;
    width: 20%;
    height: 18%;
    border-color: rgba(192, 132, 252, 0.45);
  }

  .hotspot-tr-elevation {
    top: 10%;
    right: 22%;
    width: 18%;
    height: 13%;
    border-color: rgba(251, 191, 36, 0.55);
  }

  .hotspot-bl-capacity {
    bottom: 5%;
    left: 5%;
    width: 28%;
    height: 16%;
    border-color: rgba(56, 189, 248, 0.45);
  }

  .hotspot-bc-draw {
    bottom: 4%;
    left: 38%;
    width: 25%;
    height: 18%;
    border-color: rgba(245, 158, 11, 0.45);
  }

  .hotspot-br-move {
    bottom: 5%;
    right: 5%;
    width: 28%;
    height: 16%;
    border-color: rgba(167, 139, 250, 0.45);
  }

  .card-hotspot.highlighted {
    border-style: solid;
    border-width: 2.5px;
    background: transparent;
    z-index: 10;
  }

  .card-hotspot.hotspot-tl-cover.highlighted {
    border-color: #34d399;
    box-shadow: inset 0 0 10px rgba(52, 211, 153, 0.2), 0 0 16px rgba(52, 211, 153, 0.7);
  }

  .card-hotspot.hotspot-tc-name.highlighted {
    border-color: #38bdf8;
    box-shadow: inset 0 0 10px rgba(56, 189, 248, 0.2), 0 0 16px rgba(56, 189, 248, 0.7);
  }

  .card-hotspot.hotspot-tr-cardno.highlighted {
    border-color: #c084fc;
    box-shadow: inset 0 0 10px rgba(192, 132, 252, 0.2), 0 0 16px rgba(192, 132, 252, 0.7);
  }

  .card-hotspot.hotspot-tr-elevation.highlighted {
    border-color: #fbbf24;
    box-shadow: inset 0 0 10px rgba(251, 191, 36, 0.2), 0 0 16px rgba(251, 191, 36, 0.7);
  }

  .card-hotspot.hotspot-bl-capacity.highlighted {
    border-color: #38bdf8;
    box-shadow: inset 0 0 10px rgba(56, 189, 248, 0.2), 0 0 16px rgba(56, 189, 248, 0.7);
  }

  .card-hotspot.hotspot-bc-draw.highlighted {
    border-color: #f59e0b;
    box-shadow: inset 0 0 10px rgba(245, 158, 11, 0.2), 0 0 16px rgba(245, 158, 11, 0.7);
  }

  .card-hotspot.hotspot-br-move.highlighted {
    border-color: #a78bfa;
    box-shadow: inset 0 0 10px rgba(167, 139, 250, 0.2), 0 0 16px rgba(167, 139, 250, 0.7);
  }

  /* Action Card Hotspots */
  .hotspot-act-cmd {
    top: 3%;
    left: 4%;
    width: 32%;
    height: 18%;
    border-color: rgba(56, 189, 248, 0.45);
  }

  .hotspot-act-init {
    top: 20%;
    left: 18%;
    width: 20%;
    height: 12%;
    border-color: rgba(245, 158, 11, 0.45);
  }

  .hotspot-act-num {
    top: 3%;
    right: 4%;
    width: 22%;
    height: 12%;
    border-color: rgba(192, 132, 252, 0.45);
  }

  .hotspot-act-attempt {
    top: 4%;
    left: 42%;
    width: 48%;
    height: 15%;
    border-color: rgba(52, 211, 153, 0.45);
  }

  .hotspot-act-icons {
    top: 20%;
    left: 40%;
    width: 55%;
    height: 50%;
    border-color: rgba(56, 189, 248, 0.45);
  }

  .hotspot-act-at {
    bottom: 27%;
    right: 5%;
    width: 38%;
    height: 14%;
    border-color: rgba(239, 68, 68, 0.45);
  }

  .hotspot-act-hit {
    bottom: 12%;
    left: 36%;
    width: 58%;
    height: 14%;
    border-color: rgba(245, 158, 11, 0.45);
  }

  .card-hotspot.hotspot-act-cmd.highlighted {
    border-color: #38bdf8;
    box-shadow: inset 0 0 10px rgba(56, 189, 248, 0.2), 0 0 16px rgba(56, 189, 248, 0.7);
  }

  .card-hotspot.hotspot-act-init.highlighted {
    border-color: #f59e0b;
    box-shadow: inset 0 0 10px rgba(245, 158, 11, 0.2), 0 0 16px rgba(245, 158, 11, 0.7);
  }

  .card-hotspot.hotspot-act-num.highlighted {
    border-color: #c084fc;
    box-shadow: inset 0 0 10px rgba(192, 132, 252, 0.2), 0 0 16px rgba(192, 132, 252, 0.7);
  }

  .card-hotspot.hotspot-act-attempt.highlighted {
    border-color: #34d399;
    box-shadow: inset 0 0 10px rgba(52, 211, 153, 0.2), 0 0 16px rgba(52, 211, 153, 0.7);
  }

  .card-hotspot.hotspot-act-icons.highlighted {
    border-color: #38bdf8;
    box-shadow: inset 0 0 10px rgba(56, 189, 248, 0.2), 0 0 16px rgba(56, 189, 248, 0.7);
  }

  .card-hotspot.hotspot-act-at.highlighted {
    border-color: #ef4444;
    box-shadow: inset 0 0 10px rgba(239, 68, 68, 0.2), 0 0 16px rgba(239, 68, 68, 0.7);
  }

  .card-hotspot.hotspot-act-hit.highlighted {
    border-color: #f59e0b;
    box-shadow: inset 0 0 10px rgba(245, 158, 11, 0.2), 0 0 16px rgba(245, 158, 11, 0.7);
  }

  .hotspot-act-rn {
    bottom: 2%;
    left: 4%;
    width: 92%;
    height: 9%;
    border-color: rgba(56, 189, 248, 0.45);
  }

  .card-hotspot.hotspot-act-rn.highlighted {
    border-color: #38bdf8;
    box-shadow: inset 0 0 10px rgba(56, 189, 248, 0.2), 0 0 16px rgba(56, 189, 248, 0.7);
  }

  .action-icons-box {
    margin-top: 0.85rem;
    padding: 0.75rem 0.85rem;
    background: #0b111e;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 0.6rem;
  }

  .action-icon-flags-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 0.5rem;
  }

  .icon-toggle-label {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    padding: 0.45rem 0.6rem;
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 5px;
    cursor: pointer;
    user-select: none;
    transition: all 0.15s ease;
    position: relative;
    padding-left: 2rem;
  }

  .icon-toggle-label input[type='checkbox'] {
    position: absolute;
    left: 0.6rem;
    top: 0.6rem;
    cursor: pointer;
  }

  .icon-toggle-label:hover {
    border-color: #475569;
    background: #1e293b;
  }

  .icon-toggle-label.is-set {
    border-color: #38bdf8;
    background: rgba(56, 189, 248, 0.08);
  }

  .icon-flag-name {
    font-size: 0.78rem;
    font-weight: 700;
    color: #e2e8f0;
  }

  .icon-toggle-label.is-set .icon-flag-name {
    color: #38bdf8;
  }

  .icon-flag-desc {
    font-size: 0.68rem;
    color: #94a3b8;
  }

  .rn-matrix-box {
    margin-top: 0.85rem;
    padding: 0.65rem 0.8rem;
    background: #0b111e;
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 6px;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
  }

  .rn-header-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
  }

  .rn-summary-badge {
    font-size: 0.72rem;
    font-family: monospace;
    background: #1e293b;
    color: #38bdf8;
    padding: 0.15rem 0.45rem;
    border-radius: 4px;
    border: 1px solid rgba(56, 189, 248, 0.3);
  }

  .rn-table {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
    overflow-x: auto;
  }

  .rn-row {
    display: grid;
    grid-template-columns: 85px repeat(11, minmax(26px, 1fr));
    gap: 0.25rem;
    align-items: center;
  }

  .rn-label-col {
    font-size: 0.7rem;
    font-weight: 600;
    color: #94a3b8;
  }

  .rn-col-num {
    font-size: 0.72rem;
    font-weight: 700;
    text-align: center;
    color: #cbd5e1;
    background: #1e293b;
    padding: 0.15rem 0;
    border-radius: 3px;
  }

  .rn-input {
    width: 100%;
    padding: 0.2rem 0;
    text-align: center;
    font-size: 0.78rem;
    font-weight: 700;
    font-family: monospace;
    background: #0f172a;
    border: 1px solid #334155;
    border-radius: 3px;
    color: #38bdf8;
  }

  .rn-input:focus {
    outline: none;
    border-color: #38bdf8;
    background: #1e293b;
  }

  .attempt-pill {
    background: rgba(52, 211, 153, 0.15);
    color: #6ee7b7;
    border: 1px solid rgba(52, 211, 153, 0.35);
  }

  .init-pill {
    background: rgba(245, 158, 11, 0.15);
    color: #fde68a;
    border: 1px solid rgba(245, 158, 11, 0.35);
  }

  .at-pill {
    background: rgba(239, 68, 68, 0.15);
    color: #fca5a5;
    border: 1px solid rgba(239, 68, 68, 0.35);
  }

  .icon-pill {
    background: rgba(148, 163, 184, 0.12);
    color: #cbd5e1;
    border: 1px solid rgba(148, 163, 184, 0.25);
  }

  .preview-placeholder {
    color: #64748b;
    font-size: 0.85rem;
    text-align: center;
    padding: 1rem;
  }

  .zoom-controls {
    display: flex;
    gap: 0.3rem;
    align-items: center;
    font-size: 0.75rem;
    color: #94a3b8;
  }

  .field-crop-panel {
    width: min(100%, 300px);
    padding: 0.55rem;
    border: 1px solid rgba(148, 163, 184, 0.25);
    border-radius: 8px;
    background: rgba(15, 23, 42, 0.8);
  }

  .field-crop-title {
    display: block;
    margin-bottom: 0.4rem;
    color: #94a3b8;
    font-size: 0.68rem;
    font-weight: 700;
    text-transform: uppercase;
  }

  .field-crop-window {
    position: relative;
    width: 100%;
    overflow: hidden;
    border: 1px solid rgba(56, 189, 248, 0.5);
    border-radius: 4px;
    background: #e2e8f0;
  }

  .field-crop-window img {
    position: absolute;
    max-width: none;
    height: auto;
  }

  .zoom-btn {
    background: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.1);
    color: #cbd5e1;
    padding: 0.2rem 0.5rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.75rem;
  }

  .zoom-btn.active {
    background: #3b82f6;
    color: #fff;
  }

  .card-info-box {
    width: 100%;
    background: #0b0f1a;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    padding: 0.5rem 0.7rem;
    font-size: 0.75rem;
  }

  .card-info-box h4 {
    margin: 0 0 0.25rem;
    color: #94a3b8;
  }

  .notes-text {
    font-family: monospace;
    color: #cbd5e1;
    margin: 0;
    word-break: break-all;
  }

  /* Form Fields */
  .fields-col {
    display: flex;
    flex-direction: column;
    gap: 0.65rem;
    min-width: 0;
  }

  .field-section {
    background: #0f1629;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    padding: 0.6rem 0.85rem;
    transition: all 0.2s ease;
  }

  .field-section.section-active {
    border-color: #3b82f6;
    background: #111a33;
    box-shadow: 0 0 12px rgba(59, 130, 246, 0.25);
  }

  .section-title-bar {
    margin-bottom: 0.45rem;
    padding-bottom: 0.25rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.06);
  }

  .section-badge {
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.05em;
  }

  .badge-top { color: #38bdf8; }
  .badge-terrain { color: #34d399; }
  .badge-action { color: #f87171; }
  .badge-edges { color: #f59e0b; }

  .form-grid-3 {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.6rem;
  }

  .form-grid-4 {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.6rem;
  }

  .full-width {
    grid-column: 1 / -1;
  }

  .form-field {
    display: flex;
    flex-direction: column;
    gap: 0.15rem;
    font-size: 0.78rem;
    min-width: 0;
  }

  .field-title {
    color: #94a3b8;
    font-weight: 500;
  }

  .provenance-chip {
    display: inline-flex;
    align-items: center;
    margin-left: 0.3rem;
    padding: 0.08rem 0.32rem;
    border: 1px solid rgba(148, 163, 184, 0.38);
    border-radius: 999px;
    color: #cbd5e1;
    font-size: 0.62rem;
    font-weight: 700;
    letter-spacing: 0.02em;
    text-transform: uppercase;
    vertical-align: middle;
  }

  .provenance-chip.verified {
    border-color: rgba(52, 211, 153, 0.55);
    color: #6ee7b7;
  }

  .form-input,
  .form-select {
    background: #0b0f1a;
    border: 1px solid rgba(255, 255, 255, 0.12);
    color: #fff;
    padding: 0.32rem 0.5rem;
    border-radius: 4px;
    font-size: 0.8rem;
    width: 100%;
    box-sizing: border-box;
  }

  .form-input:focus,
  .form-select:focus {
    outline: none;
    border-color: #3b82f6;
  }

  .input-with-dropdown {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .custom-input {
    border-color: #3b82f6 !important;
  }

  .borders-bar {
    margin-top: 0.6rem;
    padding-top: 0.45rem;
    border-top: 1px dashed rgba(255, 255, 255, 0.08);
  }

  .sub-bar-title {
    font-size: 0.72rem;
    font-weight: 600;
    color: #94a3b8;
    display: block;
    margin-bottom: 0.3rem;
  }

  .borders-grid {
    display: grid;
    grid-template-columns: repeat(4, minmax(0, 1fr));
    gap: 0.5rem;
  }

  /* Fixed Dialog Footer */
  .dialog-footer {
    padding: 0.75rem 1.25rem;
    background: #0d1220;
    border-top: 1px solid rgba(255, 255, 255, 0.08);
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    flex-shrink: 0;
  }

  .reviewed-checkbox-label {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    font-size: 0.85rem;
    font-weight: 600;
    color: #6ee7b7;
    cursor: pointer;
  }

  .btn-cluster {
    display: flex;
    gap: 0.5rem;
  }

  .save-btn {
    background: #1e293b;
    border: 1px solid rgba(255, 255, 255, 0.15);
    color: #fff;
    padding: 0.45rem 1rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 600;
  }

  .save-btn:hover { background: #334155; }

  .save-next-btn {
    background: #2563eb;
    border: 1px solid #3b82f6;
    color: #fff;
    padding: 0.45rem 1rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 600;
  }

  .save-next-btn:hover { background: #1d4ed8; }

  .validate-btn {
    background: #0f2e23;
    border: 1px solid #059669;
    color: #6ee7b7;
    padding: 0.45rem 1.15rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 700;
    transition: all 0.12s ease;
  }

  .validate-btn:hover { background: #064e3b; color: #a7f3d0; }

  .validate-btn.btn-validated {
    background: #064e3b;
    border-color: #10b981;
    color: #a7f3d0;
    box-shadow: 0 0 10px rgba(16, 185, 129, 0.25);
  }

  .save-btn:disabled,
  .save-next-btn:disabled,
  .validate-btn:disabled {
    opacity: 0.5;
    cursor: not-allowed;
  }

  .loading-state,
  .empty-state {
    padding: 4rem 2rem;
    text-align: center;
    color: #94a3b8;
  }

  .spinner {
    width: 36px;
    height: 36px;
    border: 3px solid rgba(255, 255, 255, 0.1);
    border-top-color: #3b82f6;
    border-radius: 50%;
    animation: spin 0.8s linear infinite;
    margin: 0 auto 1rem;
  }

  @keyframes spin {
    to { transform: rotate(360deg); }
  }

  .action-btn {
    background: #3b82f6;
    color: #fff;
    border: none;
    padding: 0.5rem 1.25rem;
    border-radius: 4px;
    cursor: pointer;
    font-weight: 600;
  }
</style>
