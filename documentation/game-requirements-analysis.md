# Game Requirements Analysis Guide

## Purpose

This document defines how to derive complete non-AI requirements from board-game rules. It contains no implementation instructions and no AI strategy. It is the requirements artifact for the rules, state, user experience, persistence, and validation of each game.

## Lifecycle position and authority

This analysis is the requirements gate in [game-implementation-guide.md](game-implementation-guide.md#game-lifecycle-from-idea-to-playable-game). Complete it before validator implementation. It defines intended behavior; code/tests establish implemented behavior but do not silently approve an unresolved rule. AI is intentionally out of scope here: record public/private state and decision facts, then use [board-game-ai-analysis.md](board-game-ai-analysis.md) to choose whether a rules policy, RL, search, hybrid, or no AI is appropriate.

## 1. Rules questions

Answer these before design:

- What is the exact objective?
- What constitutes a legal setup?
- What is the initial state for every player?
- Who acts first and how is order determined?
- What phases exist and what ends each phase?
- Which actions are mandatory, optional, or mutually exclusive?
- What happens when no legal action exists?
- Which resources, cards, pieces, or spaces are public/private?
- What are all costs, rewards, penalties, limits, and tie-breakers?
- What ends a round and what ends the game?
- How are scores calculated, accumulated, reset, or persisted?

## 2. State requirements

Define the authoritative state model in plain language:

- Players and identities.
- Turn owner and turn order.
- Current round, turn, phase, and pending continuation.
- Board, zones, hands, decks, discard piles, resources, and scores.
- Random generator state and reproducibility requirements.
- Game-over and winner state.
- Version/concurrency expectations.
- Which fields are derived and can be recomputed.

For every field specify whether it is public, private to a player, server-only, persisted, serialized, or search-only.

## 3. Legal-action requirements

For every action type specify:

| Requirement | Questions |
|---|---|
| Preconditions | What must be true before the action? |
| Inputs | Which player, card, space, source, amount, or choice is required? |
| Validation | How is an invalid request rejected? |
| Mutation | What state changes atomically? |
| Turn/phase | Who acts next and which phase follows? |
| Randomness | What is drawn, shuffled, rolled, or revealed? |
| Response | What should the API return? |
| Errors | Which client-visible error is appropriate? |

Move identity must not be the only validation mechanism; semantic content must remain sufficient to validate a client request.

## 4. Round and lifecycle requirements

Document:

- Setup and reset.
- Round start and round end.
- Score settlement.
- Final-round behavior.
- Draw and tie behavior.
- Abandonment, restart, undo, and session completion.
- What happens on invalid, duplicate, stale, or repeated requests.
- Persistence after every authoritative transition.

## 5. Serialization and views

Define the screen contract separately from the internal state:

- What each player may see.
- How hidden cards/resources are represented.
- Board coordinates and component identifiers.
- Card/piece image and accessibility metadata.
- Current player and phase labels.
- Legal-action affordances.
- Scores, round information, and game-over display.
- Empty, loading, error, and stale-state states.

Serialization must fail closed: private information must never be exposed because a field was omitted from a view filter.

## 6. Configuration requirements

Specify the configuration needed to describe the game:

- Game ID and display name.
- Player limits.
- Topology and dimensions.
- Panels and required components.
- Round/turn/phase names and user-facing text.
- Assets and image paths.
- Difficulty labels and defaults.
- Feature flags and optional panels.

Configuration names must match the validator’s phase/state names exactly.

## 7. Frontend requirements

Define the user flows:

- Create/select a game.
- View initial state.
- Select a piece/card/resource.
- Preview legal actions.
- Submit an action.
- Show pending/disabled state.
- Refresh after server response.
- Handle errors and stale versions.
- Show opponent/AI turns.
- Finish and restart a game.

For each screen identify observable success criteria and accessibility requirements.

## 8. Persistence and API requirements

Specify:

- Endpoints and HTTP methods.
- Request and response schemas.
- Session identity.
- Authorization boundary, if applicable.
- Idempotency behavior.
- Conflict/version behavior.
- Transaction boundaries.
- Restart/recovery behavior.
- Logging and sensitive-data rules.

## 9. Non-AI acceptance requirements

A game is requirements-complete when tests can verify:

- Every rule and legal-action boundary.
- Every phase transition.
- Every score and terminal condition.
- Every random transition with deterministic seeds.
- State isolation between sessions.
- Serialization visibility rules.
- Invalid and stale requests.
- Restart, completion, and persistence behavior.
- Frontend rendering and interaction for each required action.

## 10. Requirements sign-off

Record unresolved questions explicitly. No implementation should begin with hidden assumptions about:

- Phase ownership.
- Turn advancement.
- Score timing.
- Randomness.
- Hidden information.
- Terminal conditions.
- Undo/persistence behavior.
- Client-visible state.

For each question record: stable ID, source/rule citation, status (`approved`, `open/blocking`, or `deferred`), decision owner/date, selected answer, implementation/test evidence, and downstream impact. Open questions affecting legal moves, score, actor order, or terminal behavior block the playable-game gate. A deferred issue must name the exact excluded behavior and must not be described as implemented rules support.

## 11. Playable-game acceptance handoff

Before AI adapter or training work begins, the requirements owner and implementer should be able to point to evidence for:

- all rule-bearing open questions resolved or safely bounded as explicit deferrals;
- each action's legal and illegal examples and each phase/terminal transition;
- public/private serialization contract and persistence/restart behavior;
- human UI flow for setup, all action types, errors, completion, and restart;
- deterministic backend tests, frontend tests, and a complete browser smoke game.

These criteria establish game playability, not bot readiness or strength. AI requirements and promotion evidence belong in the game's AI analysis and experiment record.
