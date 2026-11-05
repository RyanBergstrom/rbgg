"""Inline optional follow-ups for regional free actions and ordinary event-granted Ops.

The event choice `bonus_operations` uses the ordinary operations payload. Omission
declines the optional follow-up. Free regional coups/realignments bypass geographic
DEFCON bans, not battleground degradation, crisis loss, or other event restrictions.
"""
from __future__ import annotations

import random
from typing import Any

from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.operations import resolve_operations_action
from app.games.twilight_struggle.rules import check_victory_conditions


def resolve_event_bonus(
    state: dict[str, Any], handler: str, faction: str,
    choices: dict[str, Any], data: dict[str, Any], rng: random.Random | None,
    phasing_faction: str,
) -> dict[str, Any]:
    terminal = check_victory_conditions(
        state["tracks"].get("victory_points", 0), state["tracks"].get("defcon", 5), phasing_faction,
    )
    action = choices.get("bonus_operations")
    if terminal is not None or "bonus_operations" not in choices:
        return {"game_data": state, "event_triggered": True, "terminal_result": terminal}
    if not isinstance(action, dict):
        raise ValueError("bonus_operations must be an operations action object")
    if rng is None:
        raise ValueError("Event bonus requires server RNG")
    kind = action.get("type")
    free = handler in {"junta", "ortega_nicaragua", "tear_down_this_wall"}
    allowed_kinds = {"coup", "realignment"} if free else {"influence", "coup", "realignment"}
    if handler == "ortega_nicaragua":
        allowed_kinds = {"coup"}
    if handler == "glasnost":
        if not (state.get("persistent_events") or {}).get("reformer"):
            raise ValueError("Glasnost bonus requires The Reformer")
        allowed_kinds = {"influence", "realignment"}
    if kind not in allowed_kinds:
        raise ValueError(f"{handler} does not permit this bonus operations action")
    ids = {
        "junta": 47, "ortega_nicaragua": 91, "tear_down_this_wall": 96, "olympic_games": 20,
        "abm_treaty": 57, "glasnost": 90, "cia_created": 26, "lone_gunman": 62,
    }
    card = next(c for c in load_standard_card_catalog() if c["id"] == ids[handler])
    # Local import: actions imports events; bonus resolution is invoked only after imports complete.
    from app.games.twilight_struggle.actions import effective_operations_value, _server_resolve_random_inputs

    if handler == "olympic_games":
        card = {**card, "operations": 4}
    operations = effective_operations_value(state, faction, card)
    if kind == "realignment":
        targets = action.get("targets")
        limit = 1 if handler == "junta" else operations
        if not isinstance(targets, list) or not 1 <= len(targets) <= limit or any(not isinstance(t, dict) for t in targets):
            raise ValueError("Event realignment targets exceed its roll allowance")
        countries = [t.get("country") for t in targets]
    else:
        countries = [action.get("country")] if kind == "coup" else []
    for country in countries:
        info = data["countries"].get(country) if isinstance(country, str) else None
        if not info:
            raise ValueError("Event bonus requires a valid target country")
        if handler == "junta" and info["region"] not in {"Central America", "South America"}:
            raise ValueError("Junta bonus targets Central or South America")
        if handler == "ortega_nicaragua" and country not in data["adjacency"]["Nicaragua"]:
            raise ValueError("Ortega bonus targets a country adjacent to Nicaragua")
        if handler == "tear_down_this_wall" and info["region"] != "Europe":
            raise ValueError("Tear Down This Wall bonus targets Europe")
    resolved = _server_resolve_random_inputs(action, rng)
    updated = resolve_operations_action(state, faction, operations, resolved, data, free_event=free)
    terminal = updated.get("terminal_result")
    if terminal and terminal.get("reason") == "defcon_1":
        terminal = check_victory_conditions(updated["tracks"]["victory_points"], 1, phasing_faction)
        updated["terminal_result"] = terminal
    return {"game_data": updated, "event_triggered": True, "terminal_result": terminal}