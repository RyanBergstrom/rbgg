# Lost Cities RL Adapter and Experiment Record

## Purpose

Document the validator-backed adapter, Gymnasium/MaskablePPO training path,
offline evaluation, and safe live-provider integration for Lost Cities. The
rules, persisted game state, and frontend move contract remain unchanged.

The existing validator remains authoritative for legal moves and state
transitions. This file is a chronological experiment record; historical
provider statements below describe the status at the time they were written.
Current provider defaults and fallback behavior are maintained in
[rl-game-ai-playbook.md](rl-game-ai-playbook.md#14-step-11--integrate-the-model-into-the-app)
and should be verified against the live route configuration before changing
deployment behavior.

## Environment-library decision

PettingZoo is **not required** for PPO or for this project. Stable-Baselines3
uses Gymnasium environments directly, and the implemented Lost Cities trainer
uses a single learner seat with its opponent controlled inside the environment.
PettingZoo remains an optional choice if a future project specifically needs a
standard multi-agent API; it is not part of the current training or runtime
dependency path.

The generic adapter contract has no Gymnasium, PyTorch, or PettingZoo
dependency. `LostCitiesGymEnv` is the SB3-facing wrapper; it controls one seat,
plays the other seat internally, and returns player-relative observations and
score-margin rewards. Hidden opponent cards and future draw order remain
redacted.

## Existing seams that make this low-risk

The current application already has the required rule boundary:

1. `LegalMoveValidator.get_legal_moves()` enumerates legal move payloads.
2. `LegalMoveValidator.validate_move()` rejects invalid payloads.
3. `LegalMoveValidator.apply_move()` performs the game transition.
4. `GameEngine` and the move routes own persistence, versioning, confirmation,
   and the HTTP/frontend contract.
5. `MCTSEngine` consumes a policy boundary and is called only from the AI move
   route.

The RL adapter should call the validator directly in a headless environment.
It should not call HTTP routes, mutate SQLite, or share live `GameState`
instances with the API.

## Statelessness and memory findings

The current Lost Cities rule path is suitable for an in-memory training
environment, with important performance qualifications:

- `initial_game_data()` creates a normal Python dictionary and shuffled card
  lists. It does not create a session, open SQLite, or write a file.
- `get_legal_moves()`, `validate_move()`, and `check_win()` do not persist
  state. `check_win()` explicitly evaluates without mutation.
- `apply_move()` does not mutate the input state. It deep-copies `game_data`,
  applies the move to that copy, and returns a new result dictionary.
- File/database work belongs to the API route layer: session creation and
  `save_game_state()` are outside the validator and should never be called by
  training.
- Screen serialization is also outside the training path. It only builds JSON-
  compatible output and image path strings; the adapter should not call it.

The current search implementation is safe but not memory-minimal. A simulated
move currently passes through two copying layers: the generic search policy
deep-copies the state, then the Lost Cities validator deep-copies `game_data`.
MCTS also retains states in tree nodes. That is acceptable for live search, but
it is the wrong execution path for millions of training steps.

The training environment should therefore use a separate, deliberately
minimal transition path:

1. Hold one mutable episode state in memory.
2. Apply the selected action in place, or use a purpose-built compact transition
   function that returns only the next state needed by the environment.
3. Emit the observation and reward immediately.
4. Release the previous observation/action objects and avoid retaining episode
   history unless metrics explicitly require a bounded sample.
5. Reset the episode by replacing the small state object; do not construct
   `GameState`, call API routes, serialize JSON, or touch SQLite.

This optimized path must not replace the production validator until differential
tests prove that it has identical legal moves, transitions, scores, terminal
results, and seeded deals. The first adapter can safely use the existing
copy-on-transition behavior as a correctness reference, then add a benchmarked
fast path behind an explicit training-only interface.

### Main optimization targets

- Avoid `deepcopy` on every environment step after the reference tests exist.
- Avoid serializing/deserializing RNG state on every step. Keep a local
  `random.Random` instance during an episode and persist only the episode seed
  or checkpoint state when needed.
- Avoid `draw_pile.pop(0)`, which shifts the remaining list. Use a draw cursor,
  a deque, or a fixed deck plus index in the training-only state.
- Avoid move dictionaries and JSON conversion in the neural-network hot loop;
  map compact action IDs to moves at the environment boundary.
- Avoid storing all trajectories in memory. Stream aggregate metrics and retain
  only bounded diagnostic samples.

The existing API path should continue using defensive copies and serialized RNG
state because those properties support request isolation, persistence, undo,
and deterministic replay. Training performance improvements must remain isolated
from those application guarantees.

## Proposed environment contract

### Agent model

Use a two-agent AEC environment with stable IDs `player_1` and `player_2`.
Only the current player receives a meaningful action turn. The environment
must advance through the existing Lost Cities play/draw phases exactly as the
validator does.

Observations should be player-relative and fixed-shape:

- current phase and pending-draw indicator;
- current player's hand, encoded by card color/value/investment in fixed hand
  slots;
- both players' public expeditions and scores;
- public discard tops and counts;
- draw-pile count and round/progress information;
- an explicit current-player/seat feature;
- an action mask generated from the validator's legal move set.

Do not include the opponent hand, draw-pile card identities, RNG state, or
search-only fields in observations.

### Fixed action space

Use stable positional actions so a model can be loaded after a game state
changes. The initial candidate layout is:

- hand slot 0-7: play to expedition;
- hand slot 8-15: discard;
- action 16: draw from the draw pile;
- actions 17-21: draw from the blue/yellow/red/white/green discard piles.

The adapter maps these IDs to the validator's complete move payloads. An action
is legal only when the corresponding move exists in
`get_legal_moves()`. Hand position, not card identity, is the action identity.
The adapter must fail closed if an action maps ambiguously or to no legal move.

### Rewards

Start with a conservative reward contract:

- zero for ordinary transitions;
- a small bounded reward for the player's own public score delta;
- terminal reward based on final score margin from the acting player's
  perspective;
- symmetric seat-swapped evaluation.

Keep reward constants versioned with the training run. Do not reward merely
starting an expedition, drawing, or selecting an action unless benchmark data
shows that the signal is necessary; those incentives can teach the model to
exploit the shaping function instead of winning Lost Cities.

## Safe implementation phases

### Phase 0 — contract and golden tests

- Add pure card/state encoders and action-ID mapping tests.
- Test observation shape, player-relative redaction, deterministic reset, and
  one-step transitions against the validator.
- Test that every masked action maps to exactly one legal move and every legal
  move has a representable action ID.
- Test terminal handling and seat-swapped observations/rewards.

The first implementation now has the action/observation contract and a
multi-step differential trajectory test against direct validator transitions.
The adapter remains a correctness reference and still uses defensive copying;
the optimized mutable-state path is intentionally deferred until profiling.

### Initial profiling baseline

The standalone benchmark is [profile_lost_cities_rl.py](../api/scripts/profile_lost_cities_rl.py).
On the local Python 3.13 environment, 20 random complete episodes produced:

- 17,592 environment steps;
- 879.6 steps per episode on average;
- 482.38 steps per second with `tracemalloc` enabled;
- 74,784 bytes peak traced memory for the benchmark's live allocation set.

This is a reference baseline, not a training-performance claim. A one-episode
`cProfile` run identified the first optimization targets:

1. repeated `deepcopy` during `step()`;
2. Lost Cities `apply_move()` copying `game_data`;
3. repeated legal-move generation and card parsing;
4. observation encoding allocations.

The next optimization should be a separate benchmarked fast transition path,
not a change to the production validator. It must pass the existing trajectory
differential tests before any throughput comparison is considered meaningful.

The first safe optimization has now been applied inside the reference adapter:
the outer environment envelope is shallow-copied because the existing
validator already creates a fresh `game_data` object. The benchmark loop also
reuses the observation returned by `step()` instead of encoding it twice.
Across the same 20-episode sample this measured 17,592 steps at 1,180.10
steps/second, compared with the earlier 482.38-step/second baseline. This is
an adapter-level optimization, not yet the fully mutable transition engine.

The next copy hotspot was then reduced in the Lost Cities validator itself.
`apply_move()` now copies the known mutable game containers—hands,
expeditions, discard piles, scores, and the last-discard record—without a
recursive `deepcopy()` of the entire game-data dictionary. The validator still
returns a new transition result and leaves the input state unchanged. Unknown
extension fields are retained by reference and must be immutable unless an
extension copies them before mutation.

With both changes enabled, the same 20-episode benchmark measured 17,592 steps
at 1,934.31 steps/second. That is approximately 4.0 times the original
482.38-step/second reference baseline. The result is still a correctness
benchmark, not a claim about neural-network training throughput.

The card-parsing hotspot was then addressed with a fixed `CARD_METADATA`
lookup table. Card color and value queries now avoid repeated string splitting
while retaining the same helper behavior. Focused and full regression tests
pass. Because the current benchmark includes `tracemalloc` and shows runtime
variance, this change is recorded as a correctness-preserving allocation
reduction rather than a claimed throughput gain. Longer repeated benchmarks
without tracing should be used before making further optimization decisions.

The profiling harness now disables `tracemalloc` by default because memory
tracing materially changes throughput. Use its explicit `--trace-memory` mode
when measuring allocations. It also supports warmups and repeated runs and
reports median steps/second. A five-episode smoke benchmark without tracing
reported a median of 15,333.26 steps/second; the two-episode tracing check
reported 2,515.94 steps/second and 84,666 bytes peak traced memory. These are
environment measurements only and should be replaced by longer repeated runs
for formal comparisons.

The long clean benchmark then measured 86,446 steps across 100 episodes, with
three measured runs ranging from 5,773.62 to 11,346.92 steps/second and a
median of 9,812.01 steps/second. Runtime variance remains substantial on the
shared development machine, so future comparisons should use the same warmup,
episode seeds, and repeated-run protocol.

The adapter also now caches fixed card observation features and reuses the
already-generated legal moves when constructing the next observation. This
removes redundant legal-move generation and card-feature construction without
changing the validator or the observation schema. The full backend suite
continues to pass.

## Shared adapter contract

The reusable boundary is now defined in [rl_adapter.py](../api/app/core/rl_adapter.py).
It contains no ML, PettingZoo, Gymnasium, or persistence dependency and
requires only the common lifecycle surface: fixed action/observation metadata,
reset, player-relative observation, legal moves, current player, and one-step
transitions. Lost Cities implements this contract in
[lost_cities/rl_adapter.py](../api/app/games/lost_cities/rl_adapter.py).

Future games should implement the same contract while keeping their own
encoders, action maps, visibility rules, and rewards. Only genuinely shared
training runners and evaluation utilities should be extracted after a second
game adapter demonstrates the need.

## Constant-memory episode statistics

The reusable runner in [rl_runner.py](../api/app/core/rl_runner.py) now executes
any `RLAdapter` with a random legal-action policy. It retains only aggregate
counters in memory: episode count, total steps/reward, winner counts, action
counts, and minimum/maximum episode length. Optional per-episode summaries are
streamed as JSON Lines, so millions of episodes do not require storing states,
observations, or trajectories in memory.

This is intentionally evaluation infrastructure, not model-training logic. It
provides a low-overhead place to inspect outcomes before adding ML dependencies.

Summary files remain buffered by default for throughput. The evaluation CLI
supports `--flush-summaries` when preserving every completed episode after a
process interruption is more important than the small per-episode file I/O
cost. Flushing is opt-in so normal high-volume runs do not pay that cost.

The first concrete consumer is [evaluate_lost_cities_random.py](../api/scripts/evaluate_lost_cities_random.py).
It establishes a random-policy baseline using the shared runner and can write
one JSONL summary per episode. A ten-episode seeded smoke run produced 7 wins
for `player_1`, 3 wins for `player_2`, 841.6 steps per episode on average, and
an average shaped reward of -0.513. These numbers are only a baseline for
checking the environment and statistics pipeline; they are not a strength
benchmark because the policy is random and seat symmetry has not yet been
applied.

The random evaluator now supports `--starting-player player_1|player_2` for
seat-swapped checks. The first ten-episode player-2-starting smoke run produced
5 wins per player, 821.6 average steps, and average final scores of -94.1 for
`player_1` and -106.6 for `player_2`. The small sample is not evidence of
statistical parity, but it confirms that the adapter can initialize and run
from either seat. Larger paired runs should use the same seeds and compare
confidence intervals before judging first-player advantage.

The paired comparison tool is [compare_lost_cities_seats.py](../api/scripts/compare_lost_cities_seats.py).
A 100-episode-per-seat run produced 54% player-1 wins when player 1 started
(95% interval 44.2%–63.8%) and 41% player-2 wins when player 2 started
(95% interval 31.4%–50.6%). The intervals overlap, so this does not establish
a meaningful seat advantage for the random policy. It establishes the
comparison workflow; larger runs and stronger policies are needed for gameplay
conclusions.

The existing MCTS engine is now also usable as an alternate selector through
[evaluate_lost_cities_mcts.py](../api/scripts/evaluate_lost_cities_mcts.py).
The selector uses one worker, a configurable iteration budget, and maps the
chosen validator move back to the fixed adapter action ID. A two-episode,
10-iteration hybrid smoke run completed successfully, producing 347 steps per
episode and one win for each player. This proves the policy boundary works;
the tiny sample is not a strength comparison. Larger MCTS runs should be
performed only after choosing a fixed configuration and seat-swapping protocol.

The runner now accepts an alternate action selector, so policies can be
compared without changing the statistics pipeline. The first alternate
provider is [evaluate_lost_cities_heuristic.py](../api/scripts/evaluate_lost_cities_heuristic.py),
which routes decisions through the existing validator heuristic and maps the
chosen move back to the fixed RL action ID. A ten-episode smoke run completed
264 steps per episode, produced 6 player-1 wins and 4 player-2 wins, and
averaged final scores of -101.8 and -111.5 respectively. This establishes the
provider boundary; it is not yet an MCTS comparison or a trained-model result.

Episode JSONL records now also include terminal `final_scores`, and the
aggregate output includes `average_final_scores` by player. Re-running the
same ten-episode baseline produced average final scores of -93.6 for
`player_1` and -110.2 for `player_2`. Scores are collected only at terminal
episodes and accumulated as counters, so this addition does not retain game
states or materially change the training memory profile.

No production code or dependencies change in this phase beyond isolated
adapter modules and test-only tooling.

### Phase 1 — headless adapter with no ML dependency

- Implement a dependency-light game adapter and evaluation harness.
- Run random legal actions and the existing heuristic/MCTS policy through the
  adapter.
- Compare complete trajectories against direct validator execution using the
  same seed and action sequence.
- Add a short episode smoke test and an invariant checker.

The shared adapter and Lost Cities adapter now exist, with Gymnasium isolated
in the training wrapper. PettingZoo compatibility is not a required gate.

This is the integration gate. If it fails, do not install or train models.

### Phase 2 — policy-provider boundary

Introduce an internal provider contract, conceptually:

`choose_move(state, player_id, legal_moves) -> legal move payload`

Keep the current MCTS provider as the default. Add a model provider that is
disabled unless explicitly configured and that loads a model once, validates
its action mask, maps its action ID, and falls back safely when no model is
available or inference fails.

The API route should not know whether the provider used MCTS, a model, or a
heuristic. It should still submit the chosen payload through `GameEngine`.

### Phase 3 — training and evaluation

- Begin with PPO/MaskablePPO only after action masking and trajectory tests
  pass; do not assume DQN is suitable for this variable legal-action game.
- Train against random and current-policy opponents before self-play.
- Maintain held-out deterministic deals and seat-swapped tactical fixtures.
- Compare win rate, final score margin, illegal-action rate, inference latency,
  and draw/discard/play distributions against MCTS.
- Export model metadata with observation schema version, action schema version,
  reward version, seed, training opponent, and framework versions.

### Phase 4 — shadow and opt-in production use

- Run model inference in shadow mode while MCTS still makes the move.
- Record model choice, MCTS choice, legal mask, latency, and outcome without
  exposing model decisions to users.
- Enable the model only through an explicit configuration/difficulty option.
- Retain MCTS as a runtime fallback and rollback switch.

## Risks requiring explicit decisions later

1. **Imperfect information:** shared policy with player-relative observations
   versus recurrent policy/belief features.
2. **Opponent training:** fixed heuristic/MCTS opponents versus checkpoint
   self-play.
3. **Action granularity:** keep play/draw as separate environment steps (the
   natural validator contract) versus expose a whole-turn composite action.
4. **Model dependency footprint:** optional RL training dependencies must not be
   required to run the API or the existing test suite.
5. **Model governance:** where model artifacts live, how they are versioned,
   and what observation/action schema compatibility checks are mandatory.

## Non-goals for the first change

- Do not remove or rewrite MCTS.
- Do not alter Lost Cities rules or move payloads.
- Do not expose hidden state to the model to make training easier.
- Do not add SB3/PyTorch as a required API dependency before the adapter passes
  deterministic contract tests.
- Do not claim that a trained model is stronger until it beats MCTS on held-out,
  seat-swapped evaluations with legality and regression gates passing.

## Initial PPO progression

Optional RL dependencies are now declared in the `rl` extra, and the
dependency-free adapter has a Gymnasium bridge using masked PPO from
`sb3-contrib`. The first 1,000-timestep smoke model trained and saved
successfully. A 10,000-timestep run also completed at approximately 490 steps
per second during training.

Early inspection exposed a real learning issue: with sparse terminal rewards,
the policy learned long discard-pile cycles and did not finish within the
1,500-step evaluation horizon. The Gym-only training wrapper now applies a
small per-step cost, rewards consuming the draw pile, and truncates stalled
episodes. This does not change the reference adapter or production rewards.
The 10,000-step progress-shaped run still requires longer training and better
evaluation before any gameplay claim; its bounded inspection completed without
illegal actions but all three inspected episodes truncated.

The objective-driven reward revision was then trained for 100,000 timesteps.
Training converged to roughly 280-step episodes with rollout reward near 1.0
and positive value-function explained variance during the later run. A five-
episode bounded evaluation completed all games in 266–276 steps, with 3 wins
for `player_1`, 2 wins for `player_2`, average final scores of -79.0 and -81.6,
and no truncations. This is an encouraging first model result, but the sample
is too small for a strength claim; the next evaluation should use larger
seat-swapped batches and compare against the random baseline.

A paired 20-game-per-seat PPO evaluation then completed. With player 1
starting, the model produced 10 wins per player and average final scores of
-67.85 for `player_1` and -80.85 for `player_2`. With player 2 starting, it
produced 11 player-1 wins and 9 player-2 wins, with average scores of -82.95
and -72.65 respectively. Every episode completed in 264–280 steps. The model
appears to have learned a stable, fast-completing policy, but these 40 games do
not demonstrate superiority over random play; the next comparison should use
matched seeds and identical seat batches for both policies.

Matched 20-game random baselines were run with the same seeds. For the
player-1-start batch, random produced 14 player-1 wins and 6 player-2 wins,
with average scores of -92.4 and -111.35 and 881.9 steps per game. For the
player-2-start batch, random produced 9 player-1 wins and 11 player-2 wins,
with average scores of -102.0 and -103.5 and 847.0 steps per game. Against
those small matched samples, PPO completed dramatically faster and showed more
balanced outcomes, but the win results are mixed rather than conclusive:
PPO was 10-10 and 11-9, while random was 14-6 and 9-11. Larger paired samples
are required before selecting the model for further training or deployment.

The larger 100-game-per-seat comparison is now complete. PPO completed games
in 270.64–271.20 steps on average, versus 862.30–867.04 for random. PPO did
not yet show a clear win-rate advantage: when player 1 started, PPO produced
43 player-1 wins, 56 player-2 wins, and 1 draw, while random produced 53, 46,
and 1. When player 2 started, PPO produced 61 player-1 wins and 38 player-2
wins with 1 draw, while random produced 59 player-1 wins and 41 player-2 wins.
PPO's average scores were mixed: it improved the player-2-start scores to
-70.02/-81.48 compared with random's -98.22/-108.89, but the player-1-start
scores were -84.58/-66.47 compared with random's -103.79/-108.69. The strongest
current conclusion is that PPO learned a compact, terminating policy; strength
and seat symmetry remain unresolved.

The next training checkpoint addresses a contract issue found during review:
the Gymnasium observation space previously declared all features in `[0, 1]`,
although Lost Cities score features can be negative. The space now uses
unbounded floating-point limits, matching the actual observations. A fresh
500,000-timestep PPO run was started with the corrected observation contract
and objective-driven rewards. Its checkpoint will be evaluated after training
completes using the same 5,000-game-per-seat protocol.

The 500k checkpoint smoke evaluation exposed regression rather than
improvement. Across 100 games per starting seat, it completed in 366.02–380.66
steps on average, but average final scores fell to approximately -149 to -154,
compared with approximately -76 to -77 for the 100k checkpoint. Win rates
remained near even: 49/51 with player 1 starting and 53/47 with player 2
starting. The action distribution became more concentrated in a few actions,
and some games reached 740–744 steps. The 500k checkpoint should not replace
the 100k checkpoint. This is evidence of reward-policy drift or reward
hacking, not evidence that more PPO timesteps automatically improve play.

The next step is checkpoint selection and reward diagnosis: compare reward
breakdowns, terminal score margins, termination status, and action distributions
across training checkpoints. Prefer the best held-out score checkpoint rather
than always selecting the final training checkpoint.

The reward system has now been adjusted for the next experiment: draw-pile
progress is reduced from `0.01` to `0.002`, the step cost from `-0.001` to
`-0.0005`, and the timeout penalty is configurable with a default of `-0.25`.
The Gym bridge exposes these values as CLI options and accumulates per-episode
component totals. This keeps terminal score margin dominant while making
reward hacking visible.

Opponent curriculum, tactical fixtures, and recurrent policies are deliberately
not mixed into this reward experiment. They require separate controlled
comparisons so we can identify which change affects learning.

The training CLI now supports optional intermediate snapshots with
`--checkpoint-frequency N`. Future long runs can therefore save checkpoints at
fixed timestep intervals under a sibling checkpoint directory. This makes it
possible to evaluate the learning curve and select the best checkpoint rather
than trusting the final model.

## Deep analysis of the v1 models (2026-10-15)

`scripts/diagnose_lost_cities_policies.py` measured every saved model against
fixed baselines (50 games per seat; score per player per game):

| Policy | Score/game | Expeditions started/round | Losing expeditions/round | Hand-shuffle agreement | Value vs outcome corr. |
| --- | --- | --- | --- | --- | --- |
| never play | 0 | 0 | 0 | – | – |
| rule policy | +46 | 1.1 | 0.1 | – | – |
| original 100k | −72 | 1.1 | 1.1 | 0.12 | 0.02 |
| random | −103 | 5.0 | 4.0 | – | – |
| validator heuristic | −108 | 5.0 | 4.4 | – | – |
| original 500k | −145 | 5.0 | 4.3 | 0.13 | 0.05 |
| shaped 500k | −166 | 4.6 | 4.4 | 0.10 | ~0 |
| shaped 400k | −187 | 4.0 | 3.8 | 0.10 | 0.02 |

Root causes:

- The single-agent wrapper interleaved both players' moves in one stream. The
  bootstrapped next-state value was from the opponent's perspective without a
  sign flip, and the terminal reward reached only the last mover. The value
  head therefore learned nothing (flat values, ~0 correlation, negative
  explained variance). Only perspective-neutral shaping (draw progress, step
  cost) was learnable, which is why models only learned to end games quickly.
- Card choice was positional: agreement after shuffling the hand was 10–14%,
  chance level is 12.5%. Hands were unsorted and the observation forced the
  network to learn colour matching between slots and expedition summaries.
- Score feedback arrived only at round end, and 256-step rollouts were shorter
  than one game.
- Every training episode reused the same deal because the env reseeded each
  reset with its constructor seed.
- The validator heuristic scores worse than random and is not a valid strength
  baseline.

## Redesign (implemented 2026-10-15)

All changes stay within SB3 / sb3-contrib `MaskablePPO`.

1. **One-seat env** — `LostCitiesGymEnv` controls one randomly chosen seat; the
   opponent (fixed `rule`/`random`/`never_play`, or a frozen PPO snapshot) moves
   inside the env. Default mix `rule=0.6,random=0.1,snapshot=0.3`; snapshots are
   used only once registered.
2. **Dense margin reward** — per learner step,
   `reward_scale * (Δown_running_score − w · Δopp_running_score)`, where running
   score is banked score plus current board score (banked only once
   `game_over`). The per-episode sum equals `reward_scale` × final margin.
   Draw-progress bonus and step cost were removed.
3. **Observation schema v2 (252 features)** — hands sorted canonically
   (colour, investments first, value); 16 per-slot features (colour, value,
   playable, gap, play delta, expedition started, opponent usage, unseen higher
   cards, same-colour count); 23 per-colour features (both expeditions'
   count/investments/last/score, unseen counts/sums, hand playable sum and
   projected score, discard-pile top and playability); 9 globals. "Unseen" uses
   only information visible to the player. v1 (133) remains available for old
   models; the observation version is inferred from model size.
4. **Seeding fix** — only the first reset uses the constructor seed; later
   deals come from the env RNG.
5. **Training settings** — 8 vectorised envs (`dummy` or `subproc`),
   `n_steps=1024`, `batch_size=512`, `gamma=0.995`, `ent_coef=0.01`,
   `net_arch=256,256`.
6. **Behaviour cloning** — `--pretrain-episodes N` collects `rule` teacher
   decisions with discounted returns, trains policy (NLL) and value (MSE) heads
   in plain PyTorch, saves `<output>-pretrained.zip`, then fine-tunes with PPO.
7. **Evaluation** — `evaluate_lost_cities_model.py --opponent rule --model-seat`
   and `diagnose_lost_cities_policies.py --opponent rule` report the measured
   policy's average score, the opponent's score, and win rate. Targets: above 0
   (never play) and above the rule policy's +46.

Smoke run (16,384 steps, 4 envs, 20 BC episodes): BC accuracy ≈ 0.61, explained
variance rose 0.36 → 0.62 → 0.69 (previous runs were ≤ 0), ~550–600 FPS.

### v2 1M run (`runtime/lc-v2-1m`, 8 subproc envs, 2,000 BC episodes × 15 epochs)

- Teacher data: 290,712 rule decisions; BC accuracy 0.74 → 0.94.
- PPO: explained variance 0.76–0.89 from the first updates; ~570 FPS.
- Evaluation vs `rule`, 50 games per starting seat (measured policy's score /
  rule's score / win rate):

| Model | Starting P1 | Starting P2 |
| --- | --- | --- |
| BC pretrained | +33.3 / +39.3 / 0.48 | +33.3 / +46.7 / 0.36 |
| PPO 100k | **+88.1 / +63.4 / 0.62** | **+79.2 / +56.7 / 0.64** |
| PPO 200k | **+91.3 / +51.8 / 0.70** | **+89.3 / +61.4 / 0.68** |
| PPO 300k | +83.5 / +63.3 / 0.68 | +79.6 / +61.3 / 0.62 |
| PPO 400k | +81.0 / +69.3 / 0.60 | +85.2 / +65.3 / 0.60 |
| PPO 500k | +82.4 / +76.8 / 0.54 | +79.1 / +69.3 / 0.54 |
| PPO 600k | +107.8 / +78.3 / 0.64 | +102.2 / +59.1 / 0.72 |
| PPO 700k | +97.5 / +74.9 / 0.70 | +108.5 / +65.4 / 0.66 |
| PPO 800k | +98.2 / +73.8 / 0.60 | +96.2 / +74.6 / 0.60 |
| PPO 900k | +108.8 / +75.0 / 0.66 | +112.7 / +80.6 / 0.64 |
| PPO 1M | **+126.6 / +71.7 / 0.76** | **+120.7 / +78.7 / 0.68** |

Held-out confirmation (seed 777, 200 games per starting seat, vs `rule`):

| Model | Score | Rule's score | Margin | Win rate |
| --- | --- | --- | --- | --- |
| PPO 200k | +93.6 | +59.6 | +34.0 | 0.69 |
| **PPO 1M (`runtime/lc-v2-1m.zip`)** | **+122.6** | +82.1 | **+40.6** | 0.69 |

Against `random` (100 games per seat) the 1M model scored +170 vs −217 and
won every game. **Selected model: `runtime/lc-v2-1m.zip`.**

Observations: later checkpoints open more expeditions (1.9 → 3.2 per round)
and play longer games (≈280 → 340 steps). The rule opponent also scores
more against them (≈60 → 82). Win rate plateaued at ≈69% while margin kept
improving.

### Discard-feeding check (seed 777, 100 games per seat vs `rule`)

A new `feeding_discards` statistic counts discards the opponent can play
immediately on an expedition it has started. The guess that the 1M model
feeds the opponent was **wrong**:

| Model | Feeding discards/round | Discard draws/round | Cycles/round | Plays/round | Steps |
| --- | --- | --- | --- | --- | --- |
| PPO 200k | 0.02 | 4.3 | 0.8 | 10.4 | 290 |
| PPO 1M | 0.05 | 12.1 | 2.0 | 15.0 | 340 |

The 1M model stalls the deck by taking discards and re-discarding, which
extends the round so it can play more cards. The opponent gets more turns
too (hence its higher score), but the net margin improves. No feature was
added.

### Historical 1M → 2M continuation (`runtime/lc-v2-2m`, `--resume runtime/lc-v2-1m.zip`)

Same settings, about 718 FPS, explained variance 0.75–0.84. Screening vs
`rule` (50 games per seat; score / rule's score / win rate, averaged over seats):

| Checkpoint | Score | Rule | Win | Expeditions/round | Discard draws/round |
| --- | --- | --- | --- | --- | --- |
| 1.1M | +137.8 | +81.3 | 0.72 | 3.4 | 12.3 |
| 1.2M | +131.2 | +88.0 | 0.63 | 3.3 | 14.6 |
| 1.3M | +133.1 | +83.0 | 0.70 | 3.4 | 17.3 |
| 1.4M | +119.4 | +76.9 | 0.66 | 3.7 | 16.2 |
| 1.5M | +118.9 | +79.7 | 0.70 | 3.9 | 16.4 |
| 1.6M | +113.1 | +77.6 | 0.71 | 3.8 | 15.6 |
| 1.7M | +107.7 | +79.6 | 0.64 | 3.9 | 15.6 |
| 1.8M | +102.7 | +87.8 | 0.53 | 3.8 | 16.3 |
| 1.9M | +114.6 | +79.5 | 0.59 | 3.9 | 15.8 |
| 2.0M | +113.7 | +85.0 | 0.63 | 4.1 | 16.9 |

Held-out confirmation (seed 777, 200 games per seat):

| Model | Score | Rule's score | Margin | Win rate |
| --- | --- | --- | --- | --- |
| PPO 1M (current) | +122.6 | +82.1 | +40.6 | 0.69 |
| PPO 1.1M | +124.1 | +79.2 | +44.9 | 0.69 |
| PPO 1.3M | +117.3 | +94.7 | +22.6 | 0.62 |

This was the initial same-settings continuation. Its 1.1M checkpoint was within
noise of 1M and later checkpoints regressed, so the 1M model remained selected
at that point. The subsequent lower-learning-rate experiment below supersedes
that interim model selection.

The first PPO checkpoint is the first model to score positively and to beat the
rule policy head-to-head. Later checkpoints should be compared with the same
command and the best held-out checkpoint selected:

```powershell
python scripts/diagnose_lost_cities_policies.py --skip-baselines --opponent rule --episodes 200 `
  --model ck100k=runtime/lc-v2-1m-checkpoints/lc-v2-1m_100000_steps.zip `
  --model final=runtime/lc-v2-1m.zip
```

### Lower-learning-rate fine-tune and current PPO selection (2026-10-15)

Resumed from the selected 1M model using `--learning-rate 1e-4`, retaining the
saved entropy coefficient and other PPO settings. Training completed at
2,015,232 total timesteps. Ten checkpoints from 1.1M through 2.0M were screened
for 50 episodes per starting seat against the rule policy; the final 2.0M
checkpoint was the strongest screened model.

Held-out confirmation used seed 777, 200 games per starting seat, the same
diagnostic script and the rule policy. Results below average the two starting
seats; the per-seat values are shown to expose asymmetry:

| Model | P1 score / rule / win | P2 score / rule / win | Mean score | Mean rule score | Mean margin | Mean win rate |
| --- | --- | --- | ---: | ---: | ---: | ---: |
| PPO 1M baseline | 121.36 / 81.30 / 0.685 | 123.91 / 82.84 / 0.695 | 122.64 | 82.07 | 40.56 | 0.690 |
| PPO lower-LR 1.7M | 163.55 / 78.36 / 0.845 | 148.92 / 75.13 / 0.835 | 156.24 | 76.75 | 79.49 | 0.840 |
| PPO lower-LR 1.8M | 161.99 / 76.53 / 0.850 | 162.51 / 75.03 / 0.845 | 162.25 | 75.78 | 86.47 | 0.848 |
| **PPO lower-LR 2.0M** | **170.87 / 70.49 / 0.875** | **175.20 / 70.61 / 0.935** | **173.04** | **70.55** | **102.49** | **0.905** |

The lower-LR 2.0M model improves mean held-out margin by about 61.93 points
and mean win rate by 21.5 percentage points over the matched 1M baseline in
this evaluation. The result is strong enough to select it as the **current PPO
model**, but does not establish that PPO should replace MCTS as the default
game-wide AI provider. Production MCTS remains the default; PPO stays opt-in.
The selected artifact is `api/runtime/lc-v2-low-lr-2m.zip` and can be
overridden with `RBGG_LOST_CITIES_PPO_MODEL`.

Training checkpoints, opponent snapshots, and intermediate run logs are
disposable after the held-out results are recorded here. Keep the selected
inference artifact and the persistent runtime database; do not treat temporary
evaluation dumps as canonical evidence.