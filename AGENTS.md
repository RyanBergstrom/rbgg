# AGENTS — rbgg Repository

## Execution guardrails

- Single-shot edits: apply changes, then stop; do not auto-compile/lint/test unless asked.
- Discovery gate: max 2 search/grep queries when paths are unknown; list candidates and ask.
- Fast-fail: if a command/test fails, stop and report the error.
- Never run global test suites; isolate targeted tests.
- Never create or modify Playwright test files; validate UI with the browser tool.

## Project

- Multi-game platform: FastAPI backend `/api`, SvelteKit frontend `/web`.
- SQLite `api/rbgg.db` is session snapshot authority; `game_store.py` is only a process cache.
- Games: checkers, lost_cities, bus, twilight_struggle, fields_of_fire. Catalog presence does not mean complete.

## Commands

Backend:

- Dev server: `cd api; python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000`
- Production entrypoint: `uvicorn wsgi:app --host 0.0.0.0 --port $PORT` (Render rootDir `api`)
- Install: `python -m pip install -c constraints.txt -e ".[dev]"` (`rl` extra for RL)
- Targeted test: `cd api; python -m pytest tests/test_filename.py`
- Fast scaffold check: `python -m pytest tests/test_scaffold.py`

Frontend:

- Dev server: `cd web; npm run dev` (port 5173)
- Type check: `npm run check`
- Unit tests: `npm run test:unit` or `vitest run path/to/file.test.ts`
- Build: `npm run build`
- Env: `web/.env.example` sets `VITE_API_BASE=http://127.0.0.1:8000/api/v1`; backend CORS allows localhost:5173.

## Layout constraints

- Runtime only under `api/runtime/`; root `runtime/` must not exist.
- `api/runtime/` root has exactly one production model per game; older/test artifacts go in `api/runtime/<game>/`.
- Scripts only under `api/scripts/<game-or-shared>/`; root `scripts/` must not exist.

## Toolchain

- Backend: Python 3.13 (`>=3.13,<3.14`), FastAPI, Uvicorn.
- Frontend: Node `>=22.22.2`, SvelteKit 2.70.3, Svelte 5, TypeScript.
- Games are registered in `api/app/__init__.py`; validators live in `app/games/*/validator.py`.
- Static image mounts: `/api/v1/img`, `/api/v1/img/bus`, `/api/v1/img/twilight-struggle`, `/api/v1/img/fof`.

## Game-specific notes

- Lost Cities: production path uses MaskablePPO `lc-v2-low-lr-2m.zip` with MCTS fallback.
- Bus: uses `bus-v2-2.5m.zip`; stale-render fix requires lookup expressions inlined inside `{#each}` `{@const}` blocks.
- Twilight Struggle: default model `api/runtime/twilight-ppo-v2-safe-500k.zip`; override with `RBGG_TWILIGHT_PPO_MODEL`; provider with `RBGG_TWILIGHT_AI_PROVIDER`; PPO falls back to legal-move policy; cards are immutable records; staged interactive choices handle card triggers.
- Fields of Fire:
  - Rules implementation in `api/app/games/fields_of_fire/validator.py`; LOS in `los.py`.
  - Action config: `api/configs/fof/fields_of_fire_actions.json`, sourced from `documentation/fof/fields_of_fire_actions_deluxe_2024.csv`, loaded by `actions.py`.
  - Terrain images must come from `api/img/fof/cards`; static mount is `/api/v1/img/fof`.
  - Scenarios in `fields_of_fire_scenarios.json`; counters: `counters-final.json` validated, `counters.json` raw OCR; rulebook `documentation/fof/README.md`.
  - UI: `TurnSequenceTracker.svelte`; `CommandPanel.svelte` is in the footer of `GameProgressPanel.svelte` and is controlled by `fofCommand` store.
  - Fresh sessions start in `setup`; require `start_mission` and `lay_out_map` before command-panel actions.
  - Activation (3.3.1a): BN HQ on map and CO HQ when BN is off-map activate free; later activations cost 1 Command.
  - `pool_by_hq` is empty until missions are started and cards are drawn.

## Testing

- Backend tests: `api/tests/`; frontend tests: `web/tests/`.
- Never run the 60-seed Twilight floor test autonomously (up to 14 minutes).
- Browser validation: run frontend at http://localhost:5173, interact one action at a time, inspect console/network, then close.
- CI runs backend coverage threshold 70 and frontend check/unit/build/audit; do not treat as a local default.

## Deployment

- Render env: `RBGG_ASSET_REVIEW_ROOT=/opt/render/project/src/documentation`, `RBGG_CONFIG_ROOT=/opt/render/project/src/api/configs`.
- Health check: `/api/v1/games/`.
- Node version 22.22.2; Python version 3.13.0.