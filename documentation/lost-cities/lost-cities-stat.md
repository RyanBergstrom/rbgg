# Lost Cities Implementation Status

**Game:** Lost Cities  
**Date:** 2026-09-11  
**Status:** COMPLETE ✅  
**Guide Version Used:** v1.1 (updated during this implementation)

## Implementation Summary

All steps from the adding-a-new-game-guide completed successfully:

### ✅ Step 1: Config YAML
- **File:** `api/configs/lost_cities.yaml`
- Panels: game_progress, main_board, player_hand
- Components: 5 expeditions × 2 players, 5 discard piles, draw pile, hand area
- Multi-phase turns: play_a_card → draw_a_card

### ✅ Step 2: Backend Validator
- **File:** `api/app/games/lost_cities/validator.py` (510 lines)
- Full game logic: 60-card deck, expeditions, discard piles, draw restrictions
- Multi-phase turn handling with current_phase tracking
- Move validation by semantic content (not move_id)
- Scoring: investment multipliers, length bonus, round transitions
- MCTS AI config: iterations=300, max_depth=40

### ✅ Step 3: Serialization Helpers
- **File:** `api/app/games/lost_cities/serialize.py` (178 lines)
- serialize_hand() — faces for human, backs for AI
- serialize_expedition() — all played cards with images
- serialize_discard_pile() — top card only
- serialize_game_data() — main entry point for screen state

### ✅ Step 3.5: Custom Panels
- player_hand panel (required: false) with hand_area component

### ✅ Step 4: Registration
- **File:** `api/app/__init__.py` — registered game and validator

### ✅ Step 5: Frontend Board
- **File:** `web/src/lib/components/games/lost_cities/LostCitiesBoard.svelte` (743 lines)
- Three-row layout: AI expeditions, discard/draw, player expeditions
- Hand area with per-card play/discard buttons
- Phase indicator, score display, winner banner

### ✅ Step 6: Backend Tests
- **File:** `api/tests/test_lost_cities.py` (54 tests, all passing)
- Card utilities, expedition legality, scoring, moves, serialization, AI

### ✅ Step 7: Test Suite Pass
- All 230 tests pass (including 54 new Lost Cities tests)
- No regressions in existing checkers tests

### ✅ Step 8: Frontend Build
- `npm run build` — compiles successfully
- Images served via static mount at `/api/v1/img/`

### ✅ Step 9: Image Assets
- Copied 31 card images + box art to `api/img/lost_cities/cards/`

## Key Patterns Established

1. **Card encoding:** `"b_5"`, `"r_i"` with COLOR_SHORT/SHORT_TO_COLOR maps
2. **Multi-phase turns:** current_phase in game_data, transitions in apply_move
3. **Move validation:** match by content (type, card, color, source) not move_id
4. **Discard draw restriction:** track last_discarded, filter in get_legal_draws
5. **Round transition:** when draw_pile empty → score → _start_new_round()
6. **Serialization for non-grid:** hand/expedition/discard as arrays of objects with images
7. **Custom panels:** player_hand with clickable hand_area component
8. **Stackable components:** expedition slots and discard piles use stack_name

## Files Created/Modified

```
api/configs/lost_cities.yaml                    ← NEW
api/app/games/lost_cities/__init__.py           ← NEW
api/app/games/lost_cities/validator.py          ← NEW
api/app/games/lost_cities/serialize.py          ← NEW
api/tests/test_lost_cities.py                   ← NEW
api/app/__init__.py                             ← MODIFIED (registration)

web/src/lib/components/games/lost_cities/LostCitiesBoard.svelte  ← NEW

api/img/lost_cities/lost-cities-box-art.webp    ← COPIED
api/img/lost_cities/cards/*.jpg (31 files)      ← COPIED
```

## Validation Checklist

- [x] `pytest tests/test_lost_cities.py -v` — 54 passed
- [x] `pytest tests/ -v --ignore=tests/test_scaffold.py` — 230 passed
- [x] `cd web && npm run build` — compiles without errors
- [x] Manual browser test: setup → play → moves → AI → win detection
- [x] No TBD/TODO/FIXME in new files