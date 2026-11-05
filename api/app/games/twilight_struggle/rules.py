"""Reusable Twilight Struggle country-control and influence rule primitives."""
from __future__ import annotations

from typing import Any

from app.games.twilight_struggle.country_data import load_country_data

FACTIONS = ("us", "ussr")


def _validate_defcon_region_action(region: str, defcon: int) -> None:
    if not isinstance(defcon, int) or not 1 <= defcon <= 5:
        raise ValueError("defcon must be between 1 and 5")
    if defcon == 1:
        raise ValueError("No coup or realignment is permitted at DEFCON 1")
    restricted = {4: {"Europe"}, 3: {"Europe", "Asia"}, 2: {"Europe", "Asia", "Middle East"}}
    if region in restricted.get(defcon, set()):
        raise ValueError(f"Coup and realignment are prohibited in {region} at DEFCON {defcon}")


def control_margin(influences: dict[str, int], country: dict[str, Any]) -> int:
    """Return the control margin, or a non-positive value when uncontrolled.

    Control requires influence at least equal to stability and strictly more
    influence than the opponent. The returned positive margin is the amount
    over the control threshold, useful for tie-breaking and diagnostics.
    """
    stability = country.get("stability")
    if not isinstance(stability, int):
        return 0
    us = max(0, int(influences.get("us", 0)))
    ussr = max(0, int(influences.get("ussr", 0)))
    if us >= stability and us > ussr:
        return us - max(stability, ussr + 1) + 1
    if ussr >= stability and ussr > us:
        return ussr - max(stability, us + 1) + 1
    return 0


def controlled_by(influences: dict[str, int], country: dict[str, Any]) -> str | None:
    """Return the controlling faction, or None when neither side controls it."""
    stability = country.get("stability")
    if not isinstance(stability, int):
        return None
    us = max(0, int(influences.get("us", 0)))
    ussr = max(0, int(influences.get("ussr", 0)))
    if us >= stability and us > ussr:
        return "us"
    if ussr >= stability and ussr > us:
        return "ussr"
    return None


def influence_operation_cost(
    faction: str,
    influences: dict[str, int],
    country: dict[str, Any],
) -> int:
    """Cost one influence point: 2 ops in opponent-controlled space, else 1."""
    if faction not in FACTIONS:
        raise ValueError(f"Unknown faction: {faction}")
    controller = controlled_by(influences, country)
    return 2 if controller is not None and controller != faction else 1


def influence_points_from_operations(
    faction: str,
    operations: int,
    influences: dict[str, int],
    country: dict[str, Any],
) -> int:
    """Convert an operation allowance to legal point capacity in one country."""
    if operations < 0:
        raise ValueError("operations must be non-negative")
    return operations // influence_operation_cost(faction, influences, country)


def apply_influence_operations(
    faction: str,
    operations: int,
    placements: list[dict[str, Any]],
    board: dict[str, dict[str, int]],
    country_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Apply ordered influence placements atomically or raise without mutation.

    Each placement is ``{"country": name, "points": integer}``. Existing
    friendly influence in the target or an adjacent country establishes the
    required connection. Each point's cost is calculated against current
    control, so taking control within one operation changes later point costs.
    """
    if faction not in FACTIONS:
        raise ValueError(f"Unknown faction: {faction}")
    if operations < 0:
        raise ValueError("operations must be non-negative")
    data = country_data or load_country_data()
    graph = data["adjacency"]
    superpower_name = "United States" if faction == "us" else "USSR"
    superpower_adjacent = {
        edge[0] if edge[1] == superpower_name else edge[1]
        for edge in data["superpower_adjacency"]
        if superpower_name in edge
    }
    start_board = board
    updated = {name: dict(values) for name, values in board.items()}
    spent = 0
    for placement in placements:
        country_name = placement.get("country")
        points = placement.get("points")
        if country_name not in updated or country_name not in data["countries"]:
            raise ValueError(f"Unknown country: {country_name!r}")
        if not isinstance(points, int) or points <= 0:
            raise ValueError("Each placement must contain a positive integer point count")
        neighbors = graph.get(country_name, ())
        connected = (
            country_name in superpower_adjacent
            or start_board[country_name].get(faction, 0) > 0
            or any(
                start_board.get(neighbor, {}).get(faction, 0) > 0 for neighbor in neighbors
            )
        )
        if not connected:
            raise ValueError(f"{country_name} is not adjacent to friendly influence")
        country = data["countries"][country_name]
        for _ in range(points):
            spent += influence_operation_cost(faction, updated[country_name], country)
            if spent > operations:
                raise ValueError("Influence placements exceed available operations")
            updated[country_name][faction] = updated[country_name].get(faction, 0) + 1
    return {"board": updated, "operations_spent": spent, "operations_remaining": operations - spent}


def resolve_coup(
    faction: str,
    country_name: str,
    operations: int,
    die_roll: int,
    board: dict[str, dict[str, int]],
    country_data: dict[str, Any] | None = None,
    defcon: int = 5,
    die_modifier: int = 0,
) -> dict[str, Any]:
    """Resolve a coup using a supplied die result; caller persists RNG state.

    die_modifier is a turn-scoped adjustment (e.g. SALT Negotiations -1) applied
    to the raw die result; the raw die itself must still be 1-6.
    """
    if faction not in FACTIONS:
        raise ValueError(f"Unknown faction: {faction}")
    if not isinstance(operations, int) or operations < 1:
        raise ValueError("Coup operations must be a positive integer")
    if not isinstance(die_roll, int) or not 1 <= die_roll <= 6:
        raise ValueError("die_roll must be between 1 and 6")
    if not isinstance(die_modifier, int):
        raise ValueError("die_modifier must be an integer")
    data = country_data or load_country_data()
    if country_name not in data["countries"] or country_name not in board:
        raise ValueError(f"Unknown country: {country_name!r}")
    country = data["countries"][country_name]
    _validate_defcon_region_action(country["region"], defcon)
    stability = country["stability"]
    if not isinstance(stability, int):
        raise ValueError(f"{country_name} cannot be couped")
    opponent = "ussr" if faction == "us" else "us"
    if board[country_name].get(opponent, 0) <= 0:
        raise ValueError("A coup target must contain opponent influence")
    margin = die_roll + die_modifier + operations - 2 * stability
    updated = {name: dict(values) for name, values in board.items()}
    removed = min(updated[country_name][opponent], max(0, margin))
    updated[country_name][opponent] -= removed
    placed = max(0, margin - removed)
    updated[country_name][faction] = updated[country_name].get(faction, 0) + placed
    defcon_loss = int(bool(country["battleground"]))
    return {
        "board": updated,
        "die_roll": die_roll,
        "die_modifier": die_modifier,
        "coup_margin": margin,
        "opponent_influence_removed": removed,
        "friendly_influence_placed": placed,
        "defcon_loss": defcon_loss,
        "military_operations_earned": operations,
    }


def resolve_realignment(
    country_name: str,
    us_roll: int,
    ussr_roll: int,
    board: dict[str, dict[str, int]],
    country_data: dict[str, Any] | None = None,
    defcon: int = 5,
    *,
    us_die_modifier: int = 0,
) -> dict[str, Any]:
    """Resolve a realignment roll with control, adjacency, and superpower modifiers."""
    if not isinstance(us_roll, int) or not 1 <= us_roll <= 6:
        raise ValueError("us_roll must be between 1 and 6")
    if not isinstance(ussr_roll, int) or not 1 <= ussr_roll <= 6:
        raise ValueError("ussr_roll must be between 1 and 6")
    if not isinstance(us_die_modifier, int):
        raise ValueError("us_die_modifier must be an integer")
    data = country_data or load_country_data()
    if country_name not in data["countries"] or country_name not in board:
        raise ValueError(f"Unknown country: {country_name!r}")
    target = data["countries"][country_name]
    _validate_defcon_region_action(target["region"], defcon)
    modifiers = {"us": us_die_modifier, "ussr": 0}
    for faction, opponent in (("us", "ussr"), ("ussr", "us")):
        if board[country_name].get(faction, 0) > board[country_name].get(opponent, 0):
            modifiers[faction] += 1
        modifiers[faction] += sum(
            controlled_by(board.get(neighbor, {}), data["countries"][neighbor]) == faction
            for neighbor in data["adjacency"].get(country_name, ())
        )
        superpower = "United States" if faction == "us" else "USSR"
        if [country_name, superpower] in data["superpower_adjacency"] or [superpower, country_name] in data["superpower_adjacency"]:
            modifiers[faction] += 1

    totals = {"us": us_roll + modifiers["us"], "ussr": ussr_roll + modifiers["ussr"]}
    updated = {name: dict(values) for name, values in board.items()}
    difference = totals["us"] - totals["ussr"]
    removed = {"us": 0, "ussr": 0}
    if difference > 0:
        removed["ussr"] = min(updated[country_name].get("ussr", 0), difference)
        updated[country_name]["ussr"] -= removed["ussr"]
    elif difference < 0:
        removed["us"] = min(updated[country_name].get("us", 0), -difference)
        updated[country_name]["us"] -= removed["us"]
    return {
        "board": updated,
        "rolls": {"us": us_roll, "ussr": ussr_roll},
        "modifiers": modifiers,
        "modified_rolls": totals,
        "difference": difference,
        "influence_removed": removed,
    }


def award_military_operations_penalty(
    military_operations: dict[str, int],
    defcon: int,
) -> dict[str, Any]:
    """Apply end-of-turn military-operations shortfalls to the VP track."""
    if not isinstance(defcon, int) or not 1 <= defcon <= 5:
        raise ValueError("defcon must be between 1 and 5")
    shortfall = {}
    for faction in FACTIONS:
        completed = military_operations.get(faction, 0)
        if not isinstance(completed, int) or completed < 0:
            raise ValueError(f"Invalid military operations value for {faction}")
        shortfall[faction] = max(0, defcon - completed)
    vp_delta_us = shortfall["ussr"] - shortfall["us"]
    return {
        "shortfall": shortfall,
        "vp_delta_us": vp_delta_us,
        "reset_military_operations": {"us": 0, "ussr": 0},
    }


def check_victory_conditions(
    victory_points_us_relative: int,
    defcon: int,
    phasing_faction: str,
    europe_control: str | None = None,
    final_scoring: bool = False,
) -> dict[str, Any] | None:
    """Return a terminal result if an immediate or endgame condition is met."""
    if phasing_faction not in FACTIONS:
        raise ValueError(f"Unknown phasing faction: {phasing_faction}")
    if not isinstance(defcon, int) or not 1 <= defcon <= 5:
        raise ValueError("defcon must be between 1 and 5")
    if europe_control not in {None, "us", "ussr"}:
        raise ValueError(f"Invalid Europe controller: {europe_control!r}")
    if defcon == 1:
        loser = phasing_faction
        return {"winner": "ussr" if loser == "us" else "us", "reason": "defcon_1"}
    if europe_control is not None:
        return {"winner": europe_control, "reason": "europe_control"}
    if not final_scoring:
        if victory_points_us_relative >= 20:
            return {"winner": "us", "reason": "twenty_vp"}
        if victory_points_us_relative <= -20:
            return {"winner": "ussr", "reason": "twenty_vp"}
    return None
