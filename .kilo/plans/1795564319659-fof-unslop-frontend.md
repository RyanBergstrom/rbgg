# Friendly Command Move Validation and Execution Plan

## Context

`friendly_command` currently mixes board moves (`move_unit`, `place_vof`, `fire`, `infiltrate`) with a small set of command actions. The goal is to make every `actions.json` entry whose `phases` includes `friendly_command` available as a legal move, ignoring `move_type`, while keeping all execution server-authoritative.

## Decisions

- Every configured `friendly_command` action generates legal moves, even when `move_type` is null.
- Legal moves are fully targeted: one move per valid originator/recipient/target tuple.
- The frontend groups targeted moves by `action_id` and uses a compact target selector.
- Command cost is spent from the selected originator's `pool_by_hq`; `commands_pool` remains a derived aggregate.
- A failed attempt spends its Command; a successful attempt spends ammo or fire missions only when configured.
- `exhort` is generated only after a failed attempt and when an originator has at least 1 Command.
- `exhort` execution draws one extra Action card and re-evaluates the failed attempt.
- Originator eligibility, communication, LOS, recipient eligibility, and draw resolution are validated before a move is offered.
- `originator_hq_id` is required on command-action moves.
- No implicit actions are introduced; all command actions come from `actions.json`.

## Config Updates

The implementation agent should update only `friendly_command` actions in `api/configs/fof/fields_of_fire_actions.json` with structured fields:

- `originator_type`
- `recipient_type`
- `communication_required`
- `los_required`
- `draw_count`
- `success_icon`
- `miss_modifier`
- `ammo_type`
- `ammo_cost`
- `fire_mission_type`

Existing natural-language fields remain as documentation.

## Task List

1. Add an action-handler registry keyed by action `id` in `api/app/games/fields_of_fire/`.
2. Replace the `move_type`-filtered action loop in `get_legal_moves` with a loop over every action whose `phases` includes `friendly_command`.
3. For each action, enumerate valid originators using `originator_type` and `pool_by_hq`.
4. For each action, enumerate valid recipients and targets in its handler.
5. Enforce communication and LOS before generating a move.
6. Generate one targeted move per valid tuple, including all execution parameters and `originator_hq_id`.
7. Add `action_id` to every generated command move and use it as the frontend grouping key.
8. Update `validate_move` to dispatch by `action_id` to the action handler.
9. Update `_apply_move` to dispatch by `action_id` to the action handler.
10. Spend Command cost from the originator's `pool_by_hq` and update `commands_pool` as a derived sum.
11. Implement draw resolution using `draw_count` and `success_icon`.
12. On success, apply action effects and spend configured ammo or fire missions.
13. On failure, apply `miss_modifier` when configured and record `last_failed_attempt`.
14. Track `exhort_used` per failed attempt.
15. Generate `exhort` only when `last_failed_attempt` is set and an originator has at least 1 Command.
16. Execute `exhort` by drawing one extra Action card and re-evaluating the failed attempt.
17. Update `CommandPanel.svelte` to group targeted moves by `action_id` and provide a compact target selector.
18. Update frontend labels from action config `button_text`.
19. Add targeted tests for each friendly_command action handler.
20. Add negative tests for missing originator, insufficient Commands, invalid recipient, failed communication or LOS, and failed draws.
21. Add tests verifying Command spending, exhort gating, and ammo/fire-mission spending.

## Validation

- `cd api; python -m pytest tests/test_fields_of_fire.py tests/test_fof_turn_sequence.py`
- `cd web; npm run check`
- `cd web; npx vitest run tests/unit/play-page.test.ts`
- Browser check: load a FOF session, activate an HQ, open the command panel, verify grouped actions and target selection, then execute one successful and one failed action.

## Risks

- The action surface is large; per-action handlers need careful rule mapping.
- Config additions must stay aligned with handler expectations.
- Targeted move generation may produce many moves; UI grouping is required to keep it usable.
- Exhort state must reset correctly on each new attempt.

## Resolved Decisions

- Backend returns the full legal move set; frontend filters and groups by selected commander.
- Command actions require an explicit `originator_hq_id`; missing originators are rejected.
- Legal move generation includes every valid target tuple regardless of draw outcome.
- Draw-based actions spend Command on every attempt; ammo and fire missions are spent only on success.
- `commands_pool` remains a derived aggregate while spendability is per originator.
- `exhort` is only available after a failed attempt and requires a Command.
