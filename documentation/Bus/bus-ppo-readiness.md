# Bus PPO Readiness and Implementation Plan

**Reviewed:** 2026-10-15 (pre-implementation snapshot)  
**Status:** Superseded for implementation status by [bus-rl-analysis.md](bus-rl-analysis.md). This historical assessment records the gates identified before Bus RL work; its “not implemented” statements describe that date only, not the current repository.

> **Current-state warning:** Bus now has a dependency-free RL adapter, fixed `Discrete(1094)` actions, observation schemas v1/v2, random/null/rule policies, a one-seat Gymnasium environment, PPO training/evaluation scripts, inference integration, and RL tests. See the linked analysis for current implementation and evaluation caveats. The rules and promotion gates below remain useful only where still applicable; re-verify against current code and requirements before acting on them.

## Decision: PettingZoo is not a prerequisite

PPO does not require PettingZoo. Stable-Baselines3 trains against Gymnasium environments; this repository's Lost Cities reference uses a one-seat Gymnasium environment with the other seat controlled inside the environment. Bus can follow the same pattern: one learner seat, two to four opponent seats, and automatic opponent turns between learner decisions. Adopt PettingZoo only if a future requirement specifically needs a standardized multi-agent API or algorithms that consume it.

The core adapter contract should stay independent of Gymnasium, PyTorch, and training packages. Keep rule legality and transitions in `BusValidator`; add a Bus-specific fixed action mapping/observation encoder and Gymnasium wrapper above that seam.

## What existed at the time of this assessment

- `BusValidator` owns deterministic setup, current actor/phase, legal move generation, validation, transitions, round lifecycle, score adjustment, terminal checks, and ranking.
- Bus supports 3–5 players; its game config describes player counts and phases.
- The standard game is public information after starting-player selection. State contains players' routes/resources, action slots, buildings, passengers, clock, and scores.
- `recommend_ai_move()` is a safe legal-move fallback, not a strategic teacher or benchmark policy.
- There is no Bus RL adapter, Gymnasium environment, fixed action-ID contract, mask, vector observation, reward implementation, PPO training/evaluation script, or RL-specific test suite.
- `documentation/Bus/bus_ai.md` is an earlier search/strategy design, not a committed or implemented PPO design.

## Correctness gates before collecting PPO data

The model can only learn the behavior the validator permits. Resolve these issues before training:

1. **Do not offer resolution moves after an action's remaining quota is zero.** Resolution generation currently dispatches to action-specific moves without first checking the remaining quantity. Add a regression for zero remaining, preserving only the explicit resolution-completion transition.
2. **Enforce maximum passenger transport for Vrrooomm!.** The rule requires an action to be carried out to the fullest legal extent. Pairwise passenger/destination moves can permit a sequence that becomes stuck below the maximum number of transports when an earlier choice blocks a later one. Define and test the maximum-completion rule against the selected edition.
3. **Close rules requirements that affect legal actions or scoring.** The requirements draft still lists edition, route topology/parallel cases, passenger satisfaction timing, component exhaustion, and product decisions as unresolved or awaiting sign-off. Resolve or explicitly defer each relevant item before training.
4. **Establish deterministic validator contracts.** Add seeded multi-step trajectories, actor-transition and terminal tests, and verify every offered move validates and applies without mutating the input state.

Relevant implementation surfaces: `api/app/games/bus/validator.py`, `api/app/games/bus/serialize.py`, `api/configs/bus.yaml`, `api/tests/test_bus.py`, and `documentation/Bus/bus_requirements.md`.

## Proposed RL contract at assessment date (now implemented in part)

This is a dated design proposal, not a current implementation checklist. Compare it with [bus-rl-analysis.md](bus-rl-analysis.md) and current source before applying it; the implemented action/observation schemas and current promotion caveats are maintained there.

### Learner and opponents

- Train one fixed learner seat at a time. The environment runs all other seats internally until the learner acts again or the game terminates.
- Start with 3-player games and a fixed, reproducible opponent mix. Expand to 4–5 players only after fixed-shape encoding and 3-player baselines are validated.
- Rotate the learner to a canonical first seat in observations; encode opponent order clockwise and player count explicitly.
- Bus is public-information; encode only rule-visible state and test serialization/encoding for leakage of server-only metadata.

### Action mapping and mask

- Define a versioned, fixed-size `Discrete(N)` universe using semantic action IDs, not indexes into the current legal-move list.
- Include all action families and their stable board entities: setup building/route choices, action-slot selection/pass, route extension, bus purchase, passenger placement, building placement/type, clock choice, transport choice, and any required completion action.
- Generate the boolean action mask from validator legal moves. Require a bijection between each representable legal move and exactly one active ID; reject unmappable actions rather than guessing.
- First inventory the actual maximum action families and entity counts from the signed-off board. Do not choose `N` from the current sample of legal moves.

### Observation and reward

- Version the observation schema and fix its shape across 3–5 players. Encode phase/actor, current resolution and quota, action-space ownership/order, player-relative resources/scores/routes, 72 street states, 36 crossings, 46 building locations, passenger positions, clock/stones, and game progress. Use stable IDs and canonical order.
- Start with the exact public adjusted score objective. A dense score-delta reward can use the learner's score change minus a documented opponent aggregate; rewards must telescope to the terminal objective. Avoid heuristic bonuses until baseline evidence demonstrates a learning need.
- End with the validator's authoritative game-over state/ranking. Use Gymnasium `terminated` for true game end and `truncated` only for a protective step cap.
- Keep seed handling and opponent randomness deterministic for reproducible resets and held-out evaluation.

## Staged plan

1. **Rule correctness:** resolve/sign off the rule questions and fix quota/maximum-transport legality with regression tests.
2. **Dependency-free adapter:** implement fixed IDs, semantic move round trips, exact legality mask, canonical/versioned observation, seeded reset, and direct-validator differential tests.
3. **One-seat Gymnasium environment:** auto-play opponents internally, return learner-perspective reward/observations, and test terminal/truncation/reward telescoping.
4. **Baselines:** compare random legal, passive, and a simple Bus-specific rule policy across swapped learner seats and held-out starting-player seeds. Record rank, adjusted score, score margin, move legality, and action distributions.
5. **Training experiment:** only after the contract and baselines pass, add optional PPO dependencies/training, snapshot opponents, checkpoint selection, and fixed-opponent evaluation. Select by held-out results—not training reward or final checkpoint.

## Promotion gate

Do not route Bus production turns to PPO until rule sign-off, adapter contracts, mask and trajectory tests, opponent baselines, multi-seat held-out evaluation, inference legality, and safe MCTS/rule fallback are all demonstrated. This document is a readiness plan, not evidence that Bus is PPO-ready today.
