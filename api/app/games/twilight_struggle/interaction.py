"""Opt-in staged event choices; legacy inline/RL paths remain available.

`play_card` with mode=event and interactive=True commits the card, then the
opponent owns `event_response`. A nonterminal boycott gives the sponsor an
`event_bonus` Ops-or-decline decision. The action round closes exactly once.
Blockade commits as a USSR event and pauses for the US discard-or-remove choice.
US Operations-mode Blockade requires an explicit event_order (rules 5.2) and
pauses for fresh, US-owned card_operations and event_response stages in that order.
Latin America Debt Crisis stages the US discard decision before USSR target choice.
Missile Envy stages the opponent's choice when highest-Ops cards are tied.
Aldrich Ames Remix stages the USSR's US-hand discard choice before US Ops.
Chernobyl stages the sponsor's region selection.
Iran-Iraq War stages the sponsor's choice of invader.
Headlines and other interactive cards are not covered.
"""
from __future__ import annotations

from typing import Any

from app.core.rng import create_rng, serialize_rng
from app.games.twilight_struggle.action_rounds import complete_action_round
from app.games.twilight_struggle.actions import (
    _apply_action_restriction, _apply_we_will_bury_you_penalty,
    _server_resolve_random_inputs, blockade_discard_ids, effective_operations_value,
)
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.event_bonus import resolve_event_bonus
from app.games.twilight_struggle.events import resolve_card_event
from app.games.twilight_struggle.operations import resolve_operations_action
from app.games.twilight_struggle.rules import check_victory_conditions
from app.games.twilight_struggle.space_race import held_card_decision_pending
from app.games.twilight_struggle.state_clone import fast_copy as deepcopy
from app.games.twilight_struggle.turns import faction_action_limit, record_action

INTERACTION_PHASES = {"event_response", "event_bonus", "card_operations"}


def _actor(gd: dict[str, Any], faction: str) -> None:
    gd["current_player_faction"] = faction
    gd["current_player"] = gd["player_by_faction"][faction]


def _debt_crisis_discard_ids(gd: dict[str, Any]) -> list[int]:
    """Match the card's established inline rule: printed 3+ Ops, not modified Ops."""
    return [
        card["id"] for card in gd.get("hands", {}).get("us", [])
        if type(card.get("id")) is int and type(card.get("operations")) is int
        and card["operations"] >= 3 and not card.get("scoring")
    ]


def _missile_envy_tied_ids(gd: dict[str, Any], sponsor: str) -> list[int]:
    opponent = "ussr" if sponsor == "us" else "us"
    eligible = [
        card for card in gd.get("hands", {}).get(opponent, [])
        if not card.get("scoring") and type(card.get("operations")) is int
        and type(card.get("id")) is int
    ]
    if not eligible:
        return []
    highest = max(card["operations"] for card in eligible)
    return [card["id"] for card in eligible if card["operations"] == highest]


def missile_envy_interactive_available(gd: dict[str, Any], sponsor: str) -> bool:
    return len(_missile_envy_tied_ids(gd, sponsor)) > 1


def _che_targets(gd: dict[str, Any], excluded: str | None = None) -> list[str]:
    data = load_country_data()
    board = gd.get("countries", {})
    return sorted(
        name for name, info in data["countries"].items()
        if name != excluded
        and info.get("region") in {"Central America", "South America", "Africa"}
        and not info.get("battleground")
        and board.get(name, {}).get("us", 0) > 0
    )


def che_interactive_available(gd: dict[str, Any]) -> bool:
    return bool(_che_targets(gd))


def _complete(state: dict[str, Any], sponsor: str, pre_defcon: int) -> dict[str, Any]:
    result = complete_action_round(state, sponsor, pre_defcon)
    gd = result["game_data"]
    if gd.get("current_phase") == "turn_end":
        held = held_card_decision_pending(gd)
        if held:
            gd["current_player"] = gd["player_by_faction"][held[0]]
    return result


def start_interactive_event(state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(state)
    gd = result["game_data"]
    sponsor = gd.get("faction_by_player", {}).get(move.get("player_id"))
    card_id = move.get("card_id")
    mode = move.get("mode")
    blockade_ops = card_id == 10 and sponsor == "us" and mode == "operations"
    missile_envy = card_id == 49 and mode == "event"
    chernobyl = card_id == 94 and mode == "event"
    iran_iraq = card_id == 102 and mode == "event"
    special_relationship = card_id == 105 and mode == "event"
    truman_doctrine = card_id == 19 and mode == "event"
    muslim_revolution = card_id == 56 and mode == "event"
    che = card_id == 107 and sponsor == "ussr" and mode == "event"
    aldrich_ames_ops = card_id == 98 and sponsor == "us" and mode == "operations"
    aldrich_ames_event = card_id == 98 and sponsor == "ussr" and mode == "event"
    aldrich_ames = aldrich_ames_ops or aldrich_ames_event
    our_man_tehran = card_id == 108 and mode == "event" and sponsor == "us"
    bonus_event = card_id in {26, 47, 57, 62, 90, 91, 96} and mode == "event"
    allowed = {"type", "player_id", "card_id", "mode", "interactive", "restriction_discard_id", "move_id"}
    if blockade_ops:
        allowed.add("event_order")
    elif missile_envy:
        allowed.add("event_choices")
    else:
        # Preserve the existing payload-free event-mode protocol, including empty choices.
        allowed.update({"event_choices", "operations_action"})
    if (
        set(move) - allowed or move.get("type") != "play_card"
        or move.get("interactive") is not True or type(card_id) is not int or card_id not in {10, 19, 20, 26, 47, 49, 56, 57, 62, 90, 91, 94, 95, 96, 98, 102, 105, 107, 108}
        or not isinstance(mode, str)
        or (not blockade_ops and not aldrich_ames_ops and mode != "event")
        or (blockade_ops and move.get("event_order") not in ("before_operations", "after_operations"))
        or (move.get("event_choices") and not missile_envy)
        or (missile_envy and (not isinstance(move.get("event_choices", {}), dict)
            or "missile_envy_card_id" in move.get("event_choices", {})))
        or move.get("operations_action") is not None
        or (card_id in {10, 95, 107} and sponsor != "ussr" and not blockade_ops)
        or (card_id == 98 and not (aldrich_ames_ops or aldrich_ames_event))
        or sponsor not in {"us", "ussr"} or gd.get("current_phase") != "action_round"
        or gd.get("current_player") != move.get("player_id")
        or gd.get("current_player_faction") != sponsor or gd.get("_pending_event") is not None
        or gd.get("terminal_result") is not None or gd.get("game_over")
    ):
        raise ValueError("Interactive event requires a supported active player's event play without inline choices")
    if gd.get("actions_taken", {}).get(sponsor, 0) >= faction_action_limit(gd, sponsor):
        raise ValueError("No action rounds remain")
    if not any(c.get("id") == card_id for c in gd.get("hands", {}).get(sponsor, [])):
        raise ValueError("Interactive event card is not in the sponsor's hand")
    if missile_envy and len(_missile_envy_tied_ids(gd, sponsor)) < 2:
        raise ValueError("Interactive Missile Envy requires a tie for highest Operations in the opponent's hand")
    if aldrich_ames and not gd.get("hands", {}).get("us"):
        raise ValueError("Interactive Aldrich Ames Remix requires a US card to discard")
    if our_man_tehran and not _us_controls_middle_east(gd):
        raise ValueError("Interactive Our Man in Tehran requires US control of a Middle Eastern country")
    bonus_faction = "us" if card_id in {26, 47, 57, 96} else "ussr" if card_id in {62, 90, 91} else sponsor
    if bonus_event and card_id == 90 and not gd.get("persistent_events", {}).get("reformer"):
        raise ValueError("Interactive Glasnost bonus requires The Reformer")
    if truman_doctrine:
        if sponsor != "us" or not _truman_doctrine_targets(gd):
            raise ValueError("Interactive Truman Doctrine requires a US play and an uncontrolled European target")
    if muslim_revolution:
        if sponsor != "ussr" or gd.get("persistent_events", {}).get("awacs_sale_played"):
            raise ValueError("Interactive Muslim Revolution requires a USSR play before AWACS Sale")
    if che and not _che_targets(gd):
        raise ValueError("Interactive Che requires an eligible first coup target")
    pre_defcon = gd["tracks"]["defcon"]
    rng = create_rng(gd.get("rng_seed", 42), gd.get("rng_state_json", "{}"))
    gd = _apply_we_will_bury_you_penalty(gd, sponsor, card_id, mode, load_country_data())
    if gd.get("terminal_result") is not None:
        result["game_data"] = gd
        return _complete(result, sponsor, pre_defcon)
    gd, proceed = _apply_action_restriction(gd, sponsor, card_id, mode, move.get("restriction_discard_id"), rng)
    result["rng_state_json"] = gd["rng_state_json"] = serialize_rng(rng)
    result["game_data"] = gd
    if not proceed:
        return _complete(result, sponsor, pre_defcon)
    hand = gd["hands"][sponsor]
    card = hand.pop(next(i for i, c in enumerate(hand) if c["id"] == card_id))
    gd["_pending_event"] = {"card": card, "sponsor": sponsor, "pre_defcon": pre_defcon}
    if che:
        gd["_pending_event"].update(che=True, che_stage="first")
        gd["current_phase"] = "event_response"
        _actor(gd, sponsor)
        return result
    if missile_envy:
        gd["_pending_event"].update(
            missile_envy=True,
            event_choices=deepcopy(move.get("event_choices", {})),
        )
        gd["current_phase"] = "event_response"
        _actor(gd, "ussr" if sponsor == "us" else "us")
        return result
    if aldrich_ames:
        gd["_pending_event"].update(
            aldrich_ames=True,
            mode="operations" if aldrich_ames_ops else "event",
            operations_budget=effective_operations_value(gd, sponsor, card) if aldrich_ames_ops else None,
        )
        gd["current_phase"] = "event_response"
        _actor(gd, "ussr")
        return result
    if our_man_tehran:
        deck = gd.setdefault("draw_pile", [])
        drawn = [deck.pop(0) for _ in range(min(5, len(deck)))]
        gd["_pending_event"]["our_man_tehran"] = True
        gd["_pending_event"]["event_triggered"] = True
        gd["_pending_event"]["tehran_drawn"] = drawn
        gd["current_phase"] = "event_response"
        _actor(gd, "us")
        result["game_data"] = gd
        result["rng_state_json"] = gd["rng_state_json"] = serialize_rng(rng)
        return result
    if card_id == 20:
        # Olympic Games: opponent chooses participation or boycott; sponsor gets bonus Ops on boycott.
        gd["_pending_event"].update(olympic_games=True)
        gd["current_phase"] = "event_response"
        _actor(gd, "ussr" if sponsor == "us" else "us")
        return result
    if bonus_event:
        event_result = resolve_card_event(gd, card, sponsor, mode="event", country_data=load_country_data(), rng=rng, event_choices={})
        gd = event_result["game_data"]
        gd["_pending_event"]["bonus_event"] = True
        gd["_pending_event"]["bonus_faction"] = bonus_faction
        gd["_pending_event"]["event_triggered"] = event_result.get("event_triggered", True)
        gd["current_phase"] = "event_bonus"
        if event_result.get("terminal_result") is not None:
            gd["terminal_result"] = event_result["terminal_result"]
            result["game_data"] = gd
            result["rng_state_json"] = gd["rng_state_json"] = serialize_rng(rng)
            return _complete(result, sponsor, pre_defcon)
        _actor(gd, bonus_faction)
        result["game_data"] = gd
        result["rng_state_json"] = gd["rng_state_json"] = serialize_rng(rng)
        return result
    if chernobyl:
        gd["_pending_event"].update(chernobyl=True)
        gd["current_phase"] = "event_response"
        _actor(gd, sponsor)
        return result
    if iran_iraq:
        gd["_pending_event"].update(iran_iraq=True)
        gd["current_phase"] = "event_response"
        _actor(gd, sponsor)
        return result
    if special_relationship:
        board = gd.get("countries", {})
        data = load_country_data()
        from app.games.twilight_struggle.rules import controlled_by
        if ("U.K." not in board or controlled_by(board["U.K."], data["countries"]["U.K."]) != "us"):
            raise ValueError("Interactive Special Relationship requires US control of the U.K.")
        gd["_pending_event"].update(special_relationship=True)
        gd["current_phase"] = "event_response"
        _actor(gd, sponsor)
        return result
    if truman_doctrine:
        gd["_pending_event"].update(truman_doctrine=True)
        gd["current_phase"] = "event_response"
        _actor(gd, sponsor)
        return result
    if muslim_revolution:
        gd["_pending_event"].update(muslim_revolution=True)
        gd["current_phase"] = "event_response"
        _actor(gd, sponsor)
        return result
    if blockade_ops:
        gd["_pending_event"].update(
            mode="operations", event_order=move["event_order"],
            operations_budget=effective_operations_value(gd, sponsor, card),
            event_triggered=False,
        )
        gd["current_phase"] = "event_response" if move["event_order"] == "before_operations" else "card_operations"
        _actor(gd, "us")
        return result
    gd["current_phase"] = "event_response"
    _actor(gd, "ussr" if sponsor == "us" else "us")
    return result


def interaction_moves(gd: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
    if gd.get("current_player") != player_id or not isinstance(gd.get("_pending_event"), dict):
        return []
    if gd.get("current_phase") == "card_operations":
        pending = gd["_pending_event"]
        if (pending["card"]["id"] in {10, 98} and pending.get("mode") == "operations"
            and pending["sponsor"] == "us" and gd.get("faction_by_player", {}).get(player_id) == "us"):
            return [{"type": "card_operations", "player_id": player_id}]
        return []
    if gd.get("current_phase") == "event_response":
        pending = gd["_pending_event"]
        if pending.get("our_man_tehran"):
            if gd.get("faction_by_player", {}).get(player_id) != "us":
                return []
            return [{
                "type": "event_response", "player_id": player_id,
                "decision": "discard_revealed_cards",
                "revealed_cards": deepcopy(pending.get("tehran_drawn", [])),
            }]
        if gd["_pending_event"].get("che"):
            pending = gd["_pending_event"]
            if gd.get("faction_by_player", {}).get(player_id) != "ussr":
                return []
            if pending.get("che_stage") == "second":
                return ([{"type": "event_response", "player_id": player_id,
                          "decision": "decline_second_coup"}] + [
                    {"type": "event_response", "player_id": player_id,
                     "decision": "choose_second_target", "country": country}
                    for country in _che_targets(gd, pending.get("che_first_target"))
                ])
            return [
                {"type": "event_response", "player_id": player_id,
                 "decision": "choose_first_target", "country": country}
                for country in _che_targets(gd)
            ]
        if gd["_pending_event"]["card"]["id"] == 56:
            if gd.get("faction_by_player", {}).get(player_id) != "ussr":
                return []
            choices = _muslim_revolution_countries()
            return [
                {"type": "event_response", "player_id": player_id,
                 "decision": "choose_countries", "countries": [left, right]}
                for index, left in enumerate(choices)
                for right in choices[index + 1:]
            ]
        if gd["_pending_event"]["card"]["id"] == 19:
            if gd.get("faction_by_player", {}).get(player_id) != "us":
                return []
            return [
                {"type": "event_response", "player_id": player_id,
                 "decision": "choose_country", "country": country}
                for country in _truman_doctrine_targets(gd)
            ]
        if gd["_pending_event"]["card"]["id"] == 105:
            if gd.get("faction_by_player", {}).get(player_id) != gd["_pending_event"]["sponsor"]:
                return []
            from app.games.twilight_struggle.events import WESTERN_EUROPEAN_NATO
            from app.games.twilight_struggle.rules import controlled_by
            data = load_country_data()
            board = gd.get("countries", {})
            if "U.K." not in board or controlled_by(board["U.K."], data["countries"]["U.K."]) != "us":
                return []
            targets = (
                WESTERN_EUROPEAN_NATO if "nato" in gd.get("persistent_events", {})
                else set(data["adjacency"].get("U.K.", []))
            )
            return [
                {"type": "event_response", "player_id": player_id,
                 "decision": "choose_country", "country": country}
                for country in sorted(targets)
            ]
        if gd["_pending_event"]["card"]["id"] == 102:
            if gd.get("faction_by_player", {}).get(player_id) != gd["_pending_event"]["sponsor"]:
                return []
            return [
                {"type": "event_response", "player_id": player_id,
                 "decision": "choose_invader", "invader": invader}
                for invader in ("Iran", "Iraq")
            ]
        if gd["_pending_event"]["card"]["id"] == 94:
            if gd.get("faction_by_player", {}).get(player_id) != gd["_pending_event"]["sponsor"]:
                return []
            from app.games.twilight_struggle.scoring import load_scoring_config
            return [
                {"type": "event_response", "player_id": player_id,
                 "decision": "choose_region", "region": region}
                for region in sorted(load_scoring_config()["regions"])
            ]
        if gd["_pending_event"]["card"]["id"] == 98:
            if gd.get("faction_by_player", {}).get(player_id) != "ussr":
                return []
            return [
                {"type": "event_response", "player_id": player_id,
                 "decision": "discard", "card_id": card["id"]}
                for card in gd.get("hands", {}).get("us", [])
            ]
        if gd["_pending_event"]["card"]["id"] == 49:
            pending = gd["_pending_event"]
            if gd.get("faction_by_player", {}).get(player_id) != ("ussr" if pending["sponsor"] == "us" else "us"):
                return []
            return [
                {"type": "event_response", "player_id": player_id,
                 "decision": "choose_card", "card_id": card_id}
                for card_id in _missile_envy_tied_ids(gd, pending["sponsor"])
            ]
        if gd["_pending_event"]["card"]["id"] == 10:
            if gd.get("faction_by_player", {}).get(player_id) != "us":
                return []
            return [{"type": "event_response", "player_id": player_id, "decision": "remove_influence"}] + [
                {"type": "event_response", "player_id": player_id, "decision": "discard", "card_id": card_id}
                for card_id in blockade_discard_ids(gd)
            ]
        if gd["_pending_event"]["card"]["id"] == 95:
            pending = gd["_pending_event"]
            if pending.get("debt_crisis_stage") == "targets":
                data = load_country_data()
                countries = sorted(
                    name for name, item in data["countries"].items()
                    if item.get("region") == "South America"
                )
                return [
                    {"type": "event_response", "player_id": player_id,
                     "decision": "targets", "countries": [left, right]}
                    for index, left in enumerate(countries)
                    for right in countries[index + 1:]
                ]
            eligible = set(_debt_crisis_discard_ids(gd))
            return ([{"type": "event_response", "player_id": player_id,
                      "decision": "decline_discard"}] + [
                {"type": "event_response", "player_id": player_id,
                 "decision": "discard", "card_id": card_id}
                for card_id in sorted(eligible)
            ])
        return [{"type": "event_response", "player_id": player_id, "decision": decision}
                for decision in ("participate", "boycott")]
    if gd.get("current_phase") == "event_bonus":
        pending = gd["_pending_event"]
        if pending.get("bonus_event"):
            if gd.get("faction_by_player", {}).get(player_id) != pending.get("bonus_faction"):
                return []
            return [
                {"type": "event_bonus", "player_id": player_id, "decline": True},
                {"type": "event_bonus", "player_id": player_id, "decline": False},
            ]
        # The payload-free template cannot validate until an ordinary Ops payload is supplied.
        return [
            {"type": "event_bonus", "player_id": player_id, "decline": True},
            {"type": "event_bonus", "player_id": player_id, "decline": False},
        ]
    return []


def _truman_doctrine_targets(gd: dict[str, Any]) -> list[str]:
    data = load_country_data()
    board = gd.get("countries", {})
    from app.games.twilight_struggle.rules import controlled_by
    return sorted(
        name for name, country in data["countries"].items()
        if country.get("region") == "Europe" and name in board
        and controlled_by(board[name], country) is None
    )


def _muslim_revolution_countries() -> list[str]:
    return ["Sudan", "Iran", "Iraq", "Egypt", "Libya", "Saudi Arabia", "Syria", "Jordan"]


def _us_controls_middle_east(gd: dict[str, Any]) -> bool:
    from app.games.twilight_struggle.rules import controlled_by
    data = load_country_data()
    board = gd.get("countries", {})
    return any(
        name in board and controlled_by(board[name], info) == "us"
        for name, info in data["countries"].items()
        if info.get("region") == "Middle East"
    )


def _respond_blockade_operations(
    result: dict[str, Any], move: dict[str, Any],
) -> dict[str, Any]:
    """One US-owned stage of the committed card; never replay commitment gates.

    The server-owned budget is captured at commitment. No Ops payload survives a
    pause: targets are supplied and validated only against the live stage board.
    """
    gd = result["game_data"]
    pending = gd["_pending_event"]
    if pending["sponsor"] != "us" or gd["faction_by_player"].get(move["player_id"]) != "us":
        raise ValueError("Only the phasing US owns these Operations and responses")
    rng = create_rng(gd.get("rng_seed", 42), gd.get("rng_state_json", "{}"))
    phase = gd["current_phase"]
    del gd["_pending_event"]
    if phase == "card_operations":
        allowed = {"type", "player_id", "operations_action", "move_id"}
        if (set(move) - allowed or move.get("type") != "card_operations"
            or not isinstance(move.get("operations_action"), dict)):
            raise ValueError("Card Operations requires only an owned ordinary Ops payload")
        action = _server_resolve_random_inputs(move["operations_action"], rng)
        gd = resolve_operations_action(gd, "us", pending["operations_budget"], action, load_country_data())
        next_phase = "event_response" if pending.get("event_order") == "after_operations" else None
    elif phase == "event_response":
        allowed = {"type", "player_id", "decision", "card_id", "move_id"}
        decision = move.get("decision")
        if (set(move) - allowed or move.get("type") != "event_response"
            or decision not in ("discard", "remove_influence")
            or (decision == "remove_influence" and "card_id" in move)
            or (decision == "discard" and (type(move.get("card_id")) is not int
                or (pending["card"]["id"] == 10 and move["card_id"] not in blockade_discard_ids(gd))
                or (pending["card"]["id"] == 98 and not any(
                    card.get("id") == move["card_id"] for card in gd.get("hands", {}).get("us", [])
                ))))):
            raise ValueError("Only the US may discard an eligible card or accept Blockade influence removal")
        choices = (
            {"blockade": move["card_id"]} if pending["card"]["id"] == 10 and decision == "discard"
            else {"aldrich_ames_remix": move["card_id"]} if pending["card"]["id"] == 98
            else {}
        )
        event = resolve_card_event(gd, pending["card"], "us", mode="operations", rng=rng, event_choices=choices)
        gd = event["game_data"]
        pending["event_triggered"] = event["event_triggered"]
        gd["terminal_result"] = event.get("terminal_result")
        next_phase = "card_operations" if pending.get("aldrich_ames") or pending.get("event_order") == "before_operations" else None
    else:
        raise ValueError("No Blockade Operations choice at this stage")
    result["game_data"] = gd
    result["rng_state_json"] = gd["rng_state_json"] = serialize_rng(rng)
    _actor(gd, "us")
    if gd.get("terminal_result") is None and next_phase is not None:
        gd["_pending_event"] = pending
        gd["current_phase"] = next_phase
        return result
    # A terminal first stage preempts the other stage. Untriggered starred cards
    # are discarded, not removed. One card play means exactly one action count.
    zone = "removed_cards" if pending["card"].get("event_removed") and pending["event_triggered"] else "discard_pile"
    gd.setdefault(zone, []).append(pending["card"])
    gd = record_action(gd, "us")
    gd["last_card_play"] = {
        "card_id": pending["card"]["id"], "faction": "us", "mode": "operations",
        "event_triggered": pending["event_triggered"], "operations_result": gd.get("last_ops_result"),
    }
    result["game_data"] = gd
    return _complete(result, "us", pending["pre_defcon"])


def respond_interactive_event(state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
    result = deepcopy(state)
    gd = result["game_data"]
    pending = gd.get("_pending_event")
    if (
        not isinstance(pending, dict) or pending.get("card", {}).get("id") not in {10, 19, 20, 49, 56, 94, 95, 98, 102, 105, 107, 108}
        or gd.get("current_phase") not in INTERACTION_PHASES
        or gd.get("current_player") != move.get("player_id")
        or gd.get("terminal_result") is not None or gd.get("game_over")
    ):
        raise ValueError("No interactive choice is owned by this player")
    if (pending["card"]["id"] == 10 and pending.get("mode") == "operations") or (
        pending["card"]["id"] == 98 and pending.get("mode") == "operations"
        and gd.get("current_phase") == "card_operations"
    ):
        return _respond_blockade_operations(result, move)
    sponsor = pending["sponsor"]
    rng = create_rng(gd.get("rng_seed", 42), gd.get("rng_state_json", "{}"))
    del gd["_pending_event"]
    if pending.get("bonus_event"):
        if (gd.get("current_phase") != "event_bonus" or move.get("type") != "event_bonus"
            or set(move) - {"type", "player_id", "decline", "operations_action", "move_id"}
            or type(move.get("decline")) is not bool
            or gd.get("faction_by_player", {}).get(move.get("player_id")) != pending.get("bonus_faction")
            or (move["decline"] and "operations_action" in move)
            or (not move["decline"] and not isinstance(move.get("operations_action"), dict))):
            raise ValueError("Only the bonus-action faction may decline or choose its bonus Operations")
        terminal = check_victory_conditions(gd["tracks"].get("victory_points", 0), gd["tracks"].get("defcon", 5), sponsor)
        ops_result = None
        if not move["decline"] and terminal is None:
            handler = pending["card"].get("effect_handler")
            event = resolve_event_bonus(gd, handler, pending["bonus_faction"], {"bonus_operations": move["operations_action"]}, load_country_data(), rng, sponsor)
            gd = event["game_data"]
            terminal = event.get("terminal_result")
            ops_result = gd.get("last_ops_result")
        zone = "removed_cards" if pending["card"].get("event_removed") and pending.get("event_triggered") else "discard_pile"
        gd.setdefault(zone, []).append(pending["card"])
        gd = record_action(gd, sponsor)
        _actor(gd, sponsor)
        gd["last_card_play"] = {"card_id": pending["card"]["id"], "faction": sponsor,
                                "mode": "event", "event_triggered": bool(pending.get("event_triggered")),
                                "operations_result": ops_result}
        gd["terminal_result"] = terminal
        if terminal is not None:
            gd["game_over"] = True
            gd["current_phase"] = "game_over"
        result["game_data"] = gd
        result["rng_state_json"] = gd["rng_state_json"] = serialize_rng(rng)
        return _complete(result, sponsor, pending["pre_defcon"])
    if pending.get("our_man_tehran"):
        revealed = pending.get("tehran_drawn", [])
        selected = move.get("card_ids")
        allowed = {"type", "player_id", "decision", "card_ids", "move_id"}
        valid_ids = {card.get("id") for card in revealed}
        if (gd.get("current_phase") != "event_response" or set(move) - allowed
            or move.get("type") != "event_response" or move.get("decision") != "discard_revealed_cards"
            or gd.get("faction_by_player", {}).get(move.get("player_id")) != "us"
            or not isinstance(selected, list) or any(type(card_id) is not int for card_id in selected)
            or len(set(selected)) != len(selected) or any(card_id not in valid_ids for card_id in selected)):
            raise ValueError("Only the US may discard a distinct subset of cards revealed by Our Man in Tehran")
        replay = deepcopy(gd)
        replay["draw_pile"] = [*revealed, *replay.get("draw_pile", [])]
        event = resolve_card_event(
            replay, pending["card"], sponsor, mode="event", rng=rng,
            event_choices={"our_man_in_tehran": selected},
        )
        gd = event["game_data"]
        zone = "removed_cards" if pending["card"].get("event_removed") and event.get("event_triggered") else "discard_pile"
        gd.setdefault(zone, []).append(pending["card"])
        gd = record_action(gd, sponsor)
        _actor(gd, sponsor)
        gd["last_card_play"] = {
            "card_id": pending["card"]["id"], "faction": sponsor, "mode": "event",
            "event_triggered": bool(event.get("event_triggered")), "operations_result": None,
        }
        gd["terminal_result"] = None
        result["game_data"] = gd
        result["rng_state_json"] = gd["rng_state_json"] = serialize_rng(rng)
        return _complete(result, sponsor, pending["pre_defcon"])
    elif pending.get("che"):
        allowed = {"type", "player_id", "decision", "country", "move_id"}
        if (gd["current_phase"] != "event_response" or sponsor != "ussr"
            or gd.get("faction_by_player", {}).get(move.get("player_id")) != "ussr"
            or set(move) - allowed or move.get("type") != "event_response"):
            raise ValueError("Only the USSR may resolve Che's coup choices")
        if pending.get("che_stage", "first") == "first":
            target = move.get("country")
            if move.get("decision") != "choose_first_target" or target not in _che_targets(gd):
                raise ValueError("USSR must choose an eligible first Che target")
            us_before = gd["countries"][target].get("us", 0)
            event = resolve_card_event(
                gd, pending["card"], sponsor, mode="event", rng=rng,
                event_choices={"che": target},
            )
            gd = event["game_data"]
            removed_us_influence = gd["countries"][target].get("us", 0) < us_before
            if event.get("terminal_result") is None and removed_us_influence and _che_targets(gd, target):
                pending.update(che_stage="second", che_first_target=target)
                gd["_pending_event"] = pending
                gd["terminal_result"] = event.get("terminal_result")
                gd["current_phase"] = "event_response"
                _actor(gd, "ussr")
                result["game_data"] = gd
                result["rng_state_json"] = gd["rng_state_json"] = serialize_rng(rng)
                return result
        else:
            decision = move.get("decision")
            if decision == "decline_second_coup" and "country" not in move:
                event = {"game_data": gd, "event_triggered": True, "terminal_result": gd.get("terminal_result")}
            elif decision == "choose_second_target" and move.get("country") in _che_targets(
                gd, pending.get("che_first_target")
            ):
                from app.games.twilight_struggle.actions import effective_operations_value
                ops_value = effective_operations_value(gd, "ussr", pending["card"])
                action = _server_resolve_random_inputs(
                    {"type": "coup", "country": move["country"]}, rng,
                )
                gd = resolve_operations_action(gd, "ussr", ops_value, action, load_country_data())
                gd["terminal_result"] = check_victory_conditions(
                    gd["tracks"]["victory_points"], gd["tracks"]["defcon"], "ussr",
                )
                if gd["terminal_result"] is not None:
                    gd["current_phase"] = "game_over"
                event = {"game_data": gd, "event_triggered": True,
                         "terminal_result": gd.get("terminal_result")}
            else:
                raise ValueError("USSR must choose a legal second Che target or decline")
        gd = event["game_data"]
    elif pending["card"]["id"] == 10:
        allowed = {"type", "player_id", "decision", "card_id", "move_id"}
        decision = move.get("decision")
        if (
            gd["current_phase"] != "event_response" or sponsor != "ussr"
            or set(move) - allowed or move.get("type") != "event_response"
            or gd["faction_by_player"].get(move["player_id"]) != "us"
            or decision not in {"discard", "remove_influence"}
            or (decision == "remove_influence" and "card_id" in move)
            or (decision == "discard" and (type(move.get("card_id")) is not int
                or move["card_id"] not in blockade_discard_ids(gd)))
        ):
            raise ValueError("Only the US may discard an eligible card or accept Blockade influence removal")
        choices = {"blockade": move["card_id"]} if decision == "discard" else {}
        event = resolve_card_event(gd, pending["card"], sponsor, mode="event", rng=rng, event_choices=choices)
        gd = event["game_data"]
    elif pending["card"]["id"] == 98:
        allowed = {"type", "player_id", "decision", "card_id", "move_id"}
        if (gd["current_phase"] != "event_response" or set(move) - allowed
            or move.get("type") != "event_response" or move.get("decision") != "discard"
            or gd["faction_by_player"].get(move["player_id"]) != "ussr"
            or type(move.get("card_id")) is not int
            or not any(card.get("id") == move["card_id"] for card in gd.get("hands", {}).get("us", []))):
            raise ValueError("Only the USSR may choose a card from the revealed US hand")
        event = resolve_card_event(
            gd, pending["card"], sponsor, mode=pending.get("mode", "event"), rng=rng,
            event_choices={"aldrich_ames_remix": move["card_id"]},
        )
        gd = event["game_data"]
        if pending.get("mode") == "operations":
            pending["event_triggered"] = event["event_triggered"]
            gd["terminal_result"] = event.get("terminal_result")
            if gd.get("terminal_result") is None:
                gd["_pending_event"] = pending
                gd["current_phase"] = "card_operations"
                _actor(gd, "us")
                result["game_data"] = gd
                result["rng_state_json"] = gd["rng_state_json"] = serialize_rng(rng)
                return result
    elif pending["card"]["id"] == 94:
        from app.games.twilight_struggle.scoring import load_scoring_config
        regions = load_scoring_config()["regions"]
        if (gd["current_phase"] != "event_response" or set(move) - {"type", "player_id", "decision", "region", "move_id"}
            or move.get("type") != "event_response" or move.get("decision") != "choose_region"
            or gd["faction_by_player"].get(move["player_id"]) != sponsor
            or move.get("region") not in regions):
            raise ValueError("Only the sponsoring faction may choose a valid Chernobyl region")
        event = resolve_card_event(
            gd, pending["card"], sponsor, mode="event", rng=rng,
            event_choices={"chernobyl": move["region"]},
        )
        gd = event["game_data"]
    elif pending["card"]["id"] == 102:
        if (gd["current_phase"] != "event_response" or set(move) - {"type", "player_id", "decision", "invader", "move_id"}
            or move.get("type") != "event_response" or move.get("decision") != "choose_invader"
            or gd["faction_by_player"].get(move["player_id"]) != sponsor
            or move.get("invader") not in {"Iran", "Iraq"}):
            raise ValueError("Only the sponsoring faction may choose Iran or Iraq as the invader")
        event = resolve_card_event(
            gd, pending["card"], sponsor, mode="event", rng=rng,
            event_choices={"iran_iraq_war": move["invader"]},
        )
        gd = event["game_data"]
    elif pending["card"]["id"] == 19:
        targets = _truman_doctrine_targets(gd)
        if (gd["current_phase"] != "event_response" or set(move) - {"type", "player_id", "decision", "country", "move_id"}
            or move.get("type") != "event_response" or move.get("decision") != "choose_country"
            or sponsor != "us" or gd["faction_by_player"].get(move["player_id"]) != "us"
            or move.get("country") not in targets):
            raise ValueError("Only the US may choose an uncontrolled European country for Truman Doctrine")
        event = resolve_card_event(
            gd, pending["card"], sponsor, mode="event", rng=rng,
            event_choices={"truman_doctrine": move["country"]},
        )
        gd = event["game_data"]
    elif pending["card"]["id"] == 56:
        countries = move.get("countries")
        allowed_countries = set(_muslim_revolution_countries())
        if (gd["current_phase"] != "event_response" or set(move) - {"type", "player_id", "decision", "countries", "move_id"}
            or move.get("type") != "event_response" or move.get("decision") != "choose_countries"
            or sponsor != "ussr" or gd["faction_by_player"].get(move["player_id"]) != "ussr"
            or not isinstance(countries, list) or len(countries) != 2
            or any(not isinstance(country, str) or country not in allowed_countries for country in countries)
            or countries[0] == countries[1]
            or gd.get("persistent_events", {}).get("awacs_sale_played")):
            raise ValueError("Only the USSR may choose two distinct listed countries for Muslim Revolution")
        event = resolve_card_event(
            gd, pending["card"], sponsor, mode="event", rng=rng,
            event_choices={"muslim_revolution": countries},
        )
        gd = event["game_data"]
    elif pending["card"]["id"] == 105:
        from app.games.twilight_struggle.rules import controlled_by
        data = load_country_data()
        board = gd.get("countries", {})
        uk_controlled = "U.K." in board and controlled_by(board["U.K."], data["countries"]["U.K."]) == "us"
        from app.games.twilight_struggle.events import WESTERN_EUROPEAN_NATO
        targets = (
            WESTERN_EUROPEAN_NATO if "nato" in gd.get("persistent_events", {})
            else set(data["adjacency"].get("U.K.", []))
        )
        if (gd["current_phase"] != "event_response" or set(move) - {"type", "player_id", "decision", "country", "move_id"}
            or move.get("type") != "event_response" or move.get("decision") != "choose_country"
            or gd["faction_by_player"].get(move["player_id"]) != sponsor or not uk_controlled
            or move.get("country") not in targets):
            raise ValueError("Only the sponsoring faction may choose a legal Special Relationship country")
        event = resolve_card_event(
            gd, pending["card"], sponsor, mode="event", rng=rng,
            event_choices={"special_relationship": move["country"]},
        )
        gd = event["game_data"]
    elif pending["card"]["id"] == 95:
        stage = pending.get("debt_crisis_stage", "discard")
        if gd["current_phase"] != "event_response" or sponsor != "ussr":
            raise ValueError("Latin America Debt Crisis is not awaiting a response")
        if stage == "discard":
            allowed = {"type", "player_id", "decision", "card_id", "move_id"}
            if (set(move) - allowed or move.get("type") != "event_response"
                or gd["faction_by_player"].get(move["player_id"]) != "us"):
                raise ValueError("Only the US chooses whether to discard for Latin America Debt Crisis")
            decision = move.get("decision")
            if decision == "discard":
                if type(move.get("card_id")) is not int or move["card_id"] not in _debt_crisis_discard_ids(gd):
                    raise ValueError("The US must discard an eligible 3+ Ops card")
                event = resolve_card_event(
                    gd, pending["card"], sponsor, mode="event", rng=rng,
                    event_choices={"debt_crisis_discard": move["card_id"]},
                )
                gd = event["game_data"]
            elif decision == "decline_discard" and "card_id" not in move:
                pending["debt_crisis_stage"] = "targets"
                gd["_pending_event"] = pending
                _actor(gd, "ussr")
                result["game_data"] = gd
                result["rng_state_json"] = gd["rng_state_json"] = serialize_rng(rng)
                return result
            else:
                raise ValueError("US must discard an eligible card or decline")
        else:
            allowed = {"type", "player_id", "decision", "countries", "move_id"}
            countries = move.get("countries")
            if (set(move) - allowed or move.get("type") != "event_response"
                or move.get("decision") != "targets"
                or gd["faction_by_player"].get(move["player_id"]) != "ussr"
                or not isinstance(countries, list) or len(countries) != 2
                or len(set(countries)) != 2):
                raise ValueError("Only the USSR chooses two distinct South American countries")
            event = resolve_card_event(
                gd, pending["card"], sponsor, mode="event", rng=rng,
                event_choices={"debt_crisis_countries": countries},
            )
            gd = event["game_data"]
    elif pending["card"]["id"] == 49:
        sponsor = pending["sponsor"]
        opponent = "ussr" if sponsor == "us" else "us"
        if (gd["current_phase"] != "event_response" or set(move) - {"type", "player_id", "decision", "card_id", "move_id"}
            or move.get("type") != "event_response" or move.get("decision") != "choose_card"
            or gd["faction_by_player"].get(move["player_id"]) != opponent
            or type(move.get("card_id")) is not int
            or move["card_id"] not in _missile_envy_tied_ids(gd, sponsor)):
            raise ValueError("Only the opponent may choose a tied highest-Ops Missile Envy card")
        event_choices = dict(pending.get("event_choices", {}))
        event_choices["missile_envy_card_id"] = move["card_id"]
        event = resolve_card_event(
            gd, pending["card"], sponsor, mode="event", rng=rng, event_choices=event_choices,
        )
        gd = event["game_data"]
    elif gd["current_phase"] == "event_response":
        allowed = {"type", "player_id", "decision", "move_id"}
        opponent = "ussr" if sponsor == "us" else "us"
        if (set(move) - allowed or move.get("type") != "event_response"
            or move.get("decision") not in {"participate", "boycott"}
            or gd["faction_by_player"].get(move["player_id"]) != opponent):
            raise ValueError("Only the opponent chooses participation or boycott")
        event = resolve_card_event(gd, pending["card"], sponsor, mode="event", rng=rng,
                                   event_choices={"olympic_games": move["decision"]})
        gd = event["game_data"]
        if move["decision"] == "boycott" and event.get("terminal_result") is None:
            gd["_pending_event"] = pending
            gd["current_phase"] = "event_bonus"
            _actor(gd, sponsor)
            result["game_data"] = gd
            result["rng_state_json"] = gd["rng_state_json"] = serialize_rng(rng)
            return result
    else:
        allowed = {"type", "player_id", "decline", "operations_action", "move_id"}
        if (set(move) - allowed or move.get("type") != "event_bonus"
            or type(move.get("decline")) is not bool
            or gd["faction_by_player"].get(move["player_id"]) != sponsor
            or (move["decline"] and "operations_action" in move)
            or (not move["decline"] and not isinstance(move.get("operations_action"), dict))):
            raise ValueError("Only the sponsor chooses bonus Ops or declines")
        choices = {} if move["decline"] else {"bonus_operations": move["operations_action"]}
        event = resolve_event_bonus(gd, "olympic_games", sponsor, choices, load_country_data(), rng, sponsor)
        gd = event["game_data"]
    # Card bookkeeping happens only after all responses. No repeat gate/event/RNG replay.
    if not event.get("card_relocated"):
        zone = "removed_cards" if pending["card"].get("event_removed") and event["event_triggered"] else "discard_pile"
        gd.setdefault(zone, []).append(pending["card"])
    gd = record_action(gd, sponsor)
    _actor(gd, sponsor)
    gd["last_card_play"] = {"card_id": pending["card"]["id"], "faction": sponsor, "mode": "event",
                            "event_triggered": True, "operations_result": None}
    gd["terminal_result"] = event.get("terminal_result")
    result["game_data"] = gd
    result["rng_state_json"] = gd["rng_state_json"] = serialize_rng(rng)
    return _complete(result, sponsor, pending["pre_defcon"])