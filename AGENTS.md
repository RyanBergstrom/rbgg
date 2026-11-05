# AGENTS — rbgg Repository

## 🛑 STRICT REQUEST-BUDGET GUARDRAILS

You operate under a strict daily budget for requests. To prevent autonomous loops:

1. **Single-Shot Edits:** Write your file changes and STOP immediately. Do not automatically compile, lint, or run tests unless explicitly ordered.
2. **The Discovery Gate:** If file locations for a feature are unknown, you have a maximum of TWO (2) sequential search/grep requests. List candidate files and wait for human selection. Do not read files speculatively.
3. **Pipelining:** When instructed, bundle your file reads, edits, and local test runners into a single concurrent parallel tool execution payload.
4. **Fast-Fail Rule:** If a command or test returns a non-zero exit code (fails), STOP immediately. Do not attempt an auto-fix round. Present the error stack and hand back control.

## Project Purpose

A multi-game platform (FastAPI backend / SvelteKit frontend) for playing board games against AI opponents.

## Architecture Map

- **Backend (`/api/`)**: Python 3.13, FastAPI, Uvicorn.
  - `app/core/`: Game engine orchestrator, SQLite DB access, logging, and base MCTS.
  - `app/games/`: Game rule validation registries (Lost Cities, Checkers, Bus, Twilight Struggle).
- **Frontend (`/web/`)**: SvelteKit 2.70.3, Svelte 5, TypeScript.
- **Authority**: SQLite (`rbgg.db`) manages session snapshot authority. `game_store.py` is purely a local process cache.

## Targeted Testing Frameworks (NEVER Run Global Suites)

- **Backend Tests (`/api/tests/`)**: `pytest`. Always isolate via `pytest tests/test_filename.py`.
- **Frontend Tests (`/web/tests/`)**: `Vitest`. Always isolate via `vitest run path/to/file.test.ts`.
- _Note:_ The 60-seed Twilight floor test takes up to 14 minutes. NEVER execute it autonomously.

## Active Game Scope & Rules Summary

1. **Lost Cities:** 2-player card game. Production path uses MaskablePPO inference model (`lc-v2-low-lr-2m.zip`) with MCTS fallback.
2. **Bus:** 3-5 player route game. Uses promoted `bus-v2-2.5m.zip` PPO model. Note: Stale-render bug fix requires lookup expressions to be strictly inlined inside `{#each}` loop `{@const}` blocks.
3. **Twilight Struggle:** Card-driven strategy engine. Staged interactive choices handle card triggers (Blockade, Olympics, Missile Envy). Cards are stored as full immutable records; never mutate card dicts in-place.

## Expected Verification Commands

- Fast API verification target: `python -m pytest tests/test_scaffold.py`

## Runtime Layout
- Only runtime folder is api/runtime/. Root runtime/ must not exist.
- api/runtime/ root must contain exactly one production model per game (e.g. bus-v2-2.5m.zip, lc-v2-low-lr-2m.zip).
- Each game has a subfolder (api/runtime/<game>/) for test/in-progress/older models, checkpoints, opponents, logs, and evals.




## Scripts Layout
- All scripts must live under api/scripts/<game-or-shared>/. Root scripts/ must not exist.
- Game-specific scripts go in api/scripts/bus/, api/scripts/lost_cities/, api/scripts/twilight/, api/scripts/checkers/, or api/scripts/fof/. Shared utilities go in api/scripts/shared/.

