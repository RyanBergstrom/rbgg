"""Action-round sequencing with server-owned dice and alternating factions."""
from __future__ import annotations

from typing import Any

from app.core.rng import create_rng, serialize_rng
from app.games.twilight_struggle.actions import _server_resolve_random_inputs, play_card_action
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import apply_event_effects
from app.games.twilight_struggle.rules import controlled_by
from app.games.twilight_struggle.turns import action_round_limit, faction_action_limit, faction_can_act


def _apply_norad_at_round_end(game_data: dict[str, Any], pre_defcon: Any, country_data: dict[str, Any]) -> dict[str, Any]:
    """NORAD (106): if the US controls Canada and DEFCON moved to 2 this round, the US adds 1 influence.

    Default resolution: the target is the alphabetically first country already holding US influence.
    """
    if "norad" not in (game_data.get("persistent_events") or {}):
        return game_data
    if game_data.get("tracks", {}).get("defcon") != 2 or pre_defcon == 2:
        return game_data
    countries = game_data.get("countries", {})
    if "Canada" not in country_data["countries"]:
        return game_data
    if controlled_by(countries.get("Canada", {}), country_data["countries"]["Canada"]) != "us":
        return game_data
    targets = sorted(name for name, inf in countries.items() if int((inf or {}).get("us", 0)) > 0)
    if not targets:
        return game_data
    return apply_event_effects(
        game_data,
        [{"type": "add_influence", "faction": "us", "country": targets[0], "amount": 1}],
        country_data,
    )

FACTIONS = ("us", "ussr")


def execute_action_round(
    state: dict[str, Any],
    faction: str,
    card_id: int,
    mode: str,
    *,
    operations_action: dict[str, Any] | None = None,
    trigger_own_event: bool = False,
    country_data: dict[str, Any] | None = None,
    chosen_defcon: int | None = None,
    event_choices: dict[str, Any] | None = None,
    restriction_discard_id: int | None = None,
) -> dict[str, Any]:
    """Play one action-round card and select the next faction/phase."""
    game_data = state.get("game_data")
    if not isinstance(game_data, dict) or game_data.get("current_phase") != "action_round":
        raise ValueError("action round is not active")
    if faction not in FACTIONS or game_data.get("current_player_faction") != faction:
        raise ValueError("action is not owned by the current faction")
    turn = game_data.get("turn")
    limits = {side: faction_action_limit(game_data, side) for side in FACTIONS}
    counts = game_data.get("actions_taken", {"us": 0, "ussr": 0})
    if counts.get(faction, 0) >= limits[faction]:
        # A faction at its limit may still play a held scoring card as an event; the turn cannot end otherwise.
        held = next((c for c in game_data.get("hands", {}).get(faction, []) if c.get("id") == card_id), None)
        if not (held is not None and held.get("scoring") and mode == "event"):
            raise ValueError(f"{faction} has completed all action rounds")

    rng = create_rng(state.get("rng_seed", 42), state.get("rng_state_json", "{}"))
    pre_defcon = game_data.get("tracks", {}).get("defcon")
    result_data = play_card_action(
        game_data,
        faction,
        card_id,
        mode,
        operations_action=operations_action,
        trigger_own_event=trigger_own_event,
        country_data=country_data or load_country_data(),
        rng=rng,
        chosen_defcon=chosen_defcon,
        event_choices=event_choices,
        restriction_discard_id=restriction_discard_id,
    )
    result = dict(state)
    result["game_data"] = result_data
    result["rng_state_json"] = serialize_rng(rng)
    result_data["rng_state_json"] = result["rng_state_json"]
    return complete_action_round(result, faction, pre_defcon, country_data)


def complete_action_round(
    state: dict[str, Any], faction: str, pre_defcon: int,
    country_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Advance only after a complete card resolution, including any interactive responses.

    The caller owns the result data and has already recorded the single card action.
    """
    result = dict(state)
    result_data = result["game_data"]
    if result_data.get("terminal_result") is not None:
        result_data["current_phase"] = "game_over"
        return result
    result_data = _apply_norad_at_round_end(result_data, pre_defcon, country_data or load_country_data())
    result["game_data"] = result_data

    new_counts = result_data["actions_taken"]
    # Scoring cards must be resolved before the turn can end, so a held scoring card keeps the round open.
    held_scoring = [
        (side, card) for side in FACTIONS for card in result_data.get("hands", {}).get(side, [])
        if card.get("scoring")
    ]
    open_factions = [side for side in FACTIONS if faction_can_act(result_data, side)]
    if not open_factions and not held_scoring:
        result_data["current_phase"] = "turn_end"
        result_data["current_player_faction"] = faction
        result_data["current_player"] = result_data.get("player_by_faction", {}).get(faction, faction)
        return result

    if not open_factions:
        # Both factions are at their limit; the next scoring card is played by its holder as an event.
        holder = held_scoring[0][0]
        result_data["current_phase"] = "action_round"
        result_data["current_player_faction"] = holder
        result_data["current_player"] = result_data.get("player_by_faction", {}).get(holder, holder)
        result_data["action_round"] = max(new_counts.values())
        return result

    # Ties go to USSR (existing alternation); a faction at its limit is skipped.
    next_faction = min(open_factions, key=lambda side: (new_counts.get(side, 0), side != "ussr"))
    result_data["current_phase"] = "action_round"
    result_data["current_player_faction"] = next_faction
    result_data["current_player"] = result_data.get("player_by_faction", {}).get(next_faction, next_faction)
    result_data["action_round"] = max(new_counts.values())
    return result
