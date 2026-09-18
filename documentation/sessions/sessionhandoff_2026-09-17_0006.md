# Session Handoff — 2026-09-16

## What We Did
Improved the MCTS heuristic scoring for Lost Cities to make rollout move selection more strategic.

## Key Changes

### Play Scoring (`compute_play_score_v2` in `validator.py`)
- Sequential constraint: only counts cards ≥ scored card
- Investment multiplier: counts only cards played after investments
- Killed penalty: lower-numbered cards × 3 (was × 1)
- Wasted investment: investments in hand × 15 when playing numbered card
- 8-card bonus: +20 if expedition reaches 8 cards

### Discard Scoring (`score_moves` in `validator.py`)
- Can't play → 10 (good discard)
- Can play, positive value → 0.5 (keep it)
- Can play, non-positive → 0 (dead card)

### `_weighted_choice` (`mcts.py`)
- Changed from shifting to clamping
- Prevents bad moves from getting inflated probability

## Test Results
- 71/72 pass (1 pre-existing failure)
- 18 new tests added across 2 test files

## Files Modified
- `app/games/lost_cities/validator.py`
- `app/core/mcts.py`
- `tests/test_score_moves_debug.py` (new)
- `tests/test_mcts_rollout_debug.py` (new)
- `AGENTS.md` (fully populated)

## Next Steps
- Consider running full game simulations to validate scoring in practice
- Monitor if discard scoring needs adjustment (0.5 threshold may need tuning)
- Checkers AI implementation is stubbed but not yet using MCTS

## Prompt for Next Session
```
Continue working on the rbgg Lost Cities MCTS engine. The scoring heuristic has been improved with compute_play_score_v2, updated discard scoring, and clamped weighted choice. Run `python scripts/simulate_game.py` to see how the AI plays with the new scoring. Consider adjusting thresholds if the AI still makes suboptimal moves.
```
