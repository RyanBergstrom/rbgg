# Twilight Struggle — Standard Base Game Requirements

**Status:** User-confirmed scope and primary source; requirements draft, not rules sign-off. Primary source: supplied 2nd Edition PDF; [The Complete Card List v1.4](The%20Complete%20Card%20List%20v1.4.pdf) is a secondary card-effect reference. This paraphrases rules for engineering requirements and does not reproduce card/rule text. Source bundle observations are in [source-inventory.md](source-inventory.md). Optional rules, tournament rules, variants, and scenarios are out of scope.

## 1. Objective and terminal conditions

Track net VP. A player reaching +20/-20 VP wins immediately when the current event/scoring resolution finishes applying its awards. Europe Control wins when Europe Scoring is played and during final scoring. Reaching DEFCON 1 by an action causes the phasing player to lose immediately. Otherwise, after Turn 10, score every region under final-scoring rules; the higher total wins and equal totals draw. During final scoring, 20 VP alone does not trigger automatic victory, while Europe Control still does. (Rules §§8.2, 10.3; pp. 9, 11.)

## 2. Setup and turn structure

Standard setup: shuffle Early War deck and deal 8 cards per player; China Card face up with USSR. Place starting influence as specified in §3 (p. 4): USSR 15 total (Syria 1, Iraq 1, North Korea 3, East Germany 3, Finland 1, 6 in Eastern Europe); US 25 total (Canada 2, Iran 1, Israel 1, Japan 1, Australia 4, Philippines 1, South Korea 1, Panama 1, South Africa 1, UK 5, 7 in Western Europe). Both space-race markers start before the track, military operations at zero, Turn 1, DEFCON 5, VP at zero.

Each turn: DEFCON improves by 1 if below 5; deal each player to hand limit; resolve simultaneous headline choices; take alternating action rounds (USSR first); check military operations and reset; return the China Card face up if it was passed; advance turn. Turn 10 is followed by final scoring. (Rules §4.5; pp. 4–5.) Turns 1–3 use six action rounds per player and 8-card hand limits; Turns 4–10 use seven and 9. Mid War cards enter at Turn 4; Late War cards enter at Turn 8. Scoring cards cannot be held. China Card is not part of the hand limit. New-era cards are shuffled into the draw pile without adding prior discards; when a deck is exhausted otherwise, reshuffle discard as prescribed. Asterisked events are removed only when the event is actually played/resolved according to the rules.

Headline selection is secret then revealed simultaneously. Resolve higher operations value first; ties go to US. Scoring cards have value zero and resolve after other headlines; if both headline cards score, US scoring resolves first. China cannot be headlined. Headline card events resolve as events.

## 3. State and visibility

- Public authoritative state: faction/actor, turn/phase/action-round, country influence, VP, DEFCON, military operations, space race, China Card ownership/face, public discards/removals, deck counts, persistent event flags, and terminal status.
- Private: each player's hand and unrevealed headline selection; serialize only for the entitled seat.
- Server-only: future deck order, RNG state, and unrevealed random outcomes.
- Pending state: selected card and event/operation mode; target/roll resolution; multi-choice card effect; operation count; turn/round continuation.
- Persist every authoritative transition through shared session services. Validator owns phase, actor, score and terminal changes. Never expose the opponent hand or future deck order through serializer, logs, or AI observations.

Country graph requires canonical country IDs, region membership, stability, battleground flag, superpower adjacency, and adjacency edges. Region classifications follow §2.1 (p. 2), including the special overlaps noted in requirements inventory. Do not infer adjacency from proximity. Verify all graph data against the board and rules before use.

## 4. Atomic action families

1. Headline: privately select a permitted card, reveal both, resolve in rules order; process event choice and continuation.
2. Action round: play an eligible hand/China card; select event or operations where permitted; resolve the required event before/after operations as chosen and according to event-specific timing.
3. Influence: spend operations to place markers in legally eligible connected countries, applying enemy-control cost and the start-of-round adjacency condition and its explicit event exception.
4. Realignment: select an eligible country, roll for both sides, compute modifiers and remove influence by roll difference; ties remove none.
5. Coup: select eligible country with opponent influence, roll and apply operations/stability formula, remove opponent influence and place any permitted friendly influence; battleground coups lower DEFCON and count toward military operations.
6. Space race: spend a card meeting the next-box operation threshold, roll within required range, advance at most the allowed frequency and resolve reward/first-entry benefit; event does not trigger.
7. Card/event choice: resolve card-specific preconditions, state changes, cancellations, persistent effects, removal, and choices. Full effects are a separate verified card catalog; unknown effects block release.
8. Turn maintenance: military-operation shortfall scoring, DEFCON/turn progression, deal/reshuffle, era insertion, China Card timing, and terminal checks.
9. Regional scoring: calculate Presence/Domination/Control, battleground and opposing-superpower-adjacency awards; Southeast Asia scoring is separate during its card and folded into Asia at final scoring.

For every action the implementation must test preconditions, semantic request validation, atomic mutation, actor/phase continuation, RNG advancement, response serialization, and invalid-action rejection. Dice and shuffles must use persisted deterministic RNG state.

## 5. Country and card data gates

The VASSAL XML identifies 85 named country/bloc spaces and coordinates. Influence-piece traits supply stability, region, and battleground values for 84 spaces; China has no such trait in the extracted setup data. The user confirmed these country values and region assignments as correct, including Canada's Europe membership. One VASSAL setup stack has a mismatched `location` attribute, so the extractor keys traits from the stack name. The accepted-value review draft is [country-map-draft.json](country-map-draft.json). The user-authored [countryreference.md](countryreference.md) is the editable source for country attributes and adjacency; [country_reference.py](tools/country_reference.py) loads the table, normalizes aliases, and symmetrizes country edges. The larger [biggermap.jpg](biggermap.jpg) is reference-only and does not change the selected game map/artwork. The separate visual candidate file is review evidence, not the runtime source. This keeps future corrections configurable, while graph invariants and rules-based audit remain required.

The user-reviewed [card-reference-validation.csv](card-reference-validation.csv) is the confirmed inventory/reference for cards included in this implementation. Entries marked validated are the available cards in scope; the entries not validated are promotional cards not owned/provided for this implementation and are excluded. Keep source-text confirmation distinct from software implementation: a validated row confirms the card reference, not that its behavior is implemented. Continue to track handlers and rule-derived tests separately; never represent an unimplemented event as a successful no-op. The VASSAL XML's card slots are metadata/layout evidence only.

## 6. Blocking sign-off register

| ID | Question / requirement | Status | Evidence needed |
|---|---|---|---|
| TS-REQ-001 | Primary rules authority | Approved: supplied 2nd Edition PDF | Record any encountered conflict; external rulings are not silently incorporated. |
| TS-REQ-002 | Product scope | Approved: standard base game; optional/tournament/variants/scenarios excluded | Tests/config enforce selected card eras and ten-turn game. |
| TS-REQ-003 | Supplied asset permission | User confirmed license for this app | Preserve provenance; permission scope limited to this app. |
| TS-REQ-004 | Country graph and attributes | User-confirmed in `countryreference.md`; loader/graph tests pass | Preserve the confirmed reference as the editable runtime source; reopen only if a rules discrepancy is found. |
| TS-REQ-005 | Card reference and event behavior | Reference inventory confirmed by user in `card-reference-validation.csv`; implementation open/blocking | Implement and test every validated/in-scope card effect, timing, choice, persistent interaction, and removal rule. Exclude unvalidated promotional cards not provided for this implementation. Track implementation separately from the CSV's reference-validation status. |
| TS-REQ-006 | Setup, deal, era insertion, reshuffle, China timing | Open/blocking until encoded/tests | Rule-cited deterministic setup/deal lifecycle tests. |
| TS-REQ-007 | Special event interactions and event exceptions | Open/blocking | Per-card fixtures, including persistent/cancelled/forced discard behavior. |
| TS-REQ-008 | Privacy and human interaction flow | Open | Two-perspective serializer tests and end-to-end browser game. |
| TS-REQ-009 | End/score conditions | Open until tested exhaustively | Fixtures for VP, DEFCON, Europe control, final scoring, tie. |

## 7. Playable-game acceptance

Do not begin RL implementation until: the graph and every card effect are verified; every action/phase/round/score/terminal path has rules-derived tests; seeded randomness and state immutability/persistence are verified; both private views fail closed; shared registry/config/routes work; humans can complete setup through endgame in the frontend; backend/frontend tests, build, and a full browser game pass. Unknown event behavior, even if rare, blocks a claim of complete base-game support.
