# Session Handoff — 2026-10-17

## Session Outcome

User reported a critical, blocking Bus bug: after completing setup (2 buildings + 2 route segments), the game correctly reaches `ACTION_SELECTION` on the human's turn, but every action-marker button on the board is unclickable (`disabled`). This session triangulated the bug down to one specific function and was interrupted (user restarting their PC) one step away from a definitive root cause. **Not yet fixed.** Playwright browser automation was used throughout and is the recommended tool to resume with.

## What Was Ruled Out (confirmed correct, do not re-investigate)

1. **Backend logic** — a scratch TestClient script (`api/scripts/debug_bus_action_selection.py`, still on disk, not part of the test suite — safe to delete once this bug is fixed) simulated a full 3-player game end-to-end and successfully submitted a `select_action` move. Separately, direct live queries to the running API (`POST /api/v1/moves/legal-moves`) during the actual stuck session always returned 7 valid `select_action` moves for `player_1` with `phase.phase_name: "ACTION_SELECTION"` and `confirm_required: false`.
2. **`isHumanTurn` / `canInteract` reactive chain in `BusBoard.svelte`** — confirmed `true`/`true` via live `data-debug-*` attributes (see below) at the exact moment the buttons render disabled.
3. **Prop-passing from `+page.svelte` to `BusBoard.svelte`** — confirmed `screenState`/`legalMoves` reach `BusBoard` correctly; `selectableActions` (the reactive array filtered from `availableMoves`) was confirmed via a `data-debug-selectable-json` attribute to contain the correct 7 entries, including one whose `action_type`/`slot` should exactly match a given button.

## Root Cause — Narrowed To One Function, Not Yet Fixed

In `web/src/lib/components/games/bus/BusBoard.svelte`:

```js
function actionMove(action, index) {
  return selectableActions.find(move => move.action_type === action && move.slot === String.fromCharCode(65 + index));
}
```

**Confirmed via live Playwright inspection (session 41, a freshly reproduced game):** at the exact render where the "line expansion slot C" button is disabled, its own `data-debug-selectable-json` attribute contains an entry `{"move_id":"select-line_expansion-C","type":"select_action","player_id":"player_1","action_type":"line_expansion","slot":"C"}` — i.e. a move exists in `selectableActions` whose `action_type` is `"line_expansion"` and whose `slot` is `"C"`, which is exactly `action_type === 'line_expansion'` and index `2` (since `String.fromCharCode(65+2) === 'C'`). Yet that same button's `data-debug-move-defined` attribute reads `"false"` — `actionMove('line_expansion', 2)` returned `undefined` despite a provably matching entry existing in the exact array it searches. **Every single action-slot button on the board (all 28) had `data-debug-move-defined="false"` simultaneously**, even though `selectableCount` was `7`.

This is the precise, reproducible contradiction to resolve next. Hypotheses not yet tested:
- A subtle type/encoding mismatch in `move.slot` or `move.action_type` (e.g. hidden whitespace, different string object, or the comparison operator not behaving as expected) — add a temporary `console.log` or extra debug attribute **inside** `actionMove()` itself that dumps the literal values being compared (`action`, `String.fromCharCode(65+index)`, and each candidate's `move.action_type`/`move.slot` with `JSON.stringify` and `typeof`) to see exactly why the `.find()` predicate fails.
- Possible Svelte `{@const}` / `{#each}` scoping or closure capture issue around the nested `{#each ACTION_TYPES as action}{#each Array(actionSlotCount(action)) as _, index}` loops — check if `action` or `index` are not the primitive values they appear to be (e.g. if Svelte's reactive `$:` recompute order causes `actionMove` to run against a stale/different closure than what the `data-debug-selectable-json` attribute on the same element reflects — note both attributes are on the *same* DOM node and should reflect the *same* render, which is itself suspicious and worth re-verifying first).

## Debug Instrumentation Left In Place (intentional — do not treat as a stray diff)

`web/src/lib/components/games/bus/BusBoard.svelte`'s `.board-action-slot` button (around line ~239) now has these temporary attributes, added specifically to continue this investigation:
`data-debug-can-interact`, `data-debug-is-human-turn`, `data-debug-action-in-progress`, `data-debug-available-count`, `data-debug-selectable-count`, `data-debug-screenstate-legal-count`, `data-debug-legalmoves-count`, `data-debug-selectable-json`, `data-debug-move-json`, `data-debug-move-defined`.

**Remove all of these once the bug is fixed and verified.** They were deliberately kept (not reverted) so the next session can resume reading them immediately via Playwright without re-instrumenting.

## How To Reproduce (Playwright, confirmed working this session)

The dev servers were already running: API on `http://127.0.0.1:8000`, web on `http://localhost:5173` (start via the `Run API (uvicorn)` task if not running; start `npm run dev` in `/web` manually if needed).

1. Navigate to `http://localhost:5173/games/bus/setup`, click "Start Game" (defaults: name "Ryan", 3 players). This creates a new session and lands on `/games/bus/play?sessionId=<N>`.
2. `SETUP_BUILDINGS` phase: click any enabled `building_a_XX, zone 1, empty` button, then click `house` in the type picker that appears. Wait ~3-4s (bots auto-play their two building placements via the AI loop).
3. Repeat step 2 once more for the human's second building (the board re-enables a new set of buildings after the bots finish).
4. Wait ~3-4s — phase becomes `SETUP_FIRST_ROUTE_SEGMENTS`. Click any button in `.legal-route` (there are ~72 at this point) — this is a map overlay path element, needs `{force: true}` in Playwright since it may be visually behind other elements.
5. Wait ~3s for bots — phase becomes `SETUP_SECOND_ROUTE_SEGMENTS`, human's turn again, with 3 "Build route segment eNN" buttons visible in the `region "Legal route segments"` panel.
6. Click the first "Build route segment eNN" button. **This is the exact click that transitions the game into `ACTION_SELECTION` and reproduces the bug** — immediately after, every `.board-action-slot` button is `disabled`, even though the status bar correctly shows "Red's turn" / "ACTION_SELECTION — Choose an action marker or pass".
7. At this point, read the `data-debug-*` attributes directly via `run_playwright_code`, e.g.:
   ```js
   await page.$$eval('.board-action-slot', els => els.map(e => ({
     label: e.getAttribute('aria-label'), disabled: e.disabled,
     moveDefined: e.getAttribute('data-debug-move-defined'),
     selectableJson: e.getAttribute('data-debug-selectable-json'),
   })));
   ```

Note: bot building/route placements are **non-deterministic** per session (different crossing IDs and action slots each time), so exact IDs (e.g. `building_a_01`, `e1`, `line_expansion` slot `C`) will differ run to run — always re-read the live DOM snapshot rather than assuming fixed IDs.

## Other User-Reported Items (not yet investigated this session)

- **"Green's setup is unknown"** — a live DOM snapshot from an earlier stuck session (35) actually showed Green's `route_ends: c2, c3` as present, contradicting a literal "missing data" reading. True meaning not yet clarified — ask the user directly, or inspect the rendered map visuals (not just the text panel) once the blocking bug above is fixed and the user can reproduce it again.
- **"AI should perform its full set of moves"** — user wants bots to never appear to silently stop. No concrete bug found yet; worth revisiting `recommend_ai_move`/`routes/moves.py`'s AI continuation loop after the blocking bug is fixed, specifically whether `if chosen_move is None: break` can be hit unexpectedly.

## Files Touched This Session

- `web/src/lib/components/games/bus/BusBoard.svelte` — added temporary `data-debug-*` attributes to the action-slot button only (see above). No functional/behavioral code was changed.
- `AGENTS.md`, `work-items.md`, `documentation/sessions/sessionhandoff_2026-10-17_1500.md` (archive of the stale prior `sessionhandoff.md`, which was unrelated to this session) — documentation only.
- No backend files were changed. `api/scripts/debug_bus_action_selection.py` (scratch, pre-existing from earlier in this session) remains on disk.

## Validation

None run this session — this was a live-browser investigation only, no functional source change was made (only debug attributes added to a `.svelte` template). Run `npm run check` and `python -m pytest -v` in their respective directories once a real fix is implemented.

## Recommended Next Steps

1. Resume with Playwright exactly as described in "How To Reproduce" above.
2. At the reproduced bug state, add one more temporary debug attribute **inside `actionMove()`** itself (not just at the call site) dumping the raw comparison values (with `typeof` and `JSON.stringify`) for the specific action/index that should match, to find the actual inequality.
3. Once the real cause is identified (likely a small logic/typing bug in `actionMove()` or an adjacent reactive statement), fix it, then manually re-verify via Playwright that a fresh session reaches `ACTION_SELECTION` with at least one clickable action-slot button, and that clicking it submits successfully.
4. Remove all `data-debug-*` attributes from `BusBoard.svelte` once fixed and verified.
5. Delete `api/scripts/debug_bus_action_selection.py` once no longer needed.
6. Run `npm run check`, Vitest, and the backend pytest suite to confirm no regressions.
7. Circle back to the two deferred user items above (Green's setup display, AI move completeness).

## Prompt for Next Session

```text
Continue local rbgg work from sessionhandoff.md. There is an active, unfixed, user-blocking Bus bug: after setup, ACTION_SELECTION is reached correctly but every action-marker button renders disabled. The bug has been narrowed to `actionMove(action, index)` in web/src/lib/components/games/bus/BusBoard.svelte returning undefined from its `.find()` call even when a matching entry provably exists in `selectableActions` at render time (confirmed via temporary data-debug-* attributes already left in that file, including data-debug-selectable-json and data-debug-move-defined). Use the "How To Reproduce" steps and run_playwright_code in sessionhandoff.md to get back to the exact broken state, then add a debug attribute INSIDE actionMove() itself dumping the literal values being compared (with typeof/JSON.stringify) to find the real mismatch. Fix it, verify live via Playwright that a button becomes clickable and submits, remove the debug attributes, delete api/scripts/debug_bus_action_selection.py, and run the full test suites before considering this done.
```

---

# PREVIOUS SESSION HANDOFF (archived below for reference, see documentation/sessions/sessionhandoff_2026-10-17_1500.md for the full original)

## Session Outcome (2026-09-22)

Completed the hybrid MCTS evaluator iteration and created a reusable, game-agnostic AI development guide. The hybrid strategy now has extensive Lost Cities scoring, diagnostics, bounded simulation controls, and regression coverage. Work remains local; no remote operation or push was performed.

## Completed This Session

### Hybrid Search and Evaluation

- Added and calibrated Lost Cities horizon components for score margin, absolute score, latent expedition equity, compound investment setup, public suit potential, spread pressure, deadwood, draw quality, and inactivity.
- Corrected investment multiplier semantics to the actual rule: `1 + investment_count`, not `2 ** investment_count`.
- Added unreachable eight-card bonus handling: starting at 4 or higher cannot reach eight cards; starting at 6 can reach at most five cards.
- Penalized irreversible empty-expedition 10 starts.
- Added live/dead investment distinction and protected acceptable plays from discard branches.
- Added discard ceiling at one-ply ranking and final root selection.
- Added a persistent penalty for drawing a known dead discard card.
- Added expedition spread/overcommitment pressure.
- Hardened horizon penalties so late-game combinations remain bounded in `[0,1]`.

### Diagnostics and Tools

- Added opt-in per-search diagnostics with root summaries, path/depth, leaf values, horizon contributions, raw equity, per-color equity, public potential, setup values, and penalties.
- Added `--explain`, `--explain-first`, `--diagnostic-records`, and `--max-decisions` simulator options.
- Added compact one-line diagnostic output and explicit root summaries.
- Added `scripts/explain_horizon.py` for editable fixture-based formula inspection.
- Added Horizon Tree Explorer at `web/src/routes/horizon-tree/+page.svelte`.
- Added top/bottom path display and root average/visit summaries to the viewer.

### Documentation

- Created `documentation/ai-bot-development-guide.md`, a reusable planning guide for future games covering turn mapping, information boundaries, evaluator contracts, feature weights, spread/urgency/inactivity, deterministic fixtures, calibration, diagnostics, and promotion gates.
- Updated `AGENTS.md` and `work-items.md`.
- Archived the prior handoff at `documentation/sessions/sessionhandoff_2026-09-22_0011.md`.

## Key Current Behaviors

- Hybrid search is enabled with `MCTSConfig(strategy="hybrid")`; legacy remains the default fallback.
- Final root selection uses accumulated horizon values, confidence adjustment, discard ceiling, and acceptable-play priority.
- Diagnostics are disabled by default. `--explain` keeps them enabled for all decisions; `--explain-first` limits them to the first decision.
- `--max-decisions N` gives bounded runs and cleanly reports `SIMULATION STOPPED`.
- The simulator uses `--games-seed` for the deterministic deal/deck and `--seed` for search behavior.

## Validation

- Full backend suite: **290 passed, 1 existing FastAPI/Starlette deprecation warning**.
- Focused hybrid suite: **26 passed** after final late-game bound fixes.
- Simulation script compiles.
- Frontend `npm run check`: 0 errors, existing warnings only.
- Six-decision diagnostic run was verified with six decision headers and six diagnostic sections.

## Remaining Risks

- Lost Cities evaluator weights remain heuristic and need tactical/seat-swapped calibration.
- Hidden opponent hands and draw-pile order are not determinized; public suit potential is an approximation.
- Full-game diagnostics can be large; use `--max-decisions` and bounded records.
- Generated frontend output, package metadata, and local database artifacts may remain in the dirty tree.

## Recommended Next Steps

1. Run tactical fixtures and paired seat-swapped matches for the hybrid policy.
2. Compare raw latent-equity breakdowns against manually scored positions.
3. Add hidden-information determinization or explicit belief sampling.
4. Calibrate `tanh` scales, weights, discard ceiling, and spread thresholds from benchmark data.
5. Decide whether to promote hybrid by game/difficulty.
6. Finish/reconcile remaining application-review findings and generated artifacts.

## Prompt for Next Session

```text
Continue local rbgg work from sessionhandoff.md. Read AGENTS.md, work-items.md, documentation/ai-bot-development-guide.md, and documentation/hybrid-mcts-design.md. Run the backend baseline with the configured Python 3.13 interpreter. Keep work local and do not push. Hybrid Lost Cities search now has policy-owned evaluation, public suit potential, multiplier-aware setup, spread pressure, deadwood/draw penalties, discard ceiling, acceptable-play priority, and diagnostics. Prioritize tactical/seat-swapped benchmark calibration and hidden-information determinization. Use scripts/simulate_game.py with --max-decisions and --explain-first or --explain for bounded evidence.
```
