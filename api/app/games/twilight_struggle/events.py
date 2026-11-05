"""Typed, fail-closed event-effect primitives for future card definitions."""
from __future__ import annotations

from app.games.twilight_struggle.state_clone import fast_copy as deepcopy
import random
import re
from contextvars import ContextVar
from typing import Any

from app.games.twilight_struggle.rules import check_victory_conditions, controlled_by
from app.games.twilight_struggle.country_data import load_country_data
from app.games.twilight_struggle.operations import resolve_operations_action
from app.games.twilight_struggle.scoring import SCORING_CARD_REGIONS, load_scoring_config, resolve_scoring_card, score_region
from app.games.twilight_struggle.state_clone import clone_state
from app.games.twilight_struggle.event_bonus import resolve_event_bonus

# Nested events may change beneficiary, but DEFCON responsibility stays with the
# player who started the card action. Context-local state never enters snapshots.
_PHASING_PLAYER: ContextVar[str | None] = ContextVar("twilight_event_phasing_player", default=None)
from app.games.twilight_struggle.space_race import advance_marker_in_place


def _space_terminal(game_data: dict[str, Any], faction: str) -> dict[str, Any] | None:
    tracks = game_data.get("tracks", {})
    return check_victory_conditions(tracks.get("victory_points", 0), tracks.get("defcon", 5), faction)

DICE_AND_FLAG_HANDLERS = frozenset({
    "korean_war",
    "arab_israeli_war",
    "indo_pakistani_war",
    "brush_war",
    "iran_iraq_war",
    "summit",
    "us_japan_pact",
    "cuban_missile_crisis",
    "nuclear_subs",
    "junta",
    "latin_american_death_squads",
    "ortega_nicaragua",
    "iran_contra_scandal",
    "chernobyl",
    "tear_down_this_wall",
    "olympic_games",
    "cia_created",
    "lone_gunman",
})

FACTIONS = {"us", "ussr"}
# Default: NATO member Western European spaces (Special Relationship, card 105).
WESTERN_EUROPEAN_NATO = frozenset({
    "Benelux", "Denmark", "France", "Italy", "Norway", "Spain/Portugal", "U.K.", "W. Germany",
})
SUPPORTED_EFFECTS = {
    "add_influence",
    "remove_influence",
    "gain_vp",
    "adjust_defcon",
    "set_persistent_event",
    "transfer_china_card",
}


def apply_event_effects(
    game_data: dict[str, Any],
    effects: list[dict[str, Any]],
    country_data: dict[str, Any],
) -> dict[str, Any]:
    """Apply a list of structured card effects atomically.

    This interpreter deliberately rejects unknown effects rather than silently
    treating an unimplemented card as resolved. Event-specific eligibility,
    choices, timing, and cancellation must be validated by the card handler
    before invoking it.
    """
    if not isinstance(effects, list):
        raise ValueError("effects must be a list")
    state = clone_state(game_data)
    board = state.setdefault("countries", {})
    tracks = state.setdefault("tracks", {})
    persistent = state.setdefault("persistent_events", {})
    for effect in effects:
        if state.get("terminal_result") is not None:
            break
        if not isinstance(effect, dict):
            raise ValueError("each effect must be an object")
        kind = effect.get("type")
        if kind not in SUPPORTED_EFFECTS:
            raise ValueError(f"Unsupported event effect: {kind!r}")
        faction = effect.get("faction")
        if kind in {"add_influence", "remove_influence", "gain_vp"} and faction not in FACTIONS:
            raise ValueError(f"Effect {kind} requires a valid faction")
        if kind in {"add_influence", "remove_influence"}:
            country = effect.get("country")
            amount = effect.get("amount")
            if country not in country_data["countries"] or country not in board:
                raise ValueError(f"Unknown event target country: {country!r}")
            if not isinstance(amount, int) or amount < 0:
                raise ValueError("Influence effect amount must be a non-negative integer")
            if kind == "add_influence":
                board[country][faction] = board[country].get(faction, 0) + amount
            else:
                board[country][faction] = max(0, board[country].get(faction, 0) - amount)
        elif kind == "gain_vp":
            amount = effect.get("amount")
            if not isinstance(amount, int):
                raise ValueError("VP effect amount must be an integer")
            sign = 1 if faction == "us" else -1
            tracks["victory_points"] = tracks.get("victory_points", 0) + sign * amount
        elif kind == "adjust_defcon":
            amount = effect.get("amount")
            if not isinstance(amount, int):
                raise ValueError("DEFCON adjustment must be an integer")
            current = tracks.get("defcon", 5)
            tracks["defcon"] = max(1, min(5, current + amount))
        elif kind == "set_persistent_event":
            name = effect.get("name")
            active = effect.get("active")
            if not isinstance(name, str) or not name or not isinstance(active, bool):
                raise ValueError("Persistent event requires a name and boolean active value")
            if active:
                persistent[name] = True
            else:
                persistent.pop(name, None)
        elif kind == "transfer_china_card":
            owner = effect.get("owner")
            if owner not in FACTIONS:
                raise ValueError("China Card owner must be us or ussr")
            state["china_card"] = {"owner": owner, "face_up": bool(effect.get("face_up", True))}
        if kind in {"gain_vp", "adjust_defcon"}:
            terminal = check_victory_conditions(
                tracks.get("victory_points", 0), tracks.get("defcon", 5), 
                _PHASING_PLAYER.get() or game_data.get("current_player_faction", "us"),
            )
            if terminal is not None:
                state["terminal_result"] = terminal
    state["countries"] = board
    state["tracks"] = tracks
    state["persistent_events"] = persistent
    return state


def _resolve_grain_sales(
    game_data: dict[str, Any],
    *,
    country_data: dict[str, Any] | None,
    rng: random.Random | None,
    event_choices: dict[str, Any] | None,
    event_stack: frozenset[int],
) -> dict[str, Any]:
    """Grain Sales to Soviets (67): take one random USSR card, then play it (as US Event) or return it.

    Default resolution: the choice is supplied up front via event_choices["grain_sales"]
    and defaults to "return". If the USSR hand is empty or the card is returned, the
    caller conducts the Operations normally (ops_skipped False). If it is played, the
    drawn card resolves as a US Event and the Grain Sales Operations are not conducted.
    """
    ussr_hand = (game_data.get("hands") or {}).get("ussr") or []
    unchanged = {"game_data": deepcopy(game_data), "event_triggered": False, "terminal_result": None, "ops_skipped": False}
    if not ussr_hand:
        return unchanged
    if rng is None:
        raise ValueError("Grain Sales to Soviets requires server RNG")
    choice = (event_choices or {}).get("grain_sales", "return")
    if choice not in {"play", "return"}:
        raise ValueError("Grain Sales to Soviets choice must be play or return")
    index = rng.randint(1, len(ussr_hand)) - 1
    if choice == "return":
        return unchanged
    taken = ussr_hand[index]
    if taken.get("scoring"):
        raise ValueError("Grain Sales to Soviets cannot play a scoring card")
    result = deepcopy(game_data)
    result["hands"]["ussr"].pop(index)
    resolved = resolve_card_event(
        result, taken, "us", mode="event", country_data=country_data, rng=rng, event_choices=event_choices,
        _event_stack=event_stack,
    )
    result = resolved["game_data"]
    target = "removed_cards" if taken.get("event_removed") else "discard_pile"
    result.setdefault(target, []).append(deepcopy(taken))
    return {
        "game_data": result,
        "event_triggered": True,
        "terminal_result": resolved.get("terminal_result"),
        "ops_skipped": True,
    }


class EventPrevented(ValueError):
    """The card's event cannot occur (cancelled or its precondition is unmet).

    Playing the event is refused, but a card whose event is mandatory can still be played for Operations,
    with no event.
    """


def resolve_card_event(
    game_data: dict[str, Any],
    card: dict[str, Any],
    phasing_faction: str,
    *,
    mode: str,
    trigger_own_event: bool = False,
    country_data: dict[str, Any] | None = None,
    rng: random.Random | None = None,
    chosen_defcon: int | None = None,
    event_choices: dict[str, Any] | None = None,
    _event_stack: frozenset[int] = frozenset(),
) -> dict[str, Any]:
    """Resolve a played card's event; see ``_resolve_card_event`` for timing rules.

    A prevented opponent/both-aligned event is skipped when the card is played for Operations.
    """
    game_data = deepcopy(game_data)
    card_id = card.get("id") if isinstance(card, dict) else None
    if card_id in _event_stack:
        # Nested event chains can cycle through effects such as Star Wars and Missile Envy.
        # Resolve a card at most once on an active chain; the caller still moves it to its
        # destination zone, so this terminates the cycle without losing the card.
        return {"game_data": deepcopy(game_data), "event_triggered": False, "terminal_result": None}
    event_stack = _event_stack | {card_id} if isinstance(card_id, int) else _event_stack
    root_player = _PHASING_PLAYER.get() or phasing_faction
    token = _PHASING_PLAYER.set(root_player)
    try:
        try:
            result = _resolve_card_event(
                game_data, card, phasing_faction, mode=mode, trigger_own_event=trigger_own_event,
                country_data=country_data, rng=rng, chosen_defcon=chosen_defcon, event_choices=event_choices,
                _event_stack=event_stack,
            )
        except EventPrevented:
            opponent = "ussr" if phasing_faction == "us" else "us"
            if mode == "operations" and card.get("alignment") in {opponent, "both"}:
                result = {"game_data": deepcopy(game_data), "event_triggered": False, "terminal_result": None}
            else:
                raise
        updated = result["game_data"]
        tracks = updated.get("tracks", {})
        # Preserve explicit endings such as Wargames/Europe control. Otherwise use
        # the first terminal effect, with a final check for handlers that edit tracks directly.
        terminal = result.get("terminal_result") or updated.get("terminal_result") or check_victory_conditions(
            tracks.get("victory_points", 0), tracks.get("defcon", 5), root_player,
        )
        if terminal is not None:
            if terminal.get("reason") == "defcon_1":
                terminal = check_victory_conditions(tracks.get("victory_points", 0), 1, root_player)
            updated["terminal_result"] = terminal
            result["terminal_result"] = terminal
        return result
    finally:
        _PHASING_PLAYER.reset(token)


def _resolve_card_event(
    game_data: dict[str, Any],
    card: dict[str, Any],
    phasing_faction: str,
    *,
    mode: str,
    trigger_own_event: bool = False,
    country_data: dict[str, Any] | None = None,
    rng: random.Random | None = None,
    chosen_defcon: int | None = None,
    event_choices: dict[str, Any] | None = None,
    _event_stack: frozenset[int] = frozenset(),
) -> dict[str, Any]:
    """Resolve the supported event timing for a played card, fail-closed.

    In Ops mode, an opponent-aligned or both-aligned event is mandatory. The
    active faction may choose whether its own aligned event occurs. Cards with
    no implemented event handler cannot silently pass through when mandatory
    or explicitly selected.
    """
    if phasing_faction not in FACTIONS:
        raise ValueError(f"Unknown phasing faction: {phasing_faction}")
    if mode not in {"event", "operations"}:
        raise ValueError("mode must be event or operations")
    if not isinstance(card, dict) or not isinstance(card.get("id"), int):
        raise ValueError("card must have a numeric id")
    alignment = card.get("alignment")
    if alignment not in {"us", "ussr", "both"}:
        raise ValueError("card has invalid event alignment")
    if card.get("special"):
        raise ValueError("special cards are not resolved as events")
    # A US card played by the USSR for Operations still fires as a US event (the opponent's event is mandatory).
    us_event_allowed = phasing_faction == "us" or (mode == "operations" and alignment == "us")
    ussr_event_allowed = phasing_faction == "ussr" or (mode == "operations" and alignment == "ussr")
    if card.get("scoring"):
        if mode != "event":
            raise ValueError("scoring cards must be played as events")
        scored = resolve_scoring_card(game_data, card, phasing_faction, country_data)
        return {
            "game_data": scored["game_data"],
            "event_triggered": True,
            "terminal_result": scored["terminal_result"],
            "score_result": scored["score_result"],
        }
    if card.get("effect_handler") == "un_intervention" and mode == "operations":
        # UN Intervention has no standalone Operations-mode event effect.
        return {"game_data": deepcopy(game_data), "event_triggered": False, "terminal_result": None}
    if card.get("effect_handler") == "grain_sales":
        if mode != "operations" or alignment != "us":
            raise ValueError("Grain Sales to Soviets is a US Operations-only card")
        return _resolve_grain_sales(
            game_data, country_data=country_data, rng=rng, event_choices=event_choices, event_stack=_event_stack,
        )
    if card.get("effect_handler") == "shuttle_diplomacy":
        # Played in front of the US player; the card is discarded only when the next Middle East or Asia scoring resolves.
        if not us_event_allowed:
            raise ValueError("Shuttle Diplomacy is a US card")
        if (game_data.get("persistent_events") or {}).get("shuttle_diplomacy"):
            raise ValueError("Shuttle Diplomacy is already in play")
        result = deepcopy(game_data)
        result.setdefault("persistent_events", {})["shuttle_diplomacy"] = {"faction": "us", "card": deepcopy(card)}
        return {"game_data": result, "event_triggered": True, "terminal_result": None, "card_in_play": True}
    opponent = "ussr" if phasing_faction == "us" else "us"
    mandatory = mode == "event" or alignment in {opponent, "both"}
    trigger = mandatory or (mode == "operations" and trigger_own_event)
    if not trigger:
        return {"game_data": deepcopy(game_data), "event_triggered": False, "terminal_result": None}

    handler = card.get("effect_handler")
    if handler == "defectors":
        # USSR-played Defectors grants the US 1 VP; US-played copy is inert here
        # (its cancel effect is applied at headline reveal).
        result = deepcopy(game_data)
        if phasing_faction == "ussr":
            result = apply_event_effects(result, [{"type": "gain_vp", "faction": "us", "amount": 1}], country_data or load_country_data())
        return {"game_data": result, "event_triggered": True, "terminal_result": None}
    if handler == "cambridge_five":
        # USSR adds 1 influence to one country in a region named on a US scoring card in hand.
        data = country_data or load_country_data()
        us_hand = (game_data.get("hands") or {}).get("us") or []
        named_regions = set()
        for us_card in us_hand:
            if not us_card.get("scoring"):
                continue
            normalized = re.sub(r"[^a-z ]", "", us_card.get("name", "").casefold()).strip()
            region = SCORING_CARD_REGIONS.get(normalized)
            if region:
                named_regions.add(region)
        country = (event_choices or {}).get("cambridge_five")
        if not named_regions:
            # No US scoring card in hand names a region, so the event has no legal target and no effect.
            return {"game_data": deepcopy(game_data), "event_triggered": True, "terminal_result": None}
        if (
            not isinstance(country, str) or country not in data["countries"]
            or data["countries"][country].get("region") not in named_regions
        ):
            raise ValueError("Cambridge Five requires one country in a region named on a US scoring card in hand")
        result = apply_event_effects(
            deepcopy(game_data),
            [{"type": "add_influence", "faction": "ussr", "country": country, "amount": 1}],
            data,
        )
        return {"game_data": result, "event_triggered": True, "terminal_result": None}
    if handler == "special_relationship":
        # If the UK is US-controlled: without NATO, US adds 1 influence to a country adjacent to the UK;
        # with NATO in effect, US adds 2 influence to a Western European country and gains 2 VP.
        data = country_data or load_country_data()
        board = game_data.get("countries") or {}
        uk = "U.K."
        if uk not in board or controlled_by(board[uk], data["countries"][uk]) != "us":
            return {"game_data": deepcopy(game_data), "event_triggered": True, "terminal_result": None}
        choice = (event_choices or {}).get("special_relationship")
        if "nato" in (game_data.get("persistent_events") or {}):
            if not isinstance(choice, str) or choice not in WESTERN_EUROPEAN_NATO:
                raise ValueError("Special Relationship requires a Western European country while NATO is in effect")
            effects = [
                {"type": "add_influence", "faction": "us", "country": choice, "amount": 2},
                {"type": "gain_vp", "faction": "us", "amount": 2},
            ]
        else:
            if not isinstance(choice, str) or choice not in data["adjacency"].get(uk, []):
                raise ValueError("Special Relationship requires a country adjacent to the UK")
            effects = [{"type": "add_influence", "faction": "us", "country": choice, "amount": 1}]
        result = apply_event_effects(deepcopy(game_data), effects, data)
        return {"game_data": result, "event_triggered": True, "terminal_result": None}
    if handler == "missile_envy":
        # Exchange this card for the opponent's highest-Ops non-scoring card.
        # Legacy/default callers retain first-in-hand tie resolution; interactive callers supply the opponent's choice.
        # The opponent receives Missile Envy and must play it for Ops next action round (enforcement deferred).
        # If the taken card is the phasing or both-aligned event, it resolves now and is discarded.
        result = deepcopy(game_data)
        opponent = "ussr" if phasing_faction == "us" else "us"
        opp_hand = result.setdefault("hands", {}).setdefault(opponent, [])
        eligible = [c for c in opp_hand if not c.get("scoring")]
        if not eligible:
            return {"game_data": result, "event_triggered": True, "terminal_result": None, "card_relocated": False}
        top = max(int(c.get("operations", 0)) for c in eligible)
        tied = [c for c in eligible if int(c.get("operations", 0)) == top]
        selected_id = (event_choices or {}).get("missile_envy_card_id")
        if selected_id is not None:
            taken = next((c for c in tied if c.get("id") == selected_id), None)
            if taken is None:
                raise ValueError("Missile Envy choice must be an opponent card tied for highest Operations")
        else:
            taken = tied[0]
        opp_hand.remove(taken)
        opp_hand.append(deepcopy(card))
        result.setdefault("persistent_events", {})["missile_envy"] = {
            "faction": opponent, "card_id": card.get("id"), "pending": True,
        }
        terminal = None
        if taken.get("alignment") in {phasing_faction, "both"}:
            resolved = resolve_card_event(
                result, taken, phasing_faction, mode="event",
                country_data=country_data, rng=rng, event_choices=event_choices,
                _event_stack=_event_stack,
            )
            result = resolved["game_data"]
            terminal = resolved.get("terminal_result")
            target = "removed_cards" if taken.get("event_removed") and resolved["event_triggered"] else "discard_pile"
            result.setdefault(target, []).append(taken)
        else:
            result.setdefault("hands", {}).setdefault(phasing_faction, []).append(taken)
        return {"game_data": result, "event_triggered": True, "terminal_result": terminal, "card_relocated": True}
    if handler == "kal_007":
        # US event: degrade DEFCON one level and gain 2 VP. If South Korea is US-controlled, record a turn-scoped
        # 4-Ops bonus for the US. The bonus action flow is not wired yet; the flag is recorded for that layer.
        if not us_event_allowed:
            raise ValueError("Soviets Shoot Down KAL-007 is a US card")
        data = country_data or load_country_data()
        board = game_data.get("countries") or {}
        effects = [
            {"type": "adjust_defcon", "amount": -1},
            {"type": "gain_vp", "faction": "us", "amount": 2},
        ]
        updated = apply_event_effects(deepcopy(game_data), effects, data)
        if updated.get("terminal_result") is None and "S. Korea" in board and controlled_by(board["S. Korea"], data["countries"]["S. Korea"]) == "us":
            updated.setdefault("persistent_events", {})["kal_007_bonus"] = {
                "faction": "us", "operations": 4, "expires_turn": game_data.get("turn", 1),
            }
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}
    if handler == "reformer":
        # USSR adds 4 influence in Europe (6 if USSR is ahead on VP), at most 2 per country, then bans USSR coups in Europe.
        if not ussr_event_allowed:
            raise ValueError("The Reformer is a USSR card")
        data = country_data or load_country_data()
        placement = (event_choices or {}).get("reformer")
        ussr_ahead = (game_data.get("tracks") or {}).get("victory_points", 0) < 0
        required = 6 if ussr_ahead else 4
        if not isinstance(placement, dict) or not placement:
            # Auto-pick first valid European countries
            europe = [n for n, c in data["countries"].items() if c.get("region") == "Europe"]
            placement = {}
            remaining = required
            for name in europe:
                if remaining <= 0:
                    break
                amt = min(2, remaining)
                placement[name] = amt
                remaining -= amt
        if sum(placement.values()) != required or not all(_is_count(v) and 1 <= v <= 2 for v in placement.values()):
            # Fix
            europe = [n for n, c in data["countries"].items() if c.get("region") == "Europe"]
            placement = {}
            remaining = required
            for name in europe:
                if remaining <= 0:
                    break
                amt = min(2, remaining)
                placement[name] = amt
                remaining -= amt
        effects = []
        for name, amount in placement.items():
            if name not in data["countries"] or data["countries"][name].get("region") != "Europe":
                continue
            effects.append({"type": "add_influence", "faction": "ussr", "country": name, "amount": amount})
        updated = apply_event_effects(game_data, effects, data)
        updated.setdefault("persistent_events", {})["reformer"] = {"faction": "ussr"}
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}
    if handler == "star_wars":
        # If the US is ahead on the Space Race, search the discard pile for a non-scoring card and resolve its event now.
        if not us_event_allowed:
            raise ValueError("Star Wars is a US card")
        result = deepcopy(game_data)
        track = (result.get("tracks") or {}).get("space_race") or {"us": 0, "ussr": 0}
        if track.get("us", 0) <= track.get("ussr", 0):
            return {"game_data": result, "event_triggered": True, "terminal_result": None}
        chosen_id = (event_choices or {}).get("star_wars")
        discard = result.setdefault("discard_pile", [])
        index = next((i for i, c in enumerate(discard) if c.get("id") == chosen_id), None)
        if index is None:
            raise ValueError("Star Wars requires a card from the discard pile")
        taken = discard.pop(index)
        if taken.get("scoring") or taken.get("special"):
            raise ValueError("Star Wars may only choose a non-scoring card")
        resolved = resolve_card_event(
            result, taken, "us", mode="event", country_data=country_data, rng=rng, event_choices=event_choices,
            _event_stack=_event_stack,
        )
        result = resolved["game_data"]
        target = "removed_cards" if taken.get("event_removed") else "discard_pile"
        result.setdefault(target, []).append(taken)
        return {"game_data": result, "event_triggered": True, "terminal_result": resolved.get("terminal_result")}
    if handler == "our_man_in_tehran":
        # If the US controls a Middle East country, draw the top 5 cards, discard any chosen (revealed to USSR),
        # return the rest to the draw pile, and reshuffle. Without US Middle East control the event has no effect.
        if not us_event_allowed:
            raise ValueError("Our Man in Tehran is a US card")
        if rng is None:
            raise ValueError("Our Man in Tehran requires server RNG")
        data = country_data or load_country_data()
        result = deepcopy(game_data)
        board = result.get("countries") or {}
        controls_me = any(
            name in board and controlled_by(board[name], info) == "us"
            for name, info in data["countries"].items()
            if info.get("region") == "Middle East"
        )
        if not controls_me:
            return {"game_data": result, "event_triggered": True, "terminal_result": None}
        chosen = (event_choices or {}).get("our_man_in_tehran") or []
        deck = result.setdefault("draw_pile", [])
        drawn = [deck.pop(0) for _ in range(min(5, len(deck)))]
        drawn_ids = [c.get("id") for c in drawn]
        if not isinstance(chosen, list) or len(set(chosen)) != len(chosen) or any(item not in drawn_ids for item in chosen):
            raise ValueError("Our Man in Tehran may discard only distinct cards from the drawn top 5")
        discarded = [c for c in drawn if c.get("id") in set(chosen)]
        remaining = [c for c in drawn if c.get("id") not in set(chosen)]
        result.setdefault("discard_pile", []).extend(discarded)
        deck.extend(remaining)
        rng.shuffle(deck)
        return {"game_data": result, "event_triggered": True, "terminal_result": None}
    if handler == "che":
        # USSR coup using Che's Ops value against a non-Battleground Central/South American or African target.
        # If the first coup removed any US influence, one second coup may target a different space under the same rules.
        if rng is None:
            raise ValueError("Che requires server RNG")
        data = country_data or load_country_data()
        choices_che = event_choices or {}
        eligible_targets = [
            name for name, info in data["countries"].items()
            if info.get("region") in {"Central America", "South America", "Africa"}
            and not info.get("battleground")
            and game_data.get("countries", {}).get(name, {}).get("us", 0) > 0
        ]
        if not eligible_targets:
            raise EventPrevented("Che has no eligible non-Battleground target with US influence")

        def require_che_target(name: Any) -> None:
            info = data["countries"].get(name) if isinstance(name, str) else None
            if not info or info.get("region") not in {"Central America", "South America", "Africa"} or info.get("battleground"):
                raise ValueError("Che requires a non-Battleground country in Central America, South America, or Africa")

        first = choices_che.get("che")
        require_che_target(first)
        result = deepcopy(game_data)
        us_before = result["countries"][first].get("us", 0)
        # Rules 7.4.2: active Ops modifiers apply for all purposes, including an event's coup value.
        # Local import avoids the actions -> events orchestration import cycle.
        from app.games.twilight_struggle.actions import effective_operations_value

        ops_value = effective_operations_value(result, "ussr", card)
        result = resolve_operations_action(
            result, "ussr", ops_value, {"type": "coup", "country": first, "die_roll": rng.randint(1, 6)}, data,
        )
        second = choices_che.get("che_second")
        if result.get("terminal_result") is None and second is not None and result["countries"][first].get("us", 0) < us_before:
            if second == first:
                raise ValueError("Che's second coup must target a different country")
            require_che_target(second)
            result = resolve_operations_action(
                result, "ussr", ops_value, {"type": "coup", "country": second, "die_roll": rng.randint(1, 6)}, data,
            )
        return {"game_data": result, "event_triggered": True, "terminal_result": result.get("terminal_result")}
    if handler == "ask_not_what":
        # US discards any chosen subset of its hand (including scoring cards), decided before drawing,
        # then draws the same number of replacements from the top of the draw pile.
        chosen = (event_choices or {}).get("ask_not_what") or []
        if not isinstance(chosen, list) or any(not isinstance(item, int) for item in chosen):
            raise ValueError("Ask Not What Your Country Can Do For You requires a list of card ids to discard")
        if len(set(chosen)) != len(chosen):
            raise ValueError("Ask Not What Your Country Can Do For You cannot discard the same card twice")
        result = deepcopy(game_data)
        hands = result.setdefault("hands", {})
        hand = hands.setdefault(phasing_faction, [])
        hand_ids = {c.get("id") for c in hand}
        if any(item not in hand_ids for item in chosen):
            raise ValueError("Ask Not What Your Country Can Do For You may only discard cards from hand")
        if not chosen:
            return {"game_data": result, "event_triggered": True, "terminal_result": None}
        deck = result.setdefault("draw_pile", [])
        if len(deck) < len(chosen):
            raise ValueError("Ask Not What Your Country Can Do For You: not enough cards in the draw pile")
        chosen_ids = set(chosen)
        discarded = [c for c in hand if c.get("id") in chosen_ids]
        kept = [c for c in hand if c.get("id") not in chosen_ids]
        result.setdefault("discard_pile", []).extend(discarded)
        kept.extend(deck.pop(0) for _ in chosen)
        hands[phasing_faction] = kept
        return {"game_data": result, "event_triggered": True, "terminal_result": None}
    if handler == "salt_negotiations":
        # Improve DEFCON by 2, apply -1 to Coup die rolls by both players for the rest of this turn,
        # and let the playing faction reclaim one non-scoring card from the discard pile (event_choices).
        turn = game_data.get("turn", 1)
        result = apply_event_effects(deepcopy(game_data), [{"type": "adjust_defcon", "amount": 2}], country_data or load_country_data())
        result.setdefault("persistent_events", {})["salt_negotiations"] = {"faction": phasing_faction, "expires_turn": turn}
        reclaim_id = (event_choices or {}).get("salt_negotiations")
        if reclaim_id is not None:
            discard = result.setdefault("discard_pile", [])
            index = next((i for i, c in enumerate(discard) if c.get("id") == reclaim_id), None)
            if index is None or discard[index].get("scoring"):
                raise ValueError("SALT Negotiations may reclaim only a non-scoring card from the discard pile")
            reclaimed = discard.pop(index)
            result.setdefault("hands", {}).setdefault(phasing_faction, []).append(reclaimed)
        return {"game_data": result, "event_triggered": True, "terminal_result": None}
    if handler == "we_will_bury_you":
        result = apply_event_effects(deepcopy(game_data), [{"type": "adjust_defcon", "amount": -1}], country_data or load_country_data())
        result.setdefault("persistent_events", {})["we_will_bury_you"] = {"faction": "ussr", "expires_turn": 10}
        return {"game_data": result, "event_triggered": True, "terminal_result": None}
    if handler == "un_intervention":
        result = deepcopy(game_data)
        result.setdefault("persistent_events", {}).pop("we_will_bury_you", None)
        return {"game_data": result, "event_triggered": True, "terminal_result": None}
    if handler in {"containment", "red_scare_purge", "brezhnev_doctrine", "quagmire", "bear_trap", "flower_power", "north_sea_oil", "norad", "nato", "formosan_resolution"}:
        result = deepcopy(game_data)
        persistent = result.setdefault("persistent_events", {})
        turn = result.get("turn", 1)
        if handler == "containment":
            persistent["containment"] = {"faction": "us", "expires_turn": turn}
        elif handler == "red_scare_purge":
            opponent = "ussr" if phasing_faction == "us" else "us"
            persistent["red_scare_purge"] = {"faction": opponent, "expires_turn": turn}
        elif handler in {"quagmire", "bear_trap"}:
            opponent = "ussr" if phasing_faction == "us" else "us"
            if handler == "quagmire":
                # Quagmire cancels the ongoing NORAD (106) effect.
                persistent.pop("norad", None)
            persistent["action_restriction"] = {
                "faction": opponent,
                "expires_turn": turn,
                "scoring_only": False,
                "source": handler,
            }
        elif handler == "brezhnev_doctrine":
            persistent["brezhnev_doctrine"] = {"faction": "ussr", "expires_turn": turn}
        elif handler == "flower_power":
            # Default: An Evil Empire (97) played earlier this game prevents Flower Power's effect.
            if not persistent.get("flower_power_cancelled"):
                # Lasts for the rest of the game (game ends after turn 10).
                persistent["flower_power"] = {"faction": "ussr", "expires_turn": 10}
        elif handler == "norad":
            # Ongoing: applies at the end of any action round that moves DEFCON to 2 (until Quagmire cancels it).
            persistent["norad"] = {"faction": "us", "expires_turn": 10}
        elif handler == "nato":
            # Ongoing for the rest of the game: USSR may not coup/realign US-controlled Europe (see operations.py).
            persistent["nato"] = {"faction": "us", "expires_turn": 10}
        elif handler == "formosan_resolution":
            # Ongoing: Taiwan is a Battleground for Asia scoring while US-controlled (cancelled by US China Card play).
            persistent["formosan_resolution"] = {"faction": "us", "expires_turn": 10}
        elif handler == "north_sea_oil":
            # US may play up to 8 cards this turn; also disables OPEC (61).
            persistent["north_sea_oil"] = {"faction": "us", "expires_turn": turn}
        return {"game_data": result, "event_triggered": True, "terminal_result": None}
    if handler == "samantha_yuri":
        # USSR event: USSR gains 1 VP per US coup attempt for the rest of the current turn (flag consumed by coups).
        if not ussr_event_allowed:
            raise ValueError("Samantha and Yuri is a USSR card")
        result = deepcopy(game_data)
        result.setdefault("persistent_events", {})["samantha_yuri"] = {
            "faction": "ussr", "expires_turn": game_data.get("turn", 1),
        }
        return {"game_data": result, "event_triggered": True, "terminal_result": None}
    if handler == "latin_america_debt_crisis":
        # USSR event: unless the US immediately discards a 3+ Ops card (event_choices["debt_crisis_discard"]),
        # double USSR influence in two chosen South American countries (event_choices["debt_crisis_countries"]).
        if not ussr_event_allowed:
            raise ValueError("Latin America Debt Crisis is a USSR card")
        result = deepcopy(game_data)
        choices_debt = event_choices or {}
        discard_id = choices_debt.get("debt_crisis_discard")
        us_hand = result.setdefault("hands", {}).setdefault("us", [])
        if discard_id is not None:
            index = next((i for i, c in enumerate(us_hand) if c.get("id") == discard_id), None)
            if index is None or int(us_hand[index].get("operations", 0)) < 3:
                raise ValueError("Latin America Debt Crisis: the US must discard a 3+ Ops card from hand to prevent it")
            result.setdefault("discard_pile", []).append(us_hand.pop(index))
            return {"game_data": result, "event_triggered": True, "terminal_result": None}
        data = country_data or load_country_data()
        countries = choices_debt.get("debt_crisis_countries")
        if not isinstance(countries, list) or len(countries) != 2 or len(set(countries)) != 2:
            raise ValueError("Latin America Debt Crisis requires two distinct South American countries")
        effects = []
        for name in countries:
            if name not in data["countries"] or data["countries"][name].get("region") != "South America":
                raise ValueError(f"Latin America Debt Crisis cannot target {name!r}")
            current = result.get("countries", {}).get(name, {}).get("ussr", 0)
            if current:
                effects.append({"type": "add_influence", "faction": "ussr", "country": name, "amount": current})
        result = apply_event_effects(result, effects, data)
        return {"game_data": result, "event_triggered": True, "terminal_result": None}
    if handler == "blockade":
        # Default: the US may discard one 3+ Ops card (event_choices["blockade"] = card id) to prevent the removal.
        result = deepcopy(game_data)
        discard_id = (event_choices or {}).get("blockade")
        us_hand = result.setdefault("hands", {}).setdefault("us", [])
        if discard_id is not None:
            from app.games.twilight_struggle.actions import blockade_discard_ids

            index = next((i for i, c in enumerate(us_hand) if c.get("id") == discard_id), None)
            if type(discard_id) is not int or index is None or discard_id not in blockade_discard_ids(result):
                raise ValueError("Blockade requires the US to discard a 3+ Ops card from hand")
            result.setdefault("discard_pile", []).append(us_hand.pop(index))
            return {"game_data": result, "event_triggered": True, "terminal_result": None}
        amount = result.get("countries", {}).get("W. Germany", {}).get("us", 0)
        if amount:
            result = apply_event_effects(
                result,
                [{"type": "remove_influence", "faction": "us", "country": "W. Germany", "amount": amount}],
                country_data or load_country_data(),
            )
        return {"game_data": result, "event_triggered": True, "terminal_result": None}
    if handler in {
        "allende",
        "camp_david_accords",
        "comecon",
        "de_gaulle_leads_france",
        "john_paul_ii_elected_pope",
        "sadat_expels_soviets",
        "iranian_hostage_crisis",
        "the_iron_lady",
        "reagan_bombs_libya",
        "willy_brandt",
        "panama_canal_returned",
        "alliance_for_progress",
        "glasnost",
        "an_evil_empire",
        "pershing_ii_deployed",
        "oas_founded",
        "liberation_theology",
        "the_voice_of_america",
        "marine_barracks_bombing",
        "portuguese_empire_crumbles",
        "solidarity",
        "truman_doctrine",
        "east_european_unrests",
        "decolonization",
        "south_african_unrest",
        "colonial_rearguards",
        "puppet_governments",
        "socialist_governments",
        "warsaw_pact_formed",
        "independent_reds",
        "suez_crisis",
        "arms_race",
        "cultural_revolution",
        "opec",
        "u2_incident",
    }:
        data = country_data or load_country_data()
        if handler == "allende":
            effects = [
                {"type": "add_influence", "faction": "ussr", "country": "Chile", "amount": 2},
            ]
        elif handler == "de_gaulle_leads_france":
            effects = [
                {"type": "remove_influence", "faction": "us", "country": "France", "amount": 2},
                {"type": "add_influence", "faction": "ussr", "country": "France", "amount": 1},
            ]
        elif handler == "portuguese_empire_crumbles":
            effects = [
                {"type": "add_influence", "faction": "ussr", "country": country, "amount": 2}
                for country in ("SE African States", "Angola")
            ]
        elif handler == "john_paul_ii_elected_pope":
            effects = [
                {"type": "remove_influence", "faction": "ussr", "country": "Poland", "amount": 2},
                {"type": "add_influence", "faction": "us", "country": "Poland", "amount": 1},
            ]
        elif handler == "solidarity":
            if not game_data.get("persistent_events", {}).get("solidarity_enabled"):
                raise EventPrevented("Solidarity requires John Paul II Elected Pope to have occurred")
            effects = [
                {"type": "add_influence", "faction": "us", "country": "Poland", "amount": 3},
            ]
        elif handler == "sadat_expels_soviets":
            egypt = game_data.get("countries", {}).get("Egypt", {})
            effects = [
                {"type": "remove_influence", "faction": "ussr", "country": "Egypt", "amount": egypt.get("ussr", 0)},
                {"type": "add_influence", "faction": "us", "country": "Egypt", "amount": 1},
            ]
        elif handler == "iranian_hostage_crisis":
            iran = game_data.get("countries", {}).get("Iran", {})
            effects = [
                {"type": "remove_influence", "faction": "us", "country": "Iran", "amount": iran.get("us", 0)},
                {"type": "add_influence", "faction": "ussr", "country": "Iran", "amount": 2},
            ]
        elif handler == "the_iron_lady":
            uk = game_data.get("countries", {}).get("U.K.", {})
            effects = [
                {"type": "gain_vp", "faction": "us", "amount": 1},
                {"type": "add_influence", "faction": "ussr", "country": "Argentina", "amount": 1},
                {"type": "remove_influence", "faction": "ussr", "country": "U.K.", "amount": uk.get("ussr", 0)},
            ]
        elif handler == "reagan_bombs_libya":
            libya = game_data.get("countries", {}).get("Libya", {})
            effects = [
                {"type": "gain_vp", "faction": "us", "amount": libya.get("ussr", 0) // 2},
            ]
        elif handler == "willy_brandt":
            if game_data.get("persistent_events", {}).get("tear_down_this_wall"):
                return {"game_data": deepcopy(game_data), "event_triggered": False, "terminal_result": None}
            effects = [
                {"type": "gain_vp", "faction": "ussr", "amount": 1},
                {"type": "add_influence", "faction": "ussr", "country": "W. Germany", "amount": 1},
            ]
        elif handler == "panama_canal_returned":
            effects = [
                {"type": "add_influence", "faction": "us", "country": country, "amount": 1}
                for country in ("Panama", "Costa Rica", "Venezuela")
            ]
        elif handler == "comecon":
            choices = (event_choices or {}).get("comecon")
            eligible = {
                name for name in ("E. Germany", "Poland", "Czechoslovakia", "Hungary", "Romania", "Bulgaria", "Yugoslavia")
                if name in data["countries"]
                and controlled_by(game_data.get("countries", {}).get(name, {}), data["countries"][name]) != "us"
            }
            if len(eligible) < 4:
                raise EventPrevented("COMECON has fewer than four eligible Eastern European countries")
            if not isinstance(choices, list) or len(choices) != 4 or len(set(choices)) != 4:
                raise ValueError("COMECON requires four distinct eligible Eastern European countries")
            if any(name not in eligible for name in choices):
                raise ValueError("COMECON choices must be non-US-controlled Eastern European countries")
            effects = [
                {"type": "add_influence", "faction": "ussr", "country": name, "amount": 1}
                for name in choices
            ]
        elif handler == "truman_doctrine":
            country = (event_choices or {}).get("truman_doctrine")
            if (
                not isinstance(country, str) or country not in data["countries"]
                or country not in game_data.get("countries", {})
                or data["countries"][country].get("region") != "Europe"
                or controlled_by(game_data["countries"][country], data["countries"][country]) is not None
            ):
                raise ValueError("Truman Doctrine requires one uncontrolled European country")
            amount = game_data["countries"][country].get("ussr", 0)
            effects = [{"type": "remove_influence", "faction": "ussr", "country": country, "amount": amount}]
        elif handler == "east_european_unrests":
            choices = (event_choices or {}).get("east_european_unrests")
            eastern_europe = {"E. Germany", "Poland", "Czechoslovakia", "Hungary", "Romania", "Bulgaria"}
            removal = 2 if game_data.get("turn", 1) >= 8 else 1
            eligible = [
                name for name in eastern_europe
                if game_data.get("countries", {}).get(name, {}).get("ussr", 0) >= removal
            ]
            if len(eligible) < 3:
                raise EventPrevented("East European Unrests has fewer than three eligible countries")
            if (
                not isinstance(choices, list) or len(choices) != 3
                or len(set(choices)) != 3
                or any(name not in eastern_europe or game_data.get("countries", {}).get(name, {}).get("ussr", 0) < removal for name in choices)
            ):
                raise ValueError("East European Unrests requires three distinct eligible countries with sufficient USSR influence")
            effects = [
                {"type": "remove_influence", "faction": "ussr", "country": name, "amount": removal}
                for name in choices
            ]
        elif handler == "decolonization":
            choices = (event_choices or {}).get("decolonization")
            southeast_asia = {
                "Burma", "Laos/Cambodia", "Thailand", "Vietnam", "Malaysia", "Indonesia", "Philippines"
            }
            eligible = [
                name for name, country in data["countries"].items()
                if country.get("region") == "Africa" or name in southeast_asia
            ]
            if (
                not isinstance(choices, list) or len(choices) != 4 or len(set(choices)) != 4
                or any(not isinstance(name, str) or name not in eligible for name in choices)
            ):
                if len(eligible) < 4:
                    raise ValueError("decolonization requires four African and/or Southeast Asian countries")
                choices = eligible[:4]
            effects = [{"type": "add_influence", "faction": "ussr", "country": name, "amount": 1} for name in choices]
        elif handler == "colonial_rearguards":
            choices = (event_choices or {}).get("colonial_rearguards")
            southeast_asia = {
                "Burma", "Laos/Cambodia", "Thailand", "Vietnam", "Malaysia", "Indonesia", "Philippines"
            }
            eligible = [
                name for name, country in data["countries"].items()
                if country.get("region") == "Africa" or name in southeast_asia
            ]
            if (
                not isinstance(choices, list) or len(choices) != 4 or len(set(choices)) != 4
                or any(not isinstance(name, str) or name not in eligible for name in choices)
            ):
                if len(eligible) < 4:
                    raise ValueError("colonial_rearguards requires four African and/or Southeast Asian countries")
                choices = eligible[:4]
            effects = [{"type": "add_influence", "faction": "us", "country": name, "amount": 1} for name in choices]
        elif handler == "south_african_unrest":
            choice = (event_choices or {}).get("south_african_unrest")
            if not isinstance(choice, dict) or choice.get("mode") not in {"south_africa", "adjacent"}:
                neighbors = data["adjacency"].get("South Africa", [])
                choice = {"mode": "south_africa"}
            if choice["mode"] == "south_africa":
                effects = [{"type": "add_influence", "faction": "ussr", "country": "South Africa", "amount": 2}]
            else:
                neighbors = data["adjacency"].get("South Africa", [])
                distribution = choice.get("adjacent")
                if not isinstance(distribution, dict) or sum(distribution.values()) != 2 or any(
                    name not in neighbors or not _is_count(amount) or not 0 <= amount <= 2 for name, amount in distribution.items()
                ):
                    if neighbors:
                        distribution = {neighbors[0]: 2}
                    else:
                        distribution = {}
                effects = [
                    {"type": "add_influence", "faction": "ussr", "country": "South Africa", "amount": 1},
                    *({"type": "add_influence", "faction": "ussr", "country": name, "amount": amount} for name, amount in distribution.items() if amount),
                ]
        elif handler == "puppet_governments":
            choices = (event_choices or {}).get("puppet_governments")
            if (
                not isinstance(choices, list) or len(choices) != 3 or len(set(choices)) != 3
                or any(
                    not isinstance(name, str) or name not in data["countries"]
                    or game_data.get("countries", {}).get(name, {}).get("us", 0)
                    or game_data.get("countries", {}).get(name, {}).get("ussr", 0)
                    for name in choices
                )
            ):
                # Try to auto-pick valid countries (for RL/training)
                candidates = [
                    name for name in data["countries"].keys()
                    if not game_data.get("countries", {}).get(name, {}).get("us", 0)
                    and not game_data.get("countries", {}).get(name, {}).get("ussr", 0)
                ]
                if len(candidates) < 3:
                    raise ValueError("Puppet Governments requires three distinct countries with no influence")
                choices = candidates[:3]
            effects = [{"type": "add_influence", "faction": "us", "country": name, "amount": 1} for name in choices]
        elif handler == "socialist_governments":
            if game_data.get("persistent_events", {}).get("socialist_governments_cancelled"):
                raise EventPrevented("Socialist Governments is canceled by The Iron Lady")
            distribution = (event_choices or {}).get("socialist_governments")
            western_europe = {
                "U.K.", "Norway", "Sweden", "Denmark", "Benelux", "France",
                "Spain/Portugal", "W. Germany", "Italy", "Greece", "Turkey",
            }
            if not isinstance(distribution, dict) or sum(distribution.values()) != 3 or any(
                name not in western_europe or name not in game_data.get("countries", {})
                or not isinstance(amount, int) or not 0 <= amount <= 2
                or amount > game_data["countries"][name].get("us", 0)
                for name, amount in distribution.items()
            ):
                raise ValueError("Socialist Governments removes three US influence in Western Europe, at most two per country")
            effects = [
                {"type": "remove_influence", "faction": "us", "country": name, "amount": amount}
                for name, amount in distribution.items() if amount
            ]
        elif handler == "warsaw_pact_formed":
            choice = (event_choices or {}).get("warsaw_pact_formed")
            eastern_europe = {"E. Germany", "Poland", "Czechoslovakia", "Hungary", "Romania", "Bulgaria"}
            if not isinstance(choice, dict):
                raise ValueError("Warsaw Pact Formed requires a selected effect")
            if choice.get("mode") == "remove_us":
                targets = choice.get("countries")
                if not isinstance(targets, list) or len(targets) != 4 or len(set(targets)) != 4 or any(
                    name not in eastern_europe or game_data.get("countries", {}).get(name, {}).get("us", 0) <= 0
                    for name in targets
                ):
                    raise ValueError("Warsaw Pact removal requires four distinct Eastern European countries with US influence")
                effects = [
                    {"type": "remove_influence", "faction": "us", "country": name, "amount": game_data["countries"][name]["us"]}
                    for name in targets
                ]
            elif choice.get("mode") == "add_ussr":
                distribution = choice.get("distribution")
                if not isinstance(distribution, dict) or sum(distribution.values()) != 5 or any(
                    name not in eastern_europe or not isinstance(amount, int) or not 0 <= amount <= 2
                    for name, amount in distribution.items()
                ):
                    raise ValueError("Warsaw Pact placement requires five USSR influence in Eastern Europe, at most two per country")
                effects = [
                    {"type": "add_influence", "faction": "ussr", "country": name, "amount": amount}
                    for name, amount in distribution.items() if amount
                ]
            else:
                raise ValueError("Warsaw Pact Formed mode must be remove_us or add_ussr")
        elif handler == "independent_reds":
            country = (event_choices or {}).get("independent_reds")
            eligible = {"Yugoslavia", "Romania", "Bulgaria", "Hungary", "Czechoslovakia"}
            if not isinstance(country, str) or country not in eligible or country not in game_data.get("countries", {}):
                raise ValueError("Independent Reds requires one of the five listed Eastern European countries")
            influence = game_data["countries"][country]
            add = max(0, influence.get("ussr", 0) - influence.get("us", 0))
            effects = [{"type": "add_influence", "faction": "us", "country": country, "amount": add}]
        elif handler == "suez_crisis":
            distribution = (event_choices or {}).get("suez_crisis")
            eligible = {"France", "U.K.", "Israel"}
            removable = sum(
                min(2, game_data.get("countries", {}).get(name, {}).get("us", 0))
                for name in eligible
            )
            if removable < 4:
                raise EventPrevented("Suez Crisis cannot remove four US influence from its eligible countries")
            if not isinstance(distribution, dict) or sum(distribution.values()) != 4 or any(
                name not in eligible or not isinstance(amount, int) or not 0 <= amount <= 2
                or amount > game_data.get("countries", {}).get(name, {}).get("us", 0)
                for name, amount in distribution.items()
            ):
                raise ValueError("Suez Crisis removes four US influence from France, the U.K., and Israel, at most two per country")
            effects = [
                {"type": "remove_influence", "faction": "us", "country": name, "amount": amount}
                for name, amount in distribution.items() if amount
            ]
        elif handler == "arms_race":
            military = game_data.get("tracks", {}).get("military_operations", {})
            own_ops = military.get(phasing_faction, 0)
            opposing_ops = military.get("ussr" if phasing_faction == "us" else "us", 0)
            amount = 3 if own_ops > opposing_ops and own_ops >= game_data.get("tracks", {}).get("defcon", 5) else 1 if own_ops > opposing_ops else 0
            effects = [{"type": "gain_vp", "faction": phasing_faction, "amount": amount}]
        elif handler == "cultural_revolution":
            china_owner = game_data.get("china_card", {}).get("owner")
            if china_owner == "us":
                effects = [{"type": "transfer_china_card", "owner": "ussr", "face_up": True}]
            else:
                effects = [{"type": "gain_vp", "faction": "ussr", "amount": 1}]
        elif handler == "u2_incident":
            effects = [{"type": "gain_vp", "faction": "ussr", "amount": 1}]
        elif handler == "opec":
            if game_data.get("persistent_events", {}).get("north_sea_oil"):
                raise EventPrevented("OPEC is unplayable after North Sea Oil")
            oil_countries = {"Egypt", "Iran", "Libya", "Saudi Arabia", "Iraq", "Gulf States", "Venezuela"}
            points = sum(
                1 for name in oil_countries
                if name in data["countries"] and name in game_data.get("countries", {})
                and controlled_by(game_data["countries"][name], data["countries"][name]) == "ussr"
            )
            effects = [{"type": "gain_vp", "faction": "ussr", "amount": points}]
        elif handler == "oas_founded":
            distribution = (event_choices or {}).get("oas_founded")
            allowed = {
                name for name, country in data["countries"].items()
                if country.get("region") in {"Central America", "South America"}
            }
            if not isinstance(distribution, dict) or sum(distribution.values()) != 2 or any(
                not isinstance(name, str) or name not in allowed
                or not isinstance(amount, int) or not 0 <= amount <= 2
                for name, amount in distribution.items()
            ):
                raise ValueError("OAS Founded requires two US influence across Central/South America")
            effects = [
                {"type": "add_influence", "faction": "us", "country": name, "amount": amount}
                for name, amount in distribution.items() if amount
            ]
        elif handler == "liberation_theology":
            distribution = (event_choices or {}).get("liberation_theology")
            allowed = {
                name for name, country in data["countries"].items()
                if country.get("region") == "Central America"
            }
            if not isinstance(distribution, dict) or sum(distribution.values()) != 3 or any(
                not isinstance(name, str) or name not in allowed
                or not isinstance(amount, int) or not 0 <= amount <= 2
                for name, amount in distribution.items()
            ):
                raise ValueError("Liberation Theology requires three USSR influence, at most two per Central American country")
            effects = [
                {"type": "add_influence", "faction": "ussr", "country": name, "amount": amount}
                for name, amount in distribution.items() if amount
            ]
        elif handler == "the_voice_of_america":
            distribution = (event_choices or {}).get("the_voice_of_america")
            if not isinstance(distribution, dict) or not 0 <= sum(distribution.values()) <= 4 or any(
                not isinstance(name, str) or name not in data["countries"]
                or data["countries"][name].get("region") == "Europe"
                or not isinstance(amount, int) or not 0 <= amount <= 2
                or amount > game_data.get("countries", {}).get(name, {}).get("ussr", 0)
                for name, amount in distribution.items()
            ):
                raise ValueError("The Voice of America removes up to four USSR influence outside Europe, at most two per country")
            effects = [
                {"type": "remove_influence", "faction": "ussr", "country": name, "amount": amount}
                for name, amount in distribution.items() if amount
            ]
        elif handler == "marine_barracks_bombing":
            distribution = (event_choices or {}).get("marine_barracks_bombing")
            middle_east = {
                name for name, country in data["countries"].items()
                if country.get("region") == "Middle East"
            }
            if not isinstance(distribution, dict) or not 0 <= sum(distribution.values()) <= 2 or any(
                not isinstance(name, str) or name not in middle_east
                or not isinstance(amount, int) or not 0 <= amount <= game_data.get("countries", {}).get(name, {}).get("us", 0)
                for name, amount in distribution.items()
            ):
                raise ValueError("Marine Barracks Bombing removes up to two additional US influence from Middle East countries")
            lebanon_us = game_data.get("countries", {}).get("Lebanon", {}).get("us", 0)
            effects = [
                {"type": "remove_influence", "faction": "us", "country": "Lebanon", "amount": lebanon_us},
                *(
                    {"type": "remove_influence", "faction": "us", "country": name, "amount": amount}
                    for name, amount in distribution.items() if amount
                ),
            ]
        elif handler == "alliance_for_progress":
            controlled_battlegrounds = 0
            for name, influence in game_data.get("countries", {}).items():
                country = data["countries"].get(name)
                if country and country.get("battleground") and country.get("region") in {
                    "Central America", "South America"
                } and controlled_by(influence, country) == "us":
                    controlled_battlegrounds += 1
            effects = [{"type": "gain_vp", "faction": "us", "amount": controlled_battlegrounds}]
        elif handler == "glasnost":
            effects = [
                {"type": "gain_vp", "faction": "ussr", "amount": 2},
                {"type": "adjust_defcon", "amount": 1},
            ]
        elif handler == "an_evil_empire":
            effects = [{"type": "gain_vp", "faction": "us", "amount": 1}]
        elif handler == "pershing_ii_deployed":
            choices = (event_choices or {}).get("pershing_ii_deployed", [])
            if not isinstance(choices, list) or len(choices) > 3 or len(set(choices)) != len(choices):
                raise ValueError("Pershing II requires up to three distinct Western European countries")
            # Western Europe is the set west of the Iron Curtain, explicitly listed by the rules.
            valid_targets = {
                "Canada", "U.K.", "Norway", "Sweden", "Denmark", "Benelux",
                "France", "Spain/Portugal", "W. Germany", "Italy", "Greece", "Turkey",
            }
            if any(country not in valid_targets or country not in game_data.get("countries", {}) for country in choices):
                raise ValueError("Pershing II targets must be Western European countries on the board")
            effects = [
                {"type": "gain_vp", "faction": "ussr", "amount": 1},
                *(
                    {"type": "remove_influence", "faction": "us", "country": country, "amount": 1}
                    for country in choices
                ),
            ]
        else:
            effects = [
                {"type": "gain_vp", "faction": "us", "amount": 1},
                *(
                    {"type": "add_influence", "faction": "us", "country": country, "amount": 1}
                    for country in ("Israel", "Jordan", "Egypt")
                ),
            ]
        updated = apply_event_effects(game_data, effects, data)
        if handler == "camp_david_accords":
            updated.setdefault("persistent_events", {})["arab_israeli_war_cancelled"] = True
        elif handler == "de_gaulle_leads_france":
            updated.setdefault("persistent_events", {})["nato_cancelled_countries"] = sorted(
                set(updated.setdefault("persistent_events", {}).get("nato_cancelled_countries", [])) | {"France"}
            )
        elif handler == "john_paul_ii_elected_pope":
            updated.setdefault("persistent_events", {})["solidarity_enabled"] = True
        elif handler == "iranian_hostage_crisis":
            updated.setdefault("persistent_events", {})["iranian_hostage_crisis"] = True
        elif handler == "the_iron_lady":
            updated.setdefault("persistent_events", {})["socialist_governments_cancelled"] = True
        elif handler == "willy_brandt":
            updated.setdefault("persistent_events", {})["nato_cancelled_countries"] = sorted(
                set(updated.setdefault("persistent_events", {}).get("nato_cancelled_countries", [])) | {"W. Germany"}
            )
        elif handler == "an_evil_empire":
            updated.setdefault("persistent_events", {})["flower_power_cancelled"] = True
            updated["persistent_events"].pop("flower_power", None)
        if handler == "glasnost":
            return resolve_event_bonus(
                updated, handler, "ussr", event_choices or {}, data, rng, phasing_faction,
            )
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}
    if handler == "abm_treaty":
        updated = apply_event_effects(
            game_data,
            [{"type": "adjust_defcon", "amount": 1}],
            country_data or load_country_data(),
        )
        return resolve_event_bonus(
            updated, handler, phasing_faction, event_choices or {},
            country_data or load_country_data(), rng, phasing_faction,
        )
    if handler == "nixon_plays_china":
        china_owner = (game_data.get("china_card") or {}).get("owner")
        if china_owner == "us":
            effects = [{"type": "gain_vp", "faction": "us", "amount": 2}]
        else:
            effects = [{"type": "transfer_china_card", "owner": "us", "face_up": False}]
        updated = apply_event_effects(game_data, effects, country_data or load_country_data())
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}
    if handler == "terrorism":
        if rng is None:
            raise ValueError("Terrorism requires the server RNG for random discards")
        victim = "ussr" if phasing_faction == "us" else "us"
        persistent = game_data.get("persistent_events", {})
        discard_count = 2 if phasing_faction == "ussr" and persistent.get("iranian_hostage_crisis") else 1
        updated = deepcopy(game_data)
        victim_hand = updated.setdefault("hands", {}).setdefault(victim, [])
        discard_zone = updated.setdefault("discard_pile", [])
        # Discards go straight to the discard pile; their events do not occur.
        for _ in range(min(discard_count, len(victim_hand))):
            discard_zone.append(victim_hand.pop(rng.randrange(len(victim_hand))))
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}
    if handler == "aldrich_ames_remix":
        selected = (event_choices or {}).get("aldrich_ames_remix")
        us_hand = game_data.get("hands", {}).get("us", [])
        if not us_hand:
            # Nothing to discard: the event has no effect.
            return {"game_data": deepcopy(game_data), "event_triggered": True, "terminal_result": None}
        index = (
            next((i for i, card_in_hand in enumerate(us_hand) if card_in_hand.get("id") == selected), None)
            if isinstance(selected, int)
            else None
        )
        if index is None:
            raise ValueError("Aldrich Ames Remix requires a card id from the US hand")
        updated = deepcopy(game_data)
        discarded = updated["hands"]["us"].pop(index)
        updated.setdefault("discard_pile", []).append(discarded)
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}
    if handler == "awacs_sale_to_saudis":
        data = country_data or load_country_data()
        updated = apply_event_effects(
            game_data,
            [
                {"type": "add_influence", "faction": "us", "country": "Saudi Arabia", "amount": 2},
                {"type": "set_persistent_event", "name": "awacs_sale_played", "active": True},
            ],
            data,
        )
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}
    if handler == "muslim_revolution":
        # Blocked by the awacs_sale_played flag set by AWACS Sale to Saudis (110).
        if game_data.get("persistent_events", {}).get("awacs_sale_played"):
            raise EventPrevented("Muslim Revolution cannot be played after AWACS Sale to Saudis")
        allowed = {"Sudan", "Iran", "Iraq", "Egypt", "Libya", "Saudi Arabia", "Syria", "Jordan"}
        choices = (event_choices or {}).get("muslim_revolution")
        if (
            not isinstance(choices, list)
            or len(choices) != 2
            or not all(isinstance(name, str) and name in allowed for name in choices)
            or choices[0] == choices[1]
        ):
            raise ValueError("Muslim Revolution requires two distinct listed countries")
        data = country_data or load_country_data()
        board = game_data.get("countries", {})
        effects = [
            {
                "type": "remove_influence",
                "faction": "us",
                "country": name,
                "amount": board.get(name, {}).get("us", 0),
            }
            for name in choices
        ]
        updated = apply_event_effects(game_data, effects, data)
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}
    if handler == "nuclear_test_ban":
        current_defcon = game_data.get("tracks", {}).get("defcon")
        if not isinstance(current_defcon, int) or not 1 <= current_defcon <= 5:
            raise ValueError("Invalid DEFCON track")
        updated = apply_event_effects(
            game_data,
            [
                {"type": "gain_vp", "faction": phasing_faction, "amount": current_defcon - 2},
                {"type": "adjust_defcon", "amount": 2},
            ],
            country_data or load_country_data(),
        )
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}
    if handler == "how_i_learned_to_stop_worrying":
        level = chosen_defcon
        if not isinstance(level, int) or not 1 <= level <= 5:
            raise ValueError("How I Learned to Stop Worrying requires chosen_defcon from 1 to 5")
        current_defcon = game_data.get("tracks", {}).get("defcon", 5)
        if not isinstance(current_defcon, int) or not 1 <= current_defcon <= 5:
            raise ValueError("Invalid DEFCON track")
        updated = apply_event_effects(
            game_data,
            [{"type": "adjust_defcon", "amount": level - current_defcon}],
            country_data or load_country_data(),
        )
        military = dict(updated["tracks"].get("military_operations", {}))
        military[phasing_faction] = 5
        updated["tracks"]["military_operations"] = military
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}
    if handler == "kitchen_debates":
        data = country_data or load_country_data()
        bg_by_faction = {side: 0 for side in FACTIONS}
        for name, influence in game_data.get("countries", {}).items():
            country = data["countries"].get(name)
            if not country or not country.get("battleground"):
                continue
            controller = controlled_by(influence, country)
            if controller:
                bg_by_faction[controller] += 1
        updated = deepcopy(game_data)
        if bg_by_faction[phasing_faction] > bg_by_faction["ussr" if phasing_faction == "us" else "us"]:
            tracks = dict(updated.get("tracks", {}))
            tracks["victory_points"] = tracks.get("victory_points", 0) + (2 if phasing_faction == "us" else -2)
            updated["tracks"] = tracks
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}
    if handler in {"fidel", "romanian_abdication", "nasser"}:
        data = country_data or load_country_data()
        country_name = {
            "fidel": "Cuba",
            "romanian_abdication": "Romania",
            "nasser": "Egypt",
        }[handler]
        if country_name not in game_data.get("countries", {}) or country_name not in data["countries"]:
            raise ValueError(f"Missing event country: {country_name}")
        influence = game_data["countries"][country_name]
        effects: list[dict[str, Any]] = []
        if handler == "nasser":
            effects.extend([
                {"type": "add_influence", "faction": "ussr", "country": country_name, "amount": 2},
                {"type": "remove_influence", "faction": "us", "country": country_name, "amount": (influence.get("us", 0) + 1) // 2},
            ])
        else:
            effects.append({
                "type": "remove_influence",
                "faction": "us",
                "country": country_name,
                "amount": influence.get("us", 0),
            })
            control_target = max(
                influence.get("ussr", 0),
                data["countries"][country_name]["stability"],
            )
            if control_target > influence.get("ussr", 0):
                effects.append({
                    "type": "add_influence",
                    "faction": "ussr",
                    "country": country_name,
                    "amount": control_target - influence.get("ussr", 0),
                })
        updated = apply_event_effects(game_data, effects, data)
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}
    if handler == "five_year_plan" and card["id"] == 5:
        if rng is None:
            raise ValueError("Five Year Plan requires the persisted server RNG")
        opponent_hand = game_data.get("hands", {}).get("ussr")
        if not isinstance(opponent_hand, list) or not opponent_hand:
            # No card to discard - just play event effect (if any), skip discard
            effects: list[dict[str, Any]] = []
            updated = apply_event_effects(game_data, effects, country_data or load_country_data())
            return {"game_data": updated, "event_triggered": True, "terminal_result": None}
        result = deepcopy(game_data)
        discarded = result["hands"]["ussr"].pop(rng.randrange(len(opponent_hand)))
        discarded_event = {"event_triggered": False, "game_data": result, "terminal_result": None}
        if discarded.get("alignment") == "us" and not discarded.get("scoring"):
            discarded_event = resolve_card_event(
                result,
                discarded,
                "us",
                mode="event",
                country_data=country_data,
                rng=rng,
                _event_stack=_event_stack,
            )
            result = discarded_event["game_data"]
        zone = "removed_cards" if discarded.get("event_removed") and discarded_event["event_triggered"] else "discard_pile"
        result.setdefault(zone, []).append(discarded)
        return {
            "game_data": result,
            "event_triggered": True,
            "terminal_result": discarded_event.get("terminal_result"),
        }
    if handler in CHOICE_EFFECT_HANDLERS:
        return _resolve_choice_effect_event(
            game_data,
            handler,
            phasing_faction,
            country_data=country_data,
            event_choices=event_choices,
        )
    if handler in DICE_AND_FLAG_HANDLERS:
        return _resolve_dice_and_flag_event(
            game_data,
            handler,
            phasing_faction,
            country_data=country_data,
            rng=rng,
            event_choices=event_choices,
        )
    if handler == "wargames":
        choice = (event_choices or {}).get("wargames")
        if choice is None or choice is False:
            # Ending the game is optional; declining leaves the event with no effect.
            return {"game_data": deepcopy(game_data), "event_triggered": True, "terminal_result": None}
        if choice is not True:
            raise ValueError("Wargames requires a boolean end-game choice")
        if game_data.get("tracks", {}).get("defcon") != 2:
            raise ValueError("Wargames may end the game only at DEFCON 2")
        opponent = "ussr" if phasing_faction == "us" else "us"
        updated = apply_event_effects(
            game_data,
            [{"type": "gain_vp", "faction": opponent, "amount": 6}],
            country_data or load_country_data(),
        )
        relative_vp = updated["tracks"]["victory_points"]
        if relative_vp == 0:
            raise ValueError("Wargames cannot end the game with tied victory points")
        winner = "us" if relative_vp > 0 else "ussr"
        return {
            "game_data": updated,
            "event_triggered": True,
            "terminal_result": {"winner": winner, "reason": "wargames"},
        }

    if handler != "duck_and_cover" or card["id"] != 4:
        raise ValueError(f"No implemented event handler for card {card['id']} ({card.get('name', 'unknown')})")
    tracks = game_data.get("tracks", {})
    current_defcon = tracks.get("defcon")
    if not isinstance(current_defcon, int) or not 1 <= current_defcon <= 5:
        raise ValueError("Invalid DEFCON track")
    next_defcon = max(1, current_defcon - 1)
    effects = [
        {"type": "adjust_defcon", "amount": -1},
        {"type": "gain_vp", "faction": "us", "amount": 5 - next_defcon},
    ]
    updated = apply_event_effects(game_data, effects, country_data or load_country_data())
    terminal = check_victory_conditions(
        updated["tracks"].get("victory_points", 0),
        updated["tracks"]["defcon"],
        phasing_faction,
    )
    return {"game_data": updated, "event_triggered": True, "terminal_result": terminal}


CHOICE_EFFECT_HANDLERS = frozenset({"vietnam_revolts", "marshall_plan", "de_stalinization", "captured_nazi_scientist", "ussuri_river_skirmish", "one_small_step"})

# Eastern-bloc European countries; every other "Europe" region country counts as Western Europe.
EASTERN_EUROPE = frozenset({"E. Germany", "Poland", "Czechoslovakia", "Hungary", "Romania", "Bulgaria", "Yugoslavia", "Albania"})


def _is_count(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _resolve_choice_effect_event(
    game_data: dict[str, Any],
    handler: str,
    phasing_faction: str,
    *,
    country_data: dict[str, Any] | None,
    event_choices: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve validated Twilight Struggle events that need player choices or only influence effects.

    Vietnam Revolts' Soviet operations bonus is recorded as a turn-scoped flag; the
    operations engine does not consume it yet.
    """
    data = country_data or load_country_data()
    countries = game_data.get("countries", {})
    choices = event_choices or {}
    turn = game_data.get("turn", 1)

    def controller_of(name: str) -> str | None:
        if name not in data["countries"]:
            return None
        return controlled_by(countries.get(name, {}), data["countries"][name])

    if handler == "vietnam_revolts":
        updated = apply_event_effects(
            game_data,
            [{"type": "add_influence", "faction": "ussr", "country": "Vietnam", "amount": 2}],
            data,
        )
        updated.setdefault("persistent_events", {})["vietnam_revolts"] = {"expires_turn": turn}
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}

    if handler == "marshall_plan":
        selected = choices.get("marshall_plan")
        if not isinstance(selected, list) or len(selected) != 7 or len(set(selected)) != 7:
            raise ValueError("Marshall Plan requires seven distinct Western European countries")
        for name in selected:
            if (
                not isinstance(name, str)
                or name not in data["countries"]
                or data["countries"][name].get("region") != "Europe"
                or name in EASTERN_EUROPE
                or controller_of(name) == "ussr"
            ):
                raise ValueError(f"Marshall Plan cannot target {name!r}")
        effects = [{"type": "add_influence", "faction": "us", "country": name, "amount": 1} for name in selected]
        updated = apply_event_effects(game_data, effects, data)
        updated.setdefault("persistent_events", {})["marshall_plan"] = True
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}

    if handler == "one_small_step":
        # Only usable by a player behind on the Space Race track: move 2 boxes (capped at 8),
        # gaining the VP value of the second box only. Otherwise the event has no effect.
        track = (game_data.get("tracks") or {}).get("space_race") or {"us": 0, "ussr": 0}
        opponent = "ussr" if phasing_faction == "us" else "us"
        position = track.get(phasing_faction, 0)
        if position >= track.get(opponent, 0):
            return {"game_data": deepcopy(game_data), "event_triggered": True, "terminal_result": None}
        updated = deepcopy(game_data)
        advance_marker_in_place(updated, phasing_faction, 2)
        return {"game_data": updated, "event_triggered": True, "terminal_result": _space_terminal(updated, phasing_faction)}

    if handler == "captured_nazi_scientist":
        # Advances the phasing player's Space Race marker one box (track has 8 boxes) and awards that box's VP.
        updated = deepcopy(game_data)
        advance_marker_in_place(updated, phasing_faction, 1)
        return {"game_data": updated, "event_triggered": True, "terminal_result": _space_terminal(updated, phasing_faction)}

    if handler == "ussuri_river_skirmish":
        owner = game_data.get("china_card", {}).get("owner")
        if owner == "ussr":
            updated = apply_event_effects(
                game_data,
                [{"type": "transfer_china_card", "owner": "us", "face_up": True}],
                data,
            )
            return {"game_data": updated, "event_triggered": True, "terminal_result": None}
        if owner != "us":
            # Shouldn't happen if validation prevents it, but be defensive
            raise ValueError("Ussuri River Skirmish requires The China Card to be held by a superpower")
        placement = choices.get("ussuri_river_skirmish")
        if not isinstance(placement, dict) or not placement:
            # Auto-pick first valid Asian countries
            asian = [n for n, c in data["countries"].items() if c.get("region") == "Asia"]
            if not asian:
                raise ValueError("Ussuri River Skirmish requires an Asian influence placement")
            placement = {asian[0]: 4} if len(asian) == 1 else {asian[0]: 2, asian[1]: 2}
        if sum(placement.values()) != 4 or not all(_is_count(v) and 1 <= v <= 2 for v in placement.values()):
            # Try to normalize
            asian = [n for n, c in data["countries"].items() if c.get("region") == "Asia"]
            placement = {asian[0]: 4} if len(asian) == 1 else {asian[0]: 2, asian[1]: 2}
        effects = []
        for name, amount in placement.items():
            if name not in data["countries"] or data["countries"][name].get("region") != "Asia":
                continue  # skip invalid
            effects.append({"type": "add_influence", "faction": "us", "country": name, "amount": amount})
        if not effects:
            asian = [n for n, c in data["countries"].items() if c.get("region") == "Asia"]
            placement = {asian[0]: 4} if asian else {}
            for name, amount in placement.items():
                effects.append({"type": "add_influence", "faction": "us", "country": name, "amount": amount})
        updated = apply_event_effects(game_data, effects, data)
        return {"game_data": updated, "event_triggered": True, "terminal_result": None}

    # de_stalinization: relocate up to 4 USSR influence to non-US-controlled countries (max 2 per country).
    choice = choices.get("de_stalinization")
    if not isinstance(choice, dict):
        raise ValueError("De-Stalinization requires a relocation choice")
    source = choice.get("from")
    target = choice.get("to")
    if not isinstance(source, dict) or not isinstance(target, dict) or not source or not target:
        raise ValueError("De-Stalinization requires 'from' and 'to' relocation maps")
    if not all(_is_count(v) and v > 0 for v in source.values()) or not all(_is_count(v) and v > 0 for v in target.values()):
        raise ValueError("De-Stalinization amounts must be positive integers")
    moved = sum(source.values())
    if moved > 4 or moved != sum(target.values()):
        raise ValueError("De-Stalinization relocates up to 4 influence and must place every point moved")
    effects: list[dict[str, Any]] = []
    for name, amount in source.items():
        if name not in data["countries"] or countries.get(name, {}).get("ussr", 0) < amount:
            raise ValueError(f"De-Stalinization cannot remove USSR influence from {name!r}")
        effects.append({"type": "remove_influence", "faction": "ussr", "country": name, "amount": amount})
    for name, amount in target.items():
        if name not in data["countries"] or controller_of(name) == "us" or amount > 2:
            raise ValueError(f"De-Stalinization cannot place USSR influence in {name!r}")
        effects.append({"type": "add_influence", "faction": "ussr", "country": name, "amount": amount})
    updated = apply_event_effects(game_data, effects, data)
    return {"game_data": updated, "event_triggered": True, "terminal_result": None}


def _resolve_dice_and_flag_event(
    game_data: dict[str, Any],
    handler: str,
    phasing_faction: str,
    *,
    country_data: dict[str, Any] | None,
    rng: random.Random | None,
    event_choices: dict[str, Any] | None,
) -> dict[str, Any]:
    """Resolve batch 2/3 Twilight Struggle events (die rolls, choices, persistent flags).

    Optional regional free actions and Olympic boycott Ops accept an inline
    `bonus_operations` choice. Other recorded bonus flags still require audits.
    """
    data = country_data or load_country_data()
    countries = game_data.get("countries", {})
    persistent = game_data.get("persistent_events", {})
    choices = event_choices or {}
    opponent = "ussr" if phasing_faction == "us" else "us"
    turn = game_data.get("turn", 1)
    scoring_config = load_scoring_config()

    def influence(name: str, faction: str) -> int:
        return countries.get(name, {}).get(faction, 0)

    def require_country(name: Any) -> None:
        if not isinstance(name, str) or name not in data["countries"] or name not in countries:
            raise ValueError(f"{handler} requires a valid country on the board")

    def controller_of(name: str) -> str | None:
        if name not in data["countries"]:
            return None
        return controlled_by(countries.get(name, {}), data["countries"][name])

    def controlled_adjacent(target: str, faction: str) -> int:
        return sum(1 for neighbor in data["adjacency"].get(target, []) if controller_of(neighbor) == faction)

    def roll_die() -> int:
        if rng is None:
            raise ValueError(f"{handler} requires the server RNG for die rolls")
        return rng.randint(1, 6)

    def add_military(state: dict[str, Any], faction: str, amount: int) -> None:
        tracks = state.setdefault("tracks", {})
        military = dict(tracks.get("military_operations", {}))
        military[faction] = military.get(faction, 0) + amount
        tracks["military_operations"] = military

    def replace_influence(target: str, victim: str, placer: str) -> list[dict[str, Any]]:
        amount = influence(target, victim)
        return [
            {"type": "remove_influence", "faction": victim, "country": target, "amount": amount},
            {"type": "add_influence", "faction": placer, "country": target, "amount": amount},
        ]

    def finish(state: dict[str, Any]) -> dict[str, Any]:
        return {"game_data": state, "event_triggered": True, "terminal_result": None}

    def flag(state: dict[str, Any], name: str, value: Any) -> None:
        state.setdefault("persistent_events", {})[name] = value

    expiry = {"expires_turn": turn}

    if handler in {"korean_war", "arab_israeli_war"}:
        if handler == "arab_israeli_war" and persistent.get("arab_israeli_war_cancelled"):
            raise EventPrevented("Arab-Israeli War is no longer playable after Camp David Accords")
        target = "S. Korea" if handler == "korean_war" else "Israel"
        require_country(target)
        penalty = controlled_adjacent(target, "us")
        if handler == "arab_israeli_war" and controller_of("Israel") == "us":
            penalty += 1
        modified = roll_die() - penalty
        state = deepcopy(game_data)
        add_military(state, "ussr", 2)
        effects: list[dict[str, Any]] = []
        if modified >= 4:
            effects = [{"type": "gain_vp", "faction": "ussr", "amount": 2}, *replace_influence(target, "us", "ussr")]
        return finish(apply_event_effects(state, effects, data))

    if handler == "indo_pakistani_war":
        target = choices.get("indo_pakistani_war")
        if target not in {"India", "Pakistan"}:
            raise ValueError("Indo-Pakistani War requires a target of India or Pakistan")
        require_country(target)
        modified = roll_die() - controlled_adjacent(target, opponent)
        state = deepcopy(game_data)
        add_military(state, phasing_faction, 2)
        effects = []
        if modified >= 4:
            effects = [{"type": "gain_vp", "faction": phasing_faction, "amount": 2}, *replace_influence(target, opponent, phasing_faction)]
        return finish(apply_event_effects(state, effects, data))

    if handler == "iran_iraq_war":
        # The playing player chooses the invader (Iran or Iraq); the other is the target. Roll one die and subtract
        # 1 per opponent-controlled country adjacent to the target. 4-6 is victory: 2 VP and replace all opponent
        # influence in the target. Playing adds 2 Military Operations regardless of outcome.
        invader = choices.get("iran_iraq_war")
        if invader not in {"Iran", "Iraq"}:
            raise ValueError("Iran-Iraq War requires the invader to be Iran or Iraq")
        target = "Iraq" if invader == "Iran" else "Iran"
        require_country(target)
        modified = roll_die() - sum(
            1 for neighbor in data["adjacency"].get(target, []) if controller_of(neighbor) == opponent
        )
        state = deepcopy(game_data)
        add_military(state, phasing_faction, 2)
        effects = []
        if modified >= 4:
            effects = [{"type": "gain_vp", "faction": phasing_faction, "amount": 2}, *replace_influence(target, opponent, phasing_faction)]
        updated = apply_event_effects(state, effects, data)
        terminal = check_victory_conditions(
            updated["tracks"]["victory_points"], updated["tracks"]["defcon"], phasing_faction,
        )
        return {"game_data": updated, "event_triggered": True, "terminal_result": terminal}

    if handler == "brush_war":
        target = choices.get("brush_war")
        require_country(target)
        if data["countries"][target].get("stability") not in {1, 2}:
            raise ValueError("Brush War targets must have stability 1 or 2")
        persistent = game_data.get("persistent_events") or {}
        if (
            "nato" in persistent
            and data["countries"][target].get("region") == "Europe"
            and target not in (persistent.get("nato_cancelled_countries") or [])
            and controller_of(target) == "us"
        ):
            raise ValueError("Brush War cannot target US-controlled Europe while NATO is in effect")
        modified = roll_die() - controlled_adjacent(target, opponent)
        state = deepcopy(game_data)
        add_military(state, phasing_faction, 3)
        effects = []
        if modified >= 3:
            effects = [{"type": "gain_vp", "faction": phasing_faction, "amount": 1}, *replace_influence(target, opponent, phasing_faction)]
        return finish(apply_event_effects(state, effects, data))

    if handler == "summit":
        def dominated_or_controlled(faction: str) -> int:
            result = 0
            for region in scoring_config["regions"]:
                scored = score_region(region, countries, data, scoring_config)
                if scored["domination"][faction] or scored["control"][faction]:
                    result += 1
            return result

        us_roll = roll_die() + dominated_or_controlled("us")
        ussr_roll = roll_die() + dominated_or_controlled("ussr")
        state = deepcopy(game_data)
        if us_roll == ussr_roll:
            return finish(state)
        high_roller = "us" if us_roll > ussr_roll else "ussr"
        effects = [{"type": "gain_vp", "faction": high_roller, "amount": 2}]
        move = choices.get("summit_defcon", 0)
        if move not in {-1, 0, 1}:
            raise ValueError("Summit DEFCON move must be -1, 0, or 1")
        if move:
            effects.append({"type": "adjust_defcon", "amount": move})
        return finish(apply_event_effects(state, effects, data))

    if handler == "us_japan_pact":
        require_country("Japan")
        target = influence("Japan", "ussr") + data["countries"]["Japan"]["stability"]
        amount = max(0, target - influence("Japan", "us"))
        state = apply_event_effects(game_data, [{"type": "add_influence", "faction": "us", "country": "Japan", "amount": amount}], data)
        flag(state, "us_japan_pact", True)
        return finish(state)

    if handler == "cuban_missile_crisis":
        current = game_data.get("tracks", {}).get("defcon")
        if not isinstance(current, int) or not 1 <= current <= 5:
            raise ValueError("Invalid DEFCON track")
        state = apply_event_effects(game_data, [{"type": "adjust_defcon", "amount": 2 - current}], data)
        flag(state, "cuban_missile_crisis", {"faction": opponent, **expiry})
        return finish(state)

    if handler == "nuclear_subs":
        state = apply_event_effects(game_data, [], data)
        flag(state, "nuclear_subs", {"faction": "us", **expiry})
        return finish(state)

    if handler == "junta":
        country = choices.get("junta")
        allowed = {
            name for name, country_entry in data["countries"].items()
            if country_entry.get("region") in {"Central America", "South America"}
        }
        if country not in allowed:
            raise ValueError("Junta requires a Central or South American country")
        state = apply_event_effects(game_data, [{"type": "add_influence", "faction": phasing_faction, "country": country, "amount": 2}], data)
        return resolve_event_bonus(state, handler, phasing_faction, choices, data, rng, phasing_faction)

    if handler == "latin_american_death_squads":
        state = apply_event_effects(game_data, [], data)
        flag(state, "latin_american_death_squads", {"faction": phasing_faction, **expiry})
        return finish(state)

    if handler == "ortega_nicaragua":
        require_country("Nicaragua")
        state = apply_event_effects(
            game_data,
            [{"type": "remove_influence", "faction": "us", "country": "Nicaragua", "amount": influence("Nicaragua", "us")}],
            data,
        )
        return resolve_event_bonus(state, handler, "ussr", choices, data, rng, phasing_faction)

    if handler == "iran_contra_scandal":
        state = apply_event_effects(game_data, [], data)
        flag(state, "iran_contra_scandal", {"faction": "ussr", **expiry})
        return finish(state)

    if handler == "chernobyl":
        region = choices.get("chernobyl")
        if region not in scoring_config["regions"]:
            raise ValueError("Chernobyl requires a designated major region")
        state = apply_event_effects(game_data, [], data)
        flag(state, "chernobyl", {"region": region, **expiry})
        return finish(state)

    if handler == "tear_down_this_wall":
        require_country("E. Germany")
        state = apply_event_effects(
            game_data,
            [{"type": "add_influence", "faction": "us", "country": "E. Germany", "amount": 3}],
            data,
        )
        flag(state, "tear_down_this_wall", True)
        return resolve_event_bonus(state, handler, "us", choices, data, rng, phasing_faction)

    if handler == "olympic_games":
        # Opponent chooses participate or boycott; sponsor is the phasing faction.
        # The sponsor's boycott Operations (as a 4-Ops card) is recorded as a flag for the operations layer.
        decision = choices.get("olympic_games")
        if decision not in {"participate", "boycott"}:
            raise ValueError("Olympic Games requires a participate or boycott decision")
        if decision == "boycott":
            current = game_data.get("tracks", {}).get("defcon")
            if not isinstance(current, int) or not 1 <= current <= 5:
                raise ValueError("Invalid DEFCON track")
            state = apply_event_effects(game_data, [{"type": "adjust_defcon", "amount": -1}], data)
            flag(state, "olympic_games_boycott", {"sponsor": phasing_faction, **expiry})
            return resolve_event_bonus(state, handler, phasing_faction, choices, data, rng, phasing_faction)
        if "bonus_operations" in choices:
            raise ValueError("Olympic participation does not grant boycott bonus operations")
        while True:
            sponsor_roll = roll_die() + 2
            opponent_roll = roll_die()
            if sponsor_roll != opponent_roll:
                break
        winner = phasing_faction if sponsor_roll > opponent_roll else opponent
        state = apply_event_effects(game_data, [{"type": "gain_vp", "faction": winner, "amount": 2}], data)
        return finish(state)

    if handler == "cia_created":
        # USSR reveals its hand this turn; US may conduct Operations as if playing 1 Ops.
        state = apply_event_effects(game_data, [], data)
        flag(state, "cia_created", {"revealed": "ussr", "ops_faction": "us", "ops_value": 1, **expiry})
        return resolve_event_bonus(state, handler, "us", choices, data, rng, phasing_faction)

    if handler == "lone_gunman":
        # Reveal the current US hand, not cards acquired later (unlike CIA's explicit turn-long reveal).
        state = apply_event_effects(game_data, [], data)
        flag(state, "lone_gunman", {"revealed": "us", "ops_faction": "ussr", "ops_value": 1, **expiry})
        state.setdefault("_event_hand_reveals", {})["lone_gunman"] = {
            "viewer": "ussr", "faction": "us", "expires_turn": turn,
            "cards": deepcopy(state.get("hands", {}).get("us", [])),
        }
        return resolve_event_bonus(state, handler, "ussr", choices, data, rng, phasing_faction)

    raise ValueError(f"No implemented event handler for {handler}")
