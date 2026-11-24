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
  let selectedJsonName = 'counters.json';

  // Final filename derived dynamically from loaded filename
  $: finalJsonName = getFinalJsonName(selectedJsonName);
  $: isViewingFinalDirectly = Boolean(selectedJsonName?.endsWith('-final.json'));

  function getFinalJsonName(name) {
    if (!name) return '';
    const base = name.replace(/\.json$/i, '');
    return `${base}-final.json`;
  }

  // Helper to reliably get a unique identifier for each counter record (image filename is unique per counter)
  function getRecordKey(rec) {
    return rec?.image?.filename || rec?.id || '';
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
  let selectedCategory = 'all'; // all, unit, marker, asset
  let selectedSubtype = 'all';
  let selectedCountry = 'all';
  let filterIssue = 'all'; // all, issues_only, clean_only
  let filterReviewed = 'all'; // all, reviewed, unreviewed
  let filterSpecial = 'all'; // all, tripod, fire_team
  let viewMode = 'grid'; // grid | table

  // Pagination
  let pageSize = 60;
  let currentPage = 1;

  // Detail Modal / Inspector Drawer
  let activeIndex = null;
  let activeRecord = null;
  let zoomLevel = 3; // 2x, 3x, 4x for 75x75 preview
  let activeFieldHighlight = null; // 'header' | 'center' | 'vof' | 'special_vof' | 'range' | 'steps' | null

  // Known options for dropdowns with custom input fallback
  const KNOWN_SUBTYPES = [
    'squad',
    'weapons_team',
    'lat',
    'hq_plt',
    'hq_co',
    'co_1sgt',
    'co_xo',
    'runner',
    'fo_spotter',
    'casualty',
    'vehicle',
    'cover',
    'pin',
    'exposed',
    'ammo',
    'vof',
    'pdf',
    'potential_contact',
    'tactical_control',
    'current_activity',
    'visibility',
    'unaware',
    'unspotted',
    'fire_mission',
  ];

  const KNOWN_BASIC_VOFS = [
    { value: 'S', label: 'S (Small Arms)' },
    { value: 'A', label: 'A (Automatic Weapons)' },
    { value: 'H', label: 'H (Heavy Weapons)' },
    { value: 'A/S', label: 'A/S (Assault Rifle - Auto PB / Small Arms others)' },
    { value: 'G!', label: 'G! (Grenade Attack)' },
    { value: 'F!', label: 'F! (Flamethrower)' },
    { value: 'D!', label: 'D! (Demolition)' },
    { value: 'S!', label: 'S! (Sniper)' },
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
        if (availableJsonFiles.includes('counters.json')) {
          selectedJsonName = 'counters.json';
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
    selectedJsonName = availableJsonFiles.includes('counters.json')
      ? 'counters.json'
      : availableJsonFiles[0] || '';
    await loadRecords();
  }

  async function loadRecords() {
    if (!selectedGameId || !selectedJsonName) return;
    loading = true;
    loadError = '';
    statusMessage = '';
    try {
      // 1. Fetch main selected file
      const res = await getAssetReviewJson(selectedGameId, selectedJsonName);
      const loadedRecords = Array.isArray(res.records) ? res.records : [];

      // Store raw loaded copies
      rawLoadedMap = new Map();
      for (const r of loadedRecords) {
        const key = getRecordKey(r);
        if (key) {
          rawLoadedMap.set(key, JSON.parse(JSON.stringify(r)));
        }
      }

      // 2. Fetch the corresponding -final.json file (unless viewing final file directly)
      finalMap = new Map();
      if (!isViewingFinalDirectly && finalJsonName) {
        try {
          const finalRes = await getAssetReviewJson(selectedGameId, finalJsonName);
          const finalRecords = Array.isArray(finalRes.records) ? finalRes.records : [];
          for (const fr of finalRecords) {
            const fKey = getRecordKey(fr);
            if (fKey) {
              finalMap.set(fKey, JSON.parse(JSON.stringify(fr)));
            }
          }
        } catch (finalErr) {
          // If 404, file doesn't exist yet, which is completely expected before validating
          if (finalErr.status !== 404) {
            console.warn('Could not load final file:', finalErr);
          }
        }
      }

      // 3. Merge: If counter key is in finalMap, display final version with reviewed = true.
      // Otherwise, display raw version with reviewed = false.
      const merged = loadedRecords.map((rawRec) => {
        const key = getRecordKey(rawRec);
        if (key && finalMap.has(key)) {
          const finalRec = JSON.parse(JSON.stringify(finalMap.get(key)));
          finalRec.classification = finalRec.classification || {};
          finalRec.classification.reviewed = true;
          return finalRec;
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
        statusMessage = `Loaded ${loadedRecords.length} records. Found ${finalMap.size} pre-validated in ${finalJsonName}.`;
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

  // Issue / Invariant detection logic
  function getIssues(rec) {
    if (!rec) return [];
    const issues = [];
    const cat = rec.category;
    const sub = rec.subtype;
    const details = rec.unit_details;
    const marker = rec.marker_details;
    const vof = details?.vof_rating || rec.combat?.vof;
    const rng = details?.range_band;

    if (!cat || cat === 'unknown') issues.push('Unknown Category');
    if (!sub || sub === 'unknown') issues.push('Unknown Subtype');
    if (rec.country === 'Unknown') issues.push('Unknown Country');

    if (cat === 'unit') {
      if (sub === 'squad') {
        if (!vof) issues.push('Squad missing VOF');
        if (!rng) issues.push('Squad missing Range');
      } else if (sub === 'weapons_team') {
        if (!details?.weapon_type) issues.push('Weapons Team missing Weapon');
        if (!vof && sub !== 'casualty') issues.push('Missing VOF');
      } else if (sub === 'lat' && (details?.lat_subtype === 'Fire Team' || details?.lat_subtype === 'Assault Team')) {
        if (!vof) issues.push(`${details.lat_subtype} missing VOF`);
      }
    } else if (cat === 'marker') {
      if (sub === 'cover' && (vof || marker?.vof_level)) {
        issues.push('Cover marker has VOF');
      }
      if (sub === 'exposed' && marker?.cover_modifier !== -2) {
        issues.push('Exposed mod not -2');
      }
    }

    if (rec.image?.confidence != null && rec.image.confidence < 0.70) {
      issues.push(`Low confidence (${rec.image.confidence})`);
    }

    return issues;
  }

  function getImageUrl(rec) {
    if (!rec?.image?.filename) return '';
    return getAssetReviewImageUrl(selectedGameId, rec.image.filename);
  }

  // Unique lists for dropdowns
  $: countries = Array.from(new Set(records.map((r) => r.country).filter(Boolean))).sort();
  $: subtypes = Array.from(new Set(records.map((r) => r.subtype).filter(Boolean))).sort();

  // Summary counts
  $: totalCount = records.length;
  $: unitCount = records.filter((r) => r.category === 'unit').length;
  $: markerCount = records.filter((r) => r.category === 'marker').length;
  $: assetCount = records.filter((r) => r.category === 'asset').length;
  $: issueCount = records.filter((r) => getIssues(r).length > 0).length;
  $: tripodCount = records.filter((r) => r.unit_details?.mount_type === 'Tripod').length;
  $: fireTeamCount = records.filter((r) => r.unit_details?.lat_subtype === 'Fire Team' || (r.subtype === 'lat' && r.unit_details?.lat_subtype === 'Fire Team')).length;
  $: assaultTeamCount = records.filter((r) => r.unit_details?.lat_subtype === 'Assault Team' || (r.subtype === 'lat' && r.unit_details?.lat_subtype === 'Assault Team')).length;
  $: finalCount = isViewingFinalDirectly
    ? records.filter((r) => Boolean(r.classification?.reviewed)).length
    : finalMap.size;

  // Filtered records
  $: filteredRecords = records.filter((rec) => {
    if (selectedCategory !== 'all' && rec.category !== selectedCategory) return false;
    if (selectedSubtype !== 'all' && rec.subtype !== selectedSubtype) return false;
    if (selectedCountry !== 'all' && rec.country !== selectedCountry) return false;

    if (filterSpecial === 'tripod' && rec.unit_details?.mount_type !== 'Tripod') return false;
    if (filterSpecial === 'fire_team' && !(rec.unit_details?.lat_subtype === 'Fire Team' || (rec.subtype === 'lat' && rec.unit_details?.lat_subtype === 'Fire Team'))) return false;
    if (filterSpecial === 'assault_team' && !(rec.unit_details?.lat_subtype === 'Assault Team' || (rec.subtype === 'lat' && rec.unit_details?.lat_subtype === 'Assault Team'))) return false;

    const issues = getIssues(rec);
    if (filterIssue === 'issues_only' && issues.length === 0) return false;
    if (filterIssue === 'clean_only' && issues.length > 0) return false;

    const isRev = Boolean(rec.classification?.reviewed);
    if (filterReviewed === 'reviewed' && !isRev) return false;
    if (filterReviewed === 'unreviewed' && isRev) return false;

    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase().trim();
      const matchId = rec.id?.toLowerCase().includes(q);
      const matchFile = rec.image?.filename?.toLowerCase().includes(q);
      const matchSub = rec.subtype?.toLowerCase().includes(q);
      const matchCountry = rec.country?.toLowerCase().includes(q);
      const matchNotes = rec.classification?.notes?.toLowerCase().includes(q);
      const matchWeapon = rec.unit_details?.weapon_type?.toLowerCase().includes(q);
      const matchMount = rec.unit_details?.mount_type?.toLowerCase().includes(q);
      const matchLat = rec.unit_details?.lat_subtype?.toLowerCase().includes(q);
      const matchDiv = rec.unit_details?.division?.toLowerCase().includes(q);
      const matchSpecialVof = rec.unit_details?.special_vof?.toLowerCase().includes(q);
      if (!matchId && !matchFile && !matchSub && !matchCountry && !matchNotes && !matchWeapon && !matchMount && !matchLat && !matchDiv && !matchSpecialVof) {
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
        // ── Turning Validation ON ──
        // 1. Mark as reviewed
        rec.classification = rec.classification || {};
        rec.classification.reviewed = true;
        rec.classification.reviewed_at = new Date().toISOString();

        // 2. Add / Upsert into final file
        const recordToSave = JSON.parse(JSON.stringify(rec));
        await syncAssetReviewJsonRecord(selectedGameId, finalJsonName, 'upsert', recordToSave, targetSyncId);

        // 3. Update memory state
        finalMap.set(key, recordToSave);
        records[realIndex] = recordToSave;
        records = [...records];

        if (activeRecord && getRecordKey(activeRecord) === key) {
          activeRecord = JSON.parse(JSON.stringify(recordToSave));
        }

        statusMessage = `Validated and added "${targetSyncId}" to ${finalJsonName}`;
      } else {
        // ── Turning Validation OFF (Unvalidate) ──
        // 1. Delete from final file
        await syncAssetReviewJsonRecord(selectedGameId, finalJsonName, 'delete', null, targetSyncId);
        finalMap.delete(key);

        // 2. Revert to original loaded version from rawLoadedMap
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

        // If inspector is viewing this record, update activeRecord too
        if (activeRecord && getRecordKey(activeRecord) === key) {
          activeRecord = JSON.parse(JSON.stringify(reverted));
        }

        statusMessage = `Removed "${targetSyncId}" from ${finalJsonName}. Reverted to ${selectedJsonName} version.`;
      }
    } catch (err) {
      statusMessage = `Operation failed for ${targetSyncId}: ${err.message}`;
    } finally {
      savingId = null;
    }
  }

  // Inspector Drawer
  function openInspector(rec) {
    if (!rec) return;
    const realIdx = records.findIndex((r) => getRecordKey(r) === getRecordKey(rec));
    activeIndex = realIdx !== -1 ? realIdx : records.indexOf(rec);
    activeRecord = JSON.parse(JSON.stringify(rec));
    if (activeRecord) {
      activeRecord.classification = activeRecord.classification || {};
      // The drawer's unit fields bind to unit_details for every record, so it must exist.
      activeRecord.unit_details = activeRecord.unit_details || {};
      if (activeRecord.category === 'marker') {
        activeRecord.marker_details = activeRecord.marker_details || {};
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
    // Find where the active record sits in filteredRecords
    const currentInFiltered = filteredRecords.findIndex((r) => getRecordKey(r) === currentKey);

    let nextInFiltered = -1;
    if (currentInFiltered !== -1) {
      nextInFiltered = currentInFiltered + direction;
    } else {
      // If the current record dropped out of filteredRecords (e.g. after being validated while filtering Unreviewed),
      // advance to the record at the same relative position or previous position
      nextInFiltered = direction > 0 ? 0 : filteredRecords.length - 1;
    }

    if (nextInFiltered >= 0 && nextInFiltered < filteredRecords.length) {
      openInspector(filteredRecords[nextInFiltered]);
    } else if (filteredRecords.length > 0) {
      // Fallback: stay on the nearest available record
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

    // Determine target record to advance to BEFORE mutating and re-filtering
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
      // Non-unit records keep unit_details null when nothing was entered for them.
      if (updatedRec.category !== 'unit' && updatedRec.unit_details && Object.keys(updatedRec.unit_details).length === 0) {
        updatedRec.unit_details = null;
      }

      if (isVerified) {
        // Save / Upsert to final file
        await syncAssetReviewJsonRecord(selectedGameId, finalJsonName, 'upsert', updatedRec, targetSyncId);
        finalMap.set(key, updatedRec);
        statusMessage = `Validated and saved "${targetSyncId}" to ${finalJsonName}`;
      } else {
        // If unverified, ensure it's not in final file
        if (finalMap.has(key)) {
          await syncAssetReviewJsonRecord(selectedGameId, finalJsonName, 'delete', null, targetSyncId);
          finalMap.delete(key);
        }
        statusMessage = `Saved "${targetSyncId}" (unverified)`;
      }

      // Update in-memory records
      const targetIdx = records.findIndex((r) => getRecordKey(r) === key);
      const updateIdx = targetIdx !== -1 ? targetIdx : activeIndex;
      records[updateIdx] = updatedRec;
      records = [...records];

      // Also persist to loaded file at updateIdx
      await updateAssetReviewJsonRow(selectedGameId, selectedJsonName, updateIdx, updatedRec);

      if (advanceNext) {
        if (nextRecordToOpen && getRecordKey(nextRecordToOpen) !== key) {
          openInspector(nextRecordToOpen);
        } else {
          navInspector(1);
        }
      }
    } catch (err) {
      statusMessage = `Save failed: ${err.message}`;
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
      <a href="/card-validator" class="secondary-nav-btn">&#127183; Card Validator</a>
      <h1>Counter Batch Validator</h1>
      <span class="file-tag" title="Loaded source file">{selectedGameId}/{selectedJsonName}</span>
      {#if !isViewingFinalDirectly}
        <span class="final-file-tag" title="Target final file for validated counters">
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
      onclick={() => { selectedCategory = 'all'; filterIssue = 'all'; filterReviewed = 'all'; filterSpecial = 'all'; }}
      onkeydown={(e) => { if (e.key === 'Enter') { selectedCategory = 'all'; filterIssue = 'all'; filterReviewed = 'all'; filterSpecial = 'all'; } }}
    >
      <span class="stat-num">{totalCount}</span>
      <span class="stat-lbl">Total Tokens</span>
    </div>

    <div
      class="audit-stat category-unit"
      role="button"
      tabindex="0"
      class:active-chip={selectedCategory === 'unit'}
      onclick={() => (selectedCategory = selectedCategory === 'unit' ? 'all' : 'unit')}
      onkeydown={(e) => { if (e.key === 'Enter') selectedCategory = selectedCategory === 'unit' ? 'all' : 'unit'; }}
    >
      <span class="stat-num">{unitCount}</span>
      <span class="stat-lbl">Units</span>
    </div>

    <div
      class="audit-stat category-marker"
      role="button"
      tabindex="0"
      class:active-chip={selectedCategory === 'marker'}
      onclick={() => (selectedCategory = selectedCategory === 'marker' ? 'all' : 'marker')}
      onkeydown={(e) => { if (e.key === 'Enter') selectedCategory = selectedCategory === 'marker' ? 'all' : 'marker'; }}
    >
      <span class="stat-num">{markerCount}</span>
      <span class="stat-lbl">Markers</span>
    </div>

    <div
      class="audit-stat category-asset"
      role="button"
      tabindex="0"
      class:active-chip={selectedCategory === 'asset'}
      onclick={() => (selectedCategory = selectedCategory === 'asset' ? 'all' : 'asset')}
      onkeydown={(e) => { if (e.key === 'Enter') selectedCategory = selectedCategory === 'asset' ? 'all' : 'asset'; }}
    >
      <span class="stat-num">{assetCount}</span>
      <span class="stat-lbl">Assets</span>
    </div>

    <div
      class="audit-stat stat-tripod"
      role="button"
      tabindex="0"
      class:active-chip={filterSpecial === 'tripod'}
      onclick={() => (filterSpecial = filterSpecial === 'tripod' ? 'all' : 'tripod')}
      onkeydown={(e) => { if (e.key === 'Enter') filterSpecial = filterSpecial === 'tripod' ? 'all' : 'tripod'; }}
      title="Filter to tripod-mounted weapon teams (yellow arrow)"
    >
      <span class="stat-num">&#10140; {tripodCount}</span>
      <span class="stat-lbl">Tripod Guns</span>
    </div>

    <div
      class="audit-stat stat-fireteam"
      role="button"
      tabindex="0"
      class:active-chip={filterSpecial === 'fire_team'}
      onclick={() => (filterSpecial = filterSpecial === 'fire_team' ? 'all' : 'fire_team')}
      onkeydown={(e) => { if (e.key === 'Enter') filterSpecial = filterSpecial === 'fire_team' ? 'all' : 'fire_team'; }}
      title="Filter to Fire Teams"
    >
      <span class="stat-num">&#128293; {fireTeamCount}</span>
      <span class="stat-lbl">Fire Teams</span>
    </div>

    <div
      class="audit-stat stat-issues"
      role="button"
      tabindex="0"
      class:active-chip={filterIssue === 'issues_only'}
      onclick={() => (filterIssue = filterIssue === 'issues_only' ? 'all' : 'issues_only')}
      onkeydown={(e) => { if (e.key === 'Enter') filterIssue = filterIssue === 'issues_only' ? 'all' : 'issues_only'; }}
    >
      <span class="stat-num">&#9888; {issueCount}</span>
      <span class="stat-lbl">Flagged Issues</span>
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
        placeholder="Filter by ID, filename, or OCR text..."
        class="search-input"
      />
      {#if searchQuery}
        <button class="clear-search" onclick={() => (searchQuery = '')}>&times;</button>
      {/if}
    </div>

    <div class="dropdowns-group">
      <select bind:value={selectedCountry} class="filter-select">
        <option value="all">All Countries ({countries.length})</option>
        {#each countries as c}
          <option value={c}>{c}</option>
        {/each}
      </select>

      <select bind:value={selectedSubtype} class="filter-select">
        <option value="all">All Subtypes ({subtypes.length})</option>
        {#each subtypes as s}
          <option value={s}>{s}</option>
        {/each}
      </select>

      <select bind:value={filterSpecial} class="filter-select">
        <option value="all">All Traits</option>
        <option value="tripod">&#10140; Tripod Guns ({tripodCount})</option>
        <option value="fire_team">&#128293; Fire Teams ({fireTeamCount})</option>
        <option value="assault_team">&#9876; Assault Teams ({assaultTeamCount})</option>
      </select>

      <select bind:value={filterIssue} class="filter-select">
        <option value="all">All Invariants</option>
        <option value="issues_only">&#9888; Has Issues Only</option>
        <option value="clean_only">✓ Clean Records Only</option>
      </select>

      <select bind:value={filterReviewed} class="filter-select">
        <option value="all">All Review Statuses</option>
        <option value="reviewed">✓ In Final File ({finalCount})</option>
        <option value="unreviewed">○ Not in Final File ({totalCount - finalCount})</option>
      </select>

      <select bind:value={pageSize} onchange={() => (currentPage = 1)} class="filter-select page-size-select">
        <option value={30}>30 / page</option>
        <option value={60}>60 / page</option>
        <option value={120}>120 / page</option>
        <option value={240}>240 / page</option>
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
      <h2>No counters match the current filters</h2>
      <p>Try clearing your search query or setting dropdowns back to "All".</p>
      <button
        class="action-btn"
        onclick={() => {
          searchQuery = '';
          selectedCategory = 'all';
          selectedSubtype = 'all';
          selectedCountry = 'all';
          filterIssue = 'all';
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
      <div class="counter-grid">
        {#each pageRecords as rec, i (rec.image?.filename || `${rec.id || 'item'}-${i}`)}
          {@const filename = rec.image?.filename || ''}
          {@const id = rec.id || filename}
          {@const isUnit = rec.category === 'unit'}
          {@const isFireTeam = rec.unit_details?.lat_subtype === 'Fire Team' || (rec.subtype === 'lat' && rec.unit_details?.lat_subtype === 'Fire Team')}
          {@const isAssaultTeam = rec.unit_details?.lat_subtype === 'Assault Team' || (rec.subtype === 'lat' && rec.unit_details?.lat_subtype === 'Assault Team')}
          {@const isTripod = rec.unit_details?.mount_type === 'Tripod'}
          {@const vof = rec.unit_details?.vof_rating || rec.combat?.vof || ''}
          {@const specialVof = rec.unit_details?.special_vof || ''}
          {@const range = rec.unit_details?.range_band || ''}
          {@const steps = rec.unit_details?.steps_total ?? rec.unit_details?.steps_remaining}
          {@const squad = rec.unit_details?.squad_number}
          {@const platoon = rec.unit_details?.platoon}
          {@const division = rec.unit_details?.division}
          {@const issues = getIssues(rec)}
          {@const hasIssues = issues.length > 0}
          {@const isReviewed = Boolean(rec.classification?.reviewed)}
          {@const imgUrl = getImageUrl(rec)}

          <div
            class="counter-card"
            class:card-issue={hasIssues}
            class:card-reviewed={isReviewed}
          >
            <!-- Card Image & Overlay -->
            <div
              class="card-img-wrapper"
              role="button"
              tabindex="0"
              onclick={() => openInspector(rec)}
              onkeydown={(e) => { if (e.key === 'Enter') openInspector(rec); }}
            >
              {#if imgUrl}
                <img
                  src={imgUrl}
                  alt={filename}
                  class="token-img"
                  loading="lazy"
                  onerror={(e) => { e.currentTarget.style.display = 'none'; }}
                />
              {:else}
                <div class="img-missing">&#9638;</div>
              {/if}

              <!-- Country Tag -->
              <span class="badge country-badge country-{rec.country?.toLowerCase()}">
                {rec.country}
              </span>

              <!-- Category Badge -->
              {#if isFireTeam}
                <span class="badge category-badge badge-fireteam">FIRE TEAM</span>
              {:else if isAssaultTeam}
                <span class="badge category-badge badge-assaultteam">ASSAULT TM</span>
              {:else if isTripod}
                <span class="badge category-badge badge-tripod">TRIPOD</span>
              {:else}
                <span class="badge category-badge category-{rec.category}">
                  {rec.subtype || rec.category}
                </span>
              {/if}
            </div>

            <!-- Card Body / Meta -->
            <div class="card-body">
              <div class="card-id" title={rec.id}>{rec.id || filename}</div>
              <div class="card-filename" title={filename}>{filename}</div>

              <!-- Stats Pill Grid -->
              <div class="stats-row">
                {#if isUnit}
                  {#if squad || platoon}
                    <span class="stat-tag org-tag" title="{squad ? `Squad: ${squad}` : ''} {platoon ? `Platoon: ${platoon}` : ''}">
                      {#if squad && platoon}
                        {squad}/{platoon} PLT
                      {:else if platoon}
                        {platoon} PLT
                      {:else}
                        SQD {squad}
                      {/if}
                    </span>
                  {/if}
                  <span class="stat-tag vof-tag" class:tag-missing={!vof && rec.subtype === 'squad'}>
                    VOF: {vof || '—'}{#if specialVof}<sup>{specialVof}</sup>{/if}
                  </span>
                  <span class="stat-tag range-tag" class:tag-missing={!range && rec.subtype === 'squad'}>
                    RNG: {range || '—'}
                  </span>
                  {#if steps}
                    <span class="stat-tag step-tag" title="{steps} steps">
                      {'●'.repeat(Math.min(steps, 4))}
                    </span>
                  {/if}
                {:else if rec.category === 'marker'}
                  {#if rec.marker_details?.cover_modifier != null}
                    <span class="stat-tag cover-tag">
                      Mod: {rec.marker_details.cover_modifier > 0 ? '+' : ''}{rec.marker_details.cover_modifier}
                    </span>
                  {/if}
                  {#if rec.marker_details?.effects}
                    <span class="stat-tag effect-tag">{rec.marker_details.effects}</span>
                  {/if}
                {/if}
              </div>

              <!-- Specific Subtype Extras: Fire Team, Weapon Type, and Mount Type -->
              <div class="extras-row">
                {#if division}
                  <span class="extra-pill division-pill" title="Division / Formation: {division}">{division}</span>
                {/if}

                {#if isFireTeam}
                  <span class="extra-pill fireteam-pill">&#128293; Fire Team</span>
                {:else if isAssaultTeam}
                  <span class="extra-pill assaultteam-pill">&#9876; Assault Team</span>
                {:else if rec.unit_details?.lat_subtype}
                  <span class="extra-pill">{rec.unit_details.lat_subtype}</span>
                {/if}

                {#if rec.unit_details?.weapon_type}
                  <span class="extra-pill weapon-pill">{rec.unit_details.weapon_type}</span>
                {/if}

                {#if isTripod}
                  <span class="extra-pill tripod-pill" title="Tripod Mount (Yellow Arrow on Counter)">&#10140; Tripod</span>
                {:else if rec.unit_details?.mount_type}
                  <span class="extra-pill mount-pill">{rec.unit_details.mount_type}</span>
                {/if}
              </div>

              <!-- Issues Banner if any -->
              {#if hasIssues}
                <div class="issues-list" title={issues.join(', ')}>
                  &#9888; {issues[0]}
                </div>
              {/if}

              <!-- Card Actions -->
              <div class="card-actions">
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
        <table class="counters-table">
          <thead>
            <tr>
              <th style="width: 50px;">Img</th>
              <th>Counter ID / Filename</th>
              <th>Country</th>
              <th>Category</th>
              <th>Subtype / Role</th>
              <th>VOF</th>
              <th>RNG</th>
              <th>Steps</th>
              <th>Modifier / Details</th>
              <th>Confidence</th>
              <th>Status</th>
              <th style="width: 140px;">Action</th>
            </tr>
          </thead>
          <tbody>
            {#each pageRecords as rec, i (rec.image?.filename || `${rec.id || 'item'}-${i}`)}
              {@const filename = rec.image?.filename || ''}
              {@const id = rec.id || filename}
              {@const isUnit = rec.category === 'unit'}
              {@const isFireTeam = rec.unit_details?.lat_subtype === 'Fire Team' || (rec.subtype === 'lat' && rec.unit_details?.lat_subtype === 'Fire Team')}
              {@const isAssaultTeam = rec.unit_details?.lat_subtype === 'Assault Team' || (rec.subtype === 'lat' && rec.unit_details?.lat_subtype === 'Assault Team')}
              {@const isTripod = rec.unit_details?.mount_type === 'Tripod'}
              {@const vof = rec.unit_details?.vof_rating || rec.combat?.vof || ''}
              {@const specialVof = rec.unit_details?.special_vof || ''}
              {@const range = rec.unit_details?.range_band || ''}
              {@const steps = rec.unit_details?.steps_total ?? rec.unit_details?.steps_remaining}
              {@const issues = getIssues(rec)}
              {@const hasIssues = issues.length > 0}
              {@const isReviewed = Boolean(rec.classification?.reviewed)}
              {@const imgUrl = getImageUrl(rec)}

              <tr class:row-issue={hasIssues} class:row-reviewed={isReviewed}>
                <td
                  class="table-img-cell"
                  role="button"
                  tabindex="0"
                  onclick={() => openInspector(rec)}
                  onkeydown={(e) => { if (e.key === 'Enter') openInspector(rec); }}
                >
                  {#if imgUrl}
                    <img src={imgUrl} alt={filename} class="table-thumb" loading="lazy" />
                  {:else}
                    <div class="table-thumb-placeholder">&#9638;</div>
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
                    {rec.id || filename}
                  </div>
                  <div class="table-filename">{filename}</div>
                </td>
                <td>
                  <span class="badge country-badge country-{rec.country?.toLowerCase()}">
                    {rec.country}
                  </span>
                </td>
                <td>
                  {#if isFireTeam}
                    <span class="badge category-badge badge-fireteam">FIRE TEAM</span>
                  {:else if isAssaultTeam}
                    <span class="badge category-badge badge-assaultteam">ASSAULT TM</span>
                  {:else if isTripod}
                    <span class="badge category-badge badge-tripod">TRIPOD</span>
                  {:else}
                    <span class="badge category-badge category-{rec.category}">{rec.category}</span>
                  {/if}
                </td>
                <td>
                  {#if isFireTeam}
                    <span class="sub-label fireteam-label">Fire Team</span>
                  {:else if isAssaultTeam}
                    <span class="sub-label assaultteam-label">Assault Team</span>
                  {:else}
                    <span class="sub-label">{rec.subtype}</span>
                  {/if}

                  {#if isFireTeam}
                    <span class="extra-pill-table fireteam-pill-table">&#128293; Fire Team</span>
                  {:else if isAssaultTeam}
                    <span class="extra-pill-table assaultteam-pill-table">&#9876; Assault Team</span>
                  {:else if rec.unit_details?.lat_subtype}
                    <span class="extra-pill-table">{rec.unit_details.lat_subtype}</span>
                  {/if}

                  {#if rec.unit_details?.weapon_type}
                    <span class="extra-pill-table weapon-pill-table">{rec.unit_details.weapon_type}</span>
                  {/if}

                  {#if isTripod}
                    <span class="extra-pill-table tripod-pill-table">&#10140; Tripod</span>
                  {:else if rec.unit_details?.mount_type}
                    <span class="extra-pill-table mount-pill-table">{rec.unit_details.mount_type}</span>
                  {/if}
                </td>
                <td>
                  {#if isUnit}
                    <strong class:text-danger={!vof && rec.subtype === 'squad'}>
                      {vof || '—'}{#if specialVof}<sup>{specialVof}</sup>{/if}
                    </strong>
                  {:else}
                    <span class="text-muted">—</span>
                  {/if}
                </td>
                <td>
                  {#if isUnit}
                    <strong class:text-danger={!range && rec.subtype === 'squad'}>{range || '—'}</strong>
                  {:else}
                    <span class="text-muted">—</span>
                  {/if}
                </td>
                <td>
                  {#if steps}
                    <span class="step-dots" title="{steps} steps">{'●'.repeat(Math.min(steps, 4))}</span>
                  {:else}
                    <span class="text-muted">—</span>
                  {/if}
                </td>
                <td>
                  {#if rec.category === 'marker' && rec.marker_details?.cover_modifier != null}
                    <span class="stat-tag cover-tag">
                      {rec.marker_details.cover_modifier > 0 ? '+' : ''}{rec.marker_details.cover_modifier}
                    </span>
                  {:else if rec.marker_details?.effects}
                    <span class="effect-text">{rec.marker_details.effects}</span>
                  {:else}
                    <span class="text-muted">—</span>
                  {/if}
                </td>
                <td>
                  <span class="conf-pill conf-lvl-{rec.image?.confidence >= 0.85 ? 'high' : rec.image?.confidence >= 0.7 ? 'med' : 'low'}">
                    {rec.image?.confidence != null ? Math.round(rec.image.confidence * 100) + '%' : '—'}
                  </span>
                </td>
                <td>
                  {#if hasIssues}
                    <span class="issue-badge-table" title={issues.join(', ')}>
                      &#9888; {issues[0]}
                    </span>
                  {:else if isReviewed}
                    <span class="clean-badge" title="Saved to {finalJsonName}">✓ In Final</span>
                  {:else}
                    <span class="unreviewed-badge">Unreviewed</span>
                  {/if}
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

  <!-- INSPECTOR / QUICK EDIT MODAL DRAWER -->
  {#if activeRecord !== null}
    {@const issues = getIssues(activeRecord)}
    {@const imgUrl = getImageUrl(activeRecord)}
    {@const id = activeRecord.id || activeRecord.image?.filename}

    <div
      class="modal-backdrop"
      role="presentation"
      onclick={closeInspector}
    >
      <div
        class="inspector-drawer"
        role="dialog"
        tabindex="-1"
        onclick={(e) => e.stopPropagation()}
      >
        <!-- Drawer Header -->
        <div class="drawer-header">
          <div class="drawer-title-group">
            <div class="drawer-title-row">
              <h2>Inspect: {activeRecord.id}</h2>
              <span class="badge country-badge country-{activeRecord.country?.toLowerCase()}">
                {activeRecord.country}
              </span>
              {#if finalMap.has(getRecordKey(activeRecord))}
                <span class="status-indicator-badge in-final">✓ In {finalJsonName}</span>
              {:else}
                <span class="status-indicator-badge not-in-final">Loaded File Version</span>
              {/if}
            </div>
            <span class="drawer-filename">{activeRecord.image?.filename}</span>
          </div>

          <div class="drawer-header-actions">
            <button class="nav-arrow-btn" onclick={() => navInspector(-1)} title="Previous counter (&larr;)">
              &larr; Prev
            </button>
            <button class="nav-arrow-btn" onclick={() => navInspector(1)} title="Next counter (&rarr;)">
              Next &rarr;
            </button>
            <button class="close-btn" onclick={closeInspector}>&times;</button>
          </div>
        </div>

        <!-- Drawer Content Grid -->
        <div class="drawer-body">
          <!-- Left Column: Visual Preview & Diagram -->
          <div class="preview-col">
            <div
              class="large-token-preview"
              style="--zoom: {zoomLevel};"
              role="region"
              aria-label="Token spatial overview"
            >
              {#if imgUrl}
                <img src={imgUrl} alt={activeRecord.image?.filename} class="pixel-img" />
              {:else}
                <div class="preview-placeholder">No Image Found</div>
              {/if}

              <!-- Spatial Overlays representing regions on the counter -->
              <div
                class="token-hotspot hotspot-header"
                class:highlighted={activeFieldHighlight === 'header'}
                title="Header Area (Squad / Platoon / Designation)"
              >
                <span class="hotspot-label">
                  {#if activeRecord.unit_details?.squad_number || activeRecord.unit_details?.platoon}
                    {activeRecord.unit_details?.squad_number || '?'}/{activeRecord.unit_details?.platoon || '?'} PLT
                  {:else}
                    Header / Org
                  {/if}
                </span>
              </div>

              <div
                class="token-hotspot hotspot-center"
                class:highlighted={activeFieldHighlight === 'center'}
                title="Center Graphic (Weapon / Role / Insignia)"
              >
                <span class="hotspot-label">
                  {activeRecord.unit_details?.weapon_type || activeRecord.subtype || 'Art / Weapon'}
                </span>
              </div>

              <div
                class="token-hotspot hotspot-vof"
                class:highlighted={activeFieldHighlight === 'vof' || activeFieldHighlight === 'special_vof'}
                title="Bottom-Left: Basic & Special VOF"
              >
                <span class="hotspot-label">
                  {activeRecord.unit_details?.vof_rating || '—'}{#if activeRecord.unit_details?.special_vof}<sup>{activeRecord.unit_details.special_vof}</sup>{/if}
                </span>
              </div>

              <div
                class="token-hotspot hotspot-steps"
                class:highlighted={activeFieldHighlight === 'steps'}
                title="Bottom-Center: Steps (Yellow Dots)"
              >
                <span class="hotspot-label">
                  {#if activeRecord.unit_details?.steps_total}
                    {'●'.repeat(Math.min(activeRecord.unit_details.steps_total, 4))}
                  {:else}
                    Steps
                  {/if}
                </span>
              </div>

              <div
                class="token-hotspot hotspot-range"
                class:highlighted={activeFieldHighlight === 'range'}
                title="Bottom-Right: Range Band"
              >
                <span class="hotspot-label">
                  {activeRecord.unit_details?.range_band || '—'}
                </span>
              </div>
            </div>

            <div class="zoom-controls">
              <span>Zoom:</span>
              <button class="zoom-btn" class:active={zoomLevel === 2} onclick={() => (zoomLevel = 2)}>2x</button>
              <button class="zoom-btn" class:active={zoomLevel === 3} onclick={() => (zoomLevel = 3)}>3x</button>
              <button class="zoom-btn" class:active={zoomLevel === 4} onclick={() => (zoomLevel = 4)}>4x</button>
            </div>

            <div class="spatial-guide-hint">
              &#128161; Hover over form fields on the right to see their corresponding location highlighted on the token.
            </div>

            {#if issues.length > 0}
              <div class="issues-box">
                <h4>&#9888; Invariant Issues:</h4>
                <ul>
                  {#each issues as iss}
                    <li>{iss}</li>
                  {/each}
                </ul>
              </div>
            {/if}

            <div class="ocr-evidence-box">
              <h4>OCR &amp; Computer Vision Notes</h4>
              {#if activeRecord.classification?.notes}
                <p class="notes-text">{activeRecord.classification.notes}</p>
              {/if}
              {#if activeRecord.classification?.labels}
                <div class="labels-list">
                  {#each activeRecord.classification.labels as lbl}
                    <span class="label-chip">{lbl}</span>
                  {/each}
                </div>
              {/if}
            </div>

            <!-- Step-down (read-only): shows where this counter steps to, and its fire/assault options -->
            {#if activeRecord.step_down_to || activeRecord.step_down_options}
              <div class="ocr-evidence-box step-down-box">
                <h4>Step-down</h4>
                {#if activeRecord.step_down_to}
                  <div class="step-down-row">
                    <span class="field-title">Steps down to:</span>
                    <span>{activeRecord.step_down_to.filename}</span>
                    <img
                      src={getAssetReviewImageUrl(selectedGameId, activeRecord.step_down_to.filename)}
                      alt={activeRecord.step_down_to.filename}
                      class="step-down-img"
                      loading="lazy"
                    />
                  </div>
                {/if}
                {#if activeRecord.step_down_options}
                  <div class="step-down-row">
                    <span class="field-title">Options:</span>
                    {#each activeRecord.step_down_options as opt}
                      <span class="step-down-opt">
                        <span>{opt.type === 'assault_team' ? 'Assault Team' : 'Fire Team'}: {opt.filename}</span>
                        <img
                          src={getAssetReviewImageUrl(selectedGameId, opt.filename)}
                          alt={opt.filename}
                          class="step-down-img"
                          loading="lazy"
                        />
                      </span>
                    {/each}
                  </div>
                {/if}
              </div>
            {/if}
          </div>

          <!-- Right Column: Editable Schema Properties -->
          <div class="fields-col">
            <!-- SECTION 1: TOP HEADER & ORGANIZATION -->
            <div
              class="field-section section-top"
              class:section-active={activeFieldHighlight === 'header'}
              onmouseenter={() => (activeFieldHighlight = 'header')}
              onmouseleave={() => (activeFieldHighlight = null)}
              role="region"
              aria-label="Header designation fields"
            >
              <div class="section-title-bar">
                <span class="section-badge badge-top">&#128392; Top of Counter (Organization &amp; Designation)</span>
              </div>
              <div class="form-grid">
                <label class="form-field">
                  <span class="field-title">Squad Number:</span>
                  <input
                    type="text"
                    bind:value={activeRecord.unit_details.squad_number}
                    placeholder="e.g. 1, 2, 3"
                    class="form-input"
                    onfocus={() => (activeFieldHighlight = 'header')}
                    onblur={() => (activeFieldHighlight = null)}
                  />
                </label>

                <label class="form-field">
                  <span class="field-title">Platoon:</span>
                  <input
                    type="text"
                    bind:value={activeRecord.unit_details.platoon}
                    placeholder="e.g. 1, 2, 3, CO"
                    class="form-input"
                    onfocus={() => (activeFieldHighlight = 'header')}
                    onblur={() => (activeFieldHighlight = null)}
                  />
                </label>

                <label class="form-field full-width">
                  <span class="field-title">Division / Formation Insignia:</span>
                  <input
                    type="text"
                    bind:value={activeRecord.unit_details.division}
                    placeholder="e.g. 1st Marine Div, 2nd Inf Div, 101st Airborne Div, 1 ATF"
                    class="form-input"
                    onfocus={() => (activeFieldHighlight = 'header')}
                    onblur={() => (activeFieldHighlight = null)}
                  />
                </label>
              </div>
            </div>

            <!-- SECTION 2: IDENTITY, SUBTYPE, & WEAPON -->
            <div
              class="field-section section-center"
              class:section-active={activeFieldHighlight === 'center'}
              onmouseenter={() => (activeFieldHighlight = 'center')}
              onmouseleave={() => (activeFieldHighlight = null)}
              role="region"
              aria-label="Center weapon and identity fields"
            >
              <div class="section-title-bar">
                <span class="section-badge badge-center">&#128065; Center / Role &amp; Identity</span>
              </div>
              <div class="form-grid">
                <label class="form-field">
                  <span class="field-title">Subtype (Role):</span>
                  <div class="input-with-dropdown">
                    <select
                      class="form-select"
                      value={KNOWN_SUBTYPES.includes(activeRecord.subtype) ? activeRecord.subtype : '__custom__'}
                      onchange={(e) => {
                        const val = e.currentTarget.value;
                        if (val !== '__custom__') {
                          activeRecord.subtype = val;
                        }
                      }}
                      onfocus={() => (activeFieldHighlight = 'center')}
                      onblur={() => (activeFieldHighlight = null)}
                    >
                      {#each KNOWN_SUBTYPES as st}
                        <option value={st}>{st}</option>
                      {/each}
                      <option value="__custom__">Custom / Other &rarr;</option>
                    </select>
                    {#if !KNOWN_SUBTYPES.includes(activeRecord.subtype)}
                      <input
                        type="text"
                        bind:value={activeRecord.subtype}
                        placeholder="Custom subtype"
                        class="form-input custom-input"
                        onfocus={() => (activeFieldHighlight = 'center')}
                        onblur={() => (activeFieldHighlight = null)}
                      />
                    {/if}
                  </div>
                </label>

                <label class="form-field">
                  <span class="field-title">Country:</span>
                  <select
                    bind:value={activeRecord.country}
                    class="form-select"
                    onfocus={() => (activeFieldHighlight = 'center')}
                    onblur={() => (activeFieldHighlight = null)}
                  >
                    <option value="US">US</option>
                    <option value="German">German</option>
                    <option value="Chinese">Chinese</option>
                    <option value="NKPA">NKPA</option>
                    <option value="VietCong">VietCong</option>
                    <option value="NVA">NVA</option>
                    <option value="ARVN">ARVN</option>
                    <option value="Japanese">Japanese</option>
                    <option value="Commonwealth">Commonwealth</option>
                    <option value="Australian">Australian</option>
                    <option value="Other">Other</option>
                    <option value="Unknown">Unknown</option>
                  </select>
                </label>

                <label class="form-field">
                  <span class="field-title">Category:</span>
                  <select
                    bind:value={activeRecord.category}
                    class="form-select"
                    onfocus={() => (activeFieldHighlight = 'center')}
                    onblur={() => (activeFieldHighlight = null)}
                  >
                    <option value="unit">unit</option>
                    <option value="marker">marker</option>
                    <option value="asset">asset</option>
                  </select>
                </label>

                <label class="form-field">
                  <span class="field-title">Weapon Type:</span>
                  <input
                    type="text"
                    bind:value={activeRecord.unit_details.weapon_type}
                    placeholder="Machine Gun, Mortar, Bazooka, etc."
                    class="form-input"
                    onfocus={() => (activeFieldHighlight = 'center')}
                    onblur={() => (activeFieldHighlight = null)}
                  />
                </label>

                <label class="form-field">
                  <span class="field-title">LAT Subtype:</span>
                  <select
                    bind:value={activeRecord.unit_details.lat_subtype}
                    class="form-select"
                    onfocus={() => (activeFieldHighlight = 'center')}
                    onblur={() => (activeFieldHighlight = null)}
                  >
                    <option value={null}>None</option>
                    <option value="Fire Team">Fire Team</option>
                    <option value="Assault Team">Assault Team</option>
                    <option value="Litter Team">Litter Team</option>
                    <option value="Paralyzed Team">Paralyzed Team</option>
                  </select>
                </label>

                <label class="form-field">
                  <span class="field-title">Mount Type:</span>
                  <select
                    bind:value={activeRecord.unit_details.mount_type}
                    class="form-select"
                    onfocus={() => (activeFieldHighlight = 'center')}
                    onblur={() => (activeFieldHighlight = null)}
                  >
                    <option value={null}>None</option>
                    <option value="Tripod">&#10140; Tripod (Yellow Arrow)</option>
                    <option value="Bipod">Bipod</option>
                    <option value="Vehicle">Vehicle</option>
                  </select>
                </label>

                <label class="form-field">
                  <span class="field-title">Experience:</span>
                  <select
                    bind:value={activeRecord.unit_details.experience_level}
                    class="form-select"
                    onfocus={() => (activeFieldHighlight = 'center')}
                    onblur={() => (activeFieldHighlight = null)}
                  >
                    <option value={null}>None / Standard</option>
                    <option value="Green">Green</option>
                    <option value="Line">Line</option>
                    <option value="Veteran">Veteran</option>
                    <option value="Elite">Elite</option>
                  </select>
                </label>
              </div>
            </div>

            <!-- SECTION 3: BOTTOM STRIP RATINGS (VOF, STEPS, RANGE) -->
            {#if activeRecord.category === 'unit'}
              <div
                class="field-section section-bottom"
                class:section-active={activeFieldHighlight === 'vof' || activeFieldHighlight === 'range' || activeFieldHighlight === 'steps'}
                role="region"
                aria-label="Bottom ratings bar fields"
              >
                <div class="section-title-bar">
                  <span class="section-badge badge-bottom">&#9876; Bottom Strip Ratings (VOF, Steps, Range)</span>
                </div>

                <div class="bottom-strip-layout">
                  <!-- Bottom Left: VOF -->
                  <div
                    class="strip-cell cell-vof"
                    onmouseenter={() => (activeFieldHighlight = 'vof')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <div class="cell-label">&#8601; Bottom Left</div>
                    <label class="form-field">
                      <span class="field-title">Basic VOF:</span>
                      <div class="input-with-dropdown">
                        <select
                          class="form-select"
                          value={KNOWN_BASIC_VOFS.some((v) => v.value === activeRecord.unit_details.vof_rating) ? activeRecord.unit_details.vof_rating : (activeRecord.unit_details.vof_rating ? '__custom__' : '')}
                          onchange={(e) => {
                            const val = e.currentTarget.value;
                            if (val !== '__custom__') {
                              activeRecord.unit_details.vof_rating = val || null;
                            }
                          }}
                          onfocus={() => (activeFieldHighlight = 'vof')}
                          onblur={() => (activeFieldHighlight = null)}
                        >
                          <option value="">None / —</option>
                          {#each KNOWN_BASIC_VOFS as v}
                            <option value={v.value}>{v.label}</option>
                          {/each}
                          <option value="__custom__">Custom / Other &rarr;</option>
                        </select>
                        {#if activeRecord.unit_details.vof_rating && !KNOWN_BASIC_VOFS.some((v) => v.value === activeRecord.unit_details.vof_rating)}
                          <input
                            type="text"
                            bind:value={activeRecord.unit_details.vof_rating}
                            placeholder="Custom VOF"
                            class="form-input custom-input"
                            onfocus={() => (activeFieldHighlight = 'vof')}
                            onblur={() => (activeFieldHighlight = null)}
                          />
                        {/if}
                      </div>
                    </label>

                    <label class="form-field">
                      <span class="field-title">Special VOF (Superscript):</span>
                      <select
                        bind:value={activeRecord.unit_details.special_vof}
                        class="form-select"
                        onfocus={() => (activeFieldHighlight = 'special_vof')}
                        onblur={() => (activeFieldHighlight = null)}
                      >
                        <option value={null}>None</option>
                        <option value="G!">G! (Grenade Attack / RPG / AT)</option>
                        <option value="F!">F! (Flamethrower)</option>
                        <option value="D!">D! (Demolition Charge)</option>
                        <option value="S!">S! (Sniper)</option>
                      </select>
                    </label>
                  </div>

                  <!-- Bottom Center: Steps -->
                  <div
                    class="strip-cell cell-steps"
                    onmouseenter={() => (activeFieldHighlight = 'steps')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <div class="cell-label">&#8595; Bottom Center</div>
                    <label class="form-field">
                      <span class="field-title">Total Steps (Dots):</span>
                      <input
                        type="number"
                        min="1"
                        max="4"
                        bind:value={activeRecord.unit_details.steps_total}
                        class="form-input"
                        onfocus={() => (activeFieldHighlight = 'steps')}
                        onblur={() => (activeFieldHighlight = null)}
                      />
                    </label>

                    <label class="form-field">
                      <span class="field-title">Remaining Steps:</span>
                      <input
                        type="number"
                        min="1"
                        max="4"
                        bind:value={activeRecord.unit_details.steps_remaining}
                        class="form-input"
                        onfocus={() => (activeFieldHighlight = 'steps')}
                        onblur={() => (activeFieldHighlight = null)}
                      />
                    </label>
                  </div>

                  <!-- Bottom Right: Range Band -->
                  <div
                    class="strip-cell cell-range"
                    onmouseenter={() => (activeFieldHighlight = 'range')}
                    onmouseleave={() => (activeFieldHighlight = null)}
                  >
                    <div class="cell-label">&#8600; Bottom Right</div>
                    <label class="form-field">
                      <span class="field-title">Range Band:</span>
                      <select
                        bind:value={activeRecord.unit_details.range_band}
                        class="form-select"
                        onfocus={() => (activeFieldHighlight = 'range')}
                        onblur={() => (activeFieldHighlight = null)}
                      >
                        <option value={null}>None / —</option>
                        <option value="P">P (Point Blank)</option>
                        <option value="C">C (Close)</option>
                        <option value="L">L (Long)</option>
                        <option value="V">V (Very Long)</option>
                        <option value="C-L">C-L (Close - Long)</option>
                        <option value="C-V">C-V (Close - Very Long)</option>
                      </select>
                    </label>
                  </div>
                </div>
              </div>
            {:else if activeRecord.category === 'marker'}
              <div class="field-section section-bottom">
                <div class="section-title-bar">
                  <span class="section-badge badge-bottom">&#9876; Marker Properties</span>
                </div>
                <div class="form-grid">
                  <label class="form-field">
                    <span class="field-title">Cover Modifier:</span>
                    <input
                      type="number"
                      bind:value={activeRecord.marker_details.cover_modifier}
                      placeholder="-2, +1, +3, etc."
                      class="form-input"
                    />
                  </label>

                  <label class="form-field">
                    <span class="field-title">Effects Description:</span>
                    <input type="text" bind:value={activeRecord.marker_details.effects} class="form-input" />
                  </label>
                </div>
              </div>
            {/if}
          </div>
        </div>

        <!-- Fixed Modal Footer: Always visible without scrolling -->
        <div class="drawer-footer">
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
              title="Save changes and advance to the next counter"
            >
              Save &amp; Next (&rarr;)
            </button>
            <button
              class="validate-btn"
              class:btn-validated={Boolean(activeRecord.classification?.reviewed)}
              disabled={savingId !== null}
              onclick={() => saveActiveRecord(true, !Boolean(activeRecord.classification?.reviewed))}
              title="Validate and advance to the next counter"
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

  /* Header */
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
    gap: 1rem;
    flex-wrap: wrap;
  }

  .home-btn {
    font-size: 0.85rem;
    color: #8bb4e7;
    text-decoration: none;
    padding: 0.35rem 0.75rem;
    background: rgba(255, 255, 255, 0.05);
    border-radius: 4px;
    transition: background 0.15s ease;
  }

  .home-btn:hover {
    background: rgba(255, 255, 255, 0.12);
  }

  h1 {
    font-size: 1.6rem;
    font-weight: 700;
    margin: 0;
    color: #fff;
  }

  .file-tag {
    font-size: 0.8rem;
    font-family: monospace;
    background: #1e2942;
    padding: 0.25rem 0.6rem;
    border-radius: 4px;
    color: #9cb2d6;
    border: 1px solid rgba(255, 255, 255, 0.06);
  }

  .nav-config-group {
    display: flex;
    align-items: center;
    gap: 0.75rem;
    flex-wrap: wrap;
  }

  .config-label {
    font-size: 0.85rem;
    color: #a4b5d0;
    display: flex;
    align-items: center;
    gap: 0.4rem;
  }

  .nav-select,
  .filter-select {
    background: #182238;
    color: #e1e7f0;
    border: 1px solid rgba(255, 255, 255, 0.15);
    padding: 0.4rem 0.75rem;
    border-radius: 6px;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .reload-btn {
    background: #2563eb;
    color: white;
    border: none;
    padding: 0.4rem 0.85rem;
    border-radius: 6px;
    cursor: pointer;
    font-size: 0.85rem;
    font-weight: 500;
  }

  .reload-btn:hover {
    background: #1d4ed8;
  }

  .view-toggle {
    display: flex;
    border: 1px solid rgba(255, 255, 255, 0.15);
    border-radius: 6px;
    overflow: hidden;
  }

  .toggle-btn {
    background: #182238;
    color: #8da4c4;
    border: none;
    padding: 0.4rem 0.75rem;
    font-size: 0.85rem;
    cursor: pointer;
  }

  .toggle-btn.active {
    background: #3b82f6;
    color: #fff;
  }

  /* Summary Audit Bar */
  .audit-bar {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(130px, 1fr));
    gap: 0.75rem;
    margin: 1.25rem 0;
  }

  .audit-stat {
    background: #151d30;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 8px;
    padding: 0.75rem 1rem;
    cursor: pointer;
    transition: transform 0.12s ease, border-color 0.12s ease;
    display: flex;
    flex-direction: column;
    align-items: flex-start;
  }

  .audit-stat:hover {
    transform: translateY(-2px);
    border-color: rgba(255, 255, 255, 0.2);
  }

  .audit-stat.active-chip {
    border-color: #3b82f6;
    background: #1b2640;
  }

  .stat-num {
    font-size: 1.4rem;
    font-weight: 700;
    color: #fff;
  }

  .stat-lbl {
    font-size: 0.75rem;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: #889bb8;
    margin-top: 0.2rem;
  }

  .stat-issues .stat-num {
    color: #f87171;
  }

  .stat-tripod .stat-num {
    color: #facc15;
  }

  .stat-fireteam .stat-num {
    color: #fb923c;
  }

  .stat-reviewed .stat-num {
    color: #4ade80;
  }

  /* Filters Bar */
  .filters-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
    background: #151d30;
    padding: 0.75rem 1rem;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.06);
    margin-bottom: 1.25rem;
  }

  .search-box {
    position: relative;
    flex: 1 1 260px;
  }

  .search-input {
    width: 100%;
    background: #0f1423;
    color: #fff;
    border: 1px solid rgba(255, 255, 255, 0.12);
    padding: 0.45rem 1.8rem 0.45rem 0.75rem;
    border-radius: 6px;
    font-size: 0.85rem;
    box-sizing: border-box;
  }

  .clear-search {
    position: absolute;
    right: 0.5rem;
    top: 50%;
    transform: translateY(-50%);
    background: transparent;
    border: none;
    color: #8da4c4;
    font-size: 1.1rem;
    cursor: pointer;
  }

  .dropdowns-group {
    display: flex;
    gap: 0.5rem;
    flex-wrap: wrap;
  }

  /* Alerts */
  .alert {
    padding: 0.75rem 1rem;
    border-radius: 6px;
    font-size: 0.85rem;
    margin-bottom: 1rem;
  }

  .error-alert {
    background: #3b1414;
    border: 1px solid #ef4444;
    color: #fca5a5;
  }

  .status-alert {
    background: #064e3b;
    border: 1px solid #10b981;
    color: #a7f3d0;
  }

  /* Pagination Bar */
  .pagination-bar {
    display: flex;
    justify-content: space-between;
    align-items: center;
    margin-bottom: 1rem;
    font-size: 0.85rem;
    color: #8da4c4;
  }

  .bottom-pager {
    margin-top: 1.5rem;
    justify-content: center;
    gap: 1rem;
  }

  .pager-btns {
    display: flex;
    gap: 0.25rem;
    align-items: center;
  }

  .page-nav-btn {
    background: #182238;
    color: #fff;
    border: 1px solid rgba(255, 255, 255, 0.1);
    padding: 0.35rem 0.7rem;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.85rem;
  }

  .page-nav-btn:disabled {
    opacity: 0.35;
    cursor: not-allowed;
  }

  .current-page-badge {
    padding: 0.35rem 0.6rem;
    background: #0f1423;
    border-radius: 4px;
    font-weight: 600;
  }

  /* Card Grid */
  .counter-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(210px, 1fr));
    gap: 1rem;
  }

  .counter-card {
    background: #162035;
    border: 1px solid rgba(255, 255, 255, 0.08);
    border-radius: 8px;
    overflow: hidden;
    display: flex;
    flex-direction: column;
    transition: transform 0.12s ease, box-shadow 0.12s ease;
  }

  .counter-card:hover {
    transform: translateY(-2px);
    box-shadow: 0 6px 20px rgba(0, 0, 0, 0.35);
  }

  .counter-card.card-issue {
    border-color: #ef4444;
  }

  .counter-card.card-reviewed {
    border-left: 3px solid #10b981;
  }

  .card-img-wrapper {
    position: relative;
    background: #0b0f1a;
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 1.25rem 0.5rem;
    cursor: pointer;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .token-img {
    width: 75px;
    height: 75px;
    image-rendering: pixelated;
    border: 1px solid #334155;
    box-shadow: 0 4px 10px rgba(0, 0, 0, 0.5);
    background: #1e293b;
    display: block;
  }

  .img-missing,
  .table-thumb-placeholder {
    width: 75px;
    height: 75px;
    display: flex;
    align-items: center;
    justify-content: center;
    background: #1e293b;
    color: #64748b;
    font-size: 1.5rem;
  }

  .badge {
    position: absolute;
    font-size: 0.65rem;
    font-weight: 700;
    text-transform: uppercase;
    padding: 0.15rem 0.4rem;
    border-radius: 3px;
    letter-spacing: 0.03em;
  }

  .country-badge {
    top: 0.4rem;
    left: 0.4rem;
    background: rgba(0, 0, 0, 0.7);
    color: #e2e8f0;
  }

  .country-us {
    color: #60a5fa;
  }
  .country-german {
    color: #cbd5e1;
  }
  .country-chinese {
    color: #f87171;
  }
  .country-nkpa {
    color: #fb923c;
  }
  .country-vietcong {
    color: #facc15;
  }

  .category-badge {
    top: 0.4rem;
    right: 0.4rem;
    background: #1e293b;
    color: #94a3b8;
  }

  .badge-fireteam {
    top: 0.4rem;
    right: 0.4rem;
    background: #c2410c;
    color: #ffedd5;
    border: 1px solid #ea580c;
  }

  .badge-assaultteam {
    top: 0.4rem;
    right: 0.4rem;
    background: #991b1b;
    color: #fee2e2;
    border: 1px solid #ef4444;
  }

  .badge-tripod {
    top: 0.4rem;
    right: 0.4rem;
    background: rgba(234, 179, 8, 0.25);
    color: #facc15;
    border: 1px solid #eab308;
  }

  .category-unit {
    color: #60a5fa;
  }
  .category-marker {
    color: #f97316;
  }
  .category-asset {
    color: #a855f7;
  }

  .card-body {
    padding: 0.75rem;
    display: flex;
    flex-direction: column;
    flex: 1;
    gap: 0.4rem;
  }

  .card-id {
    font-size: 0.85rem;
    font-weight: 700;
    color: #fff;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .card-filename {
    font-size: 0.7rem;
    color: #64748b;
    font-family: monospace;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .stats-row {
    display: flex;
    gap: 0.35rem;
    flex-wrap: wrap;
    margin: 0.2rem 0;
  }

  .stat-tag {
    font-size: 0.7rem;
    font-weight: 600;
    padding: 0.15rem 0.35rem;
    border-radius: 3px;
    background: #0f172a;
    color: #cbd5e1;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .org-tag {
    background: rgba(56, 189, 248, 0.15);
    color: #38bdf8;
    border-color: rgba(56, 189, 248, 0.35);
    font-weight: 700;
  }

  .vof-tag {
    color: #f87171;
    border-color: rgba(248, 113, 113, 0.3);
  }

  .vof-tag sup,
  td strong sup {
    font-size: 0.7em;
    font-weight: 800;
    color: #fbbf24;
    margin-left: 1px;
    vertical-align: super;
  }

  .range-tag {
    color: #60a5fa;
    border-color: rgba(96, 165, 250, 0.3);
  }

  .step-tag {
    color: #fbbf24;
    letter-spacing: 0.05em;
  }

  .cover-tag {
    color: #34d399;
  }

  .tag-missing {
    background: #450a0a;
    color: #f87171;
    border-color: #ef4444;
  }

  .extra-pill {
    font-size: 0.7rem;
    background: #1e293b;
    padding: 0.15rem 0.4rem;
    border-radius: 3px;
    color: #94a3b8;
    align-self: flex-start;
  }

  .extras-row {
    display: flex;
    flex-wrap: wrap;
    gap: 0.35rem;
    align-items: center;
  }

  .fireteam-pill {
    background: rgba(234, 88, 12, 0.2);
    color: #fb923c;
    border: 1px solid rgba(234, 88, 12, 0.45);
    font-weight: 600;
  }

  .assaultteam-pill {
    background: rgba(239, 68, 68, 0.2);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.45);
    font-weight: 600;
  }

  .tripod-pill {
    background: rgba(234, 179, 8, 0.2);
    color: #facc15;
    border: 1px solid rgba(234, 179, 8, 0.45);
    font-weight: 600;
  }

  .weapon-pill,
  .mount-pill {
    background: #1e293b;
    color: #94a3b8;
  }

  .division-pill {
    background: rgba(168, 85, 247, 0.15);
    color: #c084fc;
    border: 1px solid rgba(168, 85, 247, 0.35);
    font-weight: 600;
  }

  .fireteam-pill-table {
    display: inline-block;
    font-size: 0.65rem;
    background: rgba(234, 88, 12, 0.2);
    color: #fb923c;
    border: 1px solid rgba(234, 88, 12, 0.4);
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    margin-left: 0.3rem;
    font-weight: 600;
  }

  .assaultteam-pill-table {
    display: inline-block;
    font-size: 0.65rem;
    background: rgba(239, 68, 68, 0.2);
    color: #f87171;
    border: 1px solid rgba(239, 68, 68, 0.4);
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    margin-left: 0.3rem;
    font-weight: 600;
  }

  .tripod-pill-table {
    display: inline-block;
    font-size: 0.65rem;
    background: rgba(234, 179, 8, 0.2);
    color: #facc15;
    border: 1px solid rgba(234, 179, 8, 0.45);
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    margin-left: 0.3rem;
    font-weight: 600;
  }

  .fireteam-label {
    color: #fb923c;
    font-weight: 700;
  }

  .assaultteam-label {
    color: #f87171;
    font-weight: 700;
  }

  .issues-list {
    font-size: 0.7rem;
    color: #ef4444;
    background: rgba(239, 68, 68, 0.12);
    padding: 0.25rem 0.4rem;
    border-radius: 4px;
    margin-top: auto;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
  }

  .card-actions {
    display: flex;
    gap: 0.4rem;
    margin-top: 0.4rem;
  }

  .action-btn-sm {
    flex: 1;
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.35rem 0.5rem;
    border-radius: 4px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    background: #1e293b;
    color: #e2e8f0;
    cursor: pointer;
    transition: all 0.12s ease;
  }

  .action-btn-sm:hover {
    background: #334155;
  }

  .action-btn-sm.btn-validated {
    background: #064e3b;
    border-color: #059669;
    color: #6ee7b7;
  }

  .edit-btn {
    flex: 0.8;
    background: transparent;
  }

  /* Table View */
  .table-container {
    overflow-x: auto;
    background: #151d30;
    border-radius: 8px;
    border: 1px solid rgba(255, 255, 255, 0.08);
  }

  .counters-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 0.85rem;
    text-align: left;
  }

  .counters-table th {
    background: #0f1423;
    padding: 0.6rem 0.75rem;
    color: #94a3b8;
    font-weight: 600;
    border-bottom: 1px solid rgba(255, 255, 255, 0.1);
  }

  .counters-table td {
    padding: 0.5rem 0.75rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.05);
  }

  .counters-table tr:hover {
    background: #1a243d;
  }

  .counters-table tr.row-issue {
    background: rgba(239, 68, 68, 0.05);
  }

  .table-thumb {
    width: 38px;
    height: 38px;
    image-rendering: pixelated;
    border-radius: 3px;
    border: 1px solid #334155;
    cursor: pointer;
    display: block;
  }

  .table-id {
    font-weight: 700;
    color: #fff;
    cursor: pointer;
  }

  .table-filename {
    font-size: 0.7rem;
    color: #64748b;
    font-family: monospace;
  }

  .sub-label {
    font-weight: 600;
    color: #cbd5e1;
  }

  .extra-pill-table {
    display: inline-block;
    font-size: 0.65rem;
    background: #1e293b;
    padding: 0.1rem 0.35rem;
    border-radius: 3px;
    color: #94a3b8;
    margin-left: 0.3rem;
  }

  .step-dots {
    color: #fbbf24;
    font-size: 0.8rem;
  }

  .conf-pill {
    font-size: 0.75rem;
    font-weight: 600;
    padding: 0.15rem 0.4rem;
    border-radius: 3px;
  }

  .conf-lvl-high {
    color: #4ade80;
    background: rgba(74, 222, 128, 0.1);
  }
  .conf-lvl-med {
    color: #facc15;
    background: rgba(250, 204, 21, 0.1);
  }
  .conf-lvl-low {
    color: #f87171;
    background: rgba(248, 113, 113, 0.1);
  }

  .issue-badge-table {
    color: #f87171;
    font-size: 0.75rem;
    font-weight: 600;
  }

  .clean-badge {
    color: #4ade80;
    font-weight: 700;
  }

  .row-actions {
    display: flex;
    gap: 0.3rem;
  }

  .text-danger {
    color: #f87171;
  }

  .text-muted {
    color: #64748b;
  }

  /* Inspector Modal Drawer */
  .modal-backdrop {
    position: fixed;
    top: 0;
    left: 0;
    right: 0;
    bottom: 0;
    background: rgba(0, 0, 0, 0.8);
    backdrop-filter: blur(4px);
    display: flex;
    justify-content: center;
    align-items: center;
    padding: 1rem;
    z-index: 1000;
  }

  .inspector-drawer {
    width: min(1380px, 96vw);
    height: min(94vh, 830px);
    max-height: 94vh;
    background: #121829;
    border-radius: 12px;
    border: 1px solid rgba(255, 255, 255, 0.12);
    box-shadow: 0 16px 48px rgba(0, 0, 0, 0.85);
    display: flex;
    flex-direction: column;
    overflow: hidden;
  }

  .drawer-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem 1.25rem;
    border-bottom: 1px solid rgba(255, 255, 255, 0.08);
    background: #0d1220;
    flex-shrink: 0;
  }

  .drawer-title-group {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .drawer-title-row {
    display: flex;
    align-items: center;
    gap: 0.6rem;
  }

  .drawer-title-group h2 {
    margin: 0;
    font-size: 1.15rem;
    color: #fff;
  }

  .drawer-filename {
    font-size: 0.75rem;
    font-family: monospace;
    color: #64748b;
  }

  .drawer-header-actions {
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

  .drawer-body {
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

  .large-token-preview {
    position: relative;
    width: calc(75px * var(--zoom));
    height: calc(75px * var(--zoom));
    background: #080c14;
    border: 2px solid #334155;
    border-radius: 8px;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 8px 24px rgba(0, 0, 0, 0.6);
    overflow: hidden;
  }

  .pixel-img {
    width: 100%;
    height: 100%;
    image-rendering: pixelated;
    display: block;
  }

  /* Interactive Hotspots over Counter Graphic */
  .token-hotspot {
    position: absolute;
    border: 1px dashed rgba(255, 255, 255, 0.2);
    background: rgba(15, 23, 42, 0.25);
    display: flex;
    align-items: center;
    justify-content: center;
    transition: all 0.2s cubic-bezier(0.4, 0, 0.2, 1);
    pointer-events: none;
    border-radius: 4px;
  }

  .hotspot-label {
    font-size: 0.65rem;
    font-weight: 700;
    padding: 0.1rem 0.3rem;
    border-radius: 3px;
    background: rgba(0, 0, 0, 0.85);
    color: #e2e8f0;
    white-space: nowrap;
    text-shadow: 0 1px 2px #000;
    opacity: 0.88;
    transform: scale(1);
    transition: opacity 0.18s ease, transform 0.18s ease;
    border: 1px solid rgba(255, 255, 255, 0.15);
  }

  /* When the section is hovered or focused, fade the label out completely so the underlying counter text is 100% visible */
  .token-hotspot.highlighted .hotspot-label {
    opacity: 0;
    transform: scale(0.85);
    pointer-events: none;
  }

  .hotspot-header {
    top: 4%;
    left: 8%;
    right: 8%;
    height: 22%;
    border-color: rgba(56, 189, 248, 0.35);
  }

  .hotspot-center {
    top: 26%;
    left: 10%;
    right: 10%;
    height: 44%;
    border-color: rgba(251, 146, 60, 0.3);
  }

  .hotspot-vof {
    bottom: 3%;
    left: 4%;
    width: 36%;
    height: 25%;
    border-color: rgba(248, 113, 113, 0.35);
  }

  .hotspot-steps {
    bottom: 3%;
    left: 41%;
    width: 22%;
    height: 25%;
    border-color: rgba(250, 204, 21, 0.35);
  }

  .hotspot-range {
    bottom: 3%;
    right: 4%;
    width: 30%;
    height: 25%;
    border-color: rgba(96, 165, 250, 0.35);
  }

  .token-hotspot.highlighted {
    border-style: solid;
    border-width: 2.5px;
    background: transparent;
    box-shadow: inset 0 0 12px rgba(59, 130, 246, 0.25), 0 0 16px rgba(59, 130, 246, 0.6);
    border-radius: 4px;
    z-index: 10;
  }

  .token-hotspot.hotspot-vof.highlighted {
    border-color: #f87171;
    box-shadow: inset 0 0 10px rgba(239, 68, 68, 0.2), 0 0 16px rgba(239, 68, 68, 0.7);
  }

  .token-hotspot.hotspot-header.highlighted {
    border-color: #38bdf8;
    box-shadow: inset 0 0 10px rgba(56, 189, 248, 0.2), 0 0 16px rgba(56, 189, 248, 0.7);
  }

  .token-hotspot.hotspot-center.highlighted {
    border-color: #fb923c;
    box-shadow: inset 0 0 10px rgba(251, 146, 60, 0.2), 0 0 16px rgba(251, 146, 60, 0.7);
  }

  .token-hotspot.hotspot-steps.highlighted {
    border-color: #facc15;
    box-shadow: inset 0 0 10px rgba(250, 204, 21, 0.2), 0 0 16px rgba(250, 204, 21, 0.7);
  }

  .token-hotspot.hotspot-range.highlighted {
    border-color: #60a5fa;
    box-shadow: inset 0 0 10px rgba(96, 165, 250, 0.2), 0 0 16px rgba(96, 165, 250, 0.7);
  }

  .spatial-guide-hint {
    font-size: 0.7rem;
    color: #64748b;
    text-align: center;
    background: rgba(255, 255, 255, 0.03);
    padding: 0.35rem 0.5rem;
    border-radius: 4px;
    border: 1px dashed rgba(255, 255, 255, 0.08);
  }

  .zoom-controls {
    display: flex;
    gap: 0.3rem;
    align-items: center;
    font-size: 0.75rem;
    color: #94a3b8;
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

  .issues-box {
    width: 100%;
    background: rgba(239, 68, 68, 0.1);
    border: 1px solid #ef4444;
    border-radius: 6px;
    padding: 0.5rem 0.7rem;
    color: #fca5a5;
    font-size: 0.75rem;
  }

  .issues-box h4 {
    margin: 0 0 0.25rem;
    color: #ef4444;
  }

  .issues-box ul {
    margin: 0;
    padding-left: 1.2rem;
  }

  .ocr-evidence-box {
    width: 100%;
    background: #0b0f1a;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    padding: 0.5rem 0.7rem;
    font-size: 0.75rem;
  }

  .ocr-evidence-box h4 {
    margin: 0 0 0.3rem;
    color: #94a3b8;
  }

  .notes-text {
    font-family: monospace;
    color: #cbd5e1;
    margin: 0 0 0.4rem;
    word-break: break-all;
  }

  .labels-list {
    display: flex;
    flex-direction: column;
    gap: 0.2rem;
  }

  .label-chip {
    font-family: monospace;
    font-size: 0.65rem;
    background: #1e293b;
    color: #93c5fd;
    padding: 0.15rem 0.35rem;
    border-radius: 3px;
    word-break: break-all;
  }

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

  .badge-top {
    color: #38bdf8;
  }

  .badge-center {
    color: #fb923c;
  }

  .badge-bottom {
    color: #f87171;
  }

  .section-top .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr 2fr;
    gap: 0.6rem;
  }

  .section-center .form-grid {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.6rem;
  }

  .bottom-strip-layout {
    display: grid;
    grid-template-columns: repeat(3, minmax(0, 1fr));
    gap: 0.6rem;
  }

  .strip-cell {
    background: #090d18;
    border: 1px solid rgba(255, 255, 255, 0.06);
    border-radius: 6px;
    padding: 0.5rem 0.65rem;
    display: flex;
    flex-direction: column;
    gap: 0.4rem;
    transition: all 0.15s ease;
  }

  .strip-cell:hover {
    border-color: rgba(255, 255, 255, 0.18);
    background: #0c1222;
  }

  .cell-label {
    font-size: 0.7rem;
    font-weight: 700;
    color: #64748b;
    text-transform: uppercase;
    letter-spacing: 0.04em;
    border-bottom: 1px dashed rgba(255, 255, 255, 0.08);
    padding-bottom: 0.2rem;
    margin-bottom: 0.1rem;
  }

  .input-with-dropdown {
    display: flex;
    flex-direction: column;
    gap: 0.25rem;
  }

  .custom-input {
    border-color: #3b82f6 !important;
  }

  .form-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
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

  .drawer-footer {
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

  .save-btn:hover {
    background: #334155;
  }

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

  .save-next-btn:hover {
    background: #1d4ed8;
  }

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

  .validate-btn:hover {
    background: #064e3b;
    color: #a7f3d0;
  }

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
    to {
      transform: rotate(360deg);
    }
  }

  @media (max-width: 768px) {
    .validator-root {
      padding: 1rem;
    }
    .drawer-body {
      grid-template-columns: 1fr;
    }
    .form-grid {
      grid-template-columns: 1fr;
    }
  }
</style>
