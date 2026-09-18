# Implementation State — Core-First Checkers

**Last updated:** 2026-09-05
**Status:** Phase 2 complete, Phase 4 in progress

---

## Current State Summary

| Phase | Status | Notes |
|-------|--------|-------|
| Phase 0: Archive Santorini | DONE | Files moved to `api/app/games/_archived/santorini/`, all references cleaned |
| Phase 1a: Fix game_state.py | DONE | Multi-player GameState, game_data, version, winner |
| Phase 1b: Fix legal_move_interface.py | DONE | 4 abstract methods: validate_move, get_legal_moves, apply_move, check_win |
| Phase 1c: Fix engine.py | DONE | Real version check, RNG advance, apply_move + check_win in pipeline |
| Phase 1d: Fix config_loader + config_schema | DONE | `load_game_config()`, `to_dict()` methods |
| Phase 1e: Fix game_store.py | DONE | Already cleaned in Phase 0 |
| Phase 1f: Fix rng.py | DONE | Real `random.Random(seed)` with JSON serialization, `_to_tuple` fix |
| Phase 2: Build Checkers backend | DONE | validator.py, serialize.py, checkers.yaml, 25 tests |
| Phase 3: Wire routes | DONE | Routes already generic from Phase 0; start_session calls `initial_game_data()` |
| Phase 4: Build Checkers frontend | IN PROGRESS | CheckersBoard.svelte created, play page updated for move events |
| Phase 5: Full test verification | NOT STARTED | |

**78/78 tests pass** (excluding pre-existing `test_scaffold.py` failures)

---

## What Was Done

### Phase 0: Archive Santorini
- `api/app/games/santorini/` → `api/app/games/_archived/santorini/`
- All routes, catalog, registry, game_store, api.ts, play page rewritten game-agnostic
- `tests/conftest.py` — `ensure_db` autouse fixture

### Phase 1a: Fix game_state.py
- `players: list[PlayerInfo]`, `current_player_index`, `game_type`, `game_data`, `version`, `winner`
- Pydantic v2 `@field_validator`, `datetime.now(timezone.utc)`

### Phase 1b: Fix legal_move_interface.py
- Added abstract methods: `get_legal_moves`, `apply_move`, `check_win`
- Added `initial_game_data()` (non-abstract, returns `{}`)
- Added `recommend_ai_move()` (non-abstract, returns first candidate)
- Updated `_ConcreteLegalMoveValidator` test stubs

### Phase 1c: Fix engine.py
- Real version check: `expected_version != state.get("version", 0)` raises `ValueError`
- RNG: creates `random.Random(seed)`, advances with `rng.random()` after each move, serializes back
- `submit_move` returns `{move_id, status, new_state, winner}`
- `get_legal_moves_for_player` delegates to validator
- `get_ai_move` delegates to `validator.recommend_ai_move`

### Phase 1d: Fix config_loader + config_schema
- `load_game_config(game_id) -> GameConfig` loads from `configs/{game_id}.yaml`, cached
- `GameConfig.to_dict()`, `PanelConfig.to_dict()`, `ComponentConfig.to_dict()`, `PhaseConfig.to_dict()`
- Added `pyyaml` to `pyproject.toml`

### Phase 1f: Fix rng.py
- `create_rng(seed, state_json)` — creates `random.Random(seed)` and restores state from JSON
- `serialize_rng(rng)` — `json.dumps(rng.getstate())`
- `_to_tuple(obj)` — recursively converts JSON lists back to tuples for `setstate()`

### Phase 2: Build Checkers backend
- `api/app/games/checkers/__init__.py`
- `api/app/games/checkers/validator.py` — `CheckersValidator(LegalMoveValidator)` implementing full American checkers rules
- `api/app/games/checkers/serialize.py` — `initial_board()`, `board_to_dict()`, `state_response()`
- `api/configs/checkers.yaml` — game configuration
- `api/tests/test_checkers.py` — 25 tests covering initial board, simple moves, jumps, mandatory jumps, king promotion, win detection, AI
- Registered in `app/__init__.py`: `register_game("checkers", ...)` + `register_validator("checkers", CheckersValidator())`

### Phase 3: Wire routes
- `start_session` now calls `validator.initial_game_data()` to populate `game_data` on GameState
- Routes were already generic from Phase 0

### Phase 4: Build Checkers frontend (in progress)
- `web/src/lib/components/games/checkers/CheckersBoard.svelte` — interactive 8×8 board with piece selection, move highlighting, dispatches `move` event
- `web/src/routes/games/[gameId]/play/+page.svelte` — updated to handle `on:move` event, auto-starts session if none exists, calls `makeMove` on board move

---

## Quick Resume Commands

```bash
# Run all tests (excluding scaffold)
cd api && python -m pytest tests/ -v --tb=short --ignore=tests/test_scaffold.py

# Run checkers tests
cd api && python -m pytest tests/test_checkers.py -v --tb=short

# Start API server
cd api && python -m uvicorn app:app --host 127.0.0.1 --port 8000 --reload

# Start frontend
cd web && npm run dev
```

---

## Architecture Reminder

The core provides reusable infrastructure that games plug into:

| Core Module | Purpose | Games implement |
|-------------|---------|-----------------|
| `game_state.py` | Canonical GameState envelope (players, turn, game_data) | Populate `game_data` dict |
| `legal_move_interface.py` | Abstract `LegalMoveValidator` with validate_move, get_legal_moves, apply_move, check_win | Subclass this |
| `engine.py` | `MovePipeline` — defense-in-depth move processing | Use via routes |
| `config_loader.py` | Load + validate YAML configs | Write `configs/{game}.yaml` |
| `config_schema.py` | `GameConfig`, `PanelConfig`, `ComponentConfig`, `PhaseConfig` | Follow schema |
| `rng.py` | Deterministic RNG for replay | Use via MovePipeline |
| `game_store.py` | In-memory state store | Routes use this |
| `repository.py` | SQLite CRUD for sessions | Routes use this |

The flow: **Routes → MovePipeline → Validator → GameState (with game_data) → game_store → repository**
