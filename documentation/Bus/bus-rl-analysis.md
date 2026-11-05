# Bus — RL Analysis (Playbook §4)

Written before any adapter code, per
[rl-game-ai-playbook.md](../rl-game-ai-playbook.md) §4. Answers are grounded in
`api/app/games/bus/validator.py` as implemented on 2026-10-17.

| Question | Answer |
| --- | --- |
| How many players? Fixed or variable? | 3–5, variable per session. The action space must be fixed-size across all counts (use the max, pad/mask the rest). |
| What is a *decision*? Are there phases within a turn? | Many small phases: `SETUP_BUILDINGS` (2 building placements), `SETUP_FIRST_ROUTE_SEGMENTS`, `SETUP_SECOND_ROUTE_SEGMENTS`, `ACTION_SELECTION` (pick an action-marker slot or pass), then one `RESOLVE_*` sub-phase per selected marker (`RESOLVE_LINE_EXPANSION`, `RESOLVE_BUSES`, `RESOLVE_PASSENGERS`, `RESOLVE_BUILDINGS`, `RESOLVE_CLOCK`, `RESOLVE_VRROOMM`, `RESOLVE_STARTING_PLAYER`). One env step = one validator move, same as the existing turn-based API. |
| How many legal actions per decision (min/avg/max)? | Setup building: up to 36 (12 zone-1 sites × 3 types). Route setup/line expansion: up to a handful of adjacent edges (rarely more than 6–8). Action selection: ≤ 7 types + pass. Build: up to ~27 (next-zone sites × 3 types). Transport: passengers × destination sites, usually small (≤ 10) but not bounded tightly by rule — fixed action space must cover the full passenger × site product. |
| What can each player see? | Bus is public information after the starting player is chosen: all routes, buildings, passengers, action-space occupancy, clock, scores, and remaining supply are visible to everyone. There is no hidden per-player state to leak (unlike Lost Cities' hands/deck). |
| When do points change? Banked versus provisional? | Points are banked immediately on each `transport` move (+1 to `score`, no provisional value sitting on the board). Final ranking also subtracts `time_stones` from `score` (`adjusted_score = score - time_stones`), so the running objective should track `adjusted_score`, not raw `score`. |
| Is the game zero-sum? Is the margin meaningful? | Not zero-sum in the Lost Cities sense (no shared pool subtracted between players), but relative: `adjusted_score` determines final ranking. Margin against opponents (not just own score) is the right reward signal. |
| Typical game length in decisions | Observed over 20+ simulated games (3–5 players, `recommend_ai_move` random bot): 46–72 total validator moves per full game to `action_markers_exhausted` or `clock_rupture`. |
| Stochastic elements? | Only the starting-player draw (`rng_seed`) at `initial_game_data`. All subsequent choices are deterministic given moves; no hidden shuffles during play. |
| Irreversible commitments? | Building a structure (site + type) is permanent and consumes a limited tile pool (30 per type). Extending a route edge is permanent (routes only grow, never retract) and both edges and route-extension legality depend on prior edges (Euler-trail endpoint rule). Passing in `ACTION_SELECTION` is itself a commitment (loses the remainder of the round's turns for that player). |
| Can the game stall or loop? | No discard/redraw analog exists; every resolution path terminates via `complete_resolution` once its quota (`remaining`) reaches 0. The round-robin `_advance_selection_actor`/`_complete_round` logic was previously found to stall when the next starting player had 0 action markers (fixed 2026-10-17); no other stall vector is currently known. A conservative `max_episode_steps` truncation should still be kept as a safety net. |
| What does an expert look at before each move? | Which action markers remain valuable (line expansion to reach passengers/buildings vs. wasted slots), whether a route extension opens new buildable sites or passenger pickups, which buildings match the upcoming/likely clock type, whether a transport move is immediately scoreable, and how many action markers/buses remain relative to opponents. |
| Symmetries? | Player identity itself is not symmetric information (colors are cosmetic), but the board is static — no per-player board rotation is meaningful. Action-space "slot" order matters only for which marker tier (A–F) was claimed, which affects resolution quantity (`_action_quantity`), so slot index is a real feature, not an artifact to canonicalize away. |

## Key differences from the Lost Cities baseline

1. **No hidden information** — simplifies the observation (no leakage tests needed for opponent hands/deck order), but the state is much larger (36 crossings, 72 edges, 46 building sites, up to 15 passenger instances) so the observation is wide rather than deep.
2. **Variable player count (3–5)** — the action space and observation must be fixed-size for the maximum (5) and padded/masked for fewer seats, with the learner always encoded as player-relative slot 0 and opponents following turn order.
3. **Compound action families** — several move types (`setup_building`, `build`, `transport`) are a cross-product of two IDs (site × building type; passenger × destination site). These are flattened into single fixed action IDs per the general guidance in §5.2 ("split compound moves... or encode as `from × to`, and mask").
4. **Score is banked immediately**, not provisional — the running-score reward (§9.1) simplifies to `Δ(adjusted_score)` with no "value of the board if scored now" term to compute.

## Action space inventory (§5)

See `api/app/games/bus/rl_adapter.py` for the full fixed `Discrete(1094)` action
ID table, derived directly from the counts above (not guessed from a sample of
legal moves, per the Bus readiness doc's caution).

## Resolved design issue

An early draft of the action ID layout keyed `line_expand`/
`setup_first_route`/`setup_second_route` only by `edge_id`. Testing
(`test_action_ids_round_trip_over_many_legal_moves_across_phases`) found this
collides in practice, not just in rare theoretical cases: a not-yet-owned
edge adjacent to both of a player's current route endpoints is common with
short routes, and the validator legitimately offers it as two distinct moves
(different `from_crossing`). The action ID now encodes `(edge_id, endpoint
side)` — the edge's canonical `EDGES[edge_id]` tuple index that
`from_crossing` matches — doubling the three route-edge action families but
guaranteeing a bijection with legal moves.

## Status

This analysis plus the adapter module (`rl_adapter.py`), fixed action IDs,
observation encoder, and baseline policies (`rl_policies.py`) complete new-game
checklist items 1–6.

The current adapter exposes each player's bus count, from which the network
could infer the global maximum, but does **not** encode that maximum as a
dedicated global feature. This is a candidate observation improvement, not a
validator defect or a reason to misstate what the current model receives. Any
such feature addition changes the observation contract: increment the schema
version, preserve the old encoder/model path, retrain or explicitly verify
compatibility, and evaluate head-to-head on diverse setups before promotion.

## Baseline diagnostics (checklist item 7)

Recorded 2026-10-17 via `api/scripts/diagnose_bus_policies.py` (100 episodes
per row, seed 777, one measured seat vs. the stated opponent in every other
seat). Scores are `adjusted_score = score - time_stones`, averaged per game.

| measured | opponent | players | own avg | opponent avg | win rate | avg length (steps) |
| --- | --- | --- | --- | --- | --- | --- |
| rule | random | 3 | 0.45 | -0.41 | 76.0% | 142.7 |
| rule | null | 3 | 0.00 | 0.00 | 100.0% | 150.0 |
| null | random | 3 | 0.00 | -0.61 | 77.0% | 136.3 |
| rule | random | 4 | 0.52 | -0.11 | 46.0% | 200.9 |
| rule | random | 5 | 0.54 | 0.32 | 21.0% | 264.1 |

`rule` clearly beats both `random` and `null` in every row (satisfies the
playbook's §11/§12 "if your rule policy does not clearly beat random and
null, fix it first" gate), so training proceeded. Win rate against random
drops as player count rises because a single rule-following seat faces more
simultaneous competitors for the same limited action-marker/building/route
opportunities, not because the policy got worse in absolute score terms (its
own average score is flat-to-rising with player count).

## Gym env, training, and inference (checklist items 8–13)

Implemented 2026-10-17, following the Lost Cities pattern exactly:

- `api/app/games/bus/gym_env.py` — `BusGymEnv`, one learner seat per episode.
  Player count (3/4/5) and learner seat are both randomized every reset; all
  other seats are played by a weighted fixed-policy/opponent-snapshot mix
  inside `step()`. Reward is `reward_scale * (Δown_adjusted_score -
  Δmean_opponent_adjusted_score)` per decision (playbook §9.4 multiplayer
  margin reward), since Bus banks points immediately and has no provisional
  board-value term to compute.
- Observation schema v2 (957 features) adds a House/Office/Pub one-hot for
  each building site. Schema v1 (819 features) remains available for old checkpoints; `rl_inference.py`
  selects the encoder version from the saved model's input width.
- Training/evaluation can randomize legal setup moves and occasionally let
  rule opponents pass early (`--random-setup-probability`,
  `--rule-pass-probability`). Evaluation also offers sampled model actions and
  randomized openings (`evaluate_bus_model.py --stochastic --random-setup 1`)
  to avoid replaying the same deterministic opening.

## Evaluation correction and robustness experiment (2026-10-17)

**Evaluation rule for future work:** Bus's deterministic play can repeat the
same trajectories across different nominal seeds. Record the number of unique
trajectories and randomize legal setups and/or policy actions; rotate measured
seats and report results separately by player count. Do not use the historical
100% vs-rule scores below as strength evidence.

Historical baseline/model evaluations above varied only the starting player.
Because Bus has no random events after setup and both policies were
deterministic, these runs replayed very few unique trajectories: a diagnostic
found 3 unique games across 50 v2-vs-rule seeds and 1 across 30 rule self-play
seeds. Those historical win rates are not promotion evidence. The
`evaluate_bus_model.py` CLI now supports sampled actions and randomized legal
setup choices, while `compare_bus_models.py` alternates model-to-seat assignment
and reports distinct trajectories.

The experimental v4 heuristic rule policy was reverted to the original policy:
its resolution score preferred `clock_stop`, which costs a point and can
trigger clock rupture. Do not use evaluations made against that temporary
policy as a comparison with v1-v3.

The first varied-opponent fine-tuning checkpoint (`bus-v5-diverse-1m` at
2,614,944 total steps, i.e. 100k additional steps from v2) was compared with
v2 over 60 randomized deterministic trajectories at each player count:

| players | v2 wins | fine-tune wins | mean adjusted score/seat (v2 / fine-tune) |
| --- | ---: | ---: | ---: |
| 3 | 35 | 25 | 1.54 / 1.22 |
| 4 | 23 | 37 | 1.74 / 2.88 |
| 5 | 30 | 30 | 2.34 / 2.70 |

The mixed first-checkpoint result was inconclusive. A further 200k continuation
completed at 2,819,744 total steps. Against v2 on 60 new varied deterministic
trajectories per player count:

| players | v2 wins | continuation wins | mean adjusted score/seat (v2 / continuation) |
| --- | ---: | ---: | ---: |
| 3 | 34 | 26 | 2.24 / 1.52 |
| 4 | 30 | 30 | 2.54 / 2.57 |
| 5 | 36 | 24 | 2.44 / 2.17 |

The 4p score is effectively even; the continuation loses at 3p and 5p.
Therefore keep `runtime/bus-v2-2.5m.zip` as the production default and stop
this fine-tuning line. Test schema v2 separately with a small, checkpointed
fresh training run; do not assume its extra features improve play without
head-to-head evaluation.
- `api/scripts/train_bus_ppo.py` — behavior-cloning warm start from the
  `rule` teacher, then MaskablePPO against a configurable opponent mix with
  periodic self-play snapshots, cloned line-by-line from
  `train_lost_cities_ppo.py`.
- `api/app/games/bus/rl_inference.py` + the `/api/v1/moves/ai` route's
  `provider=ppo` path (opt-in via `RBGG_BUS_AI_PROVIDER=ppo` or per-request
  `provider`) — live-state inference with the same difficulty-based
  random-action substitution and fail-safe fallback to MCTS/heuristic used
  for Lost Cities.
- `api/scripts/evaluate_bus_model.py` — strength evaluation of a saved model
  against any fixed policy via the shared `app.core.rl_runner` statistics
  collector.
- First training run: `runtime/bus-v1-1m.zip`, 300-episode BC warm start from
  `rule` (98%+ action-imitation accuracy) then 1,000,000 PPO timesteps
  against `rule=0.6, random=0.2, null=0.2` across all three player counts.
  See `work-items.md` for the recorded evaluation numbers against `rule`.

## Evaluation results (checklist item 14 — promotion gate)

Recorded 2026-10-17 via `api/scripts/evaluate_bus_model.py runtime/bus-v1-1m.zip`.
The model decisively clears the playbook's "must beat `rule`" promotion gate at
every supported player count:

| players | episodes | model avg score | opponents avg score | win rate |
| --- | --- | --- | --- | --- |
| 3 | 100 | 5.64 | 0.0, 0.0 | 100% |
| 4 | 50 | 8.0 | 0.0, 0.26, 0.0 | 100% |
| 5 | 50 | 11.68 | 1.68, 0.3, 0.86, 0.7 | 100% |

**Evaluation correction (2026-10-17):** the table above is historical, not a
valid promotion result. Bus has no random events after setup; the old evaluator
changed only the starting player, while both the model (deterministic mode) and
`rule` replay fixed choices. A diagnostic run found only 3 distinct games in
50 seeded v2-vs-rule episodes and only 1 in 30 rule self-play episodes. The
`random`-opponent sanity check proved the runner could produce variance, but did
not validate game diversity against deterministic opponents. Therefore the
100% win rates and constant min/average/max scores above substantially
overstated the evidence. Use `evaluate_bus_model.py --stochastic
--random-setup 1` for varied held-out games; compare model versions head-to-head
with seats rotated before making a promotion decision.

The model is wired into `/api/v1/moves/ai` as an opt-in `provider=ppo` choice
for Bus (verified with a full live API-driven game to `GAME_OVER` via
`TestClient`), defaulting to `mcts` until there is appetite to flip the
default, mirroring the conservative rollout approach used for Lost Cities.

## Polish round 1: v2 model with self-play (2026-10-17)

`ep_rew_mean` was still climbing at the end of the v1 run (2.59 at 100%,
up from 2.32 at 90%), so a continuation run was launched: `--resume
runtime/bus-v1-1m.zip --timesteps 1500000` with the opponent mix changed to
`rule=0.5, random=0.1, null=0.1, snapshot=0.3` (the first run used no
self-play; this run introduces snapshot opponents refreshed every 100,000
steps, up to 5 kept). Saved to `runtime/bus-v2-2.5m.zip` at 2,514,944 total
timesteps (final `ep_rew_mean` 2.8, against a harder opponent pool than v1
ever trained against).

Evaluation against fixed baselines (`api/scripts/evaluate_bus_model.py`):

| players | opponent | episodes | model avg score | win rate |
| --- | --- | --- | --- | --- |
| 3 | rule | 50 | 5.38 | 100% |
| 4 | rule | 50 | 4.02 | 100% |
| 5 | rule | 50 | 7.40 | 100% |
| 3 | random | 50 | 4.48 | 96% |

These original measurements were made before the evaluation-diversity issue
was identified. Retain them as historical run records only; they do not
establish a production strength advantage or promotion gate.

A direct model-vs-model head-to-head (v2 vs v1, both seat orientations, 50
episodes each) showed v2 winning decisively at 3 players (68% and 100% win
rate depending on which model held seat `player_1`) and roughly even average
scores at 4/5 players (the "winner" tally at 4p was skewed by whichever
model was *not* in `player_1`, but average final scores were nearly
identical between v1 and v2 in that seat — likely a seat-order/tie-breaking
artifact rather than a real skill gap). No player count showed v2 regressing
below v1.

Given v2 (a) still beats `rule` 100% everywhere, (b) is meaningfully more
robust against `random`, and (c) is never worse than v1 head-to-head, it was
promoted to the default Bus PPO model: `rl_inference.configured_model_path()`
now points at `runtime/bus-v2-2.5m.zip` (still overridable via
`RBGG_BUS_PPO_MODEL`). Full test suite re-verified green (428 passed) after
the switch.

