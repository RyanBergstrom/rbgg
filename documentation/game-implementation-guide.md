# Game Implementation Guide

## Purpose

This is the end-to-end guide for taking a game idea to a rules-correct, playable implementation, then optionally adding a trained RL bot, search bot, or both. It incorporates lessons from Checkers, Lost Cities, Bus, the shared engine, validator-owned phases, serialization, persistence, and frontend integration. Rules correctness and a working human-playable game are deliverables on their own; AI is a later, independently gated layer.

## Game lifecycle from idea to playable game

Use these gates in order. Do not start model training to compensate for missing, ambiguous, or incorrect game rules.

1. **Intake and source of truth.** Identify the exact rulebook/edition, player counts, board/components, target user flow, and constraints. Record citations or supplied rule sources. Separate official rules from product choices (undo, confirmation, bot difficulty, presentation).
2. **Rules and product requirements.** Complete [game-requirements-analysis.md](game-requirements-analysis.md): initial state, actions, legal boundaries, phase/actor transitions, randomness, scoring, tie-breaks, terminal conditions, visibility, persistence, API, UI, and acceptance criteria. Mark each ambiguity approved, open/blocking, or explicitly deferred with its scope and consequence.
3. **State/action contract and design.** Specify the authoritative state, player-relative view, all action payloads, deterministic seeding, and ownership of phase advancement. Complete [board-game-ai-analysis.md](board-game-ai-analysis.md) even when AI is deferred; it records information boundaries and expert decision inputs, not a commitment to train a model.
4. **Rules implementation.** Implement configuration, validator, registry, and screen serialization. Validator is the sole authority for legal actions, transitions, score, and winner. Add rule-derived fixtures before broad UI work.
5. **Playable-game gate (required before AI).** Verify all rules and transitions, persistence/reload/session isolation, privacy-safe serialization, usable setup/play/game-over UI, and human interaction for every action. Run backend/frontend tests and an end-to-end smoke playthrough. Resolve every rules ambiguity that changes legality, scores, turn flow, or termination; otherwise explicitly gate the affected functionality. The result must be a complete game without an AI provider.
6. **AI-method decision (optional).** Choose `none/rules-only`, `RL`, `search`, or `hybrid` based on game properties, available simulator speed, information boundaries, explainability, and evaluation budget. Document why in the game's AI analysis. Do not default to MCTS merely because it is familiar, and do not require RL when a simple policy is sufficient.
7. **AI contract and baselines.** For RL, follow [rl-game-ai-playbook.md](rl-game-ai-playbook.md): dependency-free adapter, fixed semantic action IDs, exact masks, versioned observations, one-seat Gymnasium env, reward tests, and random/null/rule baselines. For search, follow [game-ai-implementation-guide.md](game-ai-implementation-guide.md). Both consume the same authoritative validator, must return validator-legal moves, and must not own rules.
8. **Train/evaluate/integrate.** Train only after adapter/env contracts and baselines pass. Select checkpoints with held-out, sufficiently diverse evaluation—not training reward. Integrate behind a provider boundary with provider/result diagnostics, configured fallback, bounded latency, and a rollback/default policy.
9. **Release and maintenance.** Run full regression and browser smoke tests, update the game index, requirements, AI analysis/experiment log, `AGENTS.md`, and `work-items.md`. Preserve model/schema compatibility and label superseded evidence as historical.

### Completion criteria by gate

| Gate | Evidence required | Must not be conflated with |
|---|---|---|
| Rules-ready | Approved rule source/rulings, state/action model, acceptance fixtures | UI completion or AI quality |
| Playable | Human can complete setup, legal play, scoring, and end game; state persists/reloads; tests pass | Bot strength |
| AI-ready | Adapter/policy contract, correct masks/legal moves, baseline policies and diagnostics | Training curves |
| Model-promoted | Diverse held-out evaluation beats the agreed baseline with acceptable legality/latency | A successful training run |

### Artifact authority

When documents disagree, use this order and resolve the mismatch rather than copying it forward:

1. Rulebook edition and explicitly recorded rulings define the game's rules.
2. The game-specific requirements document records approved product interpretation and unresolved questions.
3. Validator/API/UI code and passing tests show what is currently implemented; they do not by themselves prove an unresolved rule was approved.
4. The game-specific AI analysis and the selected method guide define intended AI behavior and contracts.
5. Reproducible experiment and promotion records define measured model evidence; model files or training reward alone are not evidence.
6. This guide, README, and general playbooks define navigation and process, not game rules or empirical results.

## Required playable implementation order

1. Complete the game requirements analysis.
2. Complete the board-game AI analysis, even if AI is deferred.
3. Define the state and phase contract.
4. Create configuration.
5. Implement validator and transitions.
6. Implement serialization.
7. Register the game.
8. Implement frontend components and flows.
9. Add tests and run all quality gates.
10. Pass the playable-game gate above before beginning AI integration or training.

## Architecture boundary

### Game-specific components

- `api/app/games/<game>/validator.py`
- `api/app/games/<game>/serialize.py`
- `api/configs/<game>.yaml`
- `web/src/lib/components/games/<game>/...`
- `api/tests/test_<game>.py`
- Frontend unit tests for the game component and flows.

### Shared components to reuse

- `GameEngine` and `MovePipeline`.
- `GameState` envelope and repository/session services.
- `LegalMoveValidator` contract.
- Catalog/registry.
- Shared API routes.
- Shared game styles and request helpers.
- Provider interface only where AI is enabled; provider choice is game-specific and can be RL, search, a rules policy, or none.

Do not duplicate turn handling, persistence, session identity, or API routes inside a game validator.

## Configuration

Create the game YAML before UI implementation. Define:

- Game identity and player limits.
- Topology and board dimensions.
- Required progress and board panels.
- Optional hand, score, discard, draw, and phase panels.
- Components, assets, positions, stacking, clickability, and accessibility labels.
- Exact round, turn, and phase names.
- Difficulty configuration.

Configuration phase names must match validator state exactly. Image URLs must be rooted at the web static API path, never filesystem-relative paths.

## Validator contract

Implement the complete validator contract:

- `initial_game_data()`.
- `validate_move()`.
- `get_legal_moves()`.
- `apply_move()`.
- `check_win()`.
- Optional serialization and policy factories.

`get_legal_moves()` must return every legal action with complete semantic fields. Include a stable `move_id`, but validation must match semantic content as well.

`apply_move()` must return a new result without mutating the authoritative input. Preserve every authoritative transition field, including RNG state, current actor, phase, round, pending continuation, scores, and game-over state.

## Turn and phase ownership

Choose one contract and use it everywhere:

### Generic engine-owned contract

Use for simple turn-based games. The validator does not independently advance current player/phase fields that the engine owns.

### Validator-owned contract

Use for multi-phase games such as Lost Cities. Every transition returns:

- `game_data.current_player`.
- `game_data.current_phase`.
- Pending-action flags where needed.

The engine mirrors these values and does not advance them a second time.

After every transition verify that legal-move owner, serialized current player, public turn, and phase all agree.

## State transition checklist

For every action test:

- Input state remains unchanged.
- Only intended fields change.
- Card/piece/resource counts remain valid.
- Current actor is correct.
- Phase is correct.
- Round boundary is correct.
- RNG state advances exactly once.
- Terminal state is final and has no legal actions.
- Persistence snapshot matches the returned state.

## Serialization

Create `serialize.py` for the screen contract. Never expose private information accidentally. Return screen-ready objects, not raw internal strings where the frontend needs metadata.

Include:

- Current player and phase.
- Public board/zones.
- Authorized private hand/resources.
- Hidden opponent representations.
- Scores and round state.
- Draw/discard counts and images.
- Game-over and winner data.

Use absolute web-root asset paths and test visibility for both players.

## Registry and startup

Register the game in the catalog/registry and verify:

- Import works from a clean process.
- Validator is discoverable by game ID.
- Config loads and validates.
- New-game creation returns the correct initial state.
- Existing shared routes handle the game without game-specific branches.

## Frontend implementation

Build the board from serialized state and configuration. Implement:

- Initial rendering.
- Selection and legal-action highlighting.
- Card/piece click behavior.
- Phase-specific controls.
- Disabled/pending states.
- Server errors and stale version responses.
- AI turn refresh and game completion.
- Responsive layout and accessibility labels.

Do not put rule authority in the frontend.

## Tests and gates

Required backend tests:

- Initial state.
- Every legal action and illegal action.
- Every phase and turn transition.
- Score and terminal conditions.
- Round boundaries.
- RNG determinism.
- Immutability.
- Serialization and hidden-information views.
- Registry/config loading.
- Routes, persistence, restart, and session isolation.

Required frontend tests:

- Initial render.
- Selection and action submission.
- Phase changes.
- Error and loading states.
- Game-over display.

Run backend tests, frontend check, unit tests, build, audit, and targeted smoke tests before declaring the game complete.
