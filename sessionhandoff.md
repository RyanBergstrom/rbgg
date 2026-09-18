# Session Handoff — 2026-09-18

## What We Did

Improved MCTS tree expansion by adding heuristic-guided move selection and removing depth limits for full game rollouts.

## Key Changes

### 1. Removed Depth Limit in Rollouts (`mcts_v3.py`)

- Changed `_simulate()` to always use `range(200)` instead of conditional `max_depth`
- Now runs full game rollouts (up to 200 moves) instead of depth-limited
- Allows MCTS to evaluate positions through complete game sequences

### 2. Added Expansion Weights (`legal_move_interface.py`, `validator.py`)

New `expansion_weights()` method in `LegalMoveValidator` interface:
- Called during tree expansion to filter/weight untried moves
- Higher weights = higher chance of expansion
- Weight 0 = excluded from expansion

Implemented in `LostCitiesValidator`:
- Scores play_expedition moves using `compute_play_score_v2()`
- Normalizes scores to 0-1 range (min-max normalization)
- Excludes moves with negative scores (weight < -10 → weight 0)
- Discard/draw moves always get weight 1.0 (no filtering)

### 3. Modified `_expand()` in `mcts.py`

- Now calls `validator.expansion_weights()` instead of using priors
- Filters out bad play moves (weight 0) before selection
- Uses weights for weighted random selection
- Falls back to priors if filtering removes everything

## Problem Solved

**Issue**: After turn 2, `prior_moves()` returns all zeros, making tree expansion essentially random.

**Solution**: `expansion_weights()` uses the heuristic scoring function to filter bad moves during expansion, guiding tree growth toward promising branches.

## Test Results

- All existing tests pass (except pre-existing `test_expedition_investment_always_legal`)
- Simulation runs successfully with new changes

## Files Modified

- `app/core/mcts_v3.py` — removed depth limit in `_simulate()`
- `app/core/legal_move_interface.py` — added `expansion_weights()` method
- `app/core/mcts.py` — modified `_expand()` to use expansion weights
- `app/games/lost_cities/validator.py` — implemented `expansion_weights()`
- `.vscode/launch.json` — added debug configuration for simulate_game.py

## Key Insight

**Expansion weights vs priors**:
- `prior_moves()` returns 0 after turn 2 (by design in Lost Cities)
- `expansion_weights()` always uses heuristic scoring regardless of turn
- Expansion weights filter moves at expansion time; priors affect UCT selection
- With 200 iterations and 10-15 legal moves, filtering bad moves is critical

## Next Steps

- Run full game simulations to validate expansion weight behavior
- Tune the normalization range (currently -10 to max score)
- Consider adjusting the -10 threshold for excluding negative-score moves
- Monitor if expansion weights are too aggressive (might exclude viable moves)
- Test with different iteration counts (200 vs 500 vs 1000)

## Open Questions

- Is the -10 threshold for excluding moves too aggressive?
- Should normalization be based on absolute scores or relative to hand?
- How do expansion weights interact with the move filter (`filter_moves`)?
- Should we add logging to track how many moves are filtered at each expansion?

## Clarifications Made

- `prior_moves()` intentionally returns 0 after turn 2 (comment says "pure MCTS — no priors")
- `expansion_weights()` is separate from `prior_moves()` — different purposes
- Full rollout (200 depth) is expensive but provides complete game evaluation

## Prompt for Next Session

```
Continue working on the rbgg Lost Cities MCTS engine. We added expansion_weights() to filter bad play moves during tree expansion and removed depth limits for full game rollouts. Run `python scripts/simulate_game.py --iters 50` to test. Consider tuning the normalization range and -10 threshold in expansion_weights(). Check if expansion weights interact correctly with filter_moves() for opening moves.
```
