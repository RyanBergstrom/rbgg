# Board-Game-to-AI Analysis Guide

## Purpose

This document is the required design artifact between a game rules document and AI implementation. It explains how to turn rules into a complete decision model: actions, state transitions, information boundaries, objectives, risks, and test positions. It is not a coding guide.

Complete the rules-correct playable-game gate in [game-implementation-guide.md](game-implementation-guide.md#game-lifecycle-from-idea-to-playable-game) before implementing any AI. This analysis is method-neutral: it does not imply MCTS or RL is mandatory. Record whether AI is deferred, rules-based, RL, search, or hybrid and justify the choice against the decision problem and available evaluation evidence.

Every new game that will receive AI must have a game-specific analysis using this structure before AI work begins. First pass the human-playable gate; then complete this method-neutral analysis before implementing the selected AI approach.

## 1. Rule inventory

Record the rules without interpretation:

- Objective and win/loss/draw conditions.
- Setup, starting resources, player order, and first-player rules.
- Every phase and sub-phase of a turn.
- Every legal action in every phase.
- Mandatory versus optional actions.
- Costs, rewards, penalties, limits, and irreversible effects.
- Random events, draws, dice, shuffles, and replacement rules.
- End-of-round, end-of-game, and tie-breaking rules.

For each rule, identify whether it changes public state, private state, available actions, score, or turn ownership.

## 2. Complete turn model

Create a table for every phase:

| Phase | Actor | Legal actions | Resulting phase | Actor after action | Randomness | Public changes | Private changes | Terminal condition |
|---|---|---|---|---|---|---|---|---|

Define the search decision unit explicitly:

- Atomic action: every legal validator action is one search edge.
- Complete turn: several mandatory sub-actions are bundled.
- Phase bundle: dependent actions are grouped only when no meaningful decision exists between them.

For RBGG, use atomic actions when a player chooses among play, discard, draw source, continuation, or other meaningful phase alternatives.

## 3. State and information model

Classify every state field:

- Public authoritative state.
- Root-player private state.
- Opponent-private state.
- Random future state.
- Derived/cache state.
- Search-only metadata.

Document what the AI is allowed to know. Hidden hands, future draw order, unrevealed dice, and private objectives must not leak into evaluation. For hidden-information games define determinization, belief sampling, or a conservative public-information approximation.

## 4. Action inventory

For each action type define:

- Preconditions.
- Required fields.
- State mutation.
- Cost and reward.
- Whether it is reversible.
- Whether it changes actor or phase.
- Immediate tactical purpose.
- Strategic purpose.
- Common traps.
- What a strong opponent can do in response.

Do not stop at legal move generation. List strategically meaningful distinctions between actions that are legally similar.

## 5. Possibility tree

For each decision type, enumerate:

1. Immediate outcomes.
2. Opponent replies.
3. Random outcomes.
4. Resource and tempo consequences.
5. Recovery paths.
6. Irreversible failure paths.
7. End-game consequences.

Use optimistic, expected, and pessimistic branches. For card games record known support, unknown support, cards already unavailable, and the number of plays needed to realize a plan.

## 6. Strategic plans and commitments

Identify the plans a player can pursue and their commitment cost:

- What starts a plan?
- What cards/resources make it viable?
- What minimum support is required?
- How many actions are needed to realize it?
- When does it become positive or winning?
- What cards become stranded?
- What other plans does it prevent?
- When should it be abandoned?

For multiple expeditions/projects, model a portfolio. A new project must compete with improving existing projects for the remaining action budget.

## 7. Evaluation features

For each feature document raw formula, direction, scale, normalization, weight hypothesis, and fixture:

- Immediate action quality.
- Current score or material margin.
- Absolute efficiency.
- Future equity and support.
- Completion or bonus probability.
- Commitment/recovery demand.
- Tempo and opportunity cost.
- Opponent denial.
- Deadwood and stranded resources.
- Urgency.
- Stagnation and repeated no-progress cycles.

Never use a feature merely because it sounds strategic. Identify the observable evidence it measures.

## 8. Candidate comparison

Define how the AI compares a move that starts a plan with one that improves an existing plan:

```text
net action value = immediate value
                 + resulting-position value
                 + future plan value
                 - recovery demand
                 - opportunity cost
                 - irreversible risk
```

For multiple active plans:

```text
portfolio pressure = recovery demand - available action budget
marginal commitment cost = pressure(after move) - pressure(before move)
```

## 9. Diagnostics and fixtures

Before implementation, create deterministic positions for:

- Best opening plan.
- Supported versus unsupported commitment.
- Positive versus negative recovery line.
- Bonus reachable versus impossible.
- Safe discard versus harmful discard.
- Useful discard draw versus merely legal discard draw.
- Hidden-information uncertainty.
- Late-game urgency.
- All-actions-bad fallback.

Every fixture must state the expected preferred action and why.

## 10. AI readiness gate

AI implementation may begin only when the analysis answers:

- What does every action do?
- Who acts next and in which phase?
- What information is hidden?
- What plans exist?
- How many actions does each plan require?
- What makes a plan recoverable?
- What makes it irrecoverable?
- How are alternatives compared?
- Which decisions need search versus deterministic rules?
- What fixtures prove the intended behavior?
- Which method (rules, RL, search, hybrid, or none) best fits the game and why?
- Has the human-playable gate passed independently of AI?
