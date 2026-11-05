# Bus Game Requirements

**Game:** *Bus*  
**Artifact type:** Non-AI game requirements analysis  
**Rules baseline:** Standard 3–5 player game, based primarily on the published English rules for the 2019 edition, with edition-specific questions recorded in the sign-off section.  
**Document status:** Draft for product, rules, UX, API, and QA review  

---

## 1. Scope and requirements conventions

This document defines the authoritative requirements for setup, rules enforcement, game state, player-visible views, lifecycle, persistence, API behavior, frontend behavior, validation, and acceptance testing for *Bus*. It intentionally excludes bot strategy, search, heuristic evaluation, and other AI behavior.

The keywords **MUST**, **MUST NOT**, **SHOULD**, and **MAY** indicate requirement strength:

- **MUST / MUST NOT:** mandatory for rules correctness or product integrity.
- **SHOULD / SHOULD NOT:** expected unless a documented product reason overrides it.
- **MAY:** optional behavior that must remain consistent if supported.

### 1.1 Rules authority

1. The selected edition's published rulebook MUST be the authority for game rules.
2. Edition differences MUST be represented explicitly in the game record.
3. Product behavior that is not specified by the rulebook, such as undo and abandonment, MUST be governed by documented product policy rather than hidden assumptions.
4. The system MUST distinguish official game rules from product conveniences such as action previews, confirmations, timers, and reconnect behavior.

---

## 2. Game objective and core rules

### 2.1 Objective

Players develop bus lines and transport passengers to the type of building demanded by the clock. A player scores one point for each passenger transported during a **Vrrooomm!** action. The winner is the player with the highest final score after subtracting one point for each time stone held.

### 2.2 Player count

- The standard game MUST support 3, 4, or 5 players.
- A session MUST NOT begin with fewer than 3 or more than 5 occupied player seats under the standard rules configuration.
- The 5-player line-expansion rule MUST apply only to a 5-player game.
- A 3-player game MUST use 4 time stones. A 4- or 5-player game MUST use 5 time stones.

### 2.3 Public information

The standard game contains no hidden player information after the random starting player is determined. The following MUST be public to every participant:

- player identities, colors, and seat order;
- current starting player;
- scores and score-disc stack order;
- remaining and committed action markers;
- bus counts;
- line markers, route ends, and route topology;
- passengers and their locations;
- buildings, building types, occupied status, and unlocked building zone;
- clock position;
- time stones remaining and held by each player;
- selected action spaces, action owners, and resolution order;
- current phase, current actor, and pending mandatory continuation;
- terminal status, final ranking, and terminal reason.

Server-only security, audit, authorization, and idempotency metadata MUST NOT alter the public game rules.

### 2.4 Scores and winner

1. Vrrooomm! MUST be the only action that directly awards positive victory points.
2. Each legally transported passenger MUST award exactly 1 point to the acting player.
3. Each time stone held by a player MUST subtract exactly 1 point during final scoring.
4. Final adjusted score MUST equal:

```text
adjustedScore = scoredPoints - timeStonesHeld
```

5. The player with the highest adjusted score MUST win.
6. If players tie on adjusted score, the tied player with more time stones MUST rank higher.
7. If still tied, the tied player whose score disc is lower in the score-track stack MUST rank higher because that player reached the tied score first.
8. The score-disc stacking order MUST therefore be authoritative and persisted.
9. Scores MUST NOT reset between rounds.

---

## 3. Components and identifiers

### 3.1 Required components

A standard game requires:

- 1 game board containing the city map and action area;
- 125 line markers across player colors;
- 100 action markers, 20 per player color;
- 25 bus tokens, 5 per player color;
- 15 passenger pieces;
- 5 score discs;
- 5 time stones, of which only 4 are used in a 3-player game;
- 90 building tiles across House, Office, and Pub types;
- 1 starting-player marker, called the Start-Bus.

### 3.2 Stable identifiers

All semantic game objects MUST have stable identifiers suitable for validation and serialization:

- player ID;
- session ID;
- game ID;
- action request ID;
- action space ID;
- route edge ID;
- crossing ID;
- building location ID;
- building tile or building instance ID;
- passenger ID;
- bus token ID or an authoritative bus count;
- time stone ID or an authoritative stone count;
- round number;
- state version.

Coordinates MAY supplement identifiers but MUST NOT replace semantic identifiers in action requests.

---

## 4. Legal setup requirements

### 4.1 Base setup

1. Each player MUST occupy a unique seat and choose or receive a unique player color.
2. Each player MUST begin with:
   - 20 action markers in that player's color;
   - the line markers assigned to that color;
   - 5 bus tokens in that color, with exactly 1 bus active in the bus depot;
   - 1 score disc on score 0;
   - 0 time stones.
3. The clock MUST begin pointing to the House.
4. Four passengers MUST begin on the roundabouts immediately adjacent to Central Park, as defined by the board data.
5. The remaining passengers MUST begin in the common supply.
6. The game MUST randomly select a starting player unless the session configuration explicitly uses a deterministic setup seed or agreed fixed starting player.
7. The starting player MUST receive the Start-Bus.
8. Random starting-player selection MUST be reproducible from a stored random seed when seeded play is enabled.

### 4.2 Initial building placement

1. Beginning with the starting player and continuing clockwise, each player MUST place exactly 2 buildings.
2. Initial buildings MUST be placed only on unoccupied Zone 1 building locations.
3. Each initial building MAY be a House, Office, or Pub, subject to available components.
4. No building location may contain more than one building.
5. Setup MUST NOT proceed to initial line placement until all players have completed their required initial building placements.

### 4.3 Initial line placement

1. Beginning with the starting player and continuing clockwise, each player MUST place one line marker on a legal street.
2. A first line marker MAY share a street occupied by another player's first line, as allowed by the setup rule.
3. Beginning with the last player in clockwise order and proceeding in reverse order, each player MUST place a second line marker.
4. The second line marker MUST extend from an end of that player's first line.
5. The normal line-expansion restrictions MUST apply to the second line marker.
6. Setup MUST complete only after every player has placed exactly 2 buildings and exactly 2 line markers.
7. The first round MUST begin with the starting player as the first action selector.

---

## 5. Round and phase requirements

### 5.1 Round structure

Every round MUST contain:

1. **Action Selection phase**
2. **Action Resolution phase**
3. **Round Completion**, unless the game ended immediately during Clock resolution

The action resolution sequence MUST be:

1. Line Expansion
2. Buses
3. Passengers
4. Buildings
5. Clock
6. Vrrooomm!
7. Starting Player

Actions not selected in the round MUST be skipped without creating an actor turn.

### 5.2 Action Selection phase

1. The starting player MUST select first.
2. Selection MUST proceed clockwise among players who have not passed and who possess action markers.
3. On a selection turn, a player MUST place one action marker in a legal action space unless eligible to pass.
4. Every participating player MUST select at least 2 actions before passing, unless a rules-authorized exceptional state makes this impossible because that player began the round with fewer than 2 action markers. This exceptional case is unresolved and MUST be confirmed before sign-off.
5. After selecting at least 2 actions in the current round, a player MAY pass on a later selection turn.
6. Passing MUST be irrevocable for the remainder of that round.
7. Selection MUST continue until every eligible player has passed or has no action markers remaining.
8. A player MAY select the same multi-slot action more than once if a legal action space remains.
9. The maximum number of selections is limited by the player's available action markers and available action spaces.
10. A placed action marker MUST immediately leave the player's available supply and become committed to its action space.
11. Committed action markers MUST remain visible throughout resolution.

### 5.3 Action-space exclusivity

- Buses MUST have exactly one selectable position per round.
- Clock MUST have exactly one selectable position per round.
- Starting Player MUST have exactly one selectable position per round.
- Line Expansion, Passengers, Buildings, and Vrrooomm! MUST use ordered lettered positions.
- The first selector of a multi-position action MUST occupy A, the next selection MUST occupy B, and so forth without gaps.
- A client MUST NOT be allowed to nominate an arbitrary non-next lettered position.

### 5.4 Resolution order within an action

1. The owner of the leftmost occupied action marker MUST resolve first.
2. The physical/action-board order MUST be authoritative.
3. For Line Expansion and Buildings, the action-board arrangement results in reverse selection order.
4. For Passengers and Vrrooomm!, the action-board arrangement results in selection order.
5. When a player selected an action multiple times, each marker MUST resolve separately in its action-board position.
6. A required multi-step action MUST remain pending until completed to its fullest legal extent.

### 5.5 Maximum number of buses

1. The **maximum number of buses** MUST equal the greatest bus count held by any player at the moment the affected action resolves.
2. For Line Expansion, Passengers, and Buildings, the A-position quantity MUST equal the maximum number of buses.
3. Each subsequent lettered position MUST reduce the quantity by one.
4. A quantity MUST NOT be negative.
5. In a 5-player game, every Line Expansion quantity MUST receive an additional 1.
6. The 5-player bonus MUST NOT apply to Passengers or Buildings.
7. If the Buses action increases the global maximum, unresolved Passenger and Building quantities in that same round MUST reflect the increased maximum.
8. Whether an unresolved Line Expansion quantity could ever be affected by Buses is moot under standard resolution because Line Expansion occurs first; the system MUST nevertheless calculate from current authoritative state rather than a stale cached round-start value.

### 5.6 Mandatory maximum completion

1. A selected action MUST be completed to its fullest legal extent.
2. A player MUST NOT voluntarily skip a selected action or part of a selected action.
3. If component shortage or legal-space shortage prevents full completion, the player MUST complete the maximum legally possible amount.
4. If zero completion is possible, the action MUST resolve with no mutation other than completion/audit state and spent-marker disposition.

---

## 6. Legal-action requirements

## 6.1 Select action

### Preconditions

- The game is active and in Action Selection.
- The requester is the current selector.
- The player has not passed this round.
- The player has at least one uncommitted action marker.
- The requested action has an available legal position.

### Inputs

- session ID;
- player ID;
- state version;
- action type.

The server MUST derive the correct action-space position. A client-supplied position, if accepted for UI correlation, MUST match the derived legal position.

### Validation and errors

Reject with a client-visible semantic error for:

- wrong phase;
- not current actor;
- player already passed;
- no action markers;
- exclusive action occupied;
- no remaining lettered position;
- stale state version;
- duplicate request with different content under the same idempotency key.

### Atomic mutation

- occupy the next legal action space;
- deduct one available action marker;
- increment the player's selections this round;
- determine the next eligible selector or begin resolution when selection is complete;
- increment state version;
- persist the transition.

### Response

The response MUST include the accepted action, updated public state/view, next actor or next phase, state version, and legal actions available to the requesting player.

## 6.2 Pass action selection

### Preconditions

- The game is in Action Selection.
- The requester is the current selector.
- The player has not passed.
- The player has made the required minimum number of selections this round, subject to the unresolved low-marker rule.

### Mutation

The player becomes passed for the current round. The next eligible player acts, or resolution begins if all eligible players have passed or exhausted their markers.

### Validation

A premature, repeated, stale, or out-of-turn pass MUST be rejected without changing game state.

## 6.3 Line Expansion

### Preconditions

- The game is resolving Line Expansion.
- The requester owns the active Line Expansion marker.
- The player has remaining required placements.
- The selected edge is a legal extension from a current route end.

### Inputs

- player ID;
- route edge ID;
- originating route-end crossing ID when the edge is ambiguous;
- state version.

### Validation rules

1. A line MUST expand from one of its two ends.
2. A line MUST normally enter a street empty of other bus lines.
3. A line MUST NOT run parallel to the player's own line.
4. Parallel construction alongside another player's line is legal only under a published exception:
   - no empty outgoing street exists at the selected end; or
   - the player's route end shares the crossing with the other player's route end under the rule's required conditions.
5. After using a parallel exception, the next extension MUST turn onto an empty street when one is available.
6. The player MUST NOT backtrack along their own route.
7. The complete route MUST remain one traversable line from end to end, passing each route street exactly once.
8. When a circle is closed, the route-end state MUST remain at the closing crossing as prescribed by the rules.
9. Existing route markers MUST never be removed during normal play.

### Atomic mutation

A legal edge becomes occupied by the player's line, route ends and any circle-end indicator are updated, the remaining required placement count decreases, and the action continues or advances.

### No legal extension

If no legal extension exists before the quota is complete, the action MUST end after recording that maximum possible completion was reached.

## 6.4 Buses

### Preconditions

- The game is resolving Buses.
- The active marker belongs to the requester.
- The player has an unused bus token available.

### Mutation

The player's active bus count increases by exactly 1, subject to the component limit. The maximum-bus derived value MUST update immediately.

### No available bus token

The rulebook/component interpretation for selecting Buses when already at 5 buses MUST be confirmed. Until sign-off, the product MUST either prohibit the selection as having no legal effect or permit it and resolve no effect, based on the approved ruling.

## 6.5 Passengers

### Preconditions

- The game is resolving Passengers.
- The requester owns the active marker.
- At least one required passenger remains and at least one passenger remains in supply.

### Inputs

- passenger ID from supply;
- one of the two station crossing IDs;
- state version.

### Validation rules

1. A new passenger MUST be placed at one of the two stations.
2. Passengers MAY be distributed between the stations across a multi-placement action.
3. The acting player's line need not connect to the selected station.
4. A passenger already in play MUST NOT be selected from supply.
5. Placement MUST stop when the required quantity is reached or supply is empty.

### Mutation

Move the passenger from supply to the selected station, decrement the remaining required count, and continue or advance.

## 6.6 Buildings

### Preconditions

- The game is resolving Buildings.
- The requester owns the active marker.
- A required placement remains.
- At least one legal building location and a tile of the requested type remain available.

### Inputs

- building location ID;
- building type: House, Office, or Pub;
- state version.

### Validation rules

1. A location MUST contain at most one building.
2. Only the currently unlocked zone MAY receive a building.
3. Zone 1 MUST be filled before Zone 2 unlocks; Zone 2 before Zone 3; Zone 3 before Zone 4.
4. The system MUST re-evaluate the unlocked zone after every placement.
5. The requested building type MUST have an available tile if tile inventory is modeled individually.

### Mutation

Place the building, update component inventory, update zone availability, decrement the action's remaining count, and continue or advance.

### Exhausted locations

When the final building location is filled, the system MUST mark the round-end terminal condition as pending. The game MUST continue resolving the current round unless it ends earlier because of Clock rupture.

## 6.7 Clock

### Preconditions

- The game is resolving Clock.
- If the Clock action was selected, the requester owns its marker.

### Inputs

When selected, the player chooses one of:

- Stop time
- Allow time to advance

If no player selected Clock, no player input is required.

### Validation and mutation

**Stop time:**

1. The clock hand remains on its current building type.
2. The acting player takes exactly one available time stone.
3. The taken stone remains associated with that player through final scoring.
4. The player incurs no immediate score-track change unless the approved UI chooses to display an adjusted-score preview.
5. If that was the last available time stone, the game ends immediately.
6. No later action in the round is resolved after immediate termination.

**Advance time:**

1. The clock moves exactly one position clockwise.
2. No time stone is taken.

**No Clock selector:**

- The clock MUST automatically advance exactly one position clockwise.

### Errors

Reject an attempted stop when no time stone is available, a choice from a non-owner, a duplicate choice after resolution, or any stale/wrong-phase request.

## 6.8 Vrrooomm!

### Preconditions

- The game is resolving Vrrooomm!.
- The requester owns the active marker.
- The active player has remaining bus capacity for this action.
- At least one legal passenger transport exists.

### Passenger eligibility

1. The passenger MUST be on a crossing connected to the acting player's line.
2. The passenger MUST want to leave their current crossing.
3. A passenger does not want to leave when an available building of the currently demanded type is present at that crossing and the passenger is satisfied there under the rules.
4. A station passenger is treated according to the rulebook's satisfaction and movement rules and MUST be movable only when a valid route and destination exist.

### Destination eligibility

1. The destination MUST be an empty building of the type currently indicated by the clock.
2. The destination crossing MUST be connected to the acting player's line.
3. Each building MUST hold no more than one passenger.
4. The source and destination MUST form a legal transport on the acting player's line.

### Inputs

- passenger ID;
- destination building ID or destination crossing/building pair;
- state version.

### Mutation

- move the passenger atomically to the selected destination building;
- mark destination occupancy;
- vacate the passenger's former building occupancy, if any;
- increment the acting player's score by 1;
- update score-disc stack order when the score changes;
- decrement remaining bus capacity;
- recompute legal transports.

### Mandatory maximum transport

1. Each bus may transport at most one passenger during one Vrrooomm! action.
2. The player MUST transport as many passengers as legally possible, up to the player's bus count.
3. The action ends when bus capacity is exhausted or no legal passenger-to-destination transport remains.
4. A player MAY choose among legal passengers and destinations when alternatives exist.
5. If a player selected Vrrooomm! more than once, full bus capacity MUST reset for each separate resolution.

## 6.9 Starting Player

1. If selected, the owner of the Starting Player action MUST receive the Start-Bus for the next round.
2. If not selected, the Start-Bus MUST pass to the player to the left of the previous starting player.
3. Resolution MUST update both the next starting player and the next round's first selector.
4. If the game will end at round completion, finalization MAY omit a cosmetic transfer, but the authoritative history MUST still identify whether the action was selected.

---

## 7. Authoritative state requirements

## 7.1 Field classification legend

- **Visibility:** Public, private, or server-only.
- **Persisted:** Required in durable session state or event history.
- **Serialized:** Included in an authorized public/player view.
- **Derived:** Recomputable from authoritative fields and not required as a source of truth.
- **Search-only:** Not applicable to this non-AI requirements artifact and MUST NOT be required for ordinary play.

## 7.2 Session and rules state

| Field | Meaning | Visibility | Persisted | Serialized | Derived |
|---|---|---|---:|---:|---:|
| sessionId | Unique game-session identity | Public to session members | Yes | Yes | No |
| gameId | Stable game identifier for Bus | Public | Yes | Yes | No |
| rulesEdition | Selected rulebook/edition | Public | Yes | Yes | No |
| playerCount | Number of occupied seats | Public | Yes | Yes | Yes |
| status | Lobby, setup, active, terminal, abandoned | Public | Yes | Yes | No |
| stateVersion | Monotonic concurrency version | Public | Yes | Yes | No |
| createdAt / updatedAt | Session timestamps | Public or server-only by policy | Yes | Optional | No |
| randomSeed | Reproducibility seed | Server-only until policy permits disclosure | Yes | No during active game | No |
| rulesFlags | Approved edition or house-rule switches | Public | Yes | Yes | No |

## 7.3 Player state

| Field | Meaning | Visibility | Persisted | Serialized | Derived |
|---|---|---|---:|---:|---:|
| playerId | Stable player identity | Public | Yes | Yes | No |
| seatIndex | Clockwise seat order | Public | Yes | Yes | No |
| displayName | User-facing player name | Public | Yes | Yes | No |
| color | Unique component color | Public | Yes | Yes | No |
| connectionStatus | Online/disconnected | Public or policy-controlled | Yes | Yes | No |
| scoredPoints | Positive points earned | Public | Yes | Yes | No |
| timeStonesHeld | Negative-point stones | Public | Yes | Yes | No |
| adjustedScore | Final or preview score | Public | Optional | Yes | Yes |
| scoreStackOrder | Relative disc order at a score | Public | Yes | Yes | No |
| actionMarkersAvailable | Unspent marker count | Public | Yes | Yes | No |
| selectionsThisRound | Number committed this round | Public | Yes | Yes | No |
| passedThisRound | Whether player dropped from selection | Public | Yes | Yes | No |
| busCount | Active buses | Public | Yes | Yes | No |
| routeState | Player-owned edges and route ends | Public | Yes | Yes | No |
| isOutOfActions | No markers remain | Public | Optional | Yes | Yes |

## 7.4 Phase and turn state

| Field | Meaning | Visibility | Persisted | Serialized | Derived |
|---|---|---|---:|---:|---:|
| roundNumber | Current round, starting at 1 after setup | Public | Yes | Yes | No |
| phase | Exact validator phase | Public | Yes | Yes | No |
| currentActorId | Player required to act, if any | Public | Yes | Yes | No |
| startingPlayerId | Current round's starting player | Public | Yes | Yes | No |
| nextStartingPlayerId | Resolved next-round owner when known | Public | Yes | Yes | No |
| selectionCursor | Current clockwise selection position | Public | Yes | Optional | No |
| resolutionAction | Action category currently resolving | Public | Yes | Yes | No |
| resolutionSlot | Active lettered/single slot | Public | Yes | Yes | No |
| pendingContinuation | Required remaining subactions | Public | Yes | Yes | No |
| requiredCount | Quantity required for active action | Public | Yes | Yes | No |
| completedCount | Quantity completed for active action | Public | Yes | Yes | No |
| terminalReason | Immediate or round-end end condition | Public when terminal/pending | Yes | Yes | No |

## 7.5 Board and component state

| Field | Meaning | Visibility | Persisted | Serialized | Derived |
|---|---|---|---:|---:|---:|
| actionSpaces | Ordered slots and marker ownership | Public | Yes | Yes | No |
| crossings | Stable map nodes and metadata | Public | Configuration | Yes | No |
| streets | Stable map edges and route occupancy | Public | Board definition plus game occupancy | Yes | No |
| buildingLocations | Site, zone, crossing, occupancy | Public | Yes | Yes | No |
| buildings | Type, location, passenger occupancy | Public | Yes | Yes | No |
| passengers | Supply or board location and occupancy | Public | Yes | Yes | No |
| clockPosition | House, Office, or Pub demand | Public | Yes | Yes | No |
| timeStonesRemaining | Available clock stones | Public | Yes | Yes | No |
| buildingSupply | Remaining tiles by type | Public | Yes | Yes | No |
| passengerSupply | Remaining passenger identities/count | Public | Yes | Yes | No |
| currentBuildingZone | Currently legal zone | Public | Optional | Yes | Yes |
| maximumBusCount | Highest player bus count | Public | Optional | Yes | Yes |

## 7.6 Terminal state

| Field | Meaning | Visibility | Persisted | Serialized | Derived |
|---|---|---|---:|---:|---:|
| isGameOver | Terminal status | Public | Yes | Yes | Yes |
| terminalReason | Clock rupture, action-marker condition, building exhaustion, abandonment | Public | Yes | Yes | No |
| finalAdjustedScores | Score minus stones | Public | Yes | Yes | Yes |
| finalRanking | Ordered players after tie breakers | Public | Yes | Yes | Yes if history is intact |
| winnerId | First-ranked player | Public | Yes | Yes | Yes |
| completedAt | Completion timestamp | Public | Yes | Yes | No |

### 7.7 Derived state rules

1. Derived fields MUST be reproducible from authoritative state.
2. A mismatch between stored derived data and authoritative data MUST resolve in favor of authoritative data.
3. Legal actions MUST be derived for the current actor and current version.
4. Public views MAY contain convenience fields such as legal destinations, route endpoints, and adjusted-score previews.
5. Search-only or AI-only state MUST NOT become necessary to validate a human action.

---

## 8. Game lifecycle requirements

### 8.1 Creation and lobby

1. A creator MUST select *Bus*, a supported player count, rules edition, and permitted session options.
2. Each seat MUST have a unique identity and color before start.
3. The session MUST NOT start until all required seats are occupied or assigned to an approved participant type.
4. The final rules configuration MUST become immutable after setup begins, except via a full restart.

### 8.2 Persistence boundary

Every accepted authoritative transition MUST be persisted atomically with:

- prior version;
- new version;
- acting identity or system actor;
- semantic action;
- timestamp;
- resulting authoritative state or replayable event data;
- idempotency key where applicable.

A success response MUST NOT be returned before the accepted transition is durably committed under the product's durability policy.

### 8.3 Round end

At normal round completion:

1. all selected actions MUST have fully resolved;
2. used action markers MUST be removed from the game permanently;
3. the next starting player MUST be established;
4. round-end terminal conditions MUST be evaluated;
5. if the game continues, per-round pass/selection state and action spaces MUST reset;
6. the round number MUST increment;
7. the next round MUST enter Action Selection with the starting player as current actor;
8. the resulting state MUST persist before the next action is accepted.

### 8.4 Game end

The game MUST end in exactly one of these official ways:

1. **Immediate Clock rupture:** the last time stone is taken. The game ends immediately and later actions in that round do not occur.
2. **Action-marker condition:** at round end, only one player has action markers remaining.
3. **Building-location exhaustion:** at round end, no free building locations remain.

If multiple round-end conditions are true, the record MAY store multiple contributing conditions but MUST expose one stable primary terminal reason.

### 8.5 Out-of-action players

1. A player with no remaining action markers MUST NOT select actions.
2. Whether such a player is described as “out of the game” MUST NOT remove their components, score, route, buses, passengers, or relevance to terminal scoring.
3. The player remains in final ranking.
4. The lifecycle must still support the rule that the game ends only at round end when only one player has markers remaining.

### 8.6 Abandonment

Because abandonment is not an official game rule:

- a player leaving MUST NOT silently alter rules state;
- the product MUST apply a declared policy: pause, replacement, forfeit, or whole-session abandonment;
- an abandoned session MUST retain its final authoritative state and terminal reason;
- abandonment MUST be distinct from an official completed game for statistics unless product policy says otherwise.

### 8.7 Restart

1. Restart MUST create a new game lifecycle or reset the existing session only through an explicit, authorized operation.
2. Restart MUST clear all board progress and restore the legal initial component inventory.
3. The product MUST declare whether the same seats, colors, setup seed, and starting player are retained.
4. A restart MUST NOT overwrite the prior completed/abandoned audit history.

### 8.8 Undo

Undo is not an official rule.

- If unsupported, the API and UI MUST clearly reject or omit undo.
- If supported, the policy MUST specify authorization, voting, time window, and whether information-changing actions can be reversed.
- Because *Bus* has no hidden draws, information leakage is limited, but undo can still reveal intentions and MUST not be assumed harmless.
- An undo MUST create a new version and audit entry rather than erase history.
- No undo SHOULD be permitted after session completion unless the session is explicitly reopened under administrative policy.

---

## 9. Invalid, duplicate, stale, and repeated requests

1. An invalid request MUST NOT partially mutate state.
2. A request from the wrong player or wrong phase MUST return a client-visible error and current state version.
3. A stale request MUST return a conflict response with enough metadata to refresh.
4. An idempotent retry with the same key and same semantic request MUST return the original accepted result without applying the action again.
5. Reuse of an idempotency key with different semantic content MUST be rejected.
6. A duplicate non-idempotent action that is no longer legal MUST be rejected as stale or already resolved.
7. Validation MUST use semantic content, current actor, current phase, and current version. A move ID alone MUST never authorize a mutation.
8. Validation errors SHOULD identify the invalid field and a stable error code but MUST NOT expose server internals.

Recommended client-visible error codes:

```text
GAME_NOT_FOUND
GAME_NOT_ACTIVE
NOT_AUTHORIZED
NOT_CURRENT_ACTOR
WRONG_PHASE
STALE_STATE
ACTION_NOT_LEGAL
ACTION_SPACE_OCCUPIED
PASS_NOT_YET_ALLOWED
PLAYER_ALREADY_PASSED
NO_ACTION_MARKERS
INVALID_ROUTE_EXTENSION
PARALLEL_ROUTE_FORBIDDEN
INVALID_BUILDING_ZONE
BUILDING_LOCATION_OCCUPIED
PASSENGER_NOT_IN_SUPPLY
INVALID_PASSENGER_SOURCE
INVALID_DESTINATION
DESTINATION_OCCUPIED
PASSENGER_ALREADY_SATISFIED
BUS_CAPACITY_EXHAUSTED
MANDATORY_ACTION_REMAINS
TIME_STONE_UNAVAILABLE
ACTION_ALREADY_RESOLVED
IDEMPOTENCY_KEY_REUSED
GAME_ALREADY_COMPLETE
```

---

## 10. Serialization and player views

### 10.1 View contract

1. Internal state and client view MUST be separate contracts.
2. The view MUST include only fields explicitly allowed for that viewer type.
3. Serialization MUST fail closed. A newly added internal field MUST remain absent from all public views until intentionally mapped.
4. Although standard *Bus* has no hidden game information, authorization, tokens, internal audit data, random seeds, and administrative metadata MUST remain protected.
5. Spectator visibility and delay MUST be controlled by session policy.

### 10.2 Required active-game view

The player view MUST provide:

- session and rules identity;
- state version;
- round and phase labels;
- current actor and starting player;
- all players in seat order;
- scores, score-stack order, bus counts, action-marker counts, and time stones;
- full city map state;
- route ownership and route ends;
- building sites, zones, types, and occupancy;
- passenger locations and satisfaction state;
- clock position and remaining stones;
- action board, occupied slots, and resolution order;
- pending mandatory count;
- legal action affordances for the viewing player when that player is the actor;
- terminal-warning state if a round-end condition is pending.

### 10.3 Coordinate and component metadata

1. Each crossing, street, building location, station, action space, and score position MUST have a stable semantic ID.
2. Display coordinates MUST be separate from topology.
3. The view MUST provide labels and accessibility names for components.
4. Route ownership MUST NOT rely on color alone; it MUST also be represented by text, pattern, icon, or accessible metadata.
5. Passenger/building occupancy MUST be distinguishable without relying solely on imagery.

### 10.4 Legal-action affordances

1. Affordances MUST be derived from the current authoritative state version.
2. The UI SHOULD highlight legal action types, route edges, station choices, building sites/types, and passenger destinations.
3. Client affordances MUST NOT be treated as proof of legality by the server.
4. When mandatory continuation exists, unrelated controls MUST be disabled or omitted.
5. The view MUST state how many placements or transports remain.

### 10.5 Empty, loading, error, and stale views

- **Loading:** show session identity when known and prevent duplicate submission.
- **Empty/lobby:** show required seats and start eligibility.
- **Error:** preserve the latest confirmed state and display a recoverable message.
- **Stale:** disable old controls, fetch the latest version, and explain that the game advanced.
- **Disconnected:** retain the last confirmed view, label it potentially out of date, and attempt recovery under product policy.
- **Terminal:** disable gameplay controls and display final scoring details, ranking, tie-break resolution, and terminal reason.

---

## 11. Configuration requirements

### 11.1 Required identity and limits

```text
gameId: bus
canonicalDisplayName: Bus
minimumPlayers: 3
maximumPlayers: 5
```

### 11.2 Required rules configuration

The configuration MUST define:

- rules edition and rules version;
- supported player counts;
- time-stone count by player count;
- 5-player Line Expansion bonus;
- component inventory;
- exact action order;
- action-space ordering and capacity;
- building types and clock sequence;
- map topology;
- stations and Central Park passenger start locations;
- building locations and zone values;
- route parallelism and route-end metadata needed to enforce the published map rules;
- score-track presentation and stack representation;
- all approved optional product rules, disabled by default unless officially part of the edition.

### 11.3 Exact phase names

Configuration phase names MUST match validator state names exactly. The canonical names SHOULD be:

```text
SETUP_BUILDINGS
SETUP_FIRST_ROUTE_SEGMENTS
SETUP_SECOND_ROUTE_SEGMENTS
ACTION_SELECTION
RESOLVE_LINE_EXPANSION
RESOLVE_BUSES
RESOLVE_PASSENGERS
RESOLVE_BUILDINGS
RESOLVE_CLOCK
RESOLVE_VRROOMM
RESOLVE_STARTING_PLAYER
ROUND_COMPLETION
GAME_OVER
```

User-facing labels MAY differ, but every label MUST map to one canonical phase.

### 11.4 Required panels

The default game presentation MUST include:

- city map;
- action board;
- clock and time stones;
- player status/score panel;
- current phase and actor panel;
- action/continuation panel;
- event history or recent-action summary;
- game-over summary.

### 11.5 Assets

Configuration MUST declare asset references and accessibility metadata for:

- board/map;
- player colors and line markers;
- action markers;
- buses;
- passengers;
- House, Office, and Pub buildings;
- clock states;
- time stones;
- Start-Bus;
- action icons.

Missing decorative assets MUST NOT prevent semantic game rendering. Missing topology or component identity data MUST prevent game activation.

### 11.6 Difficulty and AI labels

Difficulty labels MAY exist at the suite level, but they are not rules configuration and MUST NOT change legal game behavior. This document defines no AI requirements.

---

## 12. Frontend requirements

## 12.1 Create or select a game

**Flow:** A user selects *Bus*, chooses a supported player count and approved options, occupies or assigns seats, and starts when eligible.

**Success criteria:**

- unsupported player counts cannot be selected;
- rules edition and relevant options are visible before start;
- colors and seats are unique;
- start is unavailable until setup prerequisites are satisfied;
- the created session opens at the correct setup phase.

## 12.2 View initial state

The setup screen MUST show component allocations, starting player, clock at House, four initial passengers, empty action spaces, and the current setup actor. Bus setup MUST default to the minimum supported three-player count rather than an invalid two-player count. The initial API response and every refresh MUST include the legal moves for that setup actor. It MUST identify legal Zone 1 building sites during initial building placement, require the actor to choose a legal building type for the selected site, and visibly present an explicit confirmation before a selected move is submitted. Placed buildings MUST remain visible after setup, including opponent buildings, and MUST use the placing player's color. Legal action positions MUST use a bright, high-contrast dotted outline around the complete printed action position.

## 12.3 Select and preview an action

1. On the current player's selection turn, legal action categories MUST be distinguishable.
2. The next lettered position and any exclusivity constraint SHOULD be previewed.
3. The client SHOULD explain that an action marker is permanently spent.
4. Pass MUST remain unavailable until legal.
5. Submitting MUST disable repeat input until success or failure is known.

## 12.4 Resolve route placement

1. Legal route edges MUST be highlighted.
2. The selected route end MUST be apparent when multiple ends are available.
3. The UI MUST show remaining required placements.
4. Parallel-route exceptions and circle closure SHOULD provide concise explanatory text.
5. Illegal edges MUST not appear enabled, but server validation remains mandatory.

## 12.5 Resolve passenger placement

The UI MUST show both stations, passenger supply, required remaining placements, and the result of each placement. If supply is exhausted, the action MUST finish without requiring a meaningless click.

## 12.6 Resolve building placement

The UI MUST identify the currently unlocked zone, open sites, available building types, and remaining required placements. Sites in locked zones MUST be visibly unavailable with an accessible reason.

## 12.7 Resolve Clock

1. If a player owns the Clock action, the UI MUST present explicit **Stop time** and **Let time advance** choices.
2. The Stop option MUST display the one-point final penalty and remaining-stone consequence.
3. If stopping takes the last stone, the UI MUST warn that the game ends immediately.
4. If Clock was not selected, automatic advancement SHOULD be animated or announced but MUST not require input.

## 12.8 Resolve Vrrooomm!

1. The UI MUST identify movable passengers and legal empty destinations of the demanded type.
2. It MUST show remaining bus capacity and points gained in the current action.
3. After each move, legal affordances MUST refresh because occupancy changes.
4. The user MUST not be allowed to finish while another legal move is mandatory and bus capacity remains.
5. If no legal move remains, the action MUST advance automatically.

## 12.9 Opponent and system turns

- Non-acting players MUST see the current actor and pending action.
- Their gameplay controls MUST be disabled.
- Accepted actions MUST update the shared board consistently.
- Automated transitions, including unselected Clock advancement and action skipping, MUST be visible in history.

## 12.10 Errors and stale versions

- Recoverable validation errors MUST preserve the user's context where possible.
- A stale-version error MUST trigger a state refresh before further action.
- A rejected action MUST not display as committed.
- Network timeouts MUST permit safe retry using the same idempotency key.

## 12.11 Finish and restart

The game-over screen MUST show:

- raw scored points;
- time-stone penalties;
- adjusted scores;
- tie-break application;
- final ranked order and winner;
- terminal reason;
- restart/new-game options allowed by policy.

## 12.12 Accessibility

1. All actions MUST be operable with keyboard and assistive technology.
2. Focus order MUST follow setup, selection, and resolution flow.
3. Status changes MUST be announced through an appropriate live region.
4. Player identity, routes, and action markers MUST not rely on color alone.
5. Every board object MUST have a concise accessible name and state.
6. Route-edge selection MUST provide a non-pointer alternative, such as an ordered legal-move list.
7. Animations MUST respect reduced-motion preferences.
8. Required counts, scores, clock demand, occupied buildings, and terminal status MUST be available as text.

---

## 13. Persistence and API requirements

## 13.1 Session identity and authorization

1. Every request MUST identify the session and authenticated participant or authorized spectator/admin role.
2. A player MAY submit a game action only for their assigned player identity.
3. Authorization MUST be checked independently of client-supplied player ID.
4. Spectators MUST be read-only.
5. Administrative operations MUST be audited and distinct from ordinary game actions.

## 13.2 Endpoint contract

The product SHOULD expose equivalent operations to the following, regardless of transport style:

```text
POST   /games
GET    /games/{sessionId}
POST   /games/{sessionId}/actions
GET    /games/{sessionId}/history
POST   /games/{sessionId}/abandon
POST   /games/{sessionId}/restart
POST   /games/{sessionId}/undo-request   # only if enabled
```

The action endpoint MUST accept semantic action content rather than only an opaque move identifier.

### Create-game request

```json
{
  "gameId": "bus",
  "rulesEdition": "approved-edition-id",
  "playerSeats": [
    {"playerId": "player-1", "color": "color-id"}
  ],
  "options": {},
  "seed": "optional-authorized-seed"
}
```

### Action request envelope

```json
{
  "requestId": "client-generated-idempotency-key",
  "expectedVersion": 42,
  "action": {
    "type": "SEMANTIC_ACTION_TYPE",
    "parameters": {}
  }
}
```

### Successful action response

```json
{
  "requestId": "client-generated-idempotency-key",
  "accepted": true,
  "previousVersion": 42,
  "stateVersion": 43,
  "event": {},
  "view": {},
  "legalActions": []
}
```

### Error response

```json
{
  "requestId": "client-generated-idempotency-key",
  "accepted": false,
  "error": {
    "code": "STALE_STATE",
    "message": "The game has advanced. Refresh and try again.",
    "field": "expectedVersion"
  },
  "currentVersion": 43
}
```

## 13.3 HTTP behavior

- `200` or `201` MUST indicate successful retrieval/creation.
- Accepted action requests MAY return `200`.
- Malformed requests SHOULD return `400`.
- Unauthorized or forbidden requests SHOULD return `401` or `403`.
- Missing sessions SHOULD return `404`.
- Stale version or incompatible idempotency reuse SHOULD return `409`.
- Semantically illegal actions SHOULD return `422` unless the product standardizes all game-action conflicts on `409`.
- Server failures SHOULD return `5xx` without claiming that an uncommitted action succeeded.

## 13.4 Transaction and concurrency

1. Validation and mutation of one action MUST occur against one authoritative state version.
2. The transition, event/audit record, and new state version MUST commit atomically.
3. Concurrent requests against the same prior version MUST not both mutate the game.
4. At most one request may advance a given game version.
5. Automatic phase transitions MAY occur in the same transaction as the triggering action if all are deterministic and are reported in the response event sequence.
6. Long chains of automatic transitions MUST remain replayable and observable.

## 13.5 Recovery

1. A session MUST be recoverable after process restart from durable state or replayable event history.
2. Recovery MUST preserve current actor, phase, pending continuation, action slots, score-stack order, clock state, and terminal-warning flags.
3. Replaying accepted events MUST produce the same authoritative state.
4. Recovery MUST not repeat a previously committed action or automatic consequence.

## 13.6 Logging and sensitive data

Logs MAY contain session ID, request ID, actor ID, action type, version, validation result, and timing. Logs MUST NOT contain authentication secrets, session tokens, or unfiltered internal objects. Public game information MAY be logged under the product's retention policy, but personal identifiers MUST follow privacy requirements.

---

## 14. Non-AI acceptance requirements

## 14.1 Rules and setup tests

- A 3-player game uses 4 time stones; 4- and 5-player games use 5.
- Every player receives the correct initial components and one active bus.
- Clock starts at House.
- Four passengers begin at the prescribed Central Park roundabouts.
- Initial buildings are limited to Zone 1 and placed two per player clockwise.
- First line segments are placed clockwise; second segments are placed in reverse order.
- A session cannot enter Round 1 until setup is complete.

## 14.2 Selection tests

- Every player must select the minimum before passing.
- Pass is permanent for the round.
- Exclusive actions accept only one marker.
- Multi-space actions assign A, B, and subsequent positions without gaps.
- A player may select a multi-space action more than once.
- Action markers are removed from available supply immediately and from the game after the round.
- Out-of-turn, stale, duplicate, and illegal requests do not mutate state.

## 14.3 Resolution tests

- Actions resolve in the printed top-to-bottom order.
- Marker order within each action matches the action board.
- Line Expansion and Buildings exhibit reverse selection order.
- Passengers and Vrrooomm! exhibit forward selection order.
- Required counts use the current maximum bus value.
- The five-player Line Expansion bonus applies exactly once.
- Mandatory actions complete to the legal maximum.

## 14.4 Route tests

- Both route ends are recognized.
- Normal parallel placement is rejected.
- Each published parallel exception is accepted only when its conditions hold.
- Self-parallel placement is rejected.
- Illegal backtracking is rejected.
- Circle closure preserves the correct route-end state.
- The route remains one valid end-to-end traversal.
- Existing line markers cannot be removed.

## 14.5 Passenger and building tests

- Passengers can be split between stations.
- Passenger placement does not require station connection.
- Supply exhaustion ends mandatory placement at maximum possible completion.
- Buildings occupy only empty sites in the unlocked zone.
- Zone advancement occurs immediately after the prior zone fills.
- Filling the last site schedules round-end termination rather than immediate termination.

## 14.6 Clock tests

- An unselected Clock advances automatically.
- The Clock owner can advance without penalty.
- Stopping retains the current demand, transfers one stone, and produces a final-score penalty.
- Taking the last stone ends the game immediately.
- Later actions in the interrupted round do not resolve.

## 14.7 Vrrooomm! and scoring tests

- Only dissatisfied passengers are movable.
- Passenger source and empty demanded-type destination must both connect to the acting route.
- One bus moves no more than one passenger in an action.
- The player must move the maximum possible up to bus capacity.
- Every move scores exactly 1 point.
- Destination occupancy updates after each move.
- Multiple Vrrooomm! selections restore full bus capacity separately.
- Score-disc stack order updates correctly when players reach the same score.

## 14.8 Terminal and ranking tests

- All three official terminal conditions trigger at the correct timing.
- Time stones subtract from final score.
- More time stones wins the first official tie breaker among equal adjusted scores.
- Lower score disc wins the remaining tie breaker.
- Out-of-action players remain in final scoring.
- Terminal state cannot accept further game actions.

## 14.9 Persistence and isolation tests

- Every accepted transition survives restart.
- Pending forced continuations recover correctly.
- Events replay deterministically to the same state.
- Sessions do not share mutable board or component state.
- Two concurrent requests against one version cannot both commit.
- Idempotent retry returns the original result.
- Reusing an idempotency key for different content is rejected.

## 14.10 View and frontend tests

- Every phase and action renders with the correct actor and affordances.
- Public game information is visible to all authorized participants.
- Server-only fields never appear in player or spectator views.
- Route and player identity remain understandable without color.
- Legal route, station, building, Clock, and passenger choices are keyboard accessible.
- Loading, stale, error, disconnected, and terminal states are rendered.
- Mandatory continuation prevents unrelated submissions.
- Final view explains score, penalties, tie breakers, and end reason.

---

## 15. Requirements traceability matrix

| Requirement area | Primary rule source | Acceptance coverage |
|---|---|---|
| Components and base setup | Rulebook: Components, Setting Up | Setup tests |
| Initial buildings and lines | Rulebook: The First Buildings, The First Lines | Setup and route tests |
| Action selection | Rulebook: Choosing Actions | Selection tests |
| Resolution and maximum buses | Rulebook: Resolve Actions, Maximum Number of Buses | Resolution tests |
| Route legality | Rulebook: Line Expansion | Route tests |
| Buses | Rulebook: Buses | Resolution tests |
| Passenger placement | Rulebook: Passengers | Passenger tests |
| Building placement and zones | Rulebook: Buildings | Building and terminal tests |
| Clock | Rulebook: The Clock | Clock and terminal tests |
| Passenger transport and points | Rulebook: Vrrooomm! | Transport and scoring tests |
| Next starting player | Rulebook: Starting Player & The Next Round | Round lifecycle tests |
| Game end and tie breakers | Rulebook: End of the Game | Terminal and ranking tests |
| Five-player exception | Rulebook: Playing with 5 Players | Player-count tests |
| API, persistence, views, accessibility | Product requirements | API, recovery, security, and UI tests |

---

## 16. Unresolved questions requiring sign-off

No implementation should begin with implicit answers to the following.

### 16.1 Edition baseline

1. Is the target the 1999/2019 standard rules, the 2024 Complete Edition, or both?
2. If both, which differences are material to setup, board data, wording, or component inventory?
3. Must historical rulebook errata be supported as named compatibility modes, or only corrected rules?

### 16.2 Action markers near exhaustion

The rules require at least two actions each round but also say that a player with no markers is out. Approved product ruling: a player who begins a round with exactly one action marker may place that one marker and then becomes inactive for the remainder of the round.

This affects action selection and the round-end “only one player has markers” condition.

### 16.3 Exhausted personal bus supply

Approved product ruling: a player already owning all 5 buses MUST NOT select Buses. The action is absent from that player's legal action choices.

### 16.4 Component exhaustion

1. Can any building type's tile supply be exhausted before all building sites are filled under the physical component mix?
2. If a requested type is exhausted, must the player choose another available type?
3. If all building tiles are exhausted but legal sites remain, is this equivalent to no legal placement or a terminal condition?

### 16.5 Passenger satisfaction timing

The current implementation uses an automatic authoritative synchronization: immediately after building placement, passenger placement, or a clock change, satisfied passengers occupy matching empty buildings at their crossing. When the clock no longer matches a building, its passenger returns to that crossing. This keeps public state and Vrrooomm! legality synchronized without a separately submitted player action.

Rules-owner confirmation is still required before treating this timing choice as final.

### 16.6 Route geometry

Reported board corrections applied on 2026-09-23: added the missing `c2-c4`, `c4-c11`, `c9-c6`, `c13-c6`, `c23-c16`, `c25-c30`, `c28-c33`, `c33-c36`, `c33-c34`, `c20-c24`, and `c24-c21` streets; removed the invalid `c1-c6`, `c3-c9`, `c25-c27`, `c30-c32`, `c35-c36`, `c19-c22`, `c14-c20`, `c13-c15`, `c3-c6`, `c3-c2`, `c2-c5`, `c10-c8`, `c6-c10`, and `c4-c13` streets; and adjusted `c34` to its printed center.

1. Approve the remaining canonical machine-readable map topology and orientation for every crossing and street.
2. Confirm all remaining board-specific parallel-route cases and circle markers against the physical board.
3. Confirm whether setup's first shared street can create states that require special endpoint metadata.

### 16.7 Product policies

Explicitly approve:

- abandonment behavior;
- replacement of disconnected players;
- turn timers and timeout behavior;
- pause behavior;
- undo availability and authorization;
- spectator access and delay;
- restart semantics;
- event-history visibility;
- whether seeded setup is user-selectable;
- whether adjusted score is previewed during play;
- whether a session may mix human and automated participants;
- retention period for completed and abandoned sessions.

### 16.8 API conventions

Confirm:

- HTTP status convention for semantically illegal actions;
- idempotency-key lifetime;
- optimistic concurrency field name;
- whether automatic transition chains are returned as one event list or separate streamed events;
- whether action history is event-sourced or maintained as an audit adjunct to snapshots.

---

## 17. Sign-off checklist

### Rules owner

- [ ] Rules edition selected.
- [ ] Setup and player-count variations approved.
- [ ] Action-selection minimum with one remaining marker resolved.
- [ ] Route topology and parallel exceptions approved.
- [ ] Buses-at-component-limit behavior resolved.
- [ ] Passenger satisfaction timing approved.
- [ ] Score and all terminal/tie-break rules approved.

### Product owner

- [ ] Abandonment, replacement, timers, undo, restart, and spectator policies approved.
- [ ] Required views and history behavior approved.
- [ ] Accessibility requirements accepted.

### API/persistence owner

- [ ] State versioning, idempotency, and transaction behavior approved.
- [ ] Recovery and replay expectations approved.
- [ ] Authorization and logging boundaries approved.

### QA owner

- [ ] Every rule boundary maps to a deterministic test.
- [ ] Every phase transition has positive and negative coverage.
- [ ] Every terminal and tie-break path is covered.
- [ ] Session isolation, stale requests, duplicate requests, and recovery are covered.
- [ ] Every required frontend action and accessibility path is covered.

### Final gate

- [ ] All unresolved questions are answered or explicitly deferred behind a disabled feature flag.
- [ ] No hidden assumption remains about phase ownership, turn advancement, score timing, randomness, information visibility, terminal timing, undo, persistence, or client-visible state.

---

## 18. Sources

1. Cardboard Appendix, *Bus Rulebook* transcription: https://cardboardappendix.com/games/bus/rulebook/
2. BoardGameGeek, *Bus Rulebook* file page for the 2019 edition and discussion of the Buildings example inconsistency: https://boardgamegeek.com/filepage/191623/bus-rulebook
3. BoardGameGeek, *Bus: Complete Edition Rulebook* file page for the 2024 edition: https://boardgamegeek.com/filepage/278728/bus-complete-edition-rulebook
4. Published rules PDF mirror, *Bus Official Rules*: https://board-game-rules.com/wp-content/uploads/2025/01/bus_Official-Rules.pdf

> Product requirements concerning APIs, persistence, concurrency, authorization, error handling, accessibility, abandonment, restart, and undo are not claims from the board-game rules. They are suite-level requirements proposed for review and sign-off.
