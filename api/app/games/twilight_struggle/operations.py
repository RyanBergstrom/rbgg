"""Atomic execution of the three board-targeting Twilight Struggle ops actions."""
from __future__ import annotations

from app.games.twilight_struggle.state_clone import fast_copy as deepcopy
from typing import Any

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.rules import (
    FACTIONS,
    apply_influence_operations,
    check_victory_conditions,
    controlled_by,
    resolve_coup,
    resolve_realignment,
)


def _nato_protected(game_data: dict[str, Any], country: Any, data: dict[str, Any]) -> bool:
    """True when NATO (21) blocks USSR coups/realignments in this US-controlled European country."""
    persistent = game_data.get("persistent_events") or {}
    if "nato" not in persistent or not isinstance(country, str):
        return False
    if country in (persistent.get("nato_cancelled_countries") or []):
        return False
    info = data.get("countries", {}).get(country)
    if not info or info.get("region") != "Europe":
        return False
    influences = (game_data.get("countries") or {}).get(country, {})
    return controlled_by(influences, info) == "us"


def resolve_operations_action(
    game_data: dict[str, Any],
    faction: str,
    operations: int,
    action: dict[str, Any],
    country_data: dict[str, Any] | None = None,
    *,
    free_event: bool = False,
) -> dict[str, Any]:
    """Apply an influence, coup, or realignment ops choice atomically.

    Random die results are supplied as part of the action, keeping this pure
    helper deterministic; the caller owns RNG generation and persistence.
    Unsupported action families fail closed until their rules are implemented.
    """
    if faction not in FACTIONS:
        raise ValueError(f"Unknown faction: {faction}")
    if not isinstance(operations, int) or operations < 1:
        raise ValueError("operations must be a positive integer")
    if not isinstance(action, dict):
        raise ValueError("action must be an object")
    data = country_data or load_country_data()
    result = deepcopy(game_data)
    board = result.get("countries")
    tracks = result.get("tracks")
    if not isinstance(board, dict) or not isinstance(tracks, dict):
        raise ValueError("game data must contain countries and tracks")
    defcon = tracks.get("defcon")
    opponent = "ussr" if faction == "us" else "us"
    kind = action.get("type")
    persistent = result.get("persistent_events") or {}
    turn = result.get("turn", 1)

    def active_this_turn(name: str) -> bool:
        flag = persistent.get(name)
        return isinstance(flag, dict) and flag.get("expires_turn") == turn

    if faction == "ussr" and kind in {"coup", "realignment"}:
        if kind == "coup":
            targets_to_check = [action.get("country")]
        else:
            raw_targets = action.get("targets")
            targets_to_check = [t.get("country") for t in raw_targets] if isinstance(raw_targets, list) else []
        for name in targets_to_check:
            if name == "Japan" and persistent.get("us_japan_pact"):
                raise ValueError(f"US/Japan Pact prevents USSR {kind} in Japan")
            if _nato_protected(result, name, data):
                raise ValueError(f"NATO prevents USSR {kind} in US-controlled Europe: {name!r}")
    if faction == "ussr" and kind == "coup" and (result.get("persistent_events") or {}).get("reformer"):
        info = data.get("countries", {}).get(action.get("country"))
        if info and info.get("region") == "Europe":
            raise ValueError("The Reformer prevents USSR coups in Europe")

    if kind == "influence":
        if faction == "ussr" and active_this_turn("chernobyl"):
            region = persistent["chernobyl"].get("region")
            for placement in action.get("placements", []):
                info = data["countries"].get(placement.get("country"), {})
                if info.get("region") == region:
                    raise ValueError(f"Chernobyl prevents USSR Ops influence placement in {region}")
        outcome = apply_influence_operations(
            faction, operations, action.get("placements", []), board, data
        )
        result["countries"] = outcome["board"]
        result["operations_spent"] = outcome["operations_spent"]
        result["operations_remaining"] = outcome["operations_remaining"]
    elif kind == "coup":
        salt = (result.get("persistent_events") or {}).get("salt_negotiations")
        die_modifier = (
            -1
            if isinstance(salt, dict) and salt.get("expires_turn") == result.get("turn", 1)
            else 0
        )
        squads = (result.get("persistent_events") or {}).get("latin_american_death_squads")
        target_info = data["countries"].get(action.get("country"), {})
        if (
            isinstance(squads, dict)
            and squads.get("expires_turn") == result.get("turn", 1)
            and squads.get("faction") in FACTIONS
            and target_info.get("region") in {"Central America", "South America"}
        ):
            die_modifier += 1 if squads["faction"] == faction else -1
        outcome = resolve_coup(
            faction,
            action.get("country"),
            operations,
            action.get("die_roll"),
            board,
            data,
            5 if free_event else defcon,
            die_modifier=die_modifier,
        )
        crisis = (result.get("persistent_events") or {}).get("cuban_missile_crisis")
        if (
            isinstance(crisis, dict)
            and crisis.get("expires_turn") == result.get("turn", 1)
            and crisis.get("faction") == faction
        ):
            # Card 40: the restricted coup-maker loses, including event-granted coups.
            # Validate the target above, but nuclear war preempts the coup's influence changes.
            tracks["defcon"] = 1
            result["terminal_result"] = {"winner": opponent, "reason": "cuban_missile_crisis"}
            result["last_ops_result"] = {"type": "coup", "country": action.get("country"), "cancelled": True}
            return result
        result["countries"] = outcome["board"]
        if free_event:
            outcome["military_operations_earned"] = 0
        samantha = (result.get("persistent_events") or {}).get("samantha_yuri")
        if faction == "us" and isinstance(samantha, dict) and samantha.get("expires_turn") == result.get("turn", 1):
            # Samantha and Yuri (109): USSR gains 1 VP per US coup attempt this turn (US-relative VP track).
            tracks["victory_points"] = tracks.get("victory_points", 0) - 1
        military = dict(tracks.get("military_operations", {}))
        military[faction] = min(5, military.get(faction, 0) + (0 if free_event else operations))
        tracks["military_operations"] = military
        if faction == "us" and active_this_turn("nuclear_subs"):
            # Card 41 suppresses DEFCON loss only, not geographic bans or card 40's crisis loss.
            outcome["defcon_loss"] = 0
        tracks["defcon"] = max(1, defcon - outcome["defcon_loss"])
        result["last_ops_result"] = {"type": "coup", **outcome}
        result["terminal_result"] = check_victory_conditions(
            tracks.get("victory_points", 0), tracks["defcon"], faction
        )
    elif kind == "realignment":
        targets = action.get("targets")
        if not isinstance(targets, list) or not 1 <= len(targets) <= operations:
            raise ValueError("realignment targets must be a non-empty list within the ops allowance")
        updated_board = {name: dict(influence) for name, influence in board.items()}
        outcomes = []
        for target in targets:
            if not isinstance(target, dict):
                raise ValueError("each realignment target must be an object")
            outcome = resolve_realignment(
                target.get("country"),
                target.get("us_roll"),
                target.get("ussr_roll"),
                updated_board,
                data,
                5 if free_event else defcon,
                us_die_modifier=-1 if active_this_turn("iran_contra_scandal") else 0,
            )
            updated_board = outcome["board"]
            outcomes.append(outcome)
        result["countries"] = updated_board
        result["operations_spent"] = len(targets)
        result["operations_remaining"] = operations - len(targets)
        result["last_ops_result"] = {"type": "realignment", "attempts": outcomes}
    else:
        raise ValueError(f"Unsupported operations action: {kind!r}")

    result["tracks"] = tracks
    return result
