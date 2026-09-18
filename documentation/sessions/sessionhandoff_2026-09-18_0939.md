# Session Handoff — 2026-09-17

## What We Did

Fixed critical bugs in the MCTS heuristic scoring and implemented a move filter to prevent bad opening moves.

## Key Changes

### Bug Fixes (`validator.py`)

1. **`compute_play_score_v2` card inclusion bug** (line ~376-385):
   - The card being played was NOT included in `guaranteed_cards` because the loop started at `start_index` which was after the card's position
   - Fix: Added `guaranteed_cards.append(card)` before the loop, with `if c == card: continue` in loop to avoid duplication
   - Impact: Scores now correctly reflect the card being played (e.g., blue-3 went from -5.5 to -22.5)

2. **Investment duplicate bug** (line ~376-385):
   - When scoring an investment, the card was added twice: once in `guaranteed_investments` and once via `append(card)`
   - Fix: Only append card if it's not an investment: `if not is_investment(card): guaranteed_cards.append(card)`
   - Impact: Investment scores corrected (e.g., white-i went from 1.5 to 1.0)

### Move Filter (`validator.py:741-800`)

New `filter_moves` implementation for first 5 turns:
- Only play the lowest numbered card of each color in hand
- Investments are always allowed (must play investments before numbered cards)
- Additional restrictions on discards and draws for turns 1-2
- Prevents MCTS tree from expanding bad opening moves like playing white-7 with white-i in hand

## Test Results

- 91 passed, 4 failed (all pre-existing failures)
- Updated `test_score_moves_debug.py` expectations to match corrected scoring

## Files Modified

- `app/games/lost_cities/validator.py` — scoring bugs fixed, filter_moves updated
- `app/core/mcts_v3.py` — removed debug logging
- `tests/test_score_moves_debug.py` — updated test expectations

## Key Insight: MCTS Self-Play Problem

Discovered that MCTS with heuristic rollouts has a fundamental issue:
- Both players use the same heuristic during rollouts
- A "bad" move can still win if the opponent plays worse
- The heuristic must be accurate in **absolute terms**, not just relative to itself
- Visit counts reflect "whoever plays against the heuristic wins most" — not "which move is objectively best"

## Next Steps

- Run full game simulations to validate filter behavior
- Consider making heuristic more accurate for absolute move quality
- Monitor if filter is too restrictive (might prevent good unconventional plays)
- Checkers AI implementation is stubbed but not yet using MCTS

## Open Questions

- Should the heuristic be used as priors for expansion (not just rollouts)?
- Is the 5-turn filter too long? Should it be 3 turns?
- Should we mix heuristic and random rollouts to reduce self-play bias?

## Prompt for Next Session

```
Continue working on the rbgg Lost Cities MCTS engine. The compute_play_score_v2 bug is fixed (card now included in guaranteed_cards) and a move filter prevents bad opening moves (first 5 turns only play lowest card of each color). Run `python scripts/simulate_game.py --iters 200` to see how the AI plays with the filter. Consider whether the heuristic needs to be more accurate for absolute move quality, or if we should mix heuristic and random rollouts.
```
