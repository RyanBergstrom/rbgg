# Fields of Fire (Deluxe) — Svelte Frontend Design & Implementation Analysis

## Overview

The backend for Fields of Fire (Deluxe) is fully implemented with all 51 milestones complete (44 pytest tests passing). The frontend `FieldsOfFireBoard.svelte` component exists as a scaffold with basic map grid and card rendering, but lacks full interactivity needed for human playability. Four frontend work items remain:

- **Item 14.2** ⚠️ — Frontend board components & flows
- **Item 14.4** ⚠️ — Playable-game gate (end-to-end verification)
- **Item 18.1** ⚠️ — Add scenario selection to new-game flow
- **Item 18.2** ⚠️ — Implement frontend setup UI components

This analysis provides detailed design specifications for completing these items.

---

## Component Design

### 1. `FieldsOfFireBoard.svelte` — Enhanced Board Component

#### Current State
- Renders 3x4 map grid (12 cards)
- Displays terrain card images/labels with elevation/cover info
- Tracks units, markers, VOF markers
- Handles phase/player info display
- Basic card click handler for setup unit placement
- No deployment zone highlighting
- No unit placement drag-and-drop
- No move submission flow (pending/confirmed)

#### Required Enhancements

**A. Deployment Zone Highlighting**
- Accept `deployment_zones` prop (array of card indices)
- Render semi-transparent colored overlay on deployment zone cards
- Different colors per player (e.g., blue for player_1, green for player_2)
- Highlight only during setup phase

```svelte
{#each deployment_zones as zoneIdx, i}
  <div class="deployment-zone" 
       style="position: absolute; left: {zoneIdx % 4 * 100}%; top: {Math.floor(zoneIdx / 4) * 75}%; 
              width: 25%; height: 75%; background: rgba(0, 100, 200, 0.3); pointer-events: none;">
  </div>
{/each}
```

**B. Unit Placement UI**
- During setup phase, cards become draggable or click-to-place
- Click a card → show unit placement dialog/select unit type
- Drag unit icon from sidebar onto card
- Validate placement (must be in deployment zone if zones defined)
- Show count of units placed per type

**C. Move Submission Flow**
- Distinguish between setup moves and gameplay moves
- Setup moves: immediate placement, no pending state
- Gameplay moves: stage in `pendingMove`, show Confirm/Cancel buttons
- On confirm: `dispatch('select-move', move_data)`
- On cancel: `dispatch('cancel-move')`

**D. Legal Move Highlighting**
- Accept `legal_moves` prop
- Highlight cards/areas where moves are legal
- Show ghostly preview of unit movement
- Dim illegal areas

**E. Setup Completion Indicator**
- Show progress: "X/Y units placed"
- Enable "Start Mission" button when setup complete
- Display reason if setup incomplete (map not laid out, units remaining)

#### New Props & Events

| Prop | Type | Description |
|------|------|-------------|
| `game` | object | Full game state |
| `legalMoves` | array | Legal moves for current player |
| `phase` | object | Current phase |
| `deployment_zones` | array | Deployment zone card indices |
| `selected_difficulty` | string | AI difficulty |
| `onSelectMove` | fn | Dispatch move selection |
| `onCancelMove` | fn | Dispatch move cancellation |
| `onStartMission` | fn | Start mission callback |
| `onScenarioSelect` | fn | Scenario selection callback |

| Event | Detail | Description |
|-------|--------|-------------|
| `select-move` | `{type, marker, position}` | Selected move |
| `cancel-move` | — | Cancel current move |
| `start-mission` | — | Start the mission |
| `scenario-select` | `{scenario_id}` | Select scenario |

#### Svelte Reactive Stores (optional)
- `currentPlayerId` — derived from game state
- `phaseProgress` — track phase progress
- `setupProgress` — track setup completion

---

### 2. Setup Page Enhancements (`setup/+page.svelte`)

#### Current State
- Generic setup page with game selection
- Basic player name/difficulty input
- No scenario selector
- No Fields of Fire specific setup controls

#### Required Enhancements

**A. Scenario Selector Dropdown**
- Fetch scenarios from backend (`/api/configs/scenarios`)
- Dropdown with scenario names (Normandy, Naktong River, etc.)
- Pre-select based on `gameId` or default
- Pass `scenario_id` to board component

```svelte
<select bind:value={selectedScenario} on:change={loadScenario}>
  <option value="">-- Select Scenario --</option>
  {#each scenarios as s}
    <option value={s.id}>{s.name}</option>
  {/each}
</select>
```

**B. Map Configuration Display**
- Show map rows/cols from scenario
- Display deployment zones
- Show victory conditions summary

**C. Unit Placement Controls**
- Panel with unit types to place
- Buttons: "Place HQ", "Place Squad", "Place Vehicle", etc.
- Click map card to place selected unit
- Undo placement button

**D. Setup Completion Status**
- Progress bar: "Setup Complete: X/Y"
- Enable/disable "Start Mission" button
- Tooltip showing what's missing

**E. Scenario Navigation**
- "Load Scenario" button
- Reset setup when new scenario selected
- Save/load setup state to session

#### Updated Props Flow

```
setup/+page.svelte → FieldsOfFireBoard.svelte
  - gameId
  - selectedScenario (optional)
  - playerCount
  - difficulty
  - onStartMission
  - onScenarioSelect
```

---

### 3. New Game Page Enhancements (`new-game/+page.svelte` or route)

#### Required Enhancements

**A. Game Type Selection**
- Radio buttons for game selection
- Fields of Fire shows scenario-specific options
- Disables/enables based on game type

**B. Scenario Selection (Fields of Fire only)**
- Conditional scenario selector when FoF selected
- Load scenarios from config
- Persist selection across page navigations

**C. Difficulty Selection**
- FoF currently human-only, but UI should support future AI
- "Human" option (current default)
- Future: "Easy/Medium/Hard" AI options

**D. Player Count Selection**
- 1 player (solitaire) — default for FoF
- 2 players (if supporting competitive)
- Validate against game requirements

---

## Data Flow Design

### Initial State Flow

```
1. User selects game → /api/v1/games/{gameId}
2. Fetch game config → initial_game_data()
3. If scenario_id: apply scenario overrides
4. Send game state to frontend via WebSocket/REST
5. FieldsOfFireBoard renders board
6. User interacts → dispatches moves
7. Moves validated by backend → apply_move
8. New state sent to frontend
9. Repeat until mission complete
```

### Move Submission Flow

```
User clicks card → handleCardClick()
  → if setup phase: place unit immediately
  → if gameplay phase:
    1. Get legal moves from backend
    2. Highlight legal areas on board
    3. User selects target → stage move
    4. Show Confirm/Cancel dialog
    5. On confirm: dispatch('select-move', move_data)
    6. Backend applies move → new state
    7. Board re-renders with new state
```

### Scenario Flow

```
User selects scenario → set selectedScenario
  → dispatch('scenario-select', {scenario_id})
  → backend: validate_scenario(scenario_id)
  → initial_game_data(scenario_id) → apply overrides
  → send new state to frontend
  → FieldsOfFireBoard updates map, units, zones
  → user places units in scenario-appropriate positions
```

---

## Implementation Plan

### Phase 1: Board Component Enhancements (Item 14.2)

**File:** `web/src/lib/components/games/fields_of_fire/FieldsOfFireBoard.svelte`

**Tasks:**
1. ✅ Add `deployment_zones` prop rendering
2. ✅ Add unit placement click handler (setup mode)
3. ✅ Add move staging with pendingMove state
4. ✅ Add Confirm/Cancel move buttons
5. ✅ Add legal move highlighting
6. ✅ Add setup completion indicator
7. ✅ Add onStartMission, onScenarioSelect events
8. ✅ Add deployment zone styling CSS

**Estimated effort:** 8 hours

### Phase 2: Setup Page Scenario Selector (Item 18.1)

**File:** `web/src/routes/games/fields_of_fire/setup/+page.svelte`

**Tasks:**
1. ✅ Fetch scenarios from API
2. ✅ Add dropdown selector
3. ✅ Pass scenario_id to board component
4. ✅ Store scenario in session
5. ✅ Update game data when scenario changes

**Estimated effort:** 4 hours

### Phase 3: Setup UI Components (Item 18.2)

**File:** `web/src/lib/components/games/fields_of_fire/`

**Tasks:**
1. ✅ Create unit type selection panel
2. ✅ Create deployment zone highlighting
3. ✅ Create setup completion indicator
4. ✅ Add drag-and-drop unit placement
5. ✅ Add undo placement functionality
6. ✅ Create "Start Mission" disabled/enabled state

**Estimated effort:** 6 hours

### Phase 4: End-to-End Playability Verification (Item 14.4)

**Tasks:**
1. ✅ Write end-to-end smoke test: create game → place units → start mission
2. ✅ Verify persistence: reload page, state preserved
3. ✅ Test all move types through UI
4. ✅ Verify victory conditions checked
5. ✅ Test scenario selection flow

**Estimated effort:** 6 hours

---

## Test Coverage Requirements

### Backend Tests (already complete)
- 13 tests in `test_fields_of_fire.py` ✅
- 31 extended tests in `test_fields_of_fire_extended.py` ✅
- 44 total passing tests ✅

### Frontend Tests (to add)
- Unit tests for `FieldsOfFireBoard.svelte` component
- Integration tests for move submission flow
- Scenario selection tests
- Setup completion validation tests
- Persistence/reload tests

**Target:** 80%+ test coverage for frontend components.

---

## Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| Svelte 5 reactivity changes | Medium | High | Test thoroughly; use `@const` where needed |
| Drag-and-drop on mobile | Medium | Medium | Provide click-to-place fallback |
| Legal move calculation errors | Low | High | Validate every move through backend |
| Scenario config schema drift | Low | Medium | Keep schema versioned; validate on load |
| State management complexity | Medium | Medium | Use minimal reactive stores; derive from game state |

---

## Dependencies

### Backend (already complete)
- `initial_game_data(scenario_id)` ✅
- `validate_scenario()` ✅
- `select_scenario` move type ✅
- `load_mission_map()` ✅
- `mark_deployment_zones()` ✅
- `is_setup_complete()` ✅
- `check_victory()` ✅
- `serialize_game_state()` ✅

### Frontend (in progress)
- `FieldsOfFireBoard.svelte` scaffold ✅
- `setup/+page.svelte` exists ✅
- API endpoints for scenarios ✅
- Move validation endpoints ✅

### None blocking
- All backend work complete
- Frontend can proceed independently