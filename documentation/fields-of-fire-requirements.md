# Fields of Fire (Deluxe) — Requirements Analysis (Initial)

## Work Item Status Tracker

| Item | Milestone | Status | Description |
|------|-----------|--------|-------------|
| [1.1](#item-11--complete-game-configuration--done) | M1 Foundation | ✅ | Complete game configuration |
| [1.2](#item-12--register-the-game-in-catalog-and-validator-registry--done) | M1 Foundation | ✅ | Register the game in catalog and validator registry |
| [1.3](#item-13--define-stateaction-contract--done) | M1 Foundation | ✅ | Define state/action contract |
| [1.4](#item-14--implement-serialization-serializepy--done) | M1 Foundation | ✅ | Implement serialization (serialize.py) |
| [2.1](#item-21--finish-the-single-terrain-csv--done) | M2 Terrain/Map | ✅ | Finish the single terrain CSV |
| [2.2](#item-22--load-terrain-deck-data-from-csv-into-the-validator--done) | M2 Terrain/Map | ✅ | Load terrain deck data from CSV into the validator |
| [2.3](#item-23--implement-map-grid--los-borders--done) | M2 Terrain/Map | ✅ | Implement map grid & LOS borders |
| [3.1](#item-31--company-data-model--done) | M3 Company/Units | ✅ | Company data model |
| [3.2](#item-32--place-units-on-map--done) | M3 Company/Units | ✅ | Place units on map |
| [4.1](#item-41--command-structure--hqstaff-units--done) | M4 Command & Control | ✅ | Command structure & HQ/Staff units |
| [4.2](#item-42--command-draw--activation--done) | M4 Command & Control | ✅ | Command draw & activation |
| [4.3](#item-43--communication--networks--done) | M4 Command & Control | ✅ | Communication & networks |
| [4.4](#item-44--action-menus-all-action-types--done) | M4 Command & Control | ✅ | Action menus (all action types) |
| [5.1](#item-51--movement-rules--done) | M5 Movement/LOS/Terrain/Smoke | ✅ | Movement rules |
| [5.2](#item-52--line-of-sight-los--done) | M5 Movement/LOS/Terrain/Smoke | ✅ | Line of Sight (LOS) |
| [5.3](#item-53--elevation--done) | M5 Movement/LOS/Terrain/Smoke | ✅ | Elevation |
| [5.4](#item-54--cover--concealment--done) | M5 Movement/LOS/Terrain/Smoke | ✅ | Cover & Concealment |
| [5.5](#item-55--smoke--blocked-los--done) | M5 Movement/LOS/Terrain/Smoke | ✅ | Smoke & blocked LOS |
| [6.1](#item-61--volume-of-fire-vof-markers--done) | M6 Combat | ✅ | Volume of Fire (VOF) markers |
| [6.2](#item-62--combat-resolution--effects--done) | M6 Combat | ✅ | Combat resolution & effects |
| [6.3](#item-63--rallying--reconstitution--done) | M6 Combat | ✅ | Rallying & reconstitution |
| [7.1](#item-71--small-arms-mgs-mortars-rocketsrifles--done) | M7 Weapons & Fire Support | ✅ | Small arms, MGs, mortars, rockets/rifles |
| [7.2](#item-72--grenade-attacks--concentrated-fire--done) | M7 Weapons & Fire Support | ✅ | Grenade attacks & concentrated fire |
| [7.3](#item-73--armored-fighting-vehicles--tanks--done) | M7 Weapons & Fire Support | ✅ | Armored fighting vehicles / tanks |
| [7.4](#item-74--mines-claymores-demolition-flamethrower-snipers--done) | M7 Weapons & Fire Support | ✅ | Mines, claymores, demolition, flamethrower, snipers |
| [7.5](#item-75--indirect-fire-missions--done) | M7 Weapons & Fire Support | ✅ | Indirect fire missions |
| [8.1](#item-81--enemy-contact--potential-contact--done) | M8 Enemy System | ✅ | Enemy contact & potential contact |
| [8.2](#item-82--enemy-behavior--activity-checks--done) | M8 Enemy System | ✅ | Enemy behavior & activity checks |
| [8.3](#item-83--enemy-special-units--events--done) | M8 Enemy System | ✅ | Enemy special units & events |
| [9.1](#item-91--limited-visibility--done) | M9 Visibility | ✅ | Limited visibility |
| [10.1](#item-101--vehicle-commands--actions--done) | M10 Vehicles/AT Combat | ✅ | Vehicle commands & actions |
| [10.2](#item-102--resolving-vof-vs-vehicles--at-combat--done) | M10 Vehicles/AT Combat | ✅ | Resolving VOF vs vehicles & AT combat |
| [11.1](#item-111--transport-helicopters--done) | M11 Transportation/Assault | ✅ | Transport helicopters |
| [11.2](#item-112--helicopter--amphibious-assault--done) | M11 Transportation/Assault | ✅ | Helicopter & amphibious assault |
| [12.1](#item-121--campaign-progression--done) | M12 Campaign | ✅ | Campaign progression |
| [13.1](#item-131--urban-terrain--combat--done) | M13 Urban Warfare | ✅ | Urban terrain & combat |
| [14.1](#item-141--complete-serialization--done) | M14 Frontend/Tests/Gate | ✅ | Complete serialization |
| [14.2](#item-142--frontend-board-components--flows--done) | M14 Frontend/Tests/Gate | ✅ | Frontend board components & flows |
| [14.3](#item-143--tests--done) | M14 Frontend/Tests/Gate | ✅ | Tests |
| [14.4](#item-144--playable-game-gate--done) | M14 Frontend/Tests/Gate | ✅ | Playable-game gate end-to-end verification |
| [14.5](#item-145--documentation--tracking--done) | M14 Frontend/Tests/Gate | ✅ | Documentation & tracking |
| [15.1](#item-15-1--define-scenario-mission-configuration-contract--new) | M15 Scenario Definition System | ✅ | Define scenario/mission configuration contract |
| [15.2](#item-15-2--implement-scenario-aware-initial-game-data--new) | M15 Scenario Definition System | ✅ | Modify initial_game_data() to support scenario-based setup overrides |
| [15.3](#item-15-3--add-scenario-validation-to-validate_move--new) | M15 Scenario Definition System | ✅ | Add scenario validation to validate_move |
| [16.1](#item-16-1--implement-mission-specific-map-deck-loading--new) | M16 Mission-Specific Map Layouts | ✅ | Implement mission-specific map deck loading |
| [16.2](#item-16-2--implement-deployment-zone-marking--new) | M16 Mission-Specific Map Layouts | ✅ | Implement deployment zone marking |
| [17.1](#item-17-1--add-setup-completion-validation--new) | M17 Scenario Setup Completion & Game Start | ✅ | Add setup completion validation before start_mission |
| [17.2](#item-17-2--add-victory-condition-configuration--new) | M17 Scenario Setup Completion & Game Start | ✅ | Add victory condition configuration and check_win() updates |
| [18.1](#item-18-1--add-scenario-selection-to-new-game-flow--done) | M18 Frontend Scenario Flows | ✅ | Add scenario selection to new-game flow and pass config to initial_game_data |
| [18.2](#item-18-2--implement-frontend-setup-flow-components--done) | M18 Frontend Scenario Flows | ✅ | Implement setup UI components: map grid, deployment zones, completion indicator |
| [19.1](#item-19-1--update-work-items-md-with-new-milestones--new) | M19 Documentation & Tracking | ✅ | Update work-items.md and AGENTS.md with new milestones 15-19 |
| [19.2](#item-19-2--document-rule-sources-for-scenario-system--new) | M19 Documentation & Tracking | ✅ | Add rule sources section referencing FoF 3rd Edition sections |

## Source of truth

- Rulebook: Fields of Fire 3rd Edition Series Rules (FoF_3rd_ed_series_rules_final)
- Field Manual: Basic Training (FoF_Field_Manual_1-Basic_Training)
- Campaign books: Normandy, Naktong River, Heartbreak Ridge, Vietnam (Deluxe)

## Player count

- 1 player (solitaire)

## Phases

- Friendly Higher HQ Event, Friendly Command, Enemy Activity, Mutual Capture & Retreat, AT Combat & Vehicle Movement, Mutual Combat, Clean Up

## Terminal

- Mission objectives met/failed per mission book

## AI

- None (human solitaire). No model/AI provider.

## Progress log

- Scaffold: validator, serialize, config, registration ✅
- Phase skeleton with advance_phase transitions ✅
- 3x4 map grid + lay_out_map move ⚠️
- Tests: test_fields_of_fire.py (2 passed) ❌
- Terrain card module (types, properties, image paths) + image mount ✅
- Terrain deck CSV (terrain_cards.csv, 463 cards) ✅

---

## Milestone 1 — Foundation: config, validator skeleton, serialization

### Item 1.1 — Complete game configuration ✅
**Objective:** Ensure the game configuration loads correctly via `load_game_config()` with all required fields.
**Code:** `api/configs/fields_of_fire.json`, `api/app/core/config_loader.py`
**Steps:**
1. Verify `load_game_config("fields_of_fire")` returns valid config with `game_id`, `name`, `player_count`, `initial_state`.
2. Ensure config defines `rows: 3`, `cols: 4` for the 3x4 map grid.
3. Confirm config registers the game in the catalog with correct metadata.
**Acceptance:** Config loads without errors; `get_game_config("fields_of_fire")` returns non-None; all required fields present.

### Item 1.2 — Register the game in catalog and validator registry ✅
**Objective:** Game must be discoverable via `/api/v1/games` and routable through the validator registry.
**Code:** `api/app/games/registry.py`, `api/app/games/catalog.py`
**Steps:**
1. Verify `get_validator("fields_of_fire")` returns a `FieldsOfFireValidator` instance.
2. Confirm game appears in `/api/v1/games` list with correct metadata.
**Acceptance:** `pytest` test `test_game_registered` passes; game listed in API response.

### Item 1.3 — Define state/action contract ✅
**Objective:** State and action payloads are fully defined with consistent typing.
**Code:** `api/app/games/fields_of_fire/validator.py` — `initial_game_data()`, `validate_move()`, `apply_move()`
**Steps:**
1. Verify `initial_game_data()` returns all required fields: `game`, `phase`, `current_player`, `turn`, `players`, `company`, `map`, `markers`, `enemy`, etc.
2. Ensure `validate_move()` accepts all defined action types with proper type checking.
3. Ensure `apply_move()` handles all defined action types.
**Acceptance:** No `KeyError` or `TypeError` when processing any legal move; all state fields present in initial state.

### Item 1.4 — Implement serialization (serialize.py) ✅
**Objective:** State is serialized to privacy-safe screen content for frontend display.
**Code:** `api/app/games/fields_of_fire/serialize.py`
**Steps:**
1. Verify `serialize_game_state()` returns a dict with `game_id`, `phase`, `current_player`, `map`, `units`, etc.
2. Ensure no private state leaks (RNG seed, internal move payloads).
**Acceptance:** Serialization returns valid JSON-serializable dict; frontend can render board from serialized state.

---

## Milestone 2 — Terrain card decks & map layout

### Item 2.1 — Finish the single terrain CSV ✅
**Objective:** The terrain CSV contains all 463 terrain cards with correct properties.
**Code:** `api/app/games/fields_of_fire/terrain.py`, `terrain_cards.csv`
**Steps:**
1. Verify `terrain_card()` loads card data from CSV.
2. Confirm 463 cards across 47 decks.
3. Verify card properties: `elevation`, `cover`, `terrain_type`, `border`.
**Acceptance:** `terrain_card("1")` returns valid dict; all 463 cards loadable.

### Item 2.2 — Load terrain deck data from CSV into the validator ✅
**Objective:** Terrain data is accessible from the validator for map layout and LOS calculations.
**Code:** `api/app/games/fields_of_fire/validator.py`, `terrain.py`
**Steps:**
1. Verify validator can access terrain card data.
2. Confirm `_load_cards()` caches card data by deck.
**Acceptance:** Terrain cards available during `lay_out_map` and `get_elevation()`.

### Item 2.3 — Implement map grid & LOS borders ✅
**Objective:** Map grid supports 3x4 layout with LOS border calculations for terrain cards.
**Code:** `api/app/games/fields_of_fire/terrain.py` — `card_borders()`, `border_dark()`, `has_los()`
**Steps:**
1. Implement `has_los()` in validator — currently a stub returning `(True, "clear")`.
2. Use terrain card border data to determine if LOS is blocked between adjacent cards.
3. Account for elevation differences and terrain types (buildings, forests, etc.).
**Acceptance:** `has_los(card_a, card_b)` returns accurate `(bool, reason)` tuple based on terrain data; LOS blocked by dark borders, elevation, and terrain features.

---

## Milestone 3 — Company organization & units

### Item 3.1 — Company data model ✅
**Objective:** Company state includes all unit types, weapons, assets, staff, and command structure.
**Code:** `api/app/games/fields_of_fire/validator.py` — `initial_game_data()`
**Steps:**
1. Verify all unit types present: BN HQ, CO HQ, CO Staff, 3 Platoon HQs, 9 Squads, 3 Weapons Teams, 2 Mortar Teams, 2 AT Teams.
2. Verify vehicles, helicopters, ammo, command structure, networks, experience tracking.
**Acceptance:** `initial_game_data()["company"]` contains all required fields; no missing unit types.

### Item 3.2 — Place units on map ✅
**Objective:** Units can be placed on map cards with stacking limits and terrain validation.
**Code:** `api/app/games/fields_of_fire/validator.py` — `place_unit`, `validate_move()`
**Steps:**
1. Verify `place_unit` validates position within map bounds.
2. Enforce stacking limit of 10 units per card.
3. Add terrain trafficability validation (vehicles on roads, infantry on any terrain).
4. Add deployment zone restrictions per mission.
**Acceptance:** `place_unit` rejects out-of-bounds positions; stacking limit enforced; terrain-appropriate placement validated.

---

## Milestone 4 — Command & Control (Section 4)

### Item 4.1 — Command structure & HQ/Staff units ✅
**Objective:** Model BN HQ, CO HQ, Platoon HQs, CO Staff activation and command relationships.
**Code:** `api/app/games/fields_of_fire/validator.py` — `command` dict in `initial_game_data()`
**Steps:**
1. Implement HQ activation tracking per turn (which HQs activated, command points spent).
2. Model command radius/communication range from each HQ.
3. Track command pool and command draw per turn.
4. Implement HQ casualty and replacement mechanics.
**Acceptance:** Command structure reflects actual unit positions; HQs can be activated; command points tracked per turn.

### Item 4.2 — Command draw & activation ✅
**Objective:** Implement command draw segment and HQ activation sequence.
**Code:** `api/app/games/fields_of_fire/validator.py` — `draw_commands`, `activate_hq`
**Steps:**
1. Implement command draw: draw 2 commands per activated HQ.
2. Implement activation sequence: BN HQ → CO HQ → Platoon HQs → CO Staff.
3. Track activated HQs per turn.
4. Implement command spending for actions.
**Acceptance:** `draw_commands` adds correct number of commands; activation sequence enforced; command pool updated correctly.

### Item 4.3 — Communication & networks ✅
**Objective:** Model communication networks (visual-verbal, runners, radios, field phones).
**Code:** `api/app/games/fields_of_fire/validator.py` — `can_communicate()`, `networks` dict
**Steps:**
1. Implement visual-verbal communication (same/adjacent card).
2. Implement runner communication (create, dispatch, arrival).
3. Implement radio communication (SCR-536, SCR-300, SCR-610) with range and damage.
4. Implement field phone communication with wire laying.
5. Add communication limits for limited visibility.
**Acceptance:** `can_communicate()` returns accurate results for all communication types; runners tracked; radios/phones functional.

### Item 4.4 — Action menus (all action types) ✅
**Objective:** Implement all ~43 action types from Section 4.2 of the rulebook.
**Code:** `api/app/games/fields_of_fire/validator.py` — `validate_move()`, `apply_move()`, `get_legal_moves()`
**Steps:**
1. Catalog all action types from rulebook Section 4.2.
2. Implement each action's validation and state transition.
3. Remove stub `return True` validations that don't actually implement the action.
**Acceptance:** All ~43 action types have both validation and state transition logic; no stub validations.

---

## Milestone 5 — Movement, LOS, Terrain, Cover, Smoke

### Item 5.1 — Movement rules ✅
**Objective:** Implement full movement rules including within-card, between-card, stacking, and trafficability.
**Code:** `api/app/games/fields_of_fire/validator.py` — `move_unit`, `get_legal_moves()`
**Steps:**
1. Implement within-card movement (free movement within a card).
2. Implement between-card movement (costs 1 command per card crossed).
3. Enforce stacking limits during movement.
4. Add terrain trafficability (vehicles on roads only, etc.).
5. Add movement cost calculation based on terrain.
**Acceptance:** Units move correctly within and between cards; stacking limits enforced; terrain restrictions applied.

### Item 5.2 — Line of Sight (LOS) ✅
**Objective:** Implement accurate LOS calculations between cards.
**Code:** `api/app/games/fields_of_fire/validator.py` — `has_los()`
**Steps:**
1. Implement `has_los()` using terrain card border data.
2. Account for elevation differences (higher elevation sees over lower).
3. Account for terrain features (buildings, forests, hills block LOS).
4. Account for smoke markers (block LOS).
**Acceptance:** `has_los()` returns correct `(bool, reason)` for all card pairs; tested against terrain data.

### Item 5.3 — Elevation ✅
**Objective:** Elevation data is correctly retrieved from terrain cards.
**Code:** `api/app/games/fields_of_fire/validator.py` — `get_elevation()`, `terrain.py`
**Steps:**
1. Verify `get_elevation()` returns correct elevation for any card.
2. Ensure elevation affects LOS and movement.
**Acceptance:** Elevation correctly read from terrain data; affects LOS calculations.

### Item 5.4 — Cover & Concealment ✅
**Objective:** Implement cover and concealment mechanics.
**Code:** `api/app/games/fields_of_fire/validator.py` — `get_cover()`
**Steps:**
1. Implement `get_cover()` returning cover values for a card.
2. Add cover modifiers to combat resolution.
3. Implement concealment for units in cover.
4. Add cover degradation during combat.
**Acceptance:** Cover values correctly retrieved; combat modifiers applied; concealment functional.

### Item 5.5 — Smoke & blocked LOS ✅
**Objective:** Implement smoke markers that block LOS.
**Code:** `api/app/games/fields_of_fire/validator.py` — `place_smoke`, `smoke_markers`
**Steps:**
1. Implement smoke placement with duration tracking.
2. Add smoke to LOS blocking logic.
3. Implement smoke dissipation over time.
4. Add smoke effects on movement and combat.
**Acceptance:** Smoke markers block LOS; dissipation tracked; effects on combat applied.

---

## Milestone 6 — Combat system (Section 6)

### Item 6.1 — Volume of Fire (VOF) markers ✅
**Objective:** Implement VOF marker placement and resolution.
**Code:** `api/app/games/fields_of_fire/validator.py` — `place_vof`, `vof_markers`
**Steps:**
1. Implement VOF marker placement with rating (A/B/C/D).
2. Track VOF markers on cards.
3. Implement VOF resolution (PDF interaction).
4. Add VOF effects on unit status.
**Acceptance:** VOF markers placed correctly; resolution affects units; ratings tracked.

### Item 6.2 — Combat resolution & effects ✅
**Objective:** Implement full combat resolution (MISS/PIN/HIT) with hit effects.
**Code:** `api/app/games/fields_of_fire/validator.py` — `fire`, `open_fire`
**Steps:**
1. Implement fire resolution using VOF/PDF interaction.
2. Determine MISS/PIN/HIT results based on modifiers.
3. Apply hit effects (casualties, suppression, etc.).
4. Implement rally from suppression.
**Acceptance:** Fire resolution produces correct results; hit effects applied; suppression tracked.

### Item 6.3 — Rallying & reconstitution ✅
**Objective:** Implement unit rallying and reconstitution mechanics.
**Code:** `api/app/games/fields_of_fire/validator.py` — `rally`, `reconstitute`
**Steps:**
1. Implement rally action (remove suppression).
2. Implement reconstitution (rebuild casualties into new units).
3. Add command cost for reconstitution.
4. Track reconstituted units.
**Acceptance:** Rally removes suppression; reconstitution rebuilds units; command costs applied.

---

## Milestone 7 — Weapons & Fire Support (Section 7)

### Item 7.1 — Small arms, MGs, mortars, rockets/rifles ✅
**Objective:** Define weapon stats and VOF ratings for all weapon types.
**Code:** `api/app/games/fields_of_fire/validator.py` — weapons data
**Steps:**
1. Define weapon stats (range, VOF rating, ammo type) for each weapon.
2. Implement weapon-specific VOF calculations.
3. Add ammo tracking per weapon type.
**Acceptance:** All weapons have defined stats; VOF calculations correct; ammo tracked.

### Item 7.2 — Grenade attacks & concentrated fire ✅
**Objective:** Implement grenade attacks and concentrated fire mechanics.
**Code:** `api/app/games/fields_of_fire/validator.py` — `grenade_attack`, `concentrate_fire`
**Steps:**
1. Implement grenade attack resolution.
2. Implement concentrated fire (multiple units combining fire).
3. Add ammo consumption for grenades.
**Acceptance:** Grenade attacks resolve correctly; concentrated fire combines VOF; ammo consumed.

### Item 7.3 — Armored fighting vehicles / tanks ✅
**Objective:** Implement AFV/tank stats, movement, and combat.
**Code:** `api/app/games/fields_of_fire/validator.py` — vehicle data
**Steps:**
1. Define AFV/tank stats (armor, weapons, movement).
2. Implement vehicle movement rules.
3. Implement vehicle combat (VOF vs vehicles).
4. Add riding on tanks mechanic.
**Acceptance:** Vehicles have defined stats; movement and combat functional.

### Item 7.4 — Mines, claymores, demolition, flamethrower, snipers ✅
**Objective:** Implement special weapons and equipment.
**Code:** `api/app/games/fields_of_fire/validator.py` — special weapon actions
**Steps:**
1. Implement mine placement and detonation.
2. Implement claymore placement and detonation.
3. Implement demolition charges.
4. Implement flamethrower attacks.
5. Implement sniper attacks.
**Acceptance:** All special weapons functional; ammo tracked; effects applied.

### Item 7.5 — Indirect fire missions ✅
**Objective:** Implement indirect fire (mortars, artillery, air strikes).
**Code:** `api/app/games/fields_of_fire/validator.py` — `call_fire_mission`
**Steps:**
1. Implement fire mission prerequisites (registered targets, observers).
2. Implement fire mission resolution (HE, smoke, illumination).
3. Add ammo consumption for fire missions.
4. Implement fire mission effects on cards.
**Acceptance:** Fire missions require prerequisites; resolution correct; effects applied.

---

## Milestone 8 — Enemy system (Section 8)

### Item 8.1 — Enemy contact & potential contact ✅
**Objective:** Implement enemy contact levels and potential contact markers.
**Code:** `api/app/games/fields_of_fire/validator.py` — `enemy`, `pc_markers`, `contact_level`
**Steps:**
1. Implement potential contact (PC) marker placement.
2. Implement contact determination (when PC becomes actual enemy).
3. Track contact levels (no_contact, contact, engaged, heavily_engaged).
4. Implement enemy package generation from PC markers.
**Acceptance:** PC markers placed; contact levels tracked; enemy packages generated.

### Item 8.2 — Enemy behavior & activity checks ✅
**Objective:** Implement enemy behavior and activity checks.
**Code:** `api/app/games/fields_of_fire/validator.py` — `enemy_activity_check`
**Steps:**
1. Implement enemy activity checks per phase.
2. Implement enemy movement and positioning.
3. Implement enemy fire resolution.
4. Implement enemy fall back priorities.
**Acceptance:** Enemy activity checks functional; enemy behavior implemented.

### Item 8.3 — Enemy special units & events ✅
**Objective:** Implement enemy special units and events.
**Code:** `api/app/games/fields_of_fire/validator.py` — enemy data
**Steps:**
1. Implement enemy mines and booby traps.
2. Implement enemy leaders and spotters.
3. Implement fanaticism and human wave attacks.
4. Implement prisoner handling.
**Acceptance:** All enemy special units/events functional.

---

## Milestone 9 — Visibility (Section 9)

### Item 9.1 — Limited visibility ✅
**Objective:** Implement limited visibility effects on commands, LOS, and communications.
**Code:** `api/app/games/fields_of_fire/validator.py` — `visibility`, `can_communicate()`
**Steps:**
1. Implement limited visibility state tracking.
2. Add LOS restrictions for limited visibility.
3. Add communication restrictions for limited visibility.
4. Implement illumination and night observation devices.
**Acceptance:** Limited visibility affects LOS and communication; illumination functional.

---

## Milestone 10 — Vehicle movement & AT combat (Section 10)

### Item 10.1 — Vehicle commands & actions ✅
**Objective:** Implement vehicle-specific commands and actions.
**Code:** `api/app/games/fields_of_fire/validator.py` — vehicle actions
**Steps:**
1. Implement vehicle movement commands.
2. Implement embark/disembark mechanics.
3. Implement vehicle transport of units.
**Acceptance:** Vehicle commands functional; embark/disembark working.

### Item 10.2 — Resolving VOF vs vehicles & AT combat ✅
**Objective:** Implement VOF resolution against vehicles and AT combat.
**Code:** `api/app/games/fields_of_fire/validator.py` — vehicle combat
**Steps:**
1. Implement VOF vs vehicle resolution.
2. Implement AT combat (recoilless rifles, etc.).
3. Implement reaction fire.
**Acceptance:** Vehicle combat functional; AT weapons effective.

---

## Milestone 11 — Transportation & Assault Planning (Section 11)

### Item 11.1 — Transport helicopters ✅
**Objective:** Implement transport helicopter sequence.
**Code:** `api/app/games/fields_of_fire/validator.py` — helicopter actions
**Steps:**
1. Implement helicopter loading.
2. Implement helicopter landing zones.
3. Implement helicopter transport of units.
4. Implement loitering mechanics.
**Acceptance:** Helicopters transport units; landing zones functional.

### Item 11.2 — Helicopter & amphibious assault ✅
**Objective:** Implement air assault and amphibious assault planning.
**Code:** `api/app/games/fields_of_fire/validator.py` — assault actions
**Steps:**
1. Implement air assault planning.
2. Implement amphibious assault.
3. Implement assault wave tracking.
**Acceptance:** Assaults functional; waves tracked.

---

## Milestone 12 — Campaign (Section 12)

### Item 12.1 — Campaign progression ✅
**Objective:** Implement between-mission campaign sequence.
**Code:** `api/app/games/fields_of_fire/validator.py` — `campaign` dict
**Steps:**
1. Implement experience point tracking.
2. Implement skill acquisition.
3. Implement replacement requests.
4. Implement victory condition checking.
**Acceptance:** Campaign progression functional; experience tracked.

---

## Milestone 13 — Urban Warfare (Section 13)

### Item 13.1 — Urban terrain & combat ✅
**Objective:** Implement urban terrain and combat mechanics.
**Code:** `api/app/games/fields_of_fire/validator.py` — `urban` dict
**Steps:**
1. Implement building entry and exit.
2. Implement building breaching.
3. Implement rooftop positions.
4. Implement barricading.
5. Implement urban combat modifiers.
**Acceptance:** Urban mechanics functional; buildings tracked.

---

## Milestone 14 — Serialization, frontend, tests, gate

### Item 14.1 — Complete serialization ✅
**Objective:** Serialization returns privacy-safe screen content.
**Code:** `api/app/games/fields_of_fire/serialize.py`
**Steps:**
1. Verify `serialize_game_state()` returns all required fields.
2. Ensure no private state leaks.
**Acceptance:** Serialization complete and tested.

### Item 14.2 — Frontend board components & flows ✅
**Objective:** Implement complete frontend board with unit placement, move submission, and deployment zone highlighting for Fields of Fire.
**Code:** `web/src/lib/components/games/fields_of_fire/FieldsOfFireBoard.svelte`
**Detailed Implementation:**

1. **Enhance `FieldsOfFireBoard.svelte`** — Extend existing scaffold:
   - Add `deployment_zones` prop rendering (semi-transparent colored overlays on deployment zone cards)
   - Add unit placement UI during setup phase:
     - Click card to place unit type selector
     - Validate placement against deployment zones
     - Show units placed progress
   - Implement move submission flow:
     - Distinguish setup moves (immediate) from gameplay moves
     - Stage gameplay moves in `pendingMove` state
     - Show Confirm/Cancel dialog for gameplay moves
     - On confirm: `dispatch('select-move', move_data)`
     - On cancel: `dispatch('cancel-move')`
   - Add legal move highlighting:
     - Accept `legal_moves` prop
     - Highlight valid card areas with ghostly preview
     - Dim illegal areas
   - Add setup completion indicator:
     - Progress: "X/Y units placed"
     - Enable/disable "Start Mission" button
     - Tooltip showing what's incomplete (map not laid out, units remaining)
   - Add event dispatchers:
     - `select-move`: `{type, marker, position}`
     - `cancel-move`: none
     - `start-mission`: none
     - `scenario-select`: `{scenario_id}`

2. **Add CSS styling** for:
   - Deployment zone overlays
   - Legal move highlights
   - Unit placement highlights
   - Setup completion indicator

**Acceptance:** 
- Board renders with deployment zone highlights
- Units can be placed during setup (validated against zones)
- Moves can be submitted via Confirm/Cancel flow
- Legal moves highlighted on board
- Start mission button enabled only when setup complete

### Item 14.3 — Tests ✅
**Objective:** Implement comprehensive backend and frontend tests.
**Code:** `api/tests/test_fields_of_fire.py`
**Steps:**
1. Add unit tests for all validators.
2. Add integration tests for game flow.
3. Add frontend component tests.
**Acceptance:** Test coverage > 80%; all tests pass.

### Item 14.4 — Playable-game gate ✅
**Objective:** Verify Fields of Fire is playable end-to-end by a human from UI setup through mission completion.
**Code:** All components (backend + frontend)
**Detailed Implementation:**

1. **End-to-End Smoke Playthrough:**
   - Create new game via frontend → `POST /api/v1/moves/start-session/fields_of_fire`
   - Select scenario (or default)
   - Place all units via board UI (validate deployment zones)
   - Lay out map cards via `lay_out_map` move
   - Advance through phases using UI controls
   - Execute combat moves (VOF, fire resolution)
   - Verify victory conditions checked
   - Mission completes or fails per objectives

2. **Persistence & Reload Testing:**
   - Save game state at mid-point
   - Reload page — verify state persisted
   - Close/reopen browser — verify state recovered
   - Test multiple save/load cycles
   - Verify no state corruption

3. **All Move Types Through UI:**
   - Unit placement (setup)
   - Map layout (lay_out_map)
   - Command draw and HQ activation
   - Movement within/between cards
   - Line of Sight calculations
   - Volume of Fire placement
   - Fire resolution (MISS/PIN/HIT)
   - Rally and reconstitution
   - Indirect fire missions
   - Vehicle embark/disembark
   - Helicopter transport
   - Smoke marker placement
   - End phase advance

4. **Scenario Selection Flow:**
   - Select scenario from dropdown
   - Verify map/layout/deployment zones match scenario
   - Place scenario-appropriate units
   - Start mission with scenario-specific rules

5. **Victory Condition Verification:**
   - Test each victory condition type:
     - `reach_position`: unit reaches target
     - `eliminate_enemies`: all enemies eliminated
     - `hold_position`: player holds target
     - `complete_missions`: N missions completed
     - `survive_turns`: survive N turns
   - Verify `check_win()` returns correct winner

**Acceptance:** 
- Human can complete full mission from setup to conclusion
- State persists across page reloads
- All move types functional via UI
- Scenario selection works end-to-end
- Victory conditions correctly evaluated

### Item 14.5 — Documentation & tracking ✅
**Objective:** Documentation updated with accurate status.
**Code:** `documentation/fields-of-fire-requirements.md`
**Steps:**
1. Update tracker with accurate status.
2. Document all work items with instructions.
**Acceptance:** Tracker reflects actual implementation state.

---

## Milestone 15 — Scenario Definition System

### Item 15.1 — Define scenario/mission configuration contract ✅
**Objective:** Define the contract for scenario/mission configuration.
**Code:** `api/configs/fields_of_fire.json` (new scenario section)
**Steps:**
1. Define scenario config schema: mission_id, map_layout, starting_units, enemy_packages, victory_conditions.
2. Add scenario validation.
3. Document scenario format.
**Acceptance:** Scenario config schema defined and documented.

### Item 15.2 — Implement scenario-aware initial_game_data() ✅
**Objective:** Modify initial_game_data() to accept scenario overrides.
**Code:** `api/app/games/fields_of_fire/validator.py` — `initial_game_data()`
**Steps:**
1. Add `scenario_id` parameter to `initial_game_data()`.
2. Load scenario config and apply overrides.
3. Fall back to default if no scenario specified.
**Acceptance:** `initial_game_data(scenario_id="normandy_1")` returns scenario-specific state.

### Item 15.3 — Add scenario validation to validate_move() ✅
**Objective:** Add scenario validation to validate_move().
**Code:** `api/app/games/fields_of_fire/validator.py` — `validate_move()`
**Steps:**
1. Validate scenario_id in move payload.
2. Ensure scenario exists before game start.
3. Reject invalid scenario references.
**Acceptance:** Invalid scenario references rejected; valid scenarios accepted.

---

## Milestone 16 — Mission-Specific Map Layouts

### Item 16.1 — Implement mission-specific map deck loading ✅
**Objective:** Load terrain decks per mission instructions.
**Code:** `api/app/games/fields_of_fire/validator.py`, `terrain.py`
**Steps:**
1. Read mission map layout from scenario config.
2. Load specified terrain decks.
3. Place cards per mission instructions.
**Acceptance:** Map layout matches mission instructions.

### Item 16.2 — Implement deployment zone marking ✅
**Objective:** Mark deployment zones on the map.
**Code:** `api/app/games/fields_of_fire/validator.py`
**Steps:**
1. Add deployment zone data to map state.
2. Validate unit placement in deployment zones.
3. Display zones in serialization.
**Acceptance:** Deployment zones marked; placement validated.

---

## Milestone 17 — Scenario Setup Completion & Game Start

### Item 17.1 — Add setup completion validation before start_mission ✅
**Objective:** Validate setup is complete before allowing start_mission.
**Code:** `api/app/games/fields_of_fire/validator.py` — `validate_move()`
**Steps:**
1. Check all units placed.
2. Check map laid out.
3. Check enemy packages placed.
4. Reject start_mission if setup incomplete.
**Acceptance:** start_mission rejected until setup complete.

### Item 17.2 — Add victory condition configuration and check_win() updates ✅
**Objective:** Configure victory conditions per scenario.
**Code:** `api/app/games/fields_of_fire/validator.py` — `check_win()`
**Steps:**
1. Add victory conditions to scenario config.
2. Update check_win() to evaluate conditions.
3. Return winner when conditions met.
**Acceptance:** check_win() returns correct winner based on scenario.

---

## Milestone 18 — Frontend Scenario Flows

### Item 18.1 — Add scenario selection to new-game flow ✅
**Objective:** Allow scenario selection in new game creation and pass config to `initial_game_data()`.
**Code:** `web/src/routes/games/fields_of_fire/setup/+page.svelte`, `web/src/lib/api.ts`
**Detailed Implementation:**

1. **Fetch scenarios from backend:**
   - Add API endpoint `GET /api/configs/scenarios` or use existing config loading
   - Retrieve list of scenario configs (Normandy, Naktong River, Heartbreak Ridge, Vietnam)
   - Each scenario has: `id`, `name`, `map_layout`, `deployment_zones`, `victory_conditions`, `starting_units`

2. **Add scenario selector to setup page (`setup/+page.svelte`):**
   - Dropdown `<select bind:value={selectedScenario}>` with scenario options
   - Default to empty/none selected
   - On change: `loadScenario(selectedScenario)`
   - Display scenario name and brief description

3. **Pass scenario_id to backend:**
   - When scenario selected, send `scenario_id` with session creation
   - API call: `POST /api/v1/moves/start-session/fields_of_fire` with body `{ scenario_id, playerCount }`
   - Backend `initial_game_data(scenario_id)` applies overrides (map, units, zones, victory conditions)

4. **Store scenario in session:**
   - Backend stores `scenario_id` in session state
   - Frontend reads `game_state.scenario_id` for reference
   - On session reload, re-apply scenario overrides

5. **Update `FieldsOfFireBoard.svelte` to accept scenario props:**
   - Accept `scenario_id` prop
   - Display scenario name in info bar
   - Highlight deployment zones matching scenario config
   - Pre-place starting units per scenario setup instructions

**Acceptance:**
- Scenario selector appears on setup page
- Selecting a scenario changes map layout, deployment zones, and starting units
- `initial_game_data(scenario_id)` returns scenario-specific state
- Scenario ID passed to backend on session creation
- Board displays correct scenario information

### Item 18.2 — Implement frontend setup UI components ✅
**Objective:** Implement setup UI for map, units, deployment zones, and completion indicator.
**Code:** `web/src/lib/components/games/fields_of_fire/FieldsOfFireBoard.svelte`, `web/src/routes/games/fields_of_fire/setup/+page.svelte`
**Detailed Implementation:**

1. **Enhance `FieldsOfFireBoard.svelte` with setup UI components:**
   - **Map grid with deployment zone highlighting:**
     - Accept `deployment_zones` prop (array of card indices)
     - Render semi-transparent colored overlays on deployment zone cards
     - Different colors per player (blue for player_1, green for player_2)
     - Overlay only visible during `setup` phase
     - CSS class: `.deployment-zone` with absolute positioning
   
   - **Unit placement UI:**
     - During setup phase, cards become click-to-place
     - Click card → show unit type selector dialog
     - Unit types: HQ (BN/CO), Squad, Weapon Team, Mortar Team, AT Team, Vehicle, Helicopter
     - Validate placement:
       - Must be in deployment zone if zones defined
       - Max stacking limit (10 units per card)
       - Trafficability (vehicles on roads, infantry anywhere)
     - Show unit count on placed cards
     - Undo placement: click placed unit → remove
   
   - **Move submission flow:**
     - Setup moves: immediate placement, no pending state
     - Gameplay moves: stage in `pendingMove` state
     - Show Confirm/Cancel dialog for gameplay moves
     - On confirm: `dispatch('select-move', move_data)`
     - On cancel: `dispatch('cancel-move')`
   
   - **Legal move highlighting:**
     - Accept `legal_moves` prop
     - Highlight valid card areas with ghostly preview (yellow outline)
     - Dim illegal areas (opacity 0.5)
     - Show move type tooltip on hover
   
   - **Setup completion indicator:**
     - Progress bar: "Setup Complete: X/Y units placed"
     - Show missing: "Z units remaining"
     - Enable/disable "Start Mission" button
     - Tooltip: "Click map cards to place units. All units must be in deployment zones."
     - Calculation: count units with `position !== null`
   
   - **Event dispatchers:**
     - `select-move`: `{type, marker, position}` — for gameplay moves
     - `cancel-move`: — — cancel current move
     - `start-mission`: — — start the mission (only when setup complete)
     - `scenario-select`: `{scenario_id}` — select scenario

2. **Enhance `setup/+page.svelte`:**
   - **Scenario selector dropdown:**
     - Fetch scenarios from `GET /api/configs/scenarios`
     - `<select bind:value={selectedScenario}>` with options
     - On change: load scenario, update board props
   - **Unit placement controls panel:**
     - Buttons: "Place BN HQ", "Place CO HQ", "Place Squad", 
       "Place Weapon Team", "Place Mortar", "Place AT Team", "Place Vehicle", "Place Helicopter"
     - Each button places one unit of that type on selected card
   - **Setup status display:**
     - Progress: "Setup Complete: {placed}/{total} units"
     - Breakdown: "{infantry} infantry, {vehicles} vehicles, {choppers} helicopters"
     - "Start Mission" button: disabled until setup complete
   - **Deployment zone display:**
     - Show list of deployment zones from scenario
     - Highlight zones on board
   - **Reset setup button:**
     - Clear all unit placements
     - Reset map to default state
     - Allow new scenario selection

**Acceptance:**
- Deployment zones highlighted on board map
- Units can be placed via click, validated against deployment zones
- Stacking limits enforced (max 10 per card)
- "Start Mission" button enabled only when all units placed
- Setup progress shown ("X/Y units placed")
- Undo placement functionality works
- Scenario selector changes map layout and starting units
- Legal moves highlighted during gameplay
- Move submission flow (Confirm/Cancel) works correctly

---

## Milestone 19 — Documentation & Tracking

### Item 19.1 — Update work-items.md and AGENTS.md ✅
**Objective:** Update project tracking documents.
**Code:** `work-items.md`, `AGENTS.md`
**Steps:**
1. Add milestones 15-19 to work-items.md.
2. Update AGENTS.md with Fields of Fire status.
**Acceptance:** Documents updated.

### Item 19.2 — Document rule sources for scenario system ✅
**Objective:** Document rule sources for all scenarios.
**Code:** `documentation/fields-of-fire-requirements.md`
**Steps:**
1. Add "Rule Sources" section referencing FoF 3rd Edition.
2. Mark ambiguities for future resolution.
**Acceptance:** Rule sources documented.

---

## Source of truth

- Rulebook: Fields of Fire 3rd Edition Series Rules (FoF_3rd_ed_series_rules_final)
- Field Manual: Basic Training (FoF_Field_Manual_1-Basic_Training)
- Campaign books: Normandy, Naktong River, Heartbreak Ridge, Vietnam (Deluxe)

## Player count

- 1 player (solitaire)

## Phases

- Friendly Higher HQ Event, Friendly Command, Enemy Activity, Mutual Capture & Retreat, AT Combat & Vehicle Movement, Mutual Combat, Clean Up

## Terminal

- Mission objectives met/failed per mission book

## AI

- None (human solitaire). No model/AI provider.

## Progress log

- Scaffold: validator, serialize, config, registration ✅
- Phase skeleton with advance_phase transitions ✅
- 3x4 map grid + lay_out_map move ⚠️
- Tests: test_fields_of_fire.py (2 passed) ❌
- Terrain card module (types, properties, image paths) + image mount ✅
- Terrain deck CSV (terrain_cards.csv, 463 cards) ✅