# AGENTS.md — rbgg Repository

## 1. Execution & Request-Saving Guardrails (Mandatory)

You operate under a strict daily API request budget. Minimize round-trip tool calls on every turn:

1. **Parallel Tooling & Pipelining:** Never execute tool calls sequentially when they can be grouped. Bundle file reads, edits, and requested commands into a single concurrent tool payload.
2. **Single-Shot Edits (Default):** Once you apply a code modification to a file, STOP execution immediately. Do not auto-compile, lint, or run tests unless explicitly instructed in the prompt.
3. **Discovery Gate:** If exact file paths are unknown, run at most **two (2)** search/grep queries. List the 3–5 candidate files found, stop, and ask: _"Which of these files should we open?"_
4. **Fast-Fail on Errors:** If any command, build script, or test returns a non-zero exit code, STOP immediately and report the error. Do not enter an autonomous auto-fix loop.
5. **Isolated Testing Only:** Never run global test suites (e.g., root `pytest`). Only run targeted test files when explicitly asked to verify. Never run the 60-seed Twilight floor test autonomously (takes up to 14 minutes).
6. **UI Validation Policy:** Never create or modify Playwright test files. Validate UI changes via `agent-browser` against `http://localhost:5173` (one action at a time, inspect console/network, then close).
7. **Port Discipline & Final Restart:** The canonical dev ports are API `8000` (`http://127.0.0.1:8000`) and frontend `5173` (`http://localhost:5173`). The final step of every bug-fix task is to stop any existing processes on those ports, restart both servers on exactly those ports, and verify `GET /api/v1/games/` and `GET http://localhost:5173/` both return 200 before reporting completion. If a listener cannot be stopped from the current shell, report that explicitly instead of assuming the restart succeeded. Never leave a second background API or frontend process on a different port.

## 2. Session Startup Protocol

On the very first response of a new session, do not run tests or parse logs:

1. Read `AGENTS.md` and `sessionhandoff.md` (if present) to capture current project state.
2. Output a concise 3-bullet summary covering: **(a)** what was accomplished last session, **(b)** immediate target files, and **(c)** a prompt asking for confirmation before making edits.

## 3. Skill Routing

Load the matching skill via the `skill` tool when applicable:

- **Svelte components / runes / UI state:** Load `svelte-core-bestpractices` before editing `.svelte` files.
- **Bug investigation or failing tests:** Load `systematic-debugging` before proposing a fix.
- **UI verification / layout polish:** Use `agent-browser` for DOM/console checks, and `unslop` or `impeccable` when auditing UI design.
- **Explicit verification requests:** When asked to verify or complete a multi-step fix, load `verification-before-completion` and run only the targeted `pytest` / `npm run check` commands.

## 4. Architecture & Layout Constraints

- **Stack:** FastAPI backend (`/api`, Python `>=3.13,<3.14`, Uvicorn) + SvelteKit frontend (`/web`, Node `>=22.22.2`, SvelteKit 2.70.3, Svelte 5, TypeScript).
- **State Authority:** SQLite `api/rbgg.db` is the session snapshot authority; `game_store.py` is an in-memory process cache only. All rules validation and legal-move calculation live in Python (`api/app/games/*/validator.py`); Svelte renders state snapshots and dispatches player intent.
- **Game Registry & Static Mounts:** Games register in `api/app/__init__.py`. Static image mounts: `/api/v1/img`, `/api/v1/img/bus`, `/api/v1/img/twilight-struggle`, `/api/v1/img/fof`.
- **Directory Rules:**
  - Runtime artifacts belong strictly under `api/runtime/` (root `runtime/` must not exist). Keep exactly one production model per game in `api/runtime/` root; place older/test models in `api/runtime/<game>/`.
  - Utility scripts belong strictly under `api/scripts/<game-or-shared>/` (root `scripts/` must not exist).

## 5. Commands Reference

### Backend (`/api`)

- **Dev server:** `cd api; python -m uvicorn app:app --reload --host 127.0.0.1 --port 8000`
- **Production entrypoint:** `uvicorn wsgi:app --host 0.0.0.0 --port $PORT` (Render rootDir `api`)
- **Install deps:** `python -m pip install -c constraints.txt -e ".[dev]"` (`rl` extra for RL)
- **Targeted test:** `cd api; python -m pytest tests/test_filename.py -q`
- **Scaffold check:** `cd api; python -m pytest tests/test_scaffold.py -q`

### Frontend (`/web`)

- **Dev server:** `cd web; npm run dev` (port `5173`; `VITE_API_BASE=http://127.0.0.1:8000/api/v1`)
- **Type / Svelte check:** `cd web; npm run check`
- **Targeted unit test:** `cd web; npx vitest run path/to/file.test.ts`
- **Build:** `cd web; npm run build`

## 6. Game-Specific Implementation Notes

- **Catalog:** `checkers`, `lost_cities`, `bus`, `twilight_struggle`, `fields_of_fire` (catalog presence does not imply completion).
- **Lost Cities:** Production AI uses MaskablePPO `api/runtime/lc-v2-low-lr-2m.zip` with MCTS fallback.
- **Bus:** Uses `api/runtime/bus-v2-2.5m.zip`. Stale-render prevention requires lookup expressions inlined inside `{#each}` `{@const}` blocks.
- **Twilight Struggle:**
  - Default model: `api/runtime/twilight-ppo-v2-safe-500k.zip` (override via `RBGG_TWILIGHT_PPO_MODEL`, provider via `RBGG_TWILIGHT_AI_PROVIDER`; PPO falls back to legal-move policy).
  - Cards are immutable records—never mutate card dictionaries in-place. Card triggers use staged interactive choice matrices.
- **Fields of Fire (`fields_of_fire`):**
  - Core rules: `api/app/games/fields_of_fire/validator.py`; Line of Sight: `los.py`.
  - Action definitions: `api/configs/fof/fields_of_fire_actions.json` (sourced from `documentation/fof/fields_of_fire_actions_deluxe_2024.csv`, loaded by `actions.py`). Friendly-command actions are filtered by `phases` containing `friendly_command` (`move_type` is ignored) and include structured fields (`originator_type`, `recipient_type`, `communication_required`, `los_required`, `draw_count`, `success_icon`, `miss_modifier`, `ammo_type`, `ammo_cost`, `fire_mission_type`, `auto_if_no_vof`).
  - Command economy & activation: Fresh sessions start in `setup` and require `start_mission` and `lay_out_map` before command-panel actions. `pool_by_hq` is empty until missions start and cards are drawn. Command cost is deducted from the selected originator's `pool_by_hq` (`commands_pool` is a derived aggregate) on every attempt, applying draw success/failure, miss modifiers, ammo, fire-mission effects, and exhort state. Per 3.3.1a, BN HQ on-map (and CO HQ when BN is off-map) activate free; subsequent activations cost 1 Command.
  - Terrain images: Must come from `api/img/fof/cards` (served at `/api/v1/img/fof`).
  - Frontend UI: `TurnSequenceTracker.svelte`; `CommandPanel.svelte` (in `GameProgressPanel.svelte` footer, driven by `fofCommand` store) groups legal moves by `action_id` with a compact target selector.
  - Targeted FOF tests: `cd api; python -m pytest tests/test_fields_of_fire.py tests/test_fof_turn_sequence.py -q`

## 7. Deployment (Render)

- **Health check:** `/api/v1/games/`
- **Environment:** Node `22.22.2`, Python `3.13.0`, `RBGG_ASSET_REVIEW_ROOT=/opt/render/project/src/documentation`, `RBGG_CONFIG_ROOT=/opt/render/project/src/api/configs`
- **CI Reference:** CI enforces backend coverage `>=70` and frontend `check`/`unit`/`build`/`audit` (do not run as local defaults).
