# AGENTS — rbgg Repository

## Before making changes

- This file captures compact, repo-specific guidance for OpenCode agents. Read before starting work.
- Append each entry under the heading. Do not omit fields.
- Understand the requirement
- Review Related Code
- Search for Existing patterns
- Add or update tests
- Update this document if needed

### Commands

- Whenever the human says they are going to logoff or discussing logging off that means they want you to folloow the instructions in the loggoff.md file

## Project Purpose

A multi-game platform for playing board games against AI opponents. The backend serves a REST API that manages game state, validates moves, and runs MCTS-based AI. The frontend is a SvelteKit web app that renders the board and handles player interaction.

## Architecture

    ### Technology Stack

    - **Backend**: Python 3.14, FastAPI, Uvicorn
    - **Frontend**: SvelteKit 2, Svelte 4, TypeScript, Vite
    - **Database**: SQLite (via `rbgg.db`)
    - **Testing**: pytest (backend), Vitest (frontend)

    ### Front End

    - `/web/` — SvelteKit app
    - `src/` — Svelte components and routes
    - `components/` — Reusable UI components
    - `tests/` — Vitest unit tests
    - Communicates with backend via REST API at `http://127.0.0.1:8000/api`

    ### Back End

    - `/api/` — Python FastAPI application
    - `app/core/` — Game engine, MCTS implementations, config, DB, logging
    - `app/games/` — Game-specific logic (validator, serialize) per game
    - `app/routes/` — API endpoints (games, moves, sessions, settings)
    - `scripts/` — Utility scripts (game simulation, debugging)
    - `tests/` — pytest test suite

    ### Database

    - SQLite file at `rbgg.db` (root and api-level)
    - Managed via `app/core/db.py` and `app/core/repository.py`

    ### Testing Frameworks

    - **Backend**: pytest with pytest-asyncio, testpaths = ["tests"]
    - **Frontend**: Vitest with @testing-library/svelte, jsdom

## Project Layout

- `/api/` — Python API package and tooling
- `/web/` — SvelteKit frontend
- `/documentation/` — Session handoffs and docs
- `/AGENTS.md` — Agent guidance (this file)
- `/sessionhandoff.md` — Session handoff template

## Files Defintions Overview

| File                                 | Purpose                                                                                                   |
| ------------------------------------ | --------------------------------------------------------------------------------------------------------- |
| `pyproject.toml`                     | package config, setuptools build backend, dev deps (pytest, pytest-asyncio), pytest testpaths = ["tests"] |
| `app/__init__.py`                    | app module init                                                                                           |
| `app/core/__init__.py`               | core module init                                                                                          |
| `app/games/__init__.py`              | games module init                                                                                         |
| `app/routes/__init__.py`             | routes module init                                                                                        |
| `tests/__init__.py`                  | tests module init                                                                                         |
| `api/.gitignore`                     | api-specific gitignore                                                                                    |
| `/.gitignore`                        | root gitignore (includes `/api/.gitignore`)                                                               |
| `tests/test_scaffold.py`             | 5 importability test functions                                                                            |
| `app/core/mcts.py`                   | Generic MCTS engine (game-agnostic, uses LegalMoveValidator interface)                                    |
| `app/core/mcts_v2.py`                | MCTS v2 with reward-based backpropagation                                                                 |
| `app/core/mcts_v3.py`                | MCTS v3 with heuristic-weighted rollouts via `score_moves`                                                |
| `app/core/engine.py`                 | Game engine orchestrator                                                                                  |
| `app/core/game_state.py`             | Game state management                                                                                     |
| `app/core/game_store.py`             | In-memory game storage                                                                                    |
| `app/core/db.py`                     | SQLite database connection                                                                                |
| `app/core/repository.py`             | Data access layer                                                                                         |
| `app/core/config_loader.py`          | YAML config loading                                                                                       |
| `app/core/config_schema.py`          | Config validation schema                                                                                  |
| `app/core/legal_move_interface.py`   | LegalMoveValidator interface for games                                                                    |
| `app/core/log.py`                    | Logging utilities                                                                                         |
| `app/core/rng.py`                    | Deterministic RNG for reproducibility                                                                     |
| `app/games/lost_cities/validator.py` | Lost Cities game logic, move validation, scoring                                                          |
| `app/games/lost_cities/serialize.py` | Lost Cities state serialization for API responses                                                         |
| `app/games/checkers/validator.py`    | Checkers game logic and move validation                                                                   |
| `app/games/checkers/serialize.py`    | Checkers state serialization                                                                              |
| `app/games/catalog.py`               | Game catalog registry                                                                                     |
| `app/games/registry.py`              | Game registration system                                                                                  |
| `app/routes/games.py`                | Game CRUD endpoints                                                                                       |
| `app/routes/moves.py`                | Move submission and AI move endpoints                                                                     |
| `app/routes/sessions.py`             | Session management endpoints                                                                              |
| `app/routes/settings.py`             | Settings endpoints                                                                                        |
| `scripts/simulate_game.py`           | Full game simulation using MCTSEngineV3                                                                   |

## Implimented Games

### Lost Cities

- **Type**: 2-player card game
- **Cards**: 60 cards — 5 colors (yellow, blue, white, green, red), 12 cards each (2× investments, numbered 2–10)
- **Gameplay**: Players alternate play/draw phases. Play cards to expeditions (must be ascending), discard to piles, draw from pile or discard. Investments multiply expedition score. Expeditions start at -20.
- **Win condition**: Highest total score across all expeditions after deck runs out
- **Files**: `app/games/lost_cities/validator.py`, `app/games/lost_cities/serialize.py`

### Checkers

- **Type**: 2-player board game
- **Board**: 8×8 grid
- **Files**: `app/games/checkers/validator.py`, `app/games/checkers/serialize.py`

## Game Specific AI implimentation

### Lost Cities — MCTS with Heuristic Rollouts

- **Engine**: `MCTSEngineV3` (`app/core/mcts_v3.py`) — extends base MCTS with heuristic-weighted rollout move selection and expansion weights
- **Tree search**: Standard UCT with expansion weights — selection, expansion (weighted by `expansion_weights()`), simulation, backpropagation
- **Expansion weights** (`expansion_weights` in `validator.py`):
  - Scores play_expedition moves using `compute_play_score_v2()`
  - Normalizes scores to 0-1 range, excludes negative scores (weight 0)
  - Discard/draw moves always get weight 1.0
  - Called in `_expand()` to filter/weight untried moves before selection
- **Rollout selection**: `score_moves()` in `validator.py` scores each legal move; `_weighted_choice()` in `mcts.py` selects proportionally (clamped to 0, no shift)
- **Heuristic scoring** (`compute_play_score_v2` for plays):
  - Card being played is now included in `guaranteed_cards` (bug fix: was skipped because loop started after card position)
  - Investments are not duplicated in `guaranteed_cards` (bug fix: was added twice)
  - Sequential constraint: counts only cards ≥ scored card, pre-computes `highest_numbered_guaranteed`
  - Investment multiplier: counts only cards played after investments
  - Killed card penalty: sum of lower-numbered cards × 3
  - Wasted investment penalty: investments in hand × 15 when playing numbered card
  - 8-card bonus: +20 if expedition reaches 8 cards
- **Discard scoring**: 10 (can't play), 0.5 (can play, positive value), 0 (can play, non-positive value)
- **Draw scoring**: 0.5 (draw pile), variable (discard pile based on color availability)
- **Move filter** (`filter_moves` in `validator.py`):
  - Turns 1-5: Only play lowest numbered card of each color (investments always allowed)
  - Turns 1-2: Additional restrictions on discards and draws
  - Prevents tree from expanding bad opening moves

## Work-Items

- Whenever you finish a work item add it to the `/work-items.md` file

## Known Issues

- `test_expedition_investment_always_legal` — pre-existing test failure (unrelated to recent changes)
- PowerShell quoting issues with Python inline f-strings — use script files instead of `-c` commands

## Files Frequently Modified

- `app/games/lost_cities/validator.py` — game logic, scoring, move validation
- `app/core/mcts.py` — base MCTS engine, `_weighted_choice`
- `app/core/mcts_v3.py` — heuristic MCTS variant
- `tests/test_lost_cities.py` — main test suite
- `tests/test_score_moves_debug.py` — scoring tests
- `tests/test_mcts_rollout_debug.py` — rollout tests
- `scripts/simulate_game.py` — game simulation
- `.vscode/launch.json` — debug configurations

## Last step before starting

- the last thing before starting is to read and follow instructions in `/sessionhandoff.md`
