# Session Handoff — 2026-09-19 21:42 CDT (archived 2026-09-22 00:11)

## Session Outcome

Completed substantial remediation from the full-application review and performed a separate evidence-based review of the AI engine. The backend and frontend local gates were green at the prior handoff. This handoff was archived before the 2026-09-22 session work.

## Completed Work

### State, Gameplay, and Determinism

- Resolved RBGG-AUD-001: active game state is addressed by opaque SQLite session IDs rather than game type.
- Resolved RBGG-AUD-004: Lost Cities determines the winner only after the final round and handles draws correctly.
- Resolved RBGG-AUD-005: Checkers MCTS transitions alternate players correctly and preserve continuation jumps.
- Resolved RBGG-AUD-006: validators own player/phase transitions and `GameEngine` synchronizes outer state.
- Resolved RBGG-AUD-008: Lost Cities heuristic scoring uses the requested player's perspective.
- Resolved RBGG-AUD-011: deterministic RNG state flows through Lost Cities setup, rounds, and `GameEngine`.

### AI Engine Review

- Created `documentation/ai-engine-review.md` with findings AI-01 through AI-18 and a bounded rewrite recommendation.
- Confirmed production previously used base `MCTSEngine`; old V2/V3 modules were removed and behavior consolidated.
- Confirmed legacy rollout issues, incorrect priors/terminal semantics, hidden-information leakage, RNG transition loss, heuristic defects, and deep-copy/parallelism costs.

### Hybrid Search Work

- Added `MCTSConfig(strategy="hybrid")` behind a fallback strategy switch.
- Added deterministic no-rollout, horizon-bounded search with hot/cold action pools, deferred admission, policy-owned transitions/evaluation, confidence-aware final selection, and a configurable discard ceiling.
- Moved game-specific evaluation out of core MCTS into SearchPolicy modules.
- Added Lost Cities draw-source scoring, deadwood cleanup, live/dead investment logic, public suit potential, investment multiplier setup, expedition spread pressure, unreachable eight-card bonus handling, irreversible 10 endpoint penalties, and persistent dead-discard penalties.
- Added optional diagnostic tree capture and the Horizon Tree Explorer UI.
- Added simulator options including `--explain`, `--explain-first`, `--diagnostic-records`, and `--max-decisions`.
- Added editable `scripts/explain_horizon.py` for exact formula inspection.

## Key Files Worked On

- `api/app/core/mcts.py`
- `api/app/core/search_policy.py`
- `api/app/games/lost_cities/search_policy.py`
- `api/app/games/lost_cities/validator.py`
- `api/app/games/checkers/search_policy.py`
- `api/app/games/checkers/validator.py`
- `api/app/routes/moves.py`
- `api/scripts/simulate_game.py`
- `api/scripts/explain_horizon.py`
- `api/tests/test_hybrid_mcts.py`
- `documentation/hybrid-mcts-design.md`
- `documentation/ai-bot-development-guide.md`
- `web/src/routes/horizon-tree/+page.svelte`
- `AGENTS.md`
- `work-items.md`

## Validation

- Latest full backend suite: **290 passed, 1 pre-existing FastAPI/Starlette deprecation warning**.
- Latest focused hybrid suite: **26 passed** before the final diagnostic-only changes; subsequent full suite passed after the latest changes.
- Frontend `npm run check`: 0 errors, existing warnings only.
- A six-decision diagnostic run was verified with six decision headers and six diagnostic sections.

## Important Current Behavior

- Hybrid search is enabled by `MCTSConfig(strategy="hybrid")`; legacy remains the default unless explicitly selected.
- `--explain` now keeps diagnostics enabled for every decision; `--explain-first` limits diagnostics to the first decision.
- `--max-decisions N` stops the simulator cleanly after N AI decisions.
- Diagnostics now include root branch summaries, top/bottom path records, horizon components, raw equity, per-color equity, compound setup, and dead-draw penalty details.
- Discard values are capped at `0.40` during pool ranking and final root selection; acceptable plays are protected from discard branches.
- The simulator prints compact one-line path diagnostics with horizon inputs and contributions.

## Known Caveats

- Lost Cities horizon values are still heuristic and need calibration against tactical fixtures and paired seat-swapped matches.
- Hidden opponent hand and draw-pile order are not yet determinized; public suit potential is only an approximation.
- Diagnostic output can be large for full-game `--explain` runs; use `--max-decisions` and a bounded `--diagnostic-records` value.
- Generated frontend output, package metadata, and local database artifacts may remain visible in the dirty tree.

## Next Steps

1. Run focused tactical and paired seat-swapped benchmarks for the hybrid policy.
2. Validate raw latent-equity components against known Lost Cities positions.
3. Add determinization for hidden opponent hand/draw-pile information.
4. Calibrate weights and thresholds from benchmark evidence rather than hand-tuning.
5. Decide whether to promote hybrid strategy by difficulty level.
6. Finish remaining application-review findings and reconcile generated artifacts before committing.

## Prompt for Next Session

```text
Continue local rbgg work from the latest session handoff. Read AGENTS.md, sessionhandoff.md, work-items.md, documentation/ai-bot-development-guide.md, and documentation/hybrid-mcts-design.md. Run the backend baseline with the configured Python 3.13 interpreter. Keep work local and do not push. The hybrid engine is implemented behind MCTSConfig(strategy="hybrid") with SearchPolicy-owned game evaluation, confidence-aware root selection, discard ceiling, expedition spread pressure, and diagnostics. Prioritize tactical/seat-swapped benchmark validation and hidden-information determinization before further heuristic tuning. Use --max-decisions and --explain-first for bounded diagnostics.
```
