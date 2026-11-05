# Twilight Struggle — AI Analysis (Preliminary)

**Status:** preliminary method assessment only; not AI-ready. User confirmed standard base-game scope and the supplied 2nd Edition PDF as primary authority. The game has not passed the independent human-playable gate. Remaining blockers are tracked in [twilight-struggle-requirements.md](twilight-struggle-requirements.md).

## 0. Option C progress (groundwork, not a readiness claim)

`app/games/twilight_struggle/rl_adapter.py` implements `TwilightStruggleReferenceEnv` (contract: `app/core/rl_adapter.py`), tested by `tests/test_twilight_struggle_rl_adapter.py`.

- Fixed action space of 781 IDs: per-card event/influence/coup/realignment/headline/discard blocks (110 each), 84 country IDs, `DONE`, 32 event-choice slots, reveal, finish-turn, KAL-007 influence/realignment. Append-only layout.
- Compound moves are sequential sub-decisions (restriction discard, event choice, one influence point per step, coup target, realignment targets). Ops targets are masked against the board after any mandatory event, matching play order.
- Masks are built from engine checks; tests assert every assembled move passes `validate_move` over random playouts (restriction-discard moves excluded, because the validator's gate peeks at the next die roll).
- Observation (1092 floats, schema 1) is player-relative: own hand only, public discard/removed, no draw order or opponent headline; leakage tests included. Known leak: the second headline mask uses the opponent's committed headline (`_headline_pair_playable`).
- Reward: VP-margin delta scaled by 1/20 (not yet verified against final margin).
- Action space is restricted to `candidate_choices` output (representative, not exhaustive).
- Speed: about 4.3 ms per decision step with random masked play; 11 of 12 seeds finished, 1 stalled.
- Stall diagnosis and fixes (2026-10-20): impossible Suez Crisis (28), COMECON (14), East European Unrests (29), Che (107), and Five Year Plan (5) opponent events now raise `EventPrevented` when played for Ops, allowing the Ops action to proceed. Che's default targets require US influence in a qualifying non-battleground country. A Quagmire/Bear Trap `scoring_only` faction with no scoring card is considered unable to act. The random playthrough test uses shared `faction_action_limit` (including North Sea Oil). Focused Twilight tests after the latest event fixes: 127 passed; final full backend suite: 908 passed, 4 skipped.
- Training/evaluation pilot (2026-10-20): 200,704 PPO steps, ~95-97 FPS; recent training-window finish rate 98-99%, stall rate 1-2%, mean VP margin +6.5 to +7.6, win rate ~39-44%, with fluctuating reward. The first attempt hit recursive nested event resolution (Star Wars/Missile Envy); active event-chain card-ID tracking now prevents the same card being resolved twice on a single chain. Focused tests: 101 passed.
- Original paired held-out evaluation, same 100 seed IDs (20,000-20,099), deterministic inference, is preserved in `api/runtime/twilight-eval-paired-20k.jsonl`. A post-Suez/COMECON-fix rerun is in `api/runtime/twilight-eval-post-stall-fix-20k.jsonl`; historical results in these files use earlier engine semantics. The final 200k-only file, `api/runtime/twilight-eval-post-stall-fix-final-20k.jsonl`, contains an earlier partial run followed by the final rerun; use the latest 100 rows per faction/opponent. Final results after all current stall fixes: vs rule, US 12/100 wins, +4.2 VP (100/100 finished, 0 stalls) and USSR 57/100, +14.6 VP (100/100, 0 stalls); vs random, US 47/100, +6.1 VP (100/100, 0 stalls) and USSR 56/100, +11.2 VP (100/100, 0 stalls). The prior stalled seeds 20045, 20069, and 20095 replay to completion after Che/Five Year Plan fixes. Treat this as a 100-seed completion result, not proof of full rules completeness or a guarantee against future stalls. Do not compare it directly with runs using earlier event semantics.
- Historical seed-matched 200k-minus-100k analysis among games finished at both checkpoints: US vs rule mean margin difference +1.77 VP (95% normal CI +0.09 to +3.44), with 10 wins gained vs 4 lost; US vs random +2.49 (+0.89 to +4.09), 30 gained vs 18 lost; USSR vs rule +1.74 (-0.61 to +4.08), 25 gained vs 5 lost; USSR vs random +1.88 (-0.13 to +3.89), 25 gained vs 17 lost. These are exploratory normal approximations, not a substitute for a preregistered/bootstrap analysis. The reported historical stall counts (100k US/rule 0, USSR/rule 6, US/random 0, USSR/random 2; 200k 2, 2, 0, 7) predate the latest event fixes and are not comparable to the final 200k rerun. Margins/win rates condition on both games finishing.
- The final 200k model remains substantially weaker than `rule`, especially as US, despite the zero-stall result in this latest 100-seed sample. Do not promote; keep the model experimental. A random learner often ends early by 20 VP or DEFCON 1, so training episodes can be short; `--win-reward` (default 0) remains available if terminal defeat needs a stronger signal.
- Remaining adapter/evaluation caveats: action space remains restricted to representative `candidate_choices`, China Card is not offered as an adapter action, the second-headline playability mask uses the opponent's committed headline, and the latest zero-stall report is limited to one 100-seed sample against two fixed opponents. These limitations do not imply the existing Gymnasium wrapper, fixed-policy baselines, or reward-sum test are missing; those are implemented and tested. Twilight Struggle still has not passed the independent rules-correct human-playable gate.

## 1. Candidate method

The intended direction is a trained RL policy, as requested. This is plausible because decisions combine long-horizon card use, stochastic draws/dice, asymmetric faction roles, and hidden opponent hands. It remains a hypothesis, not a commitment to train or a claim that RL is preferable to all alternatives. A rules baseline and a random legal baseline will be necessary before training; evaluation must include seat/faction swaps and held-out seeded deals, with sufficiently diverse opponent behavior.

## 2. Decision model (provisional)

A natural policy decision is one atomic legal choice from the validator: choose a card and use, select an operations target/action, or make a required event choice. Mandatory continuation steps that contain meaningful choices should remain separate decisions; deterministic bookkeeping should be resolved by the validator. The exact phase/action taxonomy is blocked by approved rules, card definitions, and special-event timing.

The game is two-player and nominally zero-sum on the shared VP track, but a useful terminal objective must also account for non-VP defeat conditions, final scoring, and the end-turn timing. The reward function must wait for exact terminal and score semantics. A one-seat Gymnasium environment with the other faction controlled inside the environment is the repository's likely baseline architecture; do not put both factions' actions in one learner stream.

## 3. Information boundaries

- Public: influence map, tracks, public discard/removal zones, revealed events, public turn/phase data, and opponent actions.
- Learner-private: learner's hand and any choices only that player is entitled to see.
- Opponent-private: opponent hand and any private choices not yet revealed.
- Server-only randomness: future deck order and unrevealed random results.

The precise serialization/API privacy contract must be established before implementation. Neither the adapter nor inference may receive opponent hands, unrevealed draw order, or future dice outcomes. Hidden cards and stochastic outcomes require public-information observations and evaluation over independent draws/seeds, not privileged simulator state.

## 4. Candidate observation features (not yet specified)

A versioned observation will likely include a canonical country graph encoding (region, battleground/control attributes, each side's influence), public tracks and obligations, current phase/actor, public card zones/counts, learner hand represented by stable card IDs and public card attributes, and any event-resolution continuation state. Derived features such as control margin, adjacency/frontier, regional scoring potential, coup legality/DEFCON limits, hand operations distribution, and action-round/turn urgency should be explicit if the approved rules use them. Feature shapes and normalization depend on the verified graph and complete card catalog.

Do not encode artwork pixels or VASSAL trait strings as the rules state. Do not conflate XML region coordinates with map adjacency.

## 5. Candidate action encoding

Use fixed semantic IDs and exact masks. Card choice and operation/event choice may be represented as staged decisions rather than an unmanageable Cartesian product. IDs must remain stable across states, faction perspectives, and schema revisions. Every unmasked action must map to one complete validator-legal semantic action; every legal action must be representable. Exact action families and ID ranges are blocked until the validator contract and event-resolution model are approved.

## 6. Required baselines and evaluation (future gate)

Before model training: dependency-free adapter contract, action round-trip/mask tests, hidden-information leakage tests, observation version/shape tests, seeded reset variation tests, one-seat Gym environment tests, reward semantics tests, and legal random/null/rule policies. A rules policy is not yet designed because it depends on the verified rules and complete graph/cards.

Evaluate fixed checkpoints against fixed baselines with both US and USSR learner perspectives, faction/seat rotation, held-out deal seeds, and diverse policy trajectories. Record win rate, VP margin, terminal causes, illegal-action/fallback counts, episodes/turns, action and event distributions, runtime/latency, and per-faction results. Do not promote on training reward, self-play alone, or repeated deterministic trajectories.

## 7. Readiness blockers

1. Pass rules/requirements sign-off and implement a complete human-playable game.
2. Verify every card/event, setup, map rule, scoring rule, and terminal path against the approved authority.
3. Define and test the complete public/private state and action contracts.
4. Benchmark simulator throughput and choose a realistic vectorization/training budget.
5. Implement and measure random/null/rule baselines before training.

Until those are closed, no RL adapter, Gym environment, checkpoint, or provider integration should be represented as ready.
