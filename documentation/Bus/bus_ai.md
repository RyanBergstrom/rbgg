# Bus AI Policy Analysis

> **Status (proposal, 2026-10-15):** This document remains a strategic/search-policy
> proposal, not implemented search behavior and not the PPO training contract.
> Bus RL adapter, Gymnasium environment, training/evaluation, and inference have
> since been implemented; see [bus-rl-analysis.md](bus-rl-analysis.md). The
> separate [bus-ppo-readiness.md](bus-ppo-readiness.md) is a superseded dated
> pre-implementation snapshot. Resolve applicable rule requirements before
> claiming full rules or model-promotion readiness.

**Target game:** *Bus* (Splotter Spellen, 1999; compatible with the standard 3–5 player rules and the 2019/2024 reprints)  
**Purpose:** Design specification for implementing an AI bot in a hybrid board-game engine  
**Output contract:** The policy owns game-specific evaluation and returns normalized root-player values in `[0,1]`, plus raw diagnostics.

---

## 1. Executive summary

*Bus* is a deterministic, perfect-information, multiplayer worker-placement and network-development game. Its difficult decisions do not come from hidden cards or dice. They come from:

- permanent expenditure of a player's 20 action markers;
- sequential action drafting, where taking more actions now shortens the player's game;
- action strength determined by the current maximum bus count;
- action slots whose strength order and resolution order can oppose each other;
- irreversible route and building placement;
- shared passengers, destinations, and occupancy;
- turn-order races in the **Vrrooomm!** action;
- the option to stop time at a victory-point cost;
- abrupt and partly player-controlled end conditions.

The best implementation should therefore use **atomic decisions**, but evaluate them with a **round-aware search model**. The engine should represent action-marker placement, pass/drop-out, each action's resolution, each forced placement or passenger movement, and optional Clock use as separate state transitions. For search efficiency, deterministic forced sequences may be bundled only when the validator proves that no choice exists.

A strong first production policy should use:

1. exact rules and legality;
2. a multiplayer MaxN or paranoid/coalition-aware search mode;
3. progressive widening for route, building, and passenger-movement combinations;
4. a policy prior for action selection and spatial candidate generation;
5. a horizon evaluator that combines score, immediate ride capacity, network access, destination balance, passenger control, action-marker economy, tempo, blocking, and endgame pressure;
6. tactical fixtures that isolate each interaction before self-play tuning.

---

## 2. Rules baseline and assumptions

This analysis uses the published standard rules summarized in the sources listed at the end. The relevant baseline is:

- 3–5 players, with 20 single-use action markers per player;
- seven actions resolved from top to bottom: **Line Expansion, Buses, Passengers, Buildings, Clock, Vrrooomm!, Starting Player**;
- at least two action-marker placements per active player per round, after which a player may pass permanently for that placement phase;
- **Buses, Clock, and Starting Player** have one slot each;
- the other actions have lettered slots, and a player may select the same action more than once;
- the strength of Line Expansion, Passengers, and Buildings is based on the maximum number of buses owned by any player, reduced by slot position;
- Line Expansion and Buildings resolve in the reverse of selection advantage, while Passengers and Vrrooomm! resolve in the forward order shown by the action board;
- selected actions must be carried out to the fullest legal extent;
- only Vrrooomm! scores positive points, one point per passenger moved;
- stopping time costs one time stone, worth −1 point, and taking the final stone ends the game immediately;
- game end can also occur at round end when only one player retains action markers or no building locations remain;
- final winner is highest adjusted score, with rulebook tie breakers.

### Edition controls

The implementation should expose an edition/rules configuration rather than burying differences in evaluator code:

```text
rules.edition = STANDARD_2019 | COMPLETE_2024 | CUSTOM
rules.player_count = 3..5
rules.time_stones = 4 if player_count == 3 else 5
rules.five_player_line_bonus = 1 if player_count == 5 else 0
```

Any textual discrepancy between editions should be resolved in unit-tested rules configuration. In particular, do not encode a prose example as authoritative when it conflicts with the action-specific rule.

---

## 3. Complete turn and phase model

### 3.1 Recommended decision granularity

Use **atomic validator actions** as plies. A full round is far too large and strategically interactive to be one move.

Recommended atomic action types:

```text
PLACE_ACTION_MARKER(action_type)
PASS_ACTION_SELECTION
PLACE_ROUTE_SEGMENT(edge)
PLACE_BUILDING(site, building_type)
PLACE_PASSENGER(station)
BUY_BUS
CLOCK_STOP
CLOCK_ADVANCE
MOVE_PASSENGER(passenger_id, destination_building_id)
CLAIM_START_PLAYER
END_FORCED_ACTION
END_ROUND
```

`BUY_BUS` and `CLAIM_START_PLAYER` may be deterministic resolution events rather than player decisions. They should still appear in the event log.

### 3.2 Turn map

| Phase | Actor | Legal choices | Actor afterward | Public change | Terminal check |
|---|---|---|---|---|---|
| Initial buildings | Players in starting order | Place two buildings on legal Zone 1 sites | Next setup player | Buildings and sites | No |
| Initial first line | Players in starting order | Place one route marker on any legal street | Next setup player | Route network | No |
| Initial second line | Players in reverse order | Extend from an end legally | Next setup player | Route network/endpoints | No |
| Action selection | Current drafting player | Place marker in a legal action slot; after two placements, may pass | Next non-passed player | Marker committed forever; action slot occupied | If no active selector, begin resolution |
| Line Expansion resolution | Leftmost resolving marker, according to board order | Place required route segments one at a time | Same actor until quota complete, then next marker | Permanent route edges/endpoints | No |
| Buses resolution | Marker owner | No strategic subchoice, gain one bus | Next action | Bus capacity and global maximum may rise | No |
| Passengers resolution | Resolving marker owner | Place required passengers between the two stations | Same actor until quota complete, then next marker | Shared passenger supply/location | No |
| Buildings resolution | Resolving marker owner | Select legal sites and types until quota complete | Same actor until quota complete, then next marker | Permanent destinations and zone progression | Flag building exhaustion for round end |
| Clock resolution | Marker owner, if any | Stop time or allow advance | Next action | Clock location; possibly remove time stone | Immediate if final time stone is taken |
| Vrrooomm! resolution | Resolving marker owner | Choose required legal passenger-to-destination moves | Same actor until maximum possible moves complete, then next marker | Score, passenger locations, building occupancy | No |
| Starting Player resolution | Marker owner or automatic rotation | Usually deterministic | Round end | Next start player | Round-end checks |
| Round cleanup | System | Remove spent action markers from play | New starting player | Remaining action-marker counts | End if only one player has markers, or buildings exhausted |

### 3.3 Actor-transition contract

The rules layer, not the evaluator, must determine the next actor using an explicit state machine:

```text
SETUP_BUILDINGS
SETUP_FIRST_LINES
SETUP_SECOND_LINES
SELECT_ACTIONS
RESOLVE_LINE
RESOLVE_BUSES
RESOLVE_PASSENGERS
RESOLVE_BUILDINGS
RESOLVE_CLOCK
RESOLVE_VRROOMM
RESOLVE_START_PLAYER
ROUND_CLEANUP
TERMINAL
```

Key contracts:

- Passing during action selection is irrevocable for the current round.
- A player with no action markers cannot select actions and is effectively out, but their score, route, buses, and pieces remain relevant.
- A player resolving a multi-step action remains the actor until their required quantity is exhausted or no further legal completion exists.
- An action selected multiple times produces multiple separately ordered resolutions.
- A player must maximize completion of a chosen action. The move generator must not offer voluntary early termination.
- The maximum-bus value must be recomputed immediately after the Buses action because it changes later Passenger and Building quantities in the same round.
- Clock rupture interrupts the round immediately. Later actions are not resolved.

### 3.4 Action power

Let:

```text
M = maximum buses owned by any player at the moment the action resolves
slot_index(A)=0, slot_index(B)=1, ...
```

For Passengers and Buildings:

```text
required_count = max(0, M - slot_index)
```

For Line Expansion:

```text
required_count = max(0, M - slot_index + five_player_line_bonus)
```

The engine should verify exact board capacity and edition details, then force the actor to perform `min(required_count, maximum_legally_possible)` placements.

---

## 4. Information boundaries

### 4.1 Classification

| State information | Classification | AI use |
|---|---|---|
| Scores and score-stack order | Public, authoritative | Exact |
| Remaining action markers per player | Public, authoritative | Exact; crucial endgame clock |
| Action choices and slot positions | Public, authoritative | Exact |
| Bus counts and current maximum | Public, authoritative | Exact |
| Route edges and endpoints | Public, authoritative | Exact spatial graph |
| Buildings, types, sites, and unlocked zone | Public, authoritative | Exact |
| Passenger identities/locations and occupied buildings | Public, authoritative | Exact |
| Clock state and remaining time stones | Public, authoritative | Exact |
| Time stones held by each player | Public, authoritative | Exact final-score penalty |
| Starting-player marker | Public, authoritative | Exact |
| Future opponent choices | Strategic uncertainty, not hidden information | Search or opponent model |
| Random future information | None after any random starting-player choice | No determinization needed |

### 4.2 Consequence for search

No belief sampling or determinization is required. The uncertainty is behavioral. Search strength therefore depends on modeling multiplayer incentives, not guessing hidden state.

Use at least two opponent models during evaluation:

- **Self-interested MaxN:** each opponent maximizes their own utility.
- **Paranoid stress test:** opponents collectively minimize the root player's utility.

A production bot may blend them:

```text
opponent_response_value = 0.75 * maxn_response + 0.25 * paranoid_response
```

This reduces both naive optimism and pathological assumption of universal collusion.

---

## 5. State representation and derived graph data

### 5.1 Authoritative state

```text
GameState
  phase
  round_number
  current_actor
  starting_player
  passed_this_round[player]
  action_slots[action][slot] -> player or empty
  resolution_cursor
  current_required_count
  clock_destination_type
  time_stones_remaining
  players[player]
    score
    score_stack_order
    action_markers_remaining
    buses
    time_stones_taken
    route_edges
    route_endpoints
  buildings[site] -> type or empty
  passengers[passenger] -> crossing/building/station
  passenger_supply_remaining
  unlocked_building_zone
  terminal_reason
```

### 5.2 Derived indexes

Cache, but never treat as authoritative:

```text
crossings_on_route[player]
reachable_buildings[player][type]
reachable_unsatisfied_passengers[player]
empty_reachable_destinations[player][type]
legal_route_extensions[player][endpoint]
route_overlap_by_opponent[player]
passenger_to_destination_bipartite_graph[player][type]
maximum_transport_matching[player][type]
next_clock_type
remaining_round_lower_bound[player]
```

The most important derived calculation is a maximum bipartite matching between movable passengers accessible to a route and empty buildings of the demanded type accessible to that route. This yields exact immediate ride capacity before bus-count capping.

---

## 6. Strategic model of Bus

### 6.1 What creates value

The game is not mainly about having the longest line or most buses. Value comes from repeatedly converting a shared passenger pool into points before opponents do. A productive network needs all three of:

1. access to unsatisfied passengers;
2. access to empty buildings of the currently demanded type;
3. enough buses and sufficiently early Vrrooomm! order to make those connections score.

Permanent infrastructure should therefore be valued by **transport opportunities**, not by component count alone.

### 6.2 Action-marker economy

Each action marker is both a move and a portion of the player's remaining lifespan. Spending extra markers can win tempo, but it can also help trigger the end condition while leaving the player inactive. Evaluate each placement as a capital allocation decision.

Useful raw measurements:

```text
action_reserve = markers_remaining / 20
relative_reserve = markers_remaining - mean(opponent_markers_remaining)
expected_rounds_alive = floor(markers_remaining / 2)
marker_burn_this_round = markers_committed_this_round
```

Late in the game, the value of one marker should rise if it preserves a future scoring action, but fall if the game is likely to end before that future action occurs.

### 6.3 Tempo and slot inversion

The A slot may provide greater quantity while resolving later on Line Expansion and Buildings. Thus a nominally stronger slot can be strategically worse if earlier resolvers can block route edges or consume sites. Conversely, early Vrrooomm! order directly steals shared scoring capacity.

The evaluator must include both:

```text
quantity_value
execution_order_value
```

Do not rank slots by action power alone.

### 6.4 Clock leverage

Stopping time is not merely “pay 1 point.” It can:

- preserve a destination type on which the player has superior current matching;
- deny opponents the next destination type;
- allow repeated transportation patterns;
- threaten or cause immediate game end;
- sacrifice a point to protect a lead;
- create tie-break implications because time stones are negative points but also a later tie breaker.

Clock evaluation must compare the complete post-Clock Vrrooomm! schedule for **stop** versus **advance**, including who has each ride slot.

### 6.5 Spatial hostility

Building choices are dual-use. A building may improve the actor's network, improve an opponent's route, fill a destination to deny future deliveries, or alter where passengers become satisfied after the clock changes. Route growth also creates interference because parallel-building restrictions and shared intersections make endpoints strategically scarce.

Spatial candidate generation should prioritize moves that change at least one of:

- station access;
- count of reachable building types;
- immediate matching size;
- opponent matching size;
- endpoint mobility;
- exclusive access to a useful crossing;
- future connection to higher-zone sites;
- blocking of an opponent's legal extension.

---

## 7. One-ply action evaluator

The one-ply evaluator is a move-ordering prior, not a probability and not the final move value.

### 7.1 Common structure

```text
one_ply(action) = clamp01(
    0.18 * immediate_points
  + 0.16 * immediate_transport_delta
  + 0.12 * network_delta
  + 0.10 * denial_delta
  + 0.10 * tempo_delta
  + 0.08 * flexibility_delta
  + 0.08 * endgame_fit
  + 0.08 * action_efficiency
  + 0.05 * clock_leverage
  + 0.05 * initiative_value
  - irreversible_risk
  - marker_opportunity_cost
)
```

All components above are normalized to `[0,1]`; penalties are bounded separately. These are starting weights for ordering only.

### 7.2 Place-action-marker evaluation

Raw terms:

```text
action_power = required quantity if selected now
resolution_rank = expected order within that action
action_scarcity = probability/likelihood the slot disappears before next turn
round_combo = compatibility with already selected actions
marker_cost = marginal value of one remaining action marker
forced_execution_risk = downside from being required to complete the action
```

Specific preferences:

- **Vrrooomm!:** value exact expected points, first-mover theft, and repeated-ride combos.
- **Line Expansion:** value only legal extensions with useful access or blocking impact.
- **Buses:** value future capacity across expected remaining ride actions, plus the global effect of increasing action power for everyone.
- **Passengers:** value where placed passengers can later be captured, not just passenger count.
- **Buildings:** value destination access and denial, while considering forced quantity.
- **Clock:** value the option itself and likely stop-versus-advance outcome; do not assume stopping.
- **Starting Player:** value first access to exclusive actions and favorable draft order next round.

### 7.3 Route-segment evaluation

```text
raw_route_value =
    2.0 * newly_reachable_useful_buildings
  + 1.6 * newly_reachable_unsatisfied_passengers
  + 1.4 * station_access_delta
  + 1.2 * immediate_matching_delta
  + 0.8 * endpoint_future_degree
  + 1.0 * opponent_blocking_delta
  - 1.5 * self_trap_risk
  - 1.0 * redundant_access
```

Normalize with:

```text
route_value = 0.5 * (1 + tanh(raw_route_value / 5.0))
```

A route segment that closes a loop or reduces endpoint flexibility must receive explicit risk unless it creates immediate high-value access.

### 7.4 Building placement evaluation

For each legal `(site, type)`:

```text
self_access_gain
opponent_access_gain_max
current_type_matching_gain
next_type_matching_gain
satisfaction_disruption
site_scarcity
zone_unlock_contribution
endgame_acceleration
```

Candidate score:

```text
raw_building =
    2.0 * self_matching_gain
  + 1.0 * next_type_self_gain
  + 0.8 * site_scarcity
  + 0.8 * opponent_matching_loss
  - 1.6 * best_opponent_matching_gain
  - 0.8 * unwanted_endgame_acceleration
```

Building placement is sequential within the forced quota. Recompute after every tile because occupancy and best denial targets change.

### 7.5 Passenger placement evaluation

At the stations, evaluate ownership-neutral passengers by expected capture share:

```text
capture_share(player, station, type) =
    player's route-and-destination capacity from station
    / total competing capacity from station
```

For the acting player:

```text
raw_passenger =
    2.0 * own_capture_share
  + 1.2 * compatibility_with_selected_vrroomm
  + 0.8 * future_type_coverage
  - 1.5 * leading_opponent_capture_share
```

Avoid placing passengers where an opponent with an earlier Vrrooomm! slot can immediately take them unless placement creates a stronger later benefit.

### 7.6 Clock choice evaluation

Compute both branches exactly through all currently committed Vrrooomm! actions when feasible:

```text
stop_net = root_points_after_stop
         - opponents_weighted_points_after_stop
         - 1.0
         + terminal_lead_protection

advance_net = root_points_after_advance
            - opponents_weighted_points_after_advance
            + future_cycle_value

choose stop if stop_net > advance_net
```

The `−1.0` is the raw final-score cost of the time stone, not a normalized heuristic penalty. If stopping takes the final time stone, use terminal evaluation immediately.

### 7.7 Passenger movement evaluation

A legal passenger move always scores one point, but destination choice changes future value. Rank moves by:

- preserving scarce destinations for passengers only the root can access;
- occupying destinations that an opponent could otherwise use this action;
- placing the moved passenger where it will be favorably positioned after the next clock change;
- avoiding a destination that strands the passenger outside the root route;
- maintaining repeatable cycles among house, office, and pub access.

Because the player must transport as many passengers as possible, “do not move” is not legal when transport is available.

### 7.8 Pass evaluation

Pass is a legitimate strategic action-selection choice, not merely failure.

```text
pass_value = marker_conservation
           + endgame_timing
           + avoidance_of_forced_bad_action
           - missed_best_action
           - initiative_loss
```

A hard discard-style ceiling is not appropriate because passing can be objectively best. However, apply a **pass confidence gate**:

```text
select_pass_only_if
  pass_value >= best_placement_value + pass_margin
  OR no placement has positive expected marginal utility
```

Starting `pass_margin = 0.03` prevents shallow evaluation noise from causing premature drop-out.

---

## 8. Horizon position evaluator

### 8.1 Root-relative multiplayer value

A single score difference against one opponent is insufficient. Use a blend of lead margin, field position, and win potential.

```text
adjusted_score[p] = score[p] - time_stones_taken[p]
lead_margin = adjusted_score[root] - max(adjusted_score[opponents])
field_margin = adjusted_score[root] - mean(adjusted_score[opponents])
```

Normalize:

```text
relative_margin = 0.60 * sigmoid(lead_margin / 4.0)
                + 0.40 * sigmoid(field_margin / 5.0)

sigmoid_like(x) = 0.5 * (1 + tanh(x))
```

The denominators must be recalibrated from self-play score distributions.

### 8.2 Feature definitions

#### A. Relative score position

- **Raw:** lead and field margins after time-stone penalties.
- **Direction:** higher is better.
- **Normalization:** tanh blend above.
- **Strategic reason:** final victory is rank-based.
- **Fixture:** same infrastructure, root leads by 3 versus trails by 3.

#### B. Absolute scoring efficiency

```text
points_per_spent_marker = score / max(1, 20 - markers_remaining)
projected_points = adjusted_score + expected_future_points
absolute_efficiency = clamp01(projected_points / score_scale)
```

Starting `score_scale = 15`, then fit to observed games by player count.

#### C. Immediate ride potential

For each destination type `t`:

```text
matching[p,t] = maximum transport matching on p's route
ride_capacity[p,t] = min(buses[p], matching[p,t])
```

Weight current clock most heavily:

```text
ride_equity[p] = 0.55 * ride_capacity[p,current]
               + 0.30 * ride_capacity[p,next]
               + 0.15 * ride_capacity[p,third]
```

Normalize relative to plausible capacity:

```text
ride_value = clamp01(ride_equity[root] / 5.0)
```

#### D. Network quality

```text
network_raw =
    1.5 * station_coverage
  + 1.0 * reachable_houses
  + 1.0 * reachable_offices
  + 1.0 * reachable_pubs
  + 1.2 * destination_balance
  + 0.8 * exclusive_useful_crossings
  + 0.6 * endpoint_mobility
  - 1.0 * redundant_route_edges
  - 1.4 * trapped_endpoint_risk
```

Normalize with `0.5 * (1 + tanh(network_raw / 8.0))`.

#### E. Passenger control

```text
passenger_control_raw =
    accessible_unsatisfied_passengers[root]
  + 0.5 * passengers_positioned_for_next_type[root]
  - max(accessible_unsatisfied_passengers[opponents])
```

Normalize around observed range, starting denominator `5.0`.

#### F. Action reserve and tempo

```text
reserve_raw = markers_remaining[root] - mean(opponent_markers_remaining)
reserve_value = 0.5 * (1 + tanh(reserve_raw / 5.0))
```

Blend with selected-action quality and predicted survival:

```text
tempo_value =
    0.45 * reserve_value
  + 0.35 * current_round_commitment_quality
  + 0.20 * next_round_initiative
```

#### G. Bus investment efficiency

```text
utilization = expected_points_per_vrroomm / buses[root]
future_ride_count = expected number of reachable Vrrooomm! actions
bus_roi_raw = marginal_capacity_use * future_ride_count - global_power_conceded
```

This prevents “more buses is always better.” Buying the new global maximum can strengthen later Passenger/Building actions belonging to opponents.

#### H. Clock leverage

```text
clock_leverage_raw =
    best(stop_value, advance_value) - forced_advance_value
```

This is highest when owning the Clock choice materially changes the current round or safely ends the game.

#### I. Endgame control

```text
end_pressure =
    probability_game_ends_this_round_or_next
    * utility_if_ended
```

Inputs include markers remaining, empty building sites, remaining time stones, Clock ownership, and already committed Buildings actions.

#### J. Blocking and vulnerability

```text
blocking_net = opponent_best_transport_loss_created
             - root_transport_loss_exposed
```

Keep this bounded. Pure denial should not dominate unconverted scoring potential.

### 8.3 Starting horizon formula

```text
horizon_value =
    0.24 * relative_margin
  + 0.07 * absolute_efficiency
  + 0.18 * immediate_ride_potential
  + 0.14 * network_quality
  + 0.09 * passenger_control
  + 0.10 * action_reserve_and_tempo
  + 0.05 * bus_investment_efficiency
  + 0.05 * clock_leverage
  + 0.05 * endgame_control
  + 0.03 * blocking_net
  - forced_action_liability
  - stagnation_penalty
  - overextension_penalty
```

Positive weights sum to `1.00`. Penalties are separate bounded deductions:

```text
forced_action_liability <= 0.10
overstension_penalty    <= 0.08
stagnation_penalty      <= 0.06
```

Final normalization:

```text
final = clamp(horizon_value, 0.0, 1.0)
```

### 8.4 Penalty definitions

**Forced-action liability:** The player has selected an action whose mandatory completion is likely to improve opponents more than self or force damaging route/building placement.

**Overextension:** Buses, long route, or broad destination access exist without enough passengers, destinations, ride slots, or action markers to monetize them.

**Stagnation:** The state preserves score but has no plausible scoring action, no useful current-round commitment, poor passenger access, and little remaining initiative.

---

## 9. Terminal evaluation

### 9.1 Exact ranking

Compute adjusted scores:

```text
adjusted_score = score - time_stones_taken
```

Apply tie breakers exactly:

1. higher adjusted score;
2. among tied players, more time stones taken;
3. among players still tied, the player whose score disc is lower in the stack, meaning they reached that score first.

### 9.2 Returned utility

For a single-root scalar API:

```text
sole win = 1.0
ranked utility = (players - final_rank) / (players - 1)
```

Because the official tie breakers produce a strict ranking, a generic draw value will rarely apply. If an engine mode intentionally ignores tie breakers, use `0.5` for a shared draw.

For MaxN, return a utility vector. A useful terminal vector is normalized rank utility, with a small score-margin refinement that never reverses rank:

```text
utility[p] = rank_utility[p] + epsilon * normalized_score_margin[p]
```

Use `epsilon <= 0.01`.

Known terminal values must always replace the nonterminal heuristic.

---

## 10. Search design

### 10.1 Recommended algorithm

For 3–5 players and large spatial branching, use one of:

- **MCTS with MaxN backups**, policy priors, and progressive widening;
- **Paranoid MCTS** as a stress-test mode;
- shallow deterministic MaxN/alpha-beta variants for tactical resolution phases.

A practical hybrid:

```text
Action selection phase: MCTS + progressive widening
Route/building placement: beam search or progressive widening
Clock and Vrrooomm resolution: exact tactical search where affordable
Terminal-near states: deterministic full-width search
```

### 10.2 Round-aware horizon

Do not stop a search arbitrarily between an action selection and its consequences if avoidable. Preferred cut points:

1. after all actions in the current round resolve;
2. immediately after a Clock branch if all committed rides can be simulated;
3. after completion of the currently forced multi-placement action.

If budget forces a mid-round leaf, include all committed actions as liabilities/assets in the horizon evaluator.

### 10.3 Progressive widening

Route and building combinations explode. Expand candidates in strategic tiers:

1. changes immediate matching;
2. gains station or missing building-type access;
3. blocks the leading opponent;
4. preserves highest endpoint mobility;
5. all remaining legal moves.

Example widening rule:

```text
max_children(node) = floor(2.0 * visits(node)^0.45) + 1
```

Tune separately by action class.

### 10.4 PUCT prior

```text
selection = Q + c_puct * prior * sqrt(parent_visits) / (1 + child_visits)
```

Starting `c_puct = 1.25`. One-ply values should be softmaxed into priors only after legal generation:

```text
prior_i = softmax(one_ply_i / temperature)
```

Starting temperature `0.18`, with a floor probability to ensure exploration.

### 10.5 Transpositions and symmetry

Hash all authoritative state, including:

- action-slot ownership and pass status;
- resolution cursor and remaining forced count;
- route endpoints and loop markers;
- building occupancy;
- passenger/building occupancy distinction;
- score-disc stack order;
- remaining markers and time stones.

Canonicalize player colors only in fixtures or before the game when seat order and starting player are transformed consistently. Geographic board symmetries may be used only if the map and all setup state are transformed exactly.

---

## 11. Game-specific invariants

1. Every returned action is validator-legal.
2. A player cannot voluntarily skip a required part of a selected action.
3. Passing is legal only after the player has placed the required minimum number of markers that round.
4. Passing removes that player from further action selection for the round.
5. Used action markers never return.
6. Buses, Clock, and Starting Player cannot be selected by multiple players in the same round.
7. A player may select a multi-slot action more than once if a legal slot remains.
8. Action power uses the current global maximum bus count at resolution time.
9. Five-player line expansion adds exactly the configured bonus and no other action receives it.
10. A route extends only from a legal endpoint and remains one traversable line under the route rules.
11. Route markers are permanent.
12. Buildings occupy only legal unlocked sites, no more than one per site.
13. Building zone progression is enforced.
14. Passengers enter only at a station and cannot exceed supply.
15. A bus moves only a passenger who wants to leave.
16. Each moved passenger arrives at an empty building of the demanded type connected to that player's route.
17. A Vrrooomm! action transports the maximum possible number up to bus capacity.
18. Each moved passenger scores exactly one point.
19. Passenger and destination availability is recomputed after every move because earlier movers consume shared opportunities.
20. Clock advance occurs unless the Clock owner elects to stop time.
21. Stopping time removes one stone and applies one negative final point.
22. Taking the final time stone immediately terminates the game and cancels later actions.
23. Round-end conditions are checked at the correct time, not during arbitrary subactions.
24. Score-stack order is preserved for tie breaking.
25. Evaluation uses no information unavailable in the public state.

---

## 12. Required diagnostics

### 12.1 Root move summary

```text
move
move_class
one_ply_value
prior
visits
average_root_value
maxn_vector
paranoid_value
selection_score
sample_count
sample_min
sample_max
principal_variation
```

### 12.2 Path record

```text
depth
phase
actor
path
leaf_type
terminal_reason
leaf_value
utility_vector
```

### 12.3 Horizon breakdown

```text
adjusted_scores
lead_margin
field_margin
relative_margin
absolute_efficiency
immediate_ride_potential
network_quality
passenger_control
action_reserve_and_tempo
bus_investment_efficiency
clock_leverage
endgame_control
blocking_net
forced_action_liability
stagnation_penalty
overextension_penalty
final
```

### 12.4 Spatial and transport breakdown

```text
current_destination_type
next_destination_type
buses_by_player
maximum_buses
reachable_buildings_by_type
empty_destinations_by_type
accessible_unsatisfied_passengers
maximum_matching_by_type
ride_capacity_by_type
station_access
endpoint_legal_degree
exclusive_crossings
route_redundancy
best_opponent_access
```

### 12.5 Action-economy breakdown

```text
markers_remaining
markers_committed_this_round
minimum_future_rounds
expected_scoring_actions_remaining
selected_action_power
resolution_order
forced_quantity
marginal_marker_value
end_probability_this_round
end_probability_next_round
```

---

## 13. Deterministic fixture plan

Each fixture asserts legality, one-ply ordering, horizon-component direction, and final selection when strategically decisive.

1. **Opening building access:** choose between a building touching only self, only opponent, or both.
2. **Opening route station race:** second route segment gains station access versus balanced destination access.
3. **Mandatory two markers:** pass is unavailable before two placements and available afterward.
4. **Irrevocable pass:** a passed player is not prompted again that round.
5. **Exclusive action race:** Buses, Clock, and Starting Player close after selection.
6. **Duplicate action selection:** same player legally takes two Vrrooomm! slots.
7. **A-slot quantity versus order:** Line Expansion A is stronger but resolves after weaker slots.
8. **Route block:** earlier weak slot blocks the later A player's preferred extension.
9. **Parallel-route exception:** legal only under the exact endpoint/no-empty-street exception.
10. **Loop closure:** endpoint marker and future legal extensions remain correct.
11. **Self-parallel prohibition:** reject illegal route segment.
12. **Global bus increase:** Buses action increases later Passenger/Building quantities immediately.
13. **Bus ROI trap:** buying a bus helps opponents' committed actions more than the buyer.
14. **Passenger station choice:** one station is capturable by root, the other by an earlier opponent.
15. **Passenger supply exhaustion:** action completes only to maximum possible quantity.
16. **Building reverse resolution:** weaker slot places first and consumes the key site.
17. **Zone unlocking:** Zone 2 is unavailable until every Zone 1 site is filled.
18. **Building exhaustion:** terminal occurs at round end, not immediately.
19. **Clock repeat score:** stopping time enables a superior repeated ride and is worth the point cost.
20. **Clock restraint:** selecting Clock but allowing time to advance is optimal.
21. **Clock rupture:** final stone ends immediately and later Vrrooomm! actions do not score.
22. **Occupied destinations:** earlier ride consumes a destination, reducing later matching.
23. **Must transport maximum:** bot cannot choose only one move when two are possible.
24. **Destination preservation:** two equal-point passenger moves differ in future positioning.
25. **Repeated Vrrooomm!:** same player's second ride is recomputed from changed occupancy.
26. **Start-player value:** initiative secures an exclusive action next round.
27. **Marker conservation:** pass beats a low-value third action.
28. **Tempo burn:** extra action triggers a favorable near-term end.
29. **Premature exhaustion:** overspending leaves the player unable to score later.
30. **Only one player with markers:** correct round-end termination.
31. **Adjusted-score reversal:** leader loses after time-stone penalties.
32. **Tie breaker by stones:** tied adjusted scores favor more time stones.
33. **Tie breaker by score stack:** final exact tie resolves to the earlier achiever.
34. **Five-player line bonus:** Line Expansion receives +1 only at five players.
35. **Seat/color permutation:** equivalent transformed states return equivalent evaluations and moves.
36. **MaxN versus paranoid:** diagnostic values differ, but both remain legal and deterministic.

---

## 14. Calibration plan

### 14.1 Data collection

Run self-play separately for 3, 4, and 5 players. Record:

- final and intermediate adjusted scores;
- score margins;
- markers spent per round;
- buses purchased and realized utilization;
- matching sizes by destination type;
- action-slot values by round;
- number and value of Clock stops;
- terminal cause;
- branching factor and resolution latency.

### 14.2 Weight tuning order

1. Validate exact rules and fixtures.
2. Calibrate raw normalization scales so features use the interior of `[0,1]`.
3. Tune immediate scoring and ride matching.
4. Tune marker economy and endgame pressure.
5. Tune spatial network and blocking.
6. Tune Clock leverage.
7. Tune opponent-model blend.
8. Tune PUCT constants and progressive widening.

Do not tune all parameters simultaneously at first.

### 14.3 Saturation checks

Flag a feature when more than 20% of nonterminal samples are below `0.02` or above `0.98`, unless the feature is intentionally binary. Report distributions by player count and game phase.

### 14.4 Benchmark matrix

| Benchmark | Measure | Initial acceptance target |
|---|---|---:|
| Rule fixtures | Passing | 100% |
| Tactical fixtures | Expected top move | ≥ 90% |
| Seat/color permutations | Equivalent ranking | 100% |
| Fixed seed/config | Deterministic root result | 100% |
| Shallow vs deep search | Blunder reduction | Monotonic trend |
| Self-play vs baseline | Win/rank improvement | Statistically positive |
| Illegal selections | Count | 0 |
| Horizon saturation | Extreme-value frequency | < 20% per continuous feature |
| Search latency | p50/p95 | Product-specific budget |
| Memory | Peak/transposition growth | Product-specific budget |

For multiplayer evaluation, report first-place rate, average rank, adjusted-score margin, and pairwise dominance. Win rate alone hides meaningful improvements in 4–5 player games.

---

## 15. Promotion gates

A Bus policy is ready for production only if:

- all setup, route, action-order, forced-completion, scoring, Clock, and terminal tests pass;
- no illegal action is selected in stress runs;
- fixed-state searches are deterministic under fixed budget and seed;
- tactical fixture threshold is met in every player-count configuration;
- player-color and seat transformations preserve perspective correctly;
- exact immediate transport matching agrees with brute-force enumeration on small states;
- feature distributions do not show unexplained saturation;
- the policy outperforms a legal random bot and a greedy immediate-score bot;
- MaxN and paranoid diagnostics are both available for contested states;
- p50/p95 search latency remains within the application's limit;
- raw diagnostics explain route, passenger, building, marker, and Clock decisions;
- edition differences are configuration-tested;
- the previous strategy remains selectable as a rollback.

---

## 16. Recommended implementation sequence

### Milestone 1: Rules and state machine

Implement the complete phase enum, legal move generation, transitions, action power, route geometry, matching-based Vrrooomm!, scoring, and terminal/tie-break logic.

### Milestone 2: Tactical policy

Implement exact immediate ride value, action-slot ordering, route/building/passenger candidate scoring, pass evaluation, and Clock branch comparison.

### Milestone 3: Horizon evaluator

Add the ten positive features and three bounded penalties with the complete diagnostic schema.

### Milestone 4: Search

Add MaxN-aware MCTS, policy priors, progressive widening, transpositions, and round-aware cutoff rules.

### Milestone 5: Calibration

Run deterministic fixtures, seat permutations, self-play, scale fitting, weight tuning, and latency profiling.

---

## 17. Compact implementation checklist

- [ ] Setup order and reverse second-line placement implemented.
- [ ] Seven actions and exact resolution order implemented.
- [ ] Minimum two action selections enforced.
- [ ] Pass/drop-out behavior implemented.
- [ ] Single-slot and multi-slot action occupancy implemented.
- [ ] Current global maximum buses drives action power.
- [ ] Five-player line bonus configurable.
- [ ] Forced maximum completion enforced.
- [ ] Route endpoint, parallel, loop, and permanence rules tested.
- [ ] Building zones and exhaustion tested.
- [ ] Passenger supply and station placement tested.
- [ ] Exact transport matching and destination occupancy tested.
- [ ] Clock advance, stop, penalty, and rupture tested.
- [ ] Immediate and round-end terminal timing separated.
- [ ] Final tie breakers implemented.
- [ ] One-ply and horizon evaluators separated.
- [ ] All features expose raw and normalized values.
- [ ] Multiplayer opponent model documented.
- [ ] Progressive widening configured by action type.
- [ ] Tactical and seat-swapped fixtures pass.
- [ ] Performance and rollback gates pass.

---

## Sources

1. BoardGameGeek, **Bus** overview and game description: https://boardgamegeek.com/boardgame/552/bus  
2. Cardboard Appendix, **Bus Rulebook** transcription, including setup, action selection and resolution, all seven actions, end conditions, tie breakers, and five-player rule: https://cardboardappendix.com/games/bus/rulebook/  
3. BoardGameGeek, **Bus Rulebook** file page for the 2019 Capstone edition and discussion of a known Buildings example inconsistency: https://boardgamegeek.com/filepage/191623/bus-rulebook  
4. BoardGameGeek, **Bus: Complete Edition Rulebook** file page (2024 edition): https://boardgamegeek.com/filepage/278728/bus-complete-edition-rulebook  
5. Splotter Spellen, **Bus** publisher description: http://splotter.nl/english/bus.html

> **Implementation note:** The rulebook is authoritative for rules. Strategy formulas, weights, thresholds, search recommendations, and fixture design in this document are original engineering proposals and must be calibrated against the engine's implementation and self-play data.
