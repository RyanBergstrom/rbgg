# Session Handoff — 2026-09-22 (archived 2026-10-17)

## Session Outcome

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

---

*Note: this file was the stale `/sessionhandoff.md` found at the start of the 2026-10-17 Bus action-selection debugging session. It was archived as-is (unrelated to that session's work) when the new handoff was written.*
