# Documentation Index

This folder contains current project guidance, game specifications, experiment records, and clearly separated historical material.

## Current cross-game references

- [Game lifecycle: idea to playable AI game](game-implementation-guide.md#game-lifecycle-from-idea-to-playable-game) — required stages and gates; the game must be playable with correct rules before optional AI training.
- [RL game AI playbook](rl-game-ai-playbook.md) — current reinforcement-learning workflow. It uses Gymnasium with a one-seat learner and opponents inside the environment; PettingZoo is optional.
- [Game requirements analysis](game-requirements-analysis.md) — non-AI rules/state/API/product requirements framework.
- [Board-game AI analysis](board-game-ai-analysis.md) — information boundaries and decision-model analysis.
- [Game implementation guide](game-implementation-guide.md) — validator/config/serialization/frontend implementation conventions.
- [Game AI implementation guide](game-ai-implementation-guide.md) — search-based AI policy/evaluation guidance. RL is covered by the playbook; select either or combine them only after the rules-correct playable gate.
- [Application review tracker](application-review-tracker.md) — canonical application-audit finding status.

## Game-specific current references

### Lost Cities

- [RL adapter and experiment record](lost-cities-rl-adapter-plan.md) — PPO adapter, selected model evidence, and live-provider design. Current provider defaults are summarized in the playbook; this file retains historical experiment chronology.
- [Rules reference](lost-cities/lost_cities_rules.md) — game rules; verify rules edition/rulings before changing the validator.

### Bus

- [Bus requirements](Bus/bus_requirements.md) — canonical draft for rules, product, API, and acceptance requirements. It still has open sign-off questions.
- [Bus supplemental intake notes](Bus/more-requirements.md) — informal legacy notes; reconcile relevant decisions into the canonical requirements before treating them as approved.
- [Bus RL analysis](Bus/bus-rl-analysis.md) — implemented adapter, observation/action contracts, Gym environment, baselines, training, evaluation caveats, and model history.
- [Bus PPO readiness](Bus/bus-ppo-readiness.md) — dated pre-implementation assessment; superseded by the implementation recorded in the RL analysis. Retained for provenance, not as current status.
- [Bus AI design](Bus/bus_ai.md) — strategic search-policy proposal, not implemented search AI or the PPO specification.
- [Bus rules reference](Bus/bus-rules.md) — reference transcription; the selected edition and unresolved rulings remain governed by the requirements/sign-off process.
- [Bus board asset](Bus/bus-game-board.png) — source/reference artwork; retain.

### Twilight Struggle

- [Twilight Struggle source inventory](twilight-struggle/source-inventory.md) — inspected VASSAL/XML/PDF/image bundle, edition caveats, and unresolved asset rights.
- [The Complete Card List v1.4](twilight-struggle/The%20Complete%20Card%20List%20v1.4.pdf) — secondary card-effect reference; includes optional/promotional entries to exclude from standard base-game implementation.
- [Twilight Struggle requirements draft](twilight-struggle/twilight-struggle-requirements.md) — user-confirmed base-game scope, source-cited rules outline, acceptance requirements, and remaining data/sign-off blockers.
- [Twilight Struggle country/map draft](twilight-struggle/country-map-draft.json) — 85 country-space labels and coordinates plus provisional VASSAL trait values; adjacency is intentionally empty pending review.
- [Twilight Struggle adjacency candidates](twilight-struggle/country-adjacency-candidates.json) — best-effort candidate connections transcribed using the larger map image as a reference only; does not replace the selected game map and is not yet canonical rules data.
- [Twilight Struggle country reference](twilight-struggle/countryreference.md) — user-maintained editable country attributes and adjacency source; the loader normalizes aliases and symmetrizes listed country edges.
- [Twilight Struggle AI analysis](twilight-struggle/twilight-struggle-ai-analysis.md) — preliminary RL readiness/method assessment; not AI-ready until human-playable gate passes.
- Twilight Struggle source utilities in [tools/](twilight-struggle/tools/) — tested, read-only extraction of VASSAL country coordinates, country traits, and partial card metadata; output explicitly is not rules data.

## Historical or supporting material

- [archive/](archive/) contains superseded guides and design/review history. Use it for provenance, not as current implementation instructions.
- [sessions/](sessions/) contains dated session handoffs; these are historical records.
- [legacy-tests/](legacy-tests/) contains tests retained outside active test suites.
- [lost-cities/](lost-cities/) contains the rules source and historical implementation snapshot; the snapshot is not current implementation status.

## Runtime artifact policy

Training checkpoints, opponent snapshots, raw JSONL episodes, and transient diagnostics belong under `api/runtime/` and are disposable after their findings have been summarized here. Keep the selected inference model and the runtime database; do not use generated runtime dumps as the sole record of an experiment.
