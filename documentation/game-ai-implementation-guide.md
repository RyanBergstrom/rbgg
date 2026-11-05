# Game AI Implementation Guide

## Purpose

This is the **search-based AI** implementation guide for coding a smart policy after the rules-correct playable-game gate and AI method decision. It covers policy boundaries, evaluator design, search, hidden information, portfolio planning, diagnostics, calibration, and promotion gates. It is not the default AI architecture for every game. For learned policies, use the [RL game AI playbook](rl-game-ai-playbook.md); for shared rule/action/provider boundaries, use the [game implementation guide](game-implementation-guide.md).

## Method choice and integration boundary

Before building search, record why search is appropriate versus a rules policy or RL. Search is useful when a trustworthy evaluator and affordable transitions exist; it is not a prerequisite for RL. RL is appropriate only when a correct, fast-enough headless environment, meaningful baselines, observation/action contracts, and evaluation capacity exist. Hybrid systems may use a learned prior/value function with search, but each component must have isolated contracts and evidence.

All methods call the authoritative validator for legal actions and transitions. A provider returns a semantic move; the route validates it before applying. Provider errors, missing artifacts, invalid moves, latency limits, actual provider used, and fallback reason must be observable. Keep game rules out of the shared search engine and keep all AI-specific dependencies out of validators.

## 1. Policy boundary

The generic engine owns:

- Tree nodes and traversal.
- Selection and expansion.
- Budgets and depth.
- Backpropagation.
- Deterministic search randomness.
- Candidate diagnostics.

The game policy owns:

- Legal actions and transitions through the validator.
- Terminal reward.
- Immediate action evaluation.
- Horizon evaluation.
- Hidden-information handling.
- Strategic priors/bounds.
- Game-specific dominance and discard/draw decisions.

Do not put game-specific scoring or imports into core MCTS.

## 2. Search contract

Define and test:

- Root-player perspective.
- Terminal values: win `1.0`, draw `0.5`, loss `0.0`.
- Nonterminal horizon values in `[0,1]`.
- Action values in `[0,1]`.
- Actor transitions at every phase.
- Maximum depth meaning.
- Hidden-information sampling or public-information approximation.

Every validator transition used by search must preserve the complete transition result, including RNG and phase fields.

## 3. Immediate evaluator

For each candidate calculate:

```text
one_ply_value = immediate_action_quality
              + resulting_position_quality
              + concrete_progress
              - marginal_commitment_cost
```

Clamp only at the final policy boundary, but expose the unclamped components in diagnostics.

### Play evaluation

Score:

- Immediate score and legal progression.
- Existing expedition/project value.
- Future compatible support.
- Investment/combo setup.
- Bonus reachability.
- Stranded lower cards/resources.
- Recovery risk.
- Portfolio opportunity cost.

### Discard evaluation

Discard is not automatically bad and not automatically safe:

```text
discard value = cleanup value
              + portfolio relief
              + avoided recovery risk
              - lost plan value
              - stagnation cost
```

Allow relief-bearing discards to compete with marginal plays, while keeping ordinary neutral discards below clearly strong plays.

### Draw evaluation

Evaluate each draw source by the actual visible or hidden value obtained:

- Draw-pile uncertainty.
- Discard card usefulness.
- Existing-expedition extension.
- New-expedition recovery risk.
- Investment support.
- Opponent denial.
- Hand replacement quality.

Legal-to-play is not sufficient. A discard-pile card that would create a negative new expedition must be downgraded even if it is technically playable.

## 4. Horizon evaluator

Use explicit normalized components:

```text
horizon = relative_margin
         + absolute_efficiency
         + future_equity
         + setup_value
         - spread_pressure
         - portfolio_pressure
         - stagnation
         - known_bad_draw_penalty
```

The policy must report both normalized components and raw explanations.

### Portfolio model

Each active expedition/project consumes future play actions. Estimate:

- Plays needed to become positive.
- Plays needed to reach a meaningful target.
- Whether the bonus/maximum length remains reachable.
- Known support and unavailable cards.
- Available action budget before the deck/round ends.

Apply:

```text
marginal portfolio cost = max(0, pressure after - pressure before)
```

A fourth or fifth project requires stronger positive evidence than the first two. Do not ban it categorically; make it earn its action budget.

## 5. Hidden information

Do not evaluate from hidden opponent hands or exact future draw order unless the game rules grant that information. Choose one:

- Determinization per simulation.
- Belief sampling.
- Public-information heuristic.

Record the limitation in diagnostics and do not claim playing strength from a perfect-information search.

## 6. Pruning and widening

Use safe progressive pruning:

- Rank root actions with one-ply values and optimistic bounds.
- Keep moves within a score margin of the best.
- Retain a minimum safety set.
- Preserve at least one play and discard when legal.
- Move clearly unrecoverable openings to the cold pool or dominate them only when alternatives exist.
- Keep hidden-information surprises available for later admission.

An optimistic bound may use all known compatible support, but must not assume unavailable cards or perfect future draws.

## 7. Diagnostics

Every explained search should show:

- Move, one-ply value, visits, average, selection score.
- Path and depth.
- Horizon components.
- Spread pressure.
- Portfolio pressure.
- Marginal portfolio cost.
- Recovery demand and available action budget.
- Raw per-color/project equity.
- Draw-source value.
- Discard relief.
- Optimistic bound and whether the move was hot/cold/dominated.

Diagnostics must make it possible to answer: “Why did this move beat discarding?”

## 8. Calibration fixtures

Create deterministic tests for:

- Strong two-project plan.
- Supported third project.
- Unsupported third project.
- Fourth project with positive recovery.
- Fifth project that overloads the play budget.
- Discard relief versus marginal play.
- Useful discard draw versus merely legal discard draw.
- Known dead discard draw.
- Eight-card bonus reachable and impossible.
- Hidden-information uncertainty.
- All-actions-bad fallback.

## 9. Performance

Measure:

- Search time per decision.
- p50/p95 latency.
- Iteration throughput.
- Average depth.
- Root action coverage.
- Cache/transposition hit rate if used.
- Determinization count and variance.

Optimize only after correctness evidence exists. Prefer evaluator caching, immutable canonical state keys, transposition reuse, and progressive widening before increasing iteration counts.

## 10. Promotion gates

Do not promote a policy based on one replay. Require:

- Full rule and policy tests.
- Deterministic tactical fixtures.
- Paired seat-swapped games.
- Multiple seeds and game seeds.
- Comparison against a baseline policy.
- Positive-score rate.
- Average score and score variance.
- Frequency of four- and five-project portfolios.
- Frequency of repeated draw/discard cycles.
- Hidden-information robustness where applicable.

A policy is ready when it makes legal, explainable, reproducible decisions and demonstrates improved outcomes across a benchmark set, not merely when one game looks better.
