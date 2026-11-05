"""Card play orchestration: event timing, ops, and card-zone transitions."""
from __future__ import annotations

from app.games.twilight_struggle.state_clone import fast_copy as deepcopy
import random
from typing import Any

from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.events import apply_event_effects, resolve_card_event
from app.games.twilight_struggle.operations import resolve_operations_action
from app.games.twilight_struggle.rules import check_victory_conditions
from app.games.twilight_struggle.space_race import attempt_space_race
from app.games.twilight_struggle.turns import record_action

FACTIONS = {"us", "ussr"}
# Card ids of the 'War' cards referenced by Flower Power (59).
WAR_CARD_IDS = {11, 13, 24, 36, 102}


def effective_operations_value(game_data: dict[str, Any], faction: str, card: dict[str, Any]) -> int:
    """Apply active turn-scoped operations modifiers to a card's base value."""
    value = card.get("operations", 0)
    if not isinstance(value, int) or value < 0:
        raise ValueError("card operations must be a non-negative integer")
    turn = game_data.get("turn", 1)
    events = game_data.get("persistent_events", {})
    containment = events.get("containment", {})
    if (
        card.get("id") != 25
        and faction == "us"
        and isinstance(containment, dict)
        and containment.get("faction") == "us"
        and containment.get("expires_turn") == turn
    ):
        value = min(4, value + 1)
    purge = events.get("red_scare_purge", {})
    if (
        isinstance(purge, dict)
        and purge.get("faction") == faction
        and purge.get("expires_turn") == turn
    ):
        value = max(1, value - 1)
    doctrine = events.get("brezhnev_doctrine", {})
    if (
        card.get("id") != 51
        and faction == "ussr"
        and isinstance(doctrine, dict)
        and doctrine.get("faction") == "ussr"
        and doctrine.get("expires_turn") == turn
    ):
        value = min(4, value + 1)
    if card.get("id") == 46 and faction == "ussr":
        value += 2
    return value


def blockade_discard_ids(game_data: dict[str, Any]) -> list[int]:
    """US may discard one non-scoring held card worth 3+ modified Ops (rules 7.4.2)."""
    return [
        card["id"] for card in game_data.get("hands", {}).get("us", [])
        if not card.get("scoring") and not card.get("special") and card.get("id") != 6
        and effective_operations_value(game_data, "us", card) >= 3
    ]


def _server_resolve_random_inputs(
    operations_action: dict[str, Any], rng: random.Random,
) -> dict[str, Any]:
    """Replace client dice only after any card event has resolved."""
    kind = operations_action.get("type")
    if kind == "coup":
        return {"type": "coup", "country": operations_action.get("country"), "die_roll": rng.randint(1, 6)}
    if kind == "realignment":
        targets = operations_action.get("targets")
        if not isinstance(targets, list) or any(not isinstance(target, dict) for target in targets):
            raise ValueError("realignment targets must be a list of objects")
        return {
            "type": "realignment",
            "targets": [
                {
                    "country": target.get("country"),
                    "us_roll": rng.randint(1, 6),
                    "ussr_roll": rng.randint(1, 6),
                }
                for target in targets
            ],
        }
    if kind == "influence":
        return {"type": "influence", "placements": deepcopy(operations_action.get("placements", []))}
    raise ValueError(f"Unsupported operations action: {kind!r}")


CHINA_CARD_ID = 6
CHINA_CARD_OPERATIONS = 4


def _play_china_card(
    game_data: dict[str, Any],
    faction: str,
    mode: str,
    *,
    operations_action: dict[str, Any] | None,
    country_data: dict[str, Any] | None,
    rng: random.Random | None,
) -> dict[str, Any]:
    """Play The China Card for Operations (4), then pass it to the opponent face-down.

    The card is not in a hand and is never discarded. It is only playable by its
    face-up owner. The +1 Ops Asia bonus is not modeled here. When the US plays it
    for Operations, any in-effect Formosan Resolution is cancelled.
    """
    if mode != "operations":
        raise ValueError("The China Card may only be played for Operations")
    if not isinstance(operations_action, dict):
        raise ValueError("operations_action is required when playing for operations")
    resolved_operations_action = (
        _server_resolve_random_inputs(operations_action, rng) if rng is not None else operations_action
    )
    result = deepcopy(game_data)
    ops = resolve_operations_action(
        result, faction, CHINA_CARD_OPERATIONS, resolved_operations_action, country_data or load_country_data(),
    )
    opponent = "ussr" if faction == "us" else "us"
    ops.setdefault("china_card", {})
    ops["china_card"] = {"owner": opponent, "face_up": False}
    if faction == "us":
        ops.get("persistent_events", {}).pop("formosan_resolution", None)
    ops = record_action(ops, faction)
    ops["current_player_faction"] = faction
    ops["current_player"] = ops.get("player_by_faction", {}).get(faction, faction)
    ops["last_card_play"] = {
        "card_id": CHINA_CARD_ID,
        "faction": faction,
        "mode": mode,
        "event_triggered": False,
        "operations_result": ops.get("last_ops_result"),
    }
    ops["terminal_result"] = ops.get("terminal_result")
    return ops


RESTRICTION_DISCARD_MIN_OPS = 2
RESTRICTION_CANCEL_MAX_ROLL = 4


def _spend_restricted_round(
    result: dict[str, Any], faction: str, card_id: int, mode: str, reason: str, roll: int | None,
) -> dict[str, Any]:
    """Consume the faction's action round without resolving the chosen card."""
    result = record_action(result, faction)
    result["current_player_faction"] = faction
    result["current_player"] = result.get("player_by_faction", {}).get(faction, faction)
    result["last_card_play"] = {
        "card_id": card_id,
        "faction": faction,
        "mode": mode,
        "event_triggered": False,
        "operations_result": None,
        "restriction": {"reason": reason, "roll": roll},
    }
    result["terminal_result"] = None
    return result


def _apply_action_restriction(
    game_data: dict[str, Any],
    faction: str,
    card_id: int,
    mode: str,
    discard_card_id: int | None,
    rng: random.Random | None,
) -> tuple[dict[str, Any], bool]:
    """Gate a non-scoring play while an action restriction (Quagmire/Bear Trap) is active.

    Returns ``(state, proceed)``. ``proceed=False`` means the action round was
    spent without playing the chosen card: either the d6 roll failed or no
    eligible discard existed (which also limits the faction to scoring cards).
    On success the discard is spent, the restriction is cleared, and the card
    proceeds normally.
    """
    persistent = game_data.get("persistent_events") or {}
    restriction = persistent.get("action_restriction")
    if not isinstance(restriction, dict) or restriction.get("faction") != faction:
        return game_data, True
    hand = (game_data.get("hands") or {}).get(faction) or []
    card = next((c for c in hand if c.get("id") == card_id), None)
    if card is None or card.get("scoring"):
        return game_data, True
    if restriction.get("scoring_only"):
        raise ValueError("restricted faction may only play scoring cards this turn")
    if rng is None:
        raise ValueError("action restriction requires server RNG")

    result = deepcopy(game_data)
    hand = result["hands"][faction]
    eligible_ids = {
        c.get("id")
        for c in hand
        if c.get("id") != card_id
        and not c.get("scoring")
        and isinstance(c.get("operations"), int)
        and c["operations"] >= RESTRICTION_DISCARD_MIN_OPS
    }
    if not eligible_ids:
        result["persistent_events"]["action_restriction"]["scoring_only"] = True
        return _spend_restricted_round(result, faction, card_id, mode, "no_eligible_discard", None), False
    if discard_card_id not in eligible_ids:
        raise ValueError("restricted faction must discard an Operations card worth 2 or more")
    discard_index = next(i for i, c in enumerate(hand) if c.get("id") == discard_card_id)
    result.setdefault("discard_pile", []).append(hand.pop(discard_index))
    roll = rng.randint(1, 6)
    if roll <= RESTRICTION_CANCEL_MAX_ROLL:
        del result["persistent_events"]["action_restriction"]
        return result, True
    return _spend_restricted_round(result, faction, card_id, mode, "failed_roll", roll), False


def _apply_we_will_bury_you_penalty(
    game_data: dict[str, Any],
    faction: str,
    card_id: int,
    mode: str,
    country_data: dict[str, Any] | None,
) -> dict[str, Any]:
    """USSR gains 3 VP before the US's next card play unless UN Intervention (32) is played as an Event."""
    pending = (game_data.get("persistent_events") or {}).get("we_will_bury_you")
    if faction != "us" or not isinstance(pending, dict):
        return game_data
    if card_id == 32 and mode == "event":
        return game_data
    result = deepcopy(game_data)
    result["persistent_events"].pop("we_will_bury_you")
    return apply_event_effects(
        result, [{"type": "gain_vp", "faction": "ussr", "amount": 3}], country_data or load_country_data(),
    )


def resolve_kal_007_bonus_action(
    game_data: dict[str, Any],
    operations_action: dict[str, Any],
    *,
    country_data: dict[str, Any] | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Spend the US's KAL-007 (89) bonus: 4 Ops for influence or realignment, not coups.

    The bonus is turn-scoped and does not consume an action round. It is cleared
    on use and rejected if it is missing, belongs to another turn, or is a coup.
    """
    persistent = game_data.get("persistent_events") or {}
    bonus = persistent.get("kal_007_bonus")
    turn = game_data.get("turn", 1)
    if not isinstance(bonus, dict) or bonus.get("faction") != "us" or bonus.get("expires_turn") != turn:
        raise ValueError("No active KAL-007 bonus for the US this turn")
    if not isinstance(operations_action, dict) or operations_action.get("type") not in {"influence", "realignment"}:
        raise ValueError("KAL-007 bonus allows only influence placement or realignment")
    if rng is None:
        raise ValueError("KAL-007 bonus requires server RNG")
    resolved = _server_resolve_random_inputs(operations_action, rng)
    result = deepcopy(game_data)
    ops = resolve_operations_action(result, "us", bonus.get("operations", 4), resolved, country_data or load_country_data())
    ops.get("persistent_events", {}).pop("kal_007_bonus", None)
    ops["last_bonus_action"] = {"card_id": 89, "faction": "us", "type": operations_action["type"]}
    return ops


def _play_space_race_card(
    game_data: dict[str, Any],
    faction: str,
    card: dict[str, Any],
    card_index: int,
    rng: random.Random | None,
) -> dict[str, Any]:
    """Discard a held card in a Space Race attempt (rules 6.4). The card's event never occurs (6.4.5)."""
    if rng is None:
        raise ValueError("Space Race attempt requires server RNG")
    if card.get("scoring"):
        raise ValueError("scoring cards cannot be used for the Space Race")
    result = deepcopy(game_data)
    result["hands"][faction].pop(card_index)
    outcome = attempt_space_race(result, faction, effective_operations_value(result, faction, card), rng)
    terminal = outcome.pop("terminal_result")
    result.setdefault("discard_pile", []).append(card)
    result = record_action(result, faction)
    result["current_player_faction"] = faction
    result["current_player"] = result.get("player_by_faction", {}).get(faction, faction)
    result["last_card_play"] = {
        "card_id": card["id"],
        "faction": faction,
        "mode": "operations",
        "event_triggered": False,
        "operations_result": result.get("last_ops_result"),
    }
    result["terminal_result"] = terminal
    return result


def play_card_action(
    game_data: dict[str, Any],
    faction: str,
    card_id: int,
    mode: str,
    *,
    operations_action: dict[str, Any] | None = None,
    trigger_own_event: bool = False,
    country_data: dict[str, Any] | None = None,
    rng: random.Random | None = None,
    chosen_defcon: int | None = None,
    event_choices: dict[str, Any] | None = None,
    restriction_discard_id: int | None = None,
) -> dict[str, Any]:
    """Play one held card as an event or operations, atomically.

    For Ops, mandatory opponent/both events resolve before the chosen ops
    action. Unsupported events abort without changing the caller's state.
    Dice are embedded in ``operations_action`` only as an internal injectable
    input; API callers must use server-generated RNG values.
    """
    if faction not in FACTIONS:
        raise ValueError(f"Unknown faction: {faction}")
    if mode not in {"event", "operations"}:
        raise ValueError("mode must be event or operations")
    if not isinstance(card_id, int):
        raise ValueError("card_id must be an integer")
    game_data = _apply_we_will_bury_you_penalty(game_data, faction, card_id, mode, country_data)
    if game_data.get("terminal_result") is not None:
        return game_data
    game_data, proceed = _apply_action_restriction(
        game_data, faction, card_id, mode, restriction_discard_id, rng,
    )
    if not proceed:
        return game_data
    original_hands = game_data.get("hands")
    if not isinstance(original_hands, dict) or not isinstance(original_hands.get(faction), list):
        raise ValueError("game data is missing faction hands")
    hand = original_hands[faction]
    card_index = next((i for i, card in enumerate(hand) if card.get("id") == card_id), None)
    china = game_data.get("china_card") or {}
    if (
        card_index is None
        and card_id == CHINA_CARD_ID
        and china.get("owner") == faction
        and china.get("face_up")
    ):
        return _play_china_card(
            game_data, faction, mode,
            operations_action=operations_action, country_data=country_data, rng=rng,
        )
    if card_index is None:
        raise ValueError(f"Card {card_id} is not in the {faction} hand")
    card = hand[card_index]
    if card.get("scoring") and mode != "event":
        raise ValueError("scoring cards must be played as events")
    if mode == "operations" and not isinstance(operations_action, dict):
        raise ValueError("operations_action is required when playing for operations")
    if mode == "operations" and operations_action.get("type") == "space_race":
        return _play_space_race_card(game_data, faction, card, card_index, rng)

    result = deepcopy(game_data)
    result["hands"][faction].pop(card_index)
    event = resolve_card_event(
        result,
        card,
        faction,
        mode=mode,
        trigger_own_event=trigger_own_event,
        country_data=country_data,
        rng=rng,
        chosen_defcon=chosen_defcon,
        event_choices=event_choices,
    )
    result = event["game_data"]
    terminal = event.get("terminal_result")
    if mode == "operations" and terminal is None and not event.get("ops_skipped"):
        resolved_operations_action = (
            _server_resolve_random_inputs(operations_action or {}, rng)
            if rng is not None
            else operations_action or {}
        )
        ops = resolve_operations_action(
            result,
            faction,
            effective_operations_value(
                result,
                faction,
                card,
            ),
            resolved_operations_action,
            country_data,
        )
        result = ops
        terminal = ops.get("terminal_result")

    if event.get("card_relocated") or event.get("card_in_play"):
        pass  # The card was exchanged into the opponent's hand, or stays in play in front of its player.
    elif card.get("event_removed") and event["event_triggered"]:
        result.setdefault("removed_cards", []).append(card)
    else:
        result.setdefault("discard_pile", []).append(card)
    result = record_action(result, faction)
    result["current_player_faction"] = faction
    result["current_player"] = result.get("player_by_faction", {}).get(faction, faction)
    result["last_card_play"] = {
        "card_id": card_id,
        "faction": faction,
        "mode": mode,
        "event_triggered": event["event_triggered"],
        "operations_result": result.get("last_ops_result") if mode == "operations" else None,
    }
    # Flower Power (59): each US-played War card gives USSR 2 VP while it is in effect.
    # Space Race already returned through its exempt path above.
    if (
        faction == "us"
        and card_id in WAR_CARD_IDS
        and terminal is None
        and result.get("persistent_events", {}).get("flower_power")
    ):
        result = apply_event_effects(result, [{"type": "gain_vp", "faction": "ussr", "amount": 2}], country_data or load_country_data())
    result["terminal_result"] = terminal or result.get("terminal_result") or check_victory_conditions(
        result["tracks"].get("victory_points", 0), result["tracks"].get("defcon", 5), faction,
    )
    return result
