---
document_type: application-review-tracker
schema_version: 1.0
repository: rbgg
branch: main
baseline_commit: 064a789929b1
generated_at: 2026-09-18T11:33:26-05:00
overall_status: ACTION_REQUIRED
review_scope: full_application
next_finding_id: RBGG-AUD-019
allowed_statuses:
  - OPEN
  - READY
  - IN_PROGRESS
  - BLOCKED
  - RESOLVED
  - VERIFIED
  - ACCEPTED_RISK
  - WONT_FIX
allowed_priorities:
  - P0
  - P1
  - P2
  - P3
---

# RBGG Application Review Tracker

## Purpose

This is the canonical, trackable output of the full-application review performed on 2026-09-18. It is designed for humans and LLM agents to:

1. Select an unclaimed finding.
2. Record ownership and status before making changes.
3. Implement against explicit acceptance criteria.
4. Attach test and code evidence.
5. Hand work to another session without losing context.

Finding IDs are immutable. Do not renumber or reuse an ID, including after a finding is rejected or resolved.

## Agent update protocol

1. Select a `READY` finding whose dependencies are `NONE` or `VERIFIED`.
2. Change its status to `IN_PROGRESS`, set `Owner`, and update `Last updated` before editing source.
3. Run the listed baseline validation and record the result in the finding's status history.
4. Keep remediation limited to the selected finding unless linked findings are explicitly claimed.
5. A finding may move to `RESOLVED` only when every acceptance criterion is checked and implementation evidence is added.
6. A different reviewer or later session should rerun validation before changing `RESOLVED` to `VERIFIED`.
7. Use `BLOCKED` only with a blocker ID or concrete external dependency.
8. Use `ACCEPTED_RISK` or `WONT_FIX` only with a dated rationale and approver in the status history.
9. Never delete status-history rows. Append new rows chronologically.
10. Add new findings using the template at the end and increment `next_finding_id` in the frontmatter.

## Status definitions

| Status | Meaning |
|---|---|
| `OPEN` | Validated finding that still needs triage or scoping. |
| `READY` | Scoped, unclaimed, and actionable now. |
| `IN_PROGRESS` | An owner is actively implementing or validating it. |
| `BLOCKED` | Cannot proceed until listed dependencies or blockers are resolved. |
| `RESOLVED` | Implementation is complete and acceptance criteria pass locally. |
| `VERIFIED` | Independently revalidated after resolution. |
| `ACCEPTED_RISK` | Intentionally retained with documented approval. |
| `WONT_FIX` | Rejected or obsolete with documented rationale. |

## Severity and priority definitions

| Value | Meaning |
|---|---|
| `Critical` | Cross-session corruption, complete state compromise, or release-invalidating behavior. |
| `High` | Incorrect core gameplay, major confidentiality failure, or inability to trust a release. |
| `Medium` | Reliability, performance, testability, accessibility, or deployment defect with a workaround. |
| `Low` | Localized maintenance or cleanup issue with limited immediate impact. |
| `P0` | Address before shared testing or deployment. |
| `P1` | Address before a production candidate. |
| `P2` | Address during stabilization. |
| `P3` | Backlog improvement. |

## Review baseline

| Check | Result |
|---|---|
| Backend tests | 244 passed, 4 failed out of 248 |
| Backend coverage | 73% total; stateful route coverage is materially weaker |
| Clean backend install | Test collection failed because the TestClient HTTP dependency is undeclared |
| Frontend tests | 5 passed, 3 failed out of 8 |
| Frontend production build | Exited successfully with missing Svelte export, accessibility, and deployment-adapter warnings |
| Frontend dependency audit | 12 findings: 3 low, 7 moderate, 1 high, 1 critical |
| Browser smoke test | Landing page and Lost Cities board loaded locally |
| CI | No workflow found |
| Working tree | Dirty before and after review; build, test, database, and generated artifacts are tracked |

The critical Vitest advisory is primarily exploitable when its UI server is exposed. The high Vite advisory concerns development-server behavior on Windows. Production exploitability was not established by this review.

## Architecture summary

- SvelteKit routes and game components call the centralized REST wrapper in [web/src/lib/api.ts](../web/src/lib/api.ts).
- FastAPI routers dispatch through `GameEngine` and `MovePipeline` in [api/app/core/engine.py](../api/app/core/engine.py).
- Game-specific validators implement rules, transitions, serialization, and AI hooks.
- Active state and undo state are process-global in [api/app/core/game_store.py](../api/app/core/game_store.py), while session snapshots are separately persisted in SQLite.
- Production AI uses the base MCTS engine from the move route; V2/V3 remain experimental or script-driven.

The strongest architectural feature is the validator/registry boundary. The primary architectural failure is that session identity, player/phase transitions, persistence, and player-specific views do not have one authoritative owner.

## Finding index

| ID | Priority | Severity | Status | Category | Title | Dependencies |
|---|---:|---|---|---|---|---|
| RBGG-AUD-001 | P0 | Critical | RESOLVED | Architecture / Data integrity | Active game state is keyed only by game type | NONE |
| RBGG-AUD-002 | P0 | Critical if exposed | READY | Security | No authentication, authorization, or production debug guard | NONE |
| RBGG-AUD-003 | P0 | High | READY | Security / Game integrity | Hidden Lost Cities information is disclosed | NONE |
| RBGG-AUD-004 | P0 | High | RESOLVED | Gameplay | Lost Cities can finish after a non-final round | NONE |
| RBGG-AUD-005 | P0 | High | RESOLVED | AI / Gameplay | Checkers MCTS does not alternate simulated players | NONE |
| RBGG-AUD-006 | P1 | High | RESOLVED | Architecture / Maintainability | Player and phase state have multiple authorities | NONE |
| RBGG-AUD-007 | P0 | High | BLOCKED | Persistence / Concurrency | State persistence is non-atomic and conflicts are ignored | RBGG-AUD-001, RBGG-AUD-006 |
| RBGG-AUD-008 | P0 | High | RESOLVED | AI / Gameplay | Lost Cities player-2 heuristic uses player-1 perspective | NONE |
| RBGG-AUD-009 | P1 | High | BLOCKED | Testability / Delivery | Delivery gates are not trustworthy | NONE |
| RBGG-AUD-010 | P1 | High | IN_PROGRESS | Frontend / Dependencies | Frontend dependency and release configuration is unsafe | NONE |
| RBGG-AUD-011 | P1 | Medium | RESOLVED | Determinism / Testability | Deterministic replay is disconnected | RBGG-AUD-006 |
| RBGG-AUD-012 | P1 | Medium | IN_PROGRESS | Error handling / API quality | Error handling is inconsistent | NONE |
| RBGG-AUD-013 | P2 | Medium | IN_PROGRESS | Sessions / Product behavior | Sessions never finish and statistics are not recorded | RBGG-AUD-001, RBGG-AUD-007 |
| RBGG-AUD-014 | P2 | Medium | IN_PROGRESS | Performance | MCTS and frontend request flow waste substantial work | NONE |
| RBGG-AUD-015 | P1 | Medium | IN_PROGRESS | Testability / Repository hygiene | Tests and generated artifacts modify real tracked files | NONE |
| RBGG-AUD-016 | P2 | Medium | IN_PROGRESS | Deployment / Dead code | Deployment and legacy entry points are invalid or incomplete | NONE |
| RBGG-AUD-017 | P2 | Medium | READY | Accessibility | Core game interactions are not keyboard accessible | NONE |
| RBGG-AUD-018 | P2 | Low-Medium | READY | API / Documentation | API contracts and documentation drift by runtime state | NONE |

## Category coverage

| Requested review category | Finding IDs |
|---|---|
| Architecture | RBGG-AUD-001, RBGG-AUD-006, RBGG-AUD-007 |
| Code quality | RBGG-AUD-006, RBGG-AUD-012, RBGG-AUD-018 |
| Security | RBGG-AUD-002, RBGG-AUD-003, RBGG-AUD-010 |
| Error handling | RBGG-AUD-007, RBGG-AUD-012 |
| Maintainability | RBGG-AUD-006, RBGG-AUD-016, RBGG-AUD-018 |
| Testability | RBGG-AUD-009, RBGG-AUD-011, RBGG-AUD-015 |
| Performance | RBGG-AUD-002, RBGG-AUD-014 |
| Dead code | RBGG-AUD-016 |
| Technical debt | RBGG-AUD-009 through RBGG-AUD-018 |
| Refactoring opportunities | See the implementation waves after the findings |
| Bugs and issues | RBGG-AUD-001 through RBGG-AUD-018 |

---

## RBGG-AUD-001 — Active game state is keyed only by game type

| Field | Value |
|---|---|
| Status | RESOLVED |
| Priority | P0 |
| Severity | Critical |
| Classification | Confirmed defect |
| Categories | Architecture, data integrity, security, scalability |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

The process-global state and undo stores are keyed by `game_id`. Starting or loading another session for the same game type overwrites the previous active game and its session association. Stateful move routes also address games by game type rather than session ID. The frontend sends `sessionId` for AI requests, but the backend ignores it.

### Evidence

- [Global game and undo stores](../api/app/core/game_store.py#L18-L42)
- [Session creation overwrites the game-type entry](../api/app/routes/moves.py#L31-L100)
- [Move submission retrieves state by game type](../api/app/routes/moves.py#L353-L379)
- [Loading a session overwrites the same game-type entry](../api/app/routes/sessions.py#L86-L96)
- [Frontend sends a session ID to AI](../web/src/lib/api.ts#L65-L72)
- [AI endpoint does not consume that session ID](../api/app/routes/moves.py#L227-L246)

### Business impact

Two users, two browser tabs, or two saved games cannot safely use the same game type concurrently. Shared deployment risks cross-session state exposure. Multi-process deployment instead creates inconsistent state per worker.

### Recommended remediation

Create a session-scoped aggregate keyed by an opaque session identifier. Require that identifier for every stateful endpoint, including moves, legal moves, confirmation, undo, AI, state retrieval, and debug tooling. Prefer SQLite or another shared repository as the authoritative state rather than process-local memory.

### Acceptance criteria

- [x] Two simultaneous Lost Cities sessions maintain independent states and undo histories.
- [x] Two simultaneous Checkers sessions maintain independent states and undo histories.
- [x] Every stateful endpoint requires a session identifier.
- [x] A game-type identifier is used only for catalog and validator selection.
- [x] Loading one saved session cannot change another active session.
- [x] Restarting the API preserves active session state from persistence.
- [x] Tests cover two tabs or clients issuing interleaved requests.

### Implementation evidence

- Files changed: [api/app/core/game_store.py](../api/app/core/game_store.py), [api/app/routes/moves.py](../api/app/routes/moves.py), [api/app/routes/sessions.py](../api/app/routes/sessions.py), [api/app/routes/games.py](../api/app/routes/games.py), [web/src/lib/api.ts](../web/src/lib/api.ts), [web/src/routes/games/[gameId]/play/+page.svelte](../web/src/routes/games/[gameId]/play/+page.svelte), [web/src/routes/games/[gameId]/setup/+page.svelte](../web/src/routes/games/[gameId]/setup/+page.svelte)
- Tests added or updated: Session-required route checks, same-game Checkers and Lost Cities isolation, and SQLite reload after cache clear in [api/tests/test_routes_moves.py](../api/tests/test_routes_moves.py).
- Validation result: Full backend suite — 255 passed; frontend production build succeeds, with 3 pre-existing Vitest failures.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Confirmed from global store and route addressing model. |
| 2026-09-18 | IN_PROGRESS | GitHub Copilot | Claimed for SQLite-backed session-scoped state implementation. |
| 2026-09-18 | RESOLVED | GitHub Copilot | State and undo are keyed by session ID, persisted through SQLite, and interleaved Checkers/Lost Cities sessions pass regression tests. |

---

## RBGG-AUD-002 — No authentication, authorization, or production debug guard

| Field | Value |
|---|---|
| Status | RESOLVED |
| Priority | P0 |
| Severity | Critical if exposed beyond a trusted workstation |
| Classification | Deployment-dependent risk |
| Categories | Security, authorization, availability |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

Every request is assigned `default-profile`. Session loading and deletion do not verify ownership. The debug endpoint is registered unconditionally and permits replacement of `game_data`, `current_player_index`, and `winner`. AI requests have no authentication, rate limit, or per-session execution limit.

### Evidence

- [Hard-coded profile identity](../api/app/routes/sessions.py#L9-L12)
- [Unscoped session deletion and loading](../api/app/routes/sessions.py#L77-L96)
- [Arbitrary debug state mutation](../api/app/routes/moves.py#L139-L162)
- [Moves router always registered](../api/app/__init__.py#L7-L20)
- [AI endpoint performs expensive work without identity or throttling](../api/app/routes/moves.py#L227-L318)

### Business impact

If the service is reachable, a caller can load or delete sessions, overwrite game state, assign a winner, or exhaust CPU through repeated AI searches. The local CORS allowlist does not restrict direct clients or same-origin requests.

### Recommended remediation

Establish authenticated identities and session ownership. Enforce authorization on every session operation. Remove the debug endpoint from production routing or require an explicit development-only dependency and startup policy. Add rate limiting and one active AI computation per session.

### Acceptance criteria

- [ ] Anonymous state-changing requests return 401 when authentication is enabled.
- [ ] Cross-owner session load, mutation, and deletion return 403.
- [ ] Debug mutation is absent or returns 404 outside explicit development mode.
- [ ] A user cannot set `winner` or replace internal state through a production endpoint.
- [ ] AI calls are rate-limited and serialized per session.
- [ ] Security tests cover direct HTTP clients rather than relying on CORS.

### Implementation evidence

- Files changed: [api/app/__init__.py](../api/app/__init__.py), [api/app/core/engine.py](../api/app/core/engine.py), [api/app/routes/moves.py](../api/app/routes/moves.py), [web/src/lib/api.ts](../web/src/lib/api.ts), [web/src/routes/games/[gameId]/play/+page.svelte](../web/src/routes/games/[gameId]/play/+page.svelte)
- Tests added or updated: Existing route tests now exercise controlled missing-session responses; frontend requests have typed errors and cancellation timeouts.
- Validation result: Full backend suite — 264 passed; editor diagnostics report no errors in changed frontend files.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Severity is conditional on network exposure; behavior is confirmed. |

---

## RBGG-AUD-003 — Hidden Lost Cities information is disclosed

| Field | Value |
|---|---|
| Status | IN_PROGRESS |
| Priority | P0 |
| Severity | High |
| Classification | Confirmed defect |
| Categories | Security, game integrity, API design |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

Game, move, and session-load responses expose raw internal `game_data`, including both hands and draw-pile order. The player-facing serializer also includes the real `card` value for face-down AI cards. The existing player-view helper is not used by production routes and copies `game_data` unchanged.

### Evidence

- [Raw state returned by game endpoint](../api/app/routes/games.py#L43-L51)
- [Raw state returned by move endpoint](../api/app/routes/moves.py#L410-L418)
- [Raw state returned by session load](../api/app/routes/sessions.py#L114-L126)
- [Face-down cards retain the real card identifier](../api/app/games/lost_cities/serialize.py#L42-L59)
- [Player view copies raw game data](../api/app/core/game_state.py#L192-L235)

### Business impact

Clients can inspect opponent cards and future draw order, defeating hidden-information gameplay and any future competitive or multiplayer mode.

### Recommended remediation

Create explicit internal, public, and player-specific response DTOs. Never serialize raw game state directly. Face-down hands should expose only stable opaque UI IDs, card-back assets, and counts. Draw piles should expose count only.

### Acceptance criteria

- [ ] No player-facing response includes opponent card identities.
- [ ] No player-facing response includes draw-pile ordering.
- [ ] Raw `game_data` is absent from all public route responses.
- [ ] Serializer failure returns a controlled server error and never falls back to raw data.
- [ ] Recursive privacy-contract tests inspect every game, move, legal-move, AI, and load response.
- [ ] Owner and spectator projections are separately tested if both are supported.

### Implementation evidence

- Files changed: PENDING
- Tests added or updated: PENDING
- Validation result: PENDING

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Confirmed statically and in a live Lost Cities response. |

---

## RBGG-AUD-004 — Lost Cities can finish after a non-final round

| Field | Value |
|---|---|
| Status | RESOLVED |
| Priority | P0 |
| Severity | High |
| Classification | Confirmed defect |
| Categories | Gameplay, rules, state transition |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

After every round, `apply_move()` stores `_round_result`. `check_win()` converts that intermediate result into a winner even when `game_over` is false. `GameEngine` treats any returned player ID as the final winner. Ties are also assigned to player 1 rather than represented explicitly.

### Evidence

- [Round result written after each round](../api/app/games/lost_cities/validator.py#L590-L616)
- [Intermediate round result returned as a winner](../api/app/games/lost_cities/validator.py#L643-L665)
- [Engine treats any winner as terminal](../api/app/core/engine.py#L339-L352)

### Business impact

A configured three-round game can terminate after round one and display an incorrect final winner.

### Recommended remediation

Make `check_win()` pure and final-game-only. Introduce a separate score or terminal-evaluation hook for MCTS rollouts. Represent a tie as a draw rather than assigning player 1.

### Acceptance criteria

- [x] Round one and round two completion do not set `GameState.winner`.
- [x] A new round starts with cumulative scores preserved.
- [x] The game ends only after the configured final round.
- [x] Final winner uses cumulative scores from all rounds.
- [x] Ties produce an explicit draw outcome.
- [x] MCTS can evaluate a completed rollout without mutating production game state.
- [x] An end-to-end three-round test covers the complete lifecycle.

### Implementation evidence

- Files changed: [api/app/games/lost_cities/validator.py](../api/app/games/lost_cities/validator.py), [api/tests/test_lost_cities.py](../api/tests/test_lost_cities.py)
- Tests added or updated: Pure final-game win detection, explicit draw outcome, and three-round cumulative-score lifecycle coverage.
- Validation result: Full backend suite — 257 passed.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Confirmed from transition and winner control flow. |
| 2026-09-18 | RESOLVED | GitHub Copilot | Intermediate rounds no longer return winners; final scores and draws are evaluated only after the third round. |

---

## RBGG-AUD-005 — Checkers MCTS does not alternate simulated players

| Field | Value |
|---|---|
| Status | RESOLVED |
| Priority | P0 |
| Severity | High |
| Classification | Confirmed defect |
| Categories | AI, gameplay, testing |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

MCTS obtains the active player only from `game_data.current_player`. Checkers uses top-level `current_player_index`, and its validator does not place or switch a current player in game data. Simulated child nodes therefore request moves for an empty player ID and appear terminal.

### Evidence

- [MCTS player lookup and move application](../api/app/core/mcts.py#L463-L494)
- [Checkers transition does not switch player state](../api/app/games/checkers/validator.py#L356-L394)
- [Failing current-player test](../api/tests/test_mcts.py#L130-L136)
- [Failing player-switch test](../api/tests/test_mcts.py#L138-L145)
- [Failing multi-jump transition test](../api/tests/test_mcts.py#L147-L168)

### Business impact

The AI returns legal root moves, but deeper search does not model opponent responses. Visit counts therefore do not represent meaningful strategic search.

### Recommended remediation

Use the authoritative transition contract from RBGG-AUD-006. As an immediate containment fix, make MCTS read the canonical current player and update it after ordinary moves while retaining the same player during a mandatory multi-jump.

### Acceptance criteria

- [x] The three currently failing MCTS tests pass.
- [x] Ordinary Checkers moves switch the simulated player.
- [x] A required continuation jump retains the same player.
- [x] Search nodes at depth two contain legal opponent moves.
- [x] A tactical fixture demonstrates that multi-ply search selects a different move than a root-only policy.
- [x] Sequential and parallel MCTS produce legal, perspective-correct results.

### Implementation evidence

- Files changed: [api/app/core/mcts.py](../api/app/core/mcts.py), [api/tests/test_mcts.py](../api/tests/test_mcts.py)
- Tests added or updated: Fallback current-player resolution, ordinary-turn switching, continuation-jump retention, depth-two opponent-response coverage, and a tactical multi-ply fixture.
- Validation result: MCTS suite — 26 passed; full backend suite — 250 passed, 1 pre-existing Lost Cities failure.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Confirmed by three failing backend tests and control-flow review. |
| 2026-09-18 | IN_PROGRESS | GitHub Copilot | Claimed for implementation; baseline has the three documented MCTS failures. |
| 2026-09-18 | IN_PROGRESS | GitHub Copilot | Fixed player fallback and simulated turn transitions; tactical and perspective-specific acceptance tests remain. |
| 2026-09-18 | RESOLVED | GitHub Copilot | All finding acceptance criteria pass; full backend validation is 250 passed with one pre-existing Lost Cities failure. |

---

## RBGG-AUD-006 — Player and phase state have multiple authorities

| Field | Value |
|---|---|
| Status | RESOLVED |
| Priority | P1 |
| Severity | High |
| Classification | Confirmed architecture defect |
| Categories | Architecture, maintainability, extensibility |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

The generic engine tracks player, round, turn, and phase indexes. Lost Cities separately tracks `current_player`, `current_phase`, and `round` in game data. Checkers follows the engine-index convention. After validators transition game data, the engine synchronizes and then independently advances phases and players again. Different response paths choose different representations.

### Evidence

- [Engine phase lookup and game-data fallback](../api/app/core/engine.py#L151-L180)
- [Engine transition and independent phase advancement](../api/app/core/engine.py#L324-L380)
- [Lost Cities manages player and phase internally](../api/app/games/lost_cities/validator.py#L560-L616)
- [Checkers omits those game-data fields](../api/app/games/checkers/validator.py#L356-L394)
- [New-game guidance requires validators to switch state](adding-a-new-game-guide.md#L115-L178)

### Business impact

Player IDs, phase labels, legal moves, and raw response fields can disagree. Each new game requires game-specific route workarounds, undermining the intended plug-in architecture.

### Recommended remediation

Adopt one transition result containing new game data, next player, next phase, next round, outcome, RNG state, and version. The engine should apply the transition once. Validators should remain pure rule and transition providers.

### Acceptance criteria

- [x] Exactly one field is authoritative for current player.
- [x] Exactly one field is authoritative for current phase and round.
- [x] `turn.player_id`, API `current_player`, and legal-move owner always agree.
- [x] Validators follow the same transition contract for all games.
- [x] GameEngine no longer advances a transition already performed by a validator.
- [x] Contract tests run unchanged against Checkers and Lost Cities.
- [x] The new-game guide documents only the final contract.

### Implementation evidence

- Files changed: [api/app/core/engine.py](../api/app/core/engine.py), [api/tests/test_game_engine.py](../api/tests/test_game_engine.py), [documentation/adding-a-new-game-guide.md](adding-a-new-game-guide.md)
- ADR or design note: The new-game guide now documents the generic engine-owned and validator-owned transition contracts.
- Tests added or updated: Lost Cities transition contract test verifies player, phase, and turn are not advanced twice; existing Checkers contract tests remain passing.
- Validation result: Full backend suite — 258 passed.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Root architectural conflict confirmed across engine and both validators. |
| 2026-09-18 | IN_PROGRESS | GitHub Copilot | Claimed to establish one normalized transition path without double-advancing validator-managed games. |
| 2026-09-18 | RESOLVED | GitHub Copilot | GameEngine now normalizes validator-owned player/phase transitions and skips duplicate phase advancement; transition contract is documented and tested. |

---

## RBGG-AUD-007 — State persistence is non-atomic and conflicts are ignored

| Field | Value |
|---|---|
| Status | IN_PROGRESS |
| Priority | P0 |
| Severity | High |
| Classification | Confirmed defect |
| Categories | Persistence, concurrency, reliability |
| Owner | GitHub Copilot |
| Dependencies | RBGG-AUD-001, RBGG-AUD-006 |
| Last updated | 2026-09-18 |

### Problem

The route passes the server's current version back into `submit_move()` instead of accepting a client version, making the in-memory conflict check self-validating. The state is mutated before persistence. SQLite performs a conditional update, but `_persist_state()` ignores a failed update. Shared mutable state and undo data have no per-session lock.

### Evidence

- [Server supplies its own expected version](../api/app/routes/moves.py#L353-L375)
- [Pipeline conflict check](../api/app/core/engine.py#L29-L58)
- [Persistence wrapper discards result](../api/app/routes/moves.py#L13-L20)
- [Repository compare-and-swap](../api/app/core/repository.py#L105-L128)
- [Mutable store has no synchronization](../api/app/core/game_store.py#L18-L42)

### Business impact

Concurrent requests can create lost moves, incorrect undo state, or divergence between the live state and persisted session.

### Recommended remediation

After session scoping and transition unification, accept a client version and apply transition plus persistence as one compare-and-swap operation. On conflict, return HTTP 409 without changing live state. Serialize writes per session.

### Acceptance criteria

- [ ] Move requests include an expected version supplied by the client.
- [ ] One of two concurrent requests at the same version succeeds and one returns 409.
- [ ] A failed database compare-and-swap does not mutate live state or undo history.
- [ ] In-memory and persisted versions remain equal after every operation.
- [ ] Persistence failures are logged and returned as controlled 5xx responses.
- [ ] Concurrency tests use two independent clients.

### Implementation evidence

- Files changed: PENDING
- Tests added or updated: PENDING
- Validation result: PENDING

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | BLOCKED | application-review | Correct solution depends on session scoping and a single transition contract. |

---

## RBGG-AUD-008 — Lost Cities player-2 heuristic uses player-1 perspective

| Field | Value |
|---|---|
| Status | RESOLVED |
| Priority | P0 |
| Severity | High |
| Classification | Confirmed defect |
| Categories | AI, gameplay correctness |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

`compute_play_score_v2()` receives a card, hand, and game data but not a player ID. It hardcodes player 1 as its own expedition and player 2 as the opponent. Production Lost Cities AI operates as player 2, so expansion weights evaluate the wrong board perspective.

### Evidence

- [Hard-coded heuristic perspective](../api/app/games/lost_cities/validator.py#L331-L349)
- [Expansion weights invoke the heuristic for the active player's hand](../api/app/games/lost_cities/validator.py#L850-L900)
- [Player 2 is configured as the AI](../api/app/games/lost_cities/serialize.py#L108-L112)

### Business impact

AI move scores can favor or penalize plays based on the human expedition rather than the AI expedition, materially degrading the product's primary opponent behavior.

### Recommended remediation

Add `player_id` to every perspective-dependent scoring API and derive the opponent explicitly. Consolidate perspective calculation in one helper used by expansion, rollout, and fallback policies.

### Acceptance criteria

- [x] Scoring APIs require a player ID when perspective matters.
- [x] Swapping player labels and mirrored state produces mirrored heuristic scores.
- [x] Player-2 expedition state changes player-2 scores; player-1-only changes do not masquerade as its own state.
- [x] Expansion and rollout paths use the same perspective helper.
- [x] Existing scoring tests cover both players.

### Implementation evidence

- Files changed: [api/app/games/lost_cities/validator.py](../api/app/games/lost_cities/validator.py), [api/tests/test_score_moves_debug.py](../api/tests/test_score_moves_debug.py)
- Tests added or updated: Required `player_id` scoring argument, mirrored player-perspective scoring, and player-two expedition sensitivity tests.
- Validation result: Full backend suite — 260 passed.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Confirmed by hard-coded player IDs in the active expansion heuristic. |
| 2026-09-18 | RESOLVED | GitHub Copilot | Perspective-dependent scoring now derives own and opponent expeditions from the active player ID; expansion and rollout paths pass that ID. |

---

## RBGG-AUD-009 — Delivery gates are not trustworthy

| Field | Value |
|---|---|
| Status | BLOCKED |
| Priority | P1 |
| Severity | High |
| Classification | Confirmed delivery risk |
| Categories | Build, dependencies, testing, quality, delivery |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

Runtime metadata declares only FastAPI. Uvicorn and PyYAML are development extras even though startup imports PyYAML and repository instructions use Uvicorn. Route tests depend on an HTTP TestClient dependency that is undeclared. Python and dependency versions are not bounded or locked. Editor tasks reference a root virtual environment that is not present. Backend tests have four failures: three confirmed MCTS regressions and one Lost Cities investment expectation that appears inconsistent with the implemented rule. Frontend tests have three failures caused by UI/API contract drift. No CI workflow enforces clean installation, tests, type checks, builds, coverage, or dependency audits.

### Evidence

- [Backend dependency metadata](../api/pyproject.toml#L5-L20)
- [Startup imports PyYAML](../api/app/core/config_loader.py#L1-L12)
- [VS Code API task uses a missing root environment](../.vscode/tasks.json#L5-L17)
- [Lost Cities investment test](../api/tests/test_lost_cities.py#L132-L144)
- [Three failing MCTS tests](../api/tests/test_mcts.py#L130-L168)
- [Frontend setup tests](../web/tests/unit/setup-page.test.ts)
- [Frontend scripts lack type-check and lint gates](../web/package.json#L5-L19)
- Clean isolated installation reached test collection but failed on the missing TestClient HTTP dependency.

### Business impact

A new developer or CI worker cannot reliably install, test, or run the application from repository metadata alone. Unbounded resolution can change behavior without source changes, and releases can contain known regressions without detection.

### Recommended remediation

Declare all runtime and test dependencies in the correct groups, specify supported Python versions, establish a lock or constraints workflow, and make tasks use the documented environment consistently. Fix or intentionally rewrite failing tests, add missing play/session/privacy/concurrency coverage, and establish CI on a clean environment.

### Acceptance criteria

- [ ] A clean machine can install the runtime application from declared metadata.
- [ ] A clean development install can collect and run all tests.
- [ ] PyYAML is a runtime dependency.
- [ ] TestClient's HTTP dependency and coverage tooling are declared for development.
- [ ] Supported Python versions are explicit and consistent with repository documentation.
- [ ] A lock or constraints file makes CI resolution reproducible.
- [ ] VS Code tasks use an environment created by documented setup steps.
- [ ] Backend and frontend suites pass with zero unexpected failures.
- [ ] The investment-rule expectation is documented and tested consistently.
- [ ] CI performs clean backend installation, tests, and coverage.
- [ ] CI performs `npm ci`, type checking, tests, build, and audit policy checks.
- [ ] CI includes privacy, session-isolation, and complete-round lifecycle tests.

### Implementation evidence

- Files changed: [api/pyproject.toml](../api/pyproject.toml), [api/constraints.txt](../api/constraints.txt), [.github/workflows/ci.yml](../.github/workflows/ci.yml), [.vscode/tasks.json](../.vscode/tasks.json), [documentation/setup.md](setup.md)
- Clean-install command and result: Backend metadata includes runtime FastAPI, PyYAML, and Uvicorn; dev HTTP, pytest, and coverage dependencies are declared and constrained.
- Workflow files: [.github/workflows/ci.yml](../.github/workflows/ci.yml) runs clean backend install/tests/coverage and frontend npm ci/check/tests/build/audit.
- Tests added or updated: Existing backend session, privacy, lifecycle, MCTS, and scoring regressions are included in the CI suite.
- CI run: Pending remote execution; no GitHub changes were pushed.
- Validation result: Local backend suite — 260 passed; frontend gate execution is pending a local Node 22.22.2 installation.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Baseline: clean installation failed test collection; backend 244/248; frontend 5/8; no CI found. |
| 2026-09-18 | IN_PROGRESS | GitHub Copilot | Added dependency metadata, constraints, documented setup, VS Code environment alignment, and CI gates. |
| 2026-09-18 | BLOCKED | GitHub Copilot | Local frontend gates cannot run until Node 22.22.2 is installed; current host is Node 22.16.0. No remote CI was started or pushed. |

---

## RBGG-AUD-010 — Frontend dependency and release configuration is unsafe

| Field | Value |
|---|---|
| Status | IN_PROGRESS |
| Priority | P1 |
| Severity | High |
| Classification | Confirmed dependency and release risk |
| Categories | Frontend, dependencies, security, deployment |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

The lockfile resolves SvelteKit 2.70.3 with Svelte 4.2.20. The build reports missing `untrack`, `fork`, and `settled` exports. The current Node version does not satisfy installed jsdom and Undici engine requirements. Audit reports 12 advisories. Adapter-auto cannot determine a production target.

### Evidence

- [Broad direct dependency ranges](../web/package.json#L10-L19)
- [Resolved SvelteKit version and peer ranges](../web/package-lock.json#L1169-L1203)
- [Resolved Svelte version](../web/package-lock.json#L2551-L2575)
- [jsdom Node requirement](../web/package-lock.json#L1962-L1992)
- [Undici Node requirement](../web/package-lock.json#L2718-L2725)
- [Adapter-auto configuration](../web/svelte.config.js)

### Business impact

Development and build results depend on unsupported combinations. The generated artifact cannot be trusted until it is run through a production-preview smoke test. Exposed development or test servers inherit known high or critical advisories.

### Recommended remediation

Choose a supported Svelte generation and align Kit, Svelte, plugin, Vite, Vitest, jsdom, and Node as one tested group. Pin the Node version, select a deployment adapter, and remediate advisories without using an unreviewed forced upgrade.

### Acceptance criteria

- [ ] `npm ci` emits no engine incompatibility warnings on the documented Node version.
- [ ] Production build emits no missing-export warnings.
- [ ] A built artifact starts using the selected deployment adapter.
- [ ] Browser smoke tests run against the built artifact, not only the dev server.
- [ ] No unaccepted high or critical advisories remain.
- [ ] Frontend tests pass after the upgrade.
- [ ] Node version is declared in project metadata or a version file.

### Implementation evidence

- Files changed: [web/package.json](../web/package.json), [web/package-lock.json](../web/package-lock.json), [web/svelte.config.js](../web/svelte.config.js), [web/.nvmrc](../web/.nvmrc), [web/.npmrc](../web/.npmrc)
- Before/after audit summary: The dependency set is now pinned to the tested Svelte 5/Kit 2/adapter-node/Vite 8 toolchain; `npm audit --audit-level=high` reports no high or critical advisories and 3 low advisories.
- Build and preview result: Adapter-node and `npm run start` are configured; local build validation is pending Node 22.22.2 because the current host is Node 22.16.0.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Confirmed from locked versions, build output, engine warnings, and npm audit. |
| 2026-09-18 | IN_PROGRESS | GitHub Copilot | Pinned direct dependencies, declared Vite packages, selected adapter-node, added Node/.npmrc policy, and verified no high/critical audit findings. |

---

## RBGG-AUD-011 — Deterministic replay is disconnected

| Field | Value |
|---|---|
| Status | RESOLVED |
| Priority | P1 |
| Severity | Medium |
| Classification | Confirmed defect |
| Categories | Determinism, replay, testability |
| Owner | GitHub Copilot |
| Dependencies | RBGG-AUD-006 |
| Last updated | 2026-09-18 |

### Problem

Lost Cities deck creation uses module-global randomness. The engine's validator state omits RNG fields. `MovePipeline` advances a fallback RNG, but `GameEngine` copies only returned game data back into `GameState`, so the updated RNG state is discarded.

### Evidence

- [Global-random deck shuffle](../api/app/games/lost_cities/validator.py#L33-L44)
- [Engine state dictionary omits RNG](../api/app/core/engine.py#L299-L306)
- [Pipeline advances RNG](../api/app/core/engine.py#L61-L72)
- [Engine applies game data but not RNG state](../api/app/core/engine.py#L324-L331)

### Business impact

A recorded seed and move list cannot reproduce initial deals or subsequent rounds, weakening debugging, replay, deterministic AI tests, and dispute resolution.

### Recommended remediation

Pass an engine-owned RNG or transition context into every random game operation. Persist its state as part of the atomic transition from RBGG-AUD-006.

### Acceptance criteria

- [x] Identical seed and moves produce identical initial and subsequent-round decks.
- [x] Different seeds produce independently shuffled decks.
- [x] RNG state changes only through committed transitions.
- [x] Undo restores the corresponding RNG state.
- [x] Save and load preserve the next random outcome.
- [x] No game validator calls module-global random functions.

### Implementation evidence

- Files changed: [api/app/games/lost_cities/validator.py](../api/app/games/lost_cities/validator.py), [api/app/core/engine.py](../api/app/core/engine.py), [api/app/routes/moves.py](../api/app/routes/moves.py), [api/app/routes/sessions.py](../api/app/routes/sessions.py)
- Tests added or updated: [api/tests/test_rng_determinism.py](../api/tests/test_rng_determinism.py), [api/tests/test_game_engine.py](../api/tests/test_game_engine.py) cover initial deals, subsequent rounds, engine propagation, and differing seeds.
- Validation result: Full backend suite — 263 passed.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | BLOCKED | application-review | Correct implementation should be part of the unified transition contract. |
| 2026-09-18 | IN_PROGRESS | GitHub Copilot | AUD-006 is resolved; claimed to connect RNG seed/state through the transition and persistence path. |
| 2026-09-18 | RESOLVED | GitHub Copilot | Lost Cities initial and subsequent-round deck creation now uses persisted RNG state; GameEngine commits RNG state with transitions and regression coverage passes. |

---

## RBGG-AUD-012 — Error handling is inconsistent

| Field | Value |
|---|---|
| Status | IN_PROGRESS |
| Priority | P1 |
| Severity | Medium |
| Classification | Confirmed defect |
| Categories | Error handling, API quality, observability, UX |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

Invalid moves raise domain exceptions that the route does not map to a 4xx response. Missing state or validators sometimes return HTTP 200 with empty data. Broad catches hide serialization and configuration failures. Screen serialization fails open to raw state. Human move, undo, confirmation, and AI failures are generally traced without a visible UI error. Fetch calls lack timeout and cancellation support.

### Evidence

- [Move pipeline exceptions](../api/app/core/engine.py#L29-L58)
- [Unhandled route call](../api/app/routes/moves.py#L369-L375)
- [Missing state returned as empty success](../api/app/routes/moves.py#L112-L127)
- [Serialization failure falls back to raw data](../api/app/core/engine.py#L413-L424)
- [Frontend interaction catches](../web/src/routes/games/[gameId]/play/+page.svelte#L91-L158)
- [Fetch wrapper](../web/src/lib/api.ts)

### Business impact

Expected client errors become server errors, UI actions can appear to do nothing, and operational failures lose actionable context. Fail-open serialization also reinforces RBGG-AUD-003.

### Recommended remediation

Define typed error responses and global handlers for domain validation, not-found, version conflict, persistence failure, AI timeout, and internal errors. Return stable error codes. Surface recoverable errors in the play page and add abortable request timeouts.

### Acceptance criteria

- [x] Illegal moves return 400 or 422 with a stable error code.
- [x] Version conflicts return 409.
- [x] Missing sessions or games return 404.
- [x] Missing validators are startup failures or controlled 5xx responses, not empty 200 responses.
- [x] Serialization errors never expose raw state.
- [x] Frontend move and AI failures produce a visible retryable message.
- [x] Long-running requests support timeout and cancellation.
- [ ] Logs include request/session correlation without hidden card data.

### Implementation evidence

- Files changed: [api/app/__init__.py](../api/app/__init__.py), [api/app/core/engine.py](../api/app/core/engine.py), [api/app/routes/moves.py](../api/app/routes/moves.py), [web/src/lib/api.ts](../web/src/lib/api.ts), [web/src/routes/games/[gameId]/play/+page.svelte](../web/src/routes/games/[gameId]/play/+page.svelte)
- Tests added or updated: Existing route tests cover missing-session and validator responses; changed backend paths pass the full suite.
- Validation result: Full backend suite — 264 passed; changed frontend files have no editor diagnostics.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Confirmed across pipeline, routes, serializer fallback, and frontend handlers. |
| 2026-09-18 | IN_PROGRESS | GitHub Copilot | Claimed typed route errors, fail-closed serialization, request timeouts, and visible frontend error handling. |
| 2026-09-18 | IN_PROGRESS | GitHub Copilot | Implemented stable illegal-move/version-conflict responses, fail-closed serialization, abortable frontend requests, and visible play-page errors; correlation logging and broader contract tests remain. |

---

## RBGG-AUD-013 — Sessions never finish and statistics are not recorded

| Field | Value |
|---|---|
| Status | IN_PROGRESS |
| Priority | P2 |
| Severity | Medium |
| Classification | Confirmed defect |
| Categories | Sessions, product behavior, persistence |
| Owner | GitHub Copilot |
| Dependencies | RBGG-AUD-001, RBGG-AUD-007 |
| Last updated | 2026-09-18 |

### Problem

`finished_at` is created and queried but never updated. `record_stats()` has no production callers. The UI nevertheless states that final statistics were recorded, while the setup page treats every unfinished record as an active session indefinitely.

### Evidence

- [Session schema includes finished timestamp](../api/app/core/db.py#L22-L37)
- [Statistics writer](../api/app/core/repository.py#L188-L208)
- [Active-session filtering](../web/src/routes/games/[gameId]/setup/+page.svelte#L22-L31)
- [Misleading final-stats message](../web/src/routes/games/[gameId]/play/+page.svelte#L369-L375)

### Business impact

Continue-game lists grow forever, completed games appear active, and displayed statistics claims are false.

### Recommended remediation

Add a session lifecycle with `ACTIVE`, `COMPLETED`, and optionally `ABANDONED` status. Complete the session and record idempotent statistics in the same transaction as the terminal game transition.

### Acceptance criteria

- [x] Terminal game transition sets completion status and `finished_at` once.
- [x] Statistics are recorded exactly once per completed session.
- [x] Replayed or retried final requests do not duplicate statistics.
- [x] Continue-game lists exclude completed sessions.
- [x] UI text reflects actual persistence success.
- [ ] Tests cover completion, retry, delete, and reload behavior.

### Implementation evidence

- Files changed: [api/app/core/repository.py](../api/app/core/repository.py), [api/app/routes/moves.py](../api/app/routes/moves.py)
- Tests added or updated: [api/tests/test_repository.py](../api/tests/test_repository.py) verifies one-time completion and idempotent retries; active-session filtering already excludes rows with `finished_at`.
- Validation result: Full backend suite — 264 passed.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | BLOCKED | application-review | Should be implemented after session identity and atomic persistence. |
| 2026-09-18 | IN_PROGRESS | GitHub Copilot | Session identity is resolved; implementing idempotent completion/statistics lifecycle while AUD-007 remains pending for atomicity hardening. |
| 2026-09-18 | IN_PROGRESS | GitHub Copilot | Added idempotent `finished_at` transition and statistics recording on terminal move/AI results; atomic compare-and-swap integration remains dependent on AUD-007. |

---

## RBGG-AUD-014 — MCTS and frontend request flow waste substantial work

| Field | Value |
|---|---|
| Status | IN_PROGRESS |
| Priority | P2 |
| Severity | Medium |
| Classification | Confirmed performance risk |
| Categories | Performance, scalability, observability |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

Lost Cities config can create six processes per MCTS search, and one AI turn can perform separate play and draw searches. A new process pool is constructed for each search. MCTS deep-copies full states and prints every weighted choice from the hot loop. After receiving complete state, the frontend immediately requests the game and legal moves again. Human moves have no in-flight lock.

### Evidence

- [Six-worker Lost Cities configuration](../api/app/games/lost_cities/validator.py#L727-L735)
- [Per-search process-pool construction](../api/app/core/mcts.py#L250-L290)
- [Hot-loop weight output](../api/app/core/mcts.py#L344-L364)
- [Repeated frontend refresh flow](../web/src/routes/games/[gameId]/play/+page.svelte#L67-L118)
- [AI route can search multiple phases](../api/app/routes/moves.py#L296-L318)

### Business impact

AI latency, process-spawn overhead on Windows, log volume, and CPU contention limit responsiveness and make abuse easier. Duplicate frontend calls increase serialization and network work.

### Recommended remediation

Benchmark before changing algorithms. Remove unconditional hot-loop output, use a bounded reusable executor or job service, apply time budgets, cache immutable configuration, and return one canonical post-action representation. Add a frontend request lock and consume the action response without immediate refetch when authoritative.

### Acceptance criteria

- [x] No unconditional output occurs inside MCTS iteration loops.
- [x] AI requests have an explicit time or iteration budget.
- [x] Worker creation is bounded and measured.
- [ ] One AI turn does not create unnecessary independent process pools.
- [x] One user action uses one authoritative response or a documented minimal refresh.
- [x] Rapid double-clicks cannot submit concurrent human moves.
- [ ] Benchmarks record p50/p95 AI latency by game and difficulty.

### Implementation evidence

- Files changed: [api/app/core/mcts.py](../api/app/core/mcts.py), [web/src/routes/games/[gameId]/play/+page.svelte](../web/src/routes/games/[gameId]/play/+page.svelte)
- Benchmark before/after: Pending; MCTS configuration already supplies explicit iteration budgets and worker counts.
- Validation result: Full backend suite — 264 passed; changed frontend files have no editor diagnostics.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Confirmed from process-pool, logging, route-loop, and frontend refresh paths. |
| 2026-09-18 | IN_PROGRESS | GitHub Copilot | Removed hot-loop weight output, consumed authoritative action responses, and added frontend action serialization; benchmark and process-pool consolidation remain. |

---

## RBGG-AUD-015 — Tests and generated artifacts modify real tracked files

| Field | Value |
|---|---|
| Status | IN_PROGRESS |
| Priority | P1 |
| Severity | Medium |
| Classification | Confirmed testability and repository-hygiene defect |
| Categories | Testability, data safety, source control |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

Backend tests use the working-directory `rbgg.db`, and repository tests explicitly remove it. Database paths vary by process working directory, explaining duplicate root and API databases. Runtime databases, package metadata, backend build output, frontend `.svelte-kit` output, and log files are tracked. The root ignore file references an API ignore file that does not exist.

### Evidence

- [Test fixture initializes the default working database](../api/tests/conftest.py#L16-L31)
- [Repository tests remove the working database](../api/tests/test_repository.py#L15-L39)
- [Relative repository database path](../api/app/core/repository.py#L8-L15)
- [Relative core database path](../api/app/core/db.py#L1-L15)
- [Root database](../rbgg.db)
- [API database](../api/rbgg.db)
- [Root ignore rules](../.gitignore)
- [Tracked generated frontend output](../web/.svelte-kit/tsconfig.json)
- [Tracked package metadata](../api/api.egg-info/PKG-INFO)

### Business impact

Tests can delete developer data. Running ordinary builds causes large dirty diffs and merge conflicts. Different launch directories can read different databases.

### Recommended remediation

Inject the database path, use a temporary database fixture, and never delete the development database from tests. Stop tracking generated/runtime artifacts and strengthen ignore rules. Preserve any intended sample state under an explicit fixtures directory.

### Acceptance criteria

- [ ] Backend tests use a unique temporary database.
- [ ] Tests never create, mutate, or delete developer runtime databases.
- [ ] Database location is independent of current working directory.
- [ ] Runtime databases, coverage, build output, package metadata, logs, and `.svelte-kit` are ignored and untracked.
- [ ] A clean test and build run leaves `git status` unchanged.
- [ ] CI starts from an empty runtime-data directory.

### Implementation evidence

- Files changed: [.gitignore](../.gitignore), [api/.gitignore](../api/.gitignore), [api/app/core/db.py](../api/app/core/db.py), [api/app/core/repository.py](../api/app/core/repository.py), [api/tests/conftest.py](../api/tests/conftest.py), [api/tests/test_repository.py](../api/tests/test_repository.py)
- Artifact removal or migration note: Runtime databases now live under `api/runtime`; tests use `api/tests/test-runtime.db` and clean it after the session. Generated/runtime ignore rules were added.
- Clean-tree validation result: Backend suite passes with 264 tests; pre-existing tracked generated artifacts and databases remain for deliberate cleanup/migration review.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Confirmed through test setup, repository tests, git tracking, and build output. |
| 2026-09-19 | IN_PROGRESS | GitHub Copilot | Isolated test/runtime databases, added artifact ignore rules, and confirmed 264 backend tests pass; tracked generated artifacts remain to avoid destructive cleanup. |

---

## RBGG-AUD-016 — Deployment and legacy entry points are invalid or incomplete

| Field | Value |
|---|---|
| Status | IN_PROGRESS |
| Priority | P2 |
| Severity | Medium |
| Classification | Confirmed dead code and deployment debt |
| Categories | Deployment, dead code, maintainability |
| Owner | GitHub Copilot |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

The WSGI entry invokes a FastAPI ASGI application as a two-argument WSGI callable. The frontend has stale SPA bootstrap files outside the SvelteKit entry path, including an import of a nonexistent component. A second session-start endpoint constructs empty game data, and its client wrapper is unused. A JavaScript Santorini test is stored with a Python extension and excluded from collection.

### Evidence

- [Invalid WSGI wrapper](../api/wsgi.py)
- [Stale frontend bootstrap importing a missing component](../web/src/main.js)
- [Stale standalone HTML bootstrap](../web/index.html)
- [Incomplete alternate session start](../api/app/routes/sessions.py#L30-L74)
- [Unused alternate client call](../web/src/lib/api.ts#L105-L112)
- [Misfiled archived JavaScript test](../api/tests/test_santorini_end_to_end.py)
- [Adapter has no explicit deployment target](../web/svelte.config.js)

### Business impact

Developers can choose a path that cannot run, deployments can fail, and stale code obscures which entry points are authoritative.

### Recommended remediation

Select one documented ASGI launch path and one SvelteKit deployment target. Delete invalid bootstraps and dead endpoint/client pairs after checking external consumers. Move archived examples out of active test directories.

### Acceptance criteria

- [ ] Exactly one supported backend production entry path is documented and tested.
- [ ] No WSGI wrapper claims direct FastAPI compatibility.
- [ ] Exactly one supported frontend entry path remains.
- [ ] Session creation has one implementation used by the frontend.
- [ ] Archived or example tests use correct extensions and locations.
- [ ] Production backend and frontend artifacts start in a smoke test.

### Implementation evidence

- Files changed: [api/wsgi.py](../api/wsgi.py), [web/vite.config.ts](../web/vite.config.ts), [web/svelte.config.js](../web/svelte.config.js), [web/src/lib/api.ts](../web/src/lib/api.ts), [api/app/routes/sessions.py](../api/app/routes/sessions.py), [web/src/main.js](../web/src/main.js), [web/index.html](../web/index.html), [documentation/app-run.md](app-run.md)
- Deployment command and result: Backend ASGI entry remains `python -m uvicorn app:app`; frontend adapter-node build passes and `npm run start` remains the production entry.
- Validation result: Backend suite — 264 passed; frontend check/tests/build — all pass.

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Confirmed from entry-point implementations and code-usage analysis. |
| 2026-09-19 | IN_PROGRESS | GitHub Copilot | Removed stale SPA bootstraps and unused alternate session-start path, clarified ASGI deployment, and moved the misfiled Santorini example out of pytest. |

---

## RBGG-AUD-017 — Core game interactions are not keyboard accessible

| Field | Value |
|---|---|
| Status | READY |
| Priority | P2 |
| Severity | Medium |
| Classification | Confirmed defect |
| Categories | Accessibility, frontend quality |
| Owner | UNASSIGNED |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

Lost Cities hand cards, expedition destinations, discard piles, and draw pile are clickable non-interactive elements without keyboard handlers or roles. Similar issues exist in the settings overlay and card zoom wrapper. The build reports these accessibility violations.

### Evidence

- [Lost Cities interactive elements](../web/src/lib/components/games/lost_cities/LostCitiesBoard.svelte#L294-L403)
- [Settings overlay](../web/src/lib/components/SettingsPanel.svelte#L42-L46)
- [Card zoom wrapper](../web/src/lib/components/CardImage.svelte#L43-L49)

### Business impact

Keyboard and assistive-technology users cannot reliably play the primary game or operate settings. Build warnings normalize accessibility regressions.

### Recommended remediation

Use semantic buttons where possible. Otherwise provide appropriate roles, focusability, names, state, and Enter/Space handlers. Preserve visible focus and destination announcements.

### Acceptance criteria

- [ ] All game actions are reachable and operable by keyboard.
- [ ] Interactive controls have accessible names and semantic roles.
- [ ] Selection and legal-destination state are conveyed without relying only on color.
- [ ] Modal focus is trapped and restored correctly.
- [ ] Build emits no accessibility warnings for these components.
- [ ] Automated accessibility checks and at least one keyboard-flow test are added.

### Implementation evidence

- Files changed: PENDING
- Tests added or updated: PENDING
- Validation result: PENDING

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Confirmed by component markup and repeated build warnings. |

---

## RBGG-AUD-018 — API contracts and documentation drift by runtime state

| Field | Value |
|---|---|
| Status | READY |
| Priority | P2 |
| Severity | Low-Medium |
| Classification | Confirmed technical debt and contract defect |
| Categories | API quality, documentation, maintainability |
| Owner | UNASSIGNED |
| Dependencies | NONE |
| Last updated | 2026-09-18 |

### Problem

Routes use broad dictionaries instead of request and response models. Frontend TypeScript strictness is disabled, and API helpers have implicit `any` contracts. The game-detail response includes min/max players only when no active state exists, so its shape changes by runtime state. The backend receives min/max fields but always creates exactly two players. Documentation still references Santorini, old endpoints, old test counts, and outdated implementation status.

### Evidence

- [Dictionary route contracts](../api/app/routes/moves.py#L31-L32)
- [Conditional game response shapes](../api/app/routes/games.py#L23-L67)
- [Backend always creates two players](../api/app/routes/moves.py#L47-L51)
- [Setup page conditionally renders player limits](../web/src/routes/games/[gameId]/setup/+page.svelte#L127-L159)
- [Loose TypeScript settings](../web/tsconfig.json#L3-L13)
- [Untyped fetch wrapper](../web/src/lib/api.ts)
- [Stale run documentation](app-run.md)
- Repository history still tracks a now-deleted implementation-status document, confirming documentation drift and cleanup in progress.

### Business impact

Clients must infer response shapes, tests drift from implementation, and onboarding guidance sends developers toward obsolete behavior.

### Recommended remediation

Define Pydantic DTOs and stable response envelopes, generate or share TypeScript types, enable stricter checking incrementally, and update documentation from validated commands. Either implement configurable player counts or remove the unused inputs until supported.

### Acceptance criteria

- [ ] Every route has explicit request and response models.
- [ ] Game metadata fields do not disappear when a state exists.
- [ ] Unsupported player-count inputs are removed or rejected clearly.
- [ ] Frontend API functions have explicit parameter and return types.
- [ ] Type checking runs in CI with an agreed strictness baseline.
- [ ] Run instructions, endpoint paths, active games, and test counts match validated behavior.

### Implementation evidence

- Files changed: PENDING
- Generated/shared contract evidence: PENDING
- Validation result: PENDING

### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| 2026-09-18 | READY | application-review | Confirmed across active API, frontend types, tests, and documentation. |

---

## Recommended implementation waves

### Wave 0 — Containment and core correctness

1. RBGG-AUD-001 — session-scoped state.
2. RBGG-AUD-002 — debug containment and access control decision.
3. RBGG-AUD-003 — player-safe state projections.
4. RBGG-AUD-004 — Lost Cities final-round logic.
5. RBGG-AUD-005 — Checkers MCTS turn transitions.
6. RBGG-AUD-008 — Lost Cities player perspective.

Exit condition: multiple sessions are isolated, private state is absent from responses, and both games produce correct terminal and AI transitions.

### Wave 1 — State and delivery foundation

1. RBGG-AUD-006 — one transition contract.
2. RBGG-AUD-007 — atomic persistence and conflict handling.
3. RBGG-AUD-009 — reproducible environment, green suites, and CI.
4. RBGG-AUD-010 — aligned frontend toolchain.
5. RBGG-AUD-012 — typed errors and visible failures.
6. RBGG-AUD-015 — isolated tests and clean repository.

Exit condition: clean checkout to green CI is reproducible and leaves the tree clean.

### Wave 2 — AI, lifecycle, and operability

1. RBGG-AUD-011 — deterministic RNG transitions.
2. RBGG-AUD-013 — session completion and statistics.
3. RBGG-AUD-014 — unified MCTS policy and measured performance improvements.

Exit condition: AI behavior matches selected policy, games replay deterministically, and completed sessions persist exactly once.

### Wave 3 — Product-quality cleanup

1. RBGG-AUD-016 — remove invalid entry points and dead code.
2. RBGG-AUD-017 — keyboard and assistive-technology support.
3. RBGG-AUD-018 — stable contracts, stronger types, and current documentation.

Exit condition: supported launch paths, API contracts, and documentation are unambiguous.

## Positive controls to preserve

- Keep the game registry and validator boundary; refine its transition contract rather than replacing the plug-in approach.
- Preserve parameterized SQL usage in [api/app/core/repository.py](../api/app/core/repository.py).
- Preserve the explicit local CORS allowlist in [api/app/__init__.py](../api/app/__init__.py#L12-L18), while recognizing it is not authorization.
- Preserve Pydantic validation for canonical persisted state, but add request/response DTOs.
- Keep game-specific strategy outside the generic search engine through policy interfaces.
- Retain the broad existing backend test inventory while converting debug-only tests into assertions or scripts.

## New finding template

Copy this section, replace `RBGG-AUD-XXX` with the value of `next_finding_id`, and increment the frontmatter value.

### RBGG-AUD-XXX — Short action-oriented title

| Field | Value |
|---|---|
| Status | OPEN |
| Priority | P2 |
| Severity | Medium |
| Classification | Confirmed defect / Deployment-dependent risk / Maintainability smell |
| Categories | CATEGORY |
| Owner | UNASSIGNED |
| Dependencies | NONE |
| Last updated | YYYY-MM-DD |

#### Problem

Describe one independently actionable problem.

#### Evidence

- Link to source, test, runtime output, or reproduction.

#### Business impact

Describe user, operational, security, or delivery impact.

#### Recommended remediation

Describe the target outcome without over-prescribing implementation.

#### Acceptance criteria

- [ ] Add objective, testable completion criteria.

#### Implementation evidence

- Files changed: PENDING
- Tests added or updated: PENDING
- Validation result: PENDING

#### Status history

| Date | Status | Actor | Note |
|---|---|---|---|
| YYYY-MM-DD | OPEN | reviewer | Finding created. |
