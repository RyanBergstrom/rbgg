"""Secret headline commitment and ordered resolution."""
from __future__ import annotations

from app.games.twilight_struggle.state_clone import fast_copy as deepcopy
import random
from typing import Any

from app.games.twilight_struggle.default_choices import candidate_choices
from app.games.twilight_struggle.events import resolve_card_event

FACTIONS = ("us", "ussr")
DEFECTORS_CARD_ID = 103


def resolve_headline_event(
    game_data: dict[str, Any],
    card: dict[str, Any],
    faction: str,
    country_data: dict[str, Any] | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Resolve a headline event with no player choice, using a deterministic default if needed.

    A headline resolves with no choices when its event allows it. If the event
    needs choices, the first legal candidate from the default-choice order is used.
    If none is legal, the ValueError propagates and the reveal fails closed.
    ``resolve_card_event`` never mutates its input, so no defensive copy is made here.
    """
    try:
        return resolve_card_event(
            game_data, card, faction, mode="event", country_data=country_data, rng=rng,
        )
    except ValueError as first_error:
        for choices in candidate_choices(game_data, card, faction):
            try:
                return resolve_card_event(
                    game_data, card, faction, mode="event", country_data=country_data,
                    rng=rng, event_choices=choices,
                )
            except ValueError:
                continue
        raise first_error


def submit_headline(game_data: dict[str, Any], faction: str, card_id: int) -> dict[str, Any]:
    """Commit a non-scoring card privately; reveal begins after both commits."""
    if faction not in FACTIONS:
        raise ValueError(f"Unknown faction: {faction}")
    if game_data.get("current_phase") != "headline":
        raise ValueError("headline selection is not active")
    headlines = game_data.get("headline_cards")
    hands = game_data.get("hands")
    if not isinstance(headlines, dict) or not isinstance(hands, dict):
        raise ValueError("game data is missing headline or hand state")
    if headlines.get(faction) is not None:
        raise ValueError(f"{faction} has already committed a headline")
    card = next((item for item in hands.get(faction, []) if item.get("id") == card_id), None)
    if card is None:
        raise ValueError(f"Card {card_id} is not in the {faction} hand")
    if card.get("scoring"):
        raise ValueError("scoring cards cannot be selected as headlines")
    result = deepcopy(game_data)
    result["headline_cards"][faction] = card_id
    if all(result["headline_cards"].get(side) is not None for side in FACTIONS):
        result["current_phase"] = "headline_reveal_ready"
    return result


def reveal_headlines(
    game_data: dict[str, Any],
    country_data: dict[str, Any] | None = None,
    rng: random.Random | None = None,
) -> dict[str, Any]:
    """Resolve both committed headline events in operations-priority order.

    Higher operations resolves first; USSR wins an operations tie. Unhandled
    events fail closed and leave the source game state untouched.
    """
    if game_data.get("current_phase") != "headline_reveal_ready":
        raise ValueError("both headline cards must be committed before reveal")
    selected = game_data.get("headline_cards", {})
    hands = game_data.get("hands", {})
    if any(selected.get(faction) is None for faction in FACTIONS):
        raise ValueError("both headline cards must be committed before reveal")
    cards: dict[str, dict[str, Any]] = {}
    for faction in FACTIONS:
        card = next(
            (item for item in hands.get(faction, []) if item.get("id") == selected[faction]),
            None,
        )
        if card is None or card.get("scoring"):
            raise ValueError(f"Invalid headline card for {faction}")
        cards[faction] = card
    order = sorted(FACTIONS, key=lambda side: (cards[side].get("operations", 0), side == "ussr"), reverse=True)
    result = deepcopy(game_data)
    # Defectors (103), played by the US in the headline phase, cancels the USSR headline event.
    defectors_cancels_ussr = selected["us"] == DEFECTORS_CARD_ID and selected["ussr"] != DEFECTORS_CARD_ID
    reveal_log = [
        {"faction": faction, "card_id": selected[faction], **({"canceled": True} if defectors_cancels_ussr and faction == "ussr" else {})}
        for faction in order
    ]
    for faction in order:
        card_id = selected[faction]
        current_card = next(card for card in result["hands"][faction] if card.get("id") == card_id)
        result["hands"][faction].remove(current_card)
        if faction == "ussr" and (defectors_cancels_ussr or card_id == DEFECTORS_CARD_ID):
            # Canceled or inert headline: the card is discarded without resolving its event.
            result.setdefault("discard_pile", []).append(current_card)
            continue
        event = resolve_headline_event(
            result,
            current_card,
            faction,
            country_data=country_data,
            rng=rng,
        )
        result = event["game_data"]
        if current_card.get("event_removed"):
            result.setdefault("removed_cards", []).append(current_card)
        else:
            result.setdefault("discard_pile", []).append(current_card)
        if event.get("terminal_result") is not None:
            result["terminal_result"] = event["terminal_result"]
            result["current_phase"] = "game_over"
            break
    result["revealed_headlines"] = reveal_log
    result["headline_cards"] = {"us": None, "ussr": None}
    result["current_player_faction"] = "ussr"
    result["current_player"] = result.get("player_by_faction", {}).get("ussr", "ussr")
    if result.get("current_phase") != "game_over":
        result["current_phase"] = "action_round"
        result["actions_taken"] = {"us": 0, "ussr": 0}
        result["action_round"] = 0
    return result
