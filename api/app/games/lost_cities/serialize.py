"""Serialization helpers for Lost Cities game state."""

from __future__ import annotations

from typing import Any

from app.games.lost_cities.validator import (
    COLORS,
    COLOR_SHORT,
    SHORT_TO_COLOR,
    INVESTMENT,
    card_number,
    is_investment,
    is_numbered,
    _calculate_expedition_score,
    _calculate_player_score,
)


def initial_game_data() -> dict[str, Any]:
    """Return the initial game data for a new game (delegates to validator)."""
    from app.games.lost_cities.validator import _initial_game_data
    return _initial_game_data()


def card_image_path(card: str) -> str:
    """Get the image path for a card."""
    color_short = card.split("_")[0]
    if is_investment(card):
        return f"/api/v1/img/lost_cities/cards/{color_short}_i.jpg"
    num = card_number(card)
    return f"/api/v1/img/lost_cities/cards/{color_short}_{num}.jpg"


def card_back_path() -> str:
    """Get the card back image path."""
    return "/api/v1/img/lost_cities/cards/card_backs.jpg"


def expedition_base_image(color: str) -> str:
    """Get the base image for an expedition color."""
    color_short = COLOR_SHORT[color]
    return f"/api/v1/img/lost_cities/cards/{color_short}_base.jpg"


def serialize_hand(hand: list[str], is_current_player: bool, is_ai: bool = False) -> list[dict[str, Any]]:
    """Serialize a player's hand for the screen.
    
    For the current human player, show actual cards.
    For AI opponent, show card backs.
    """
    result = []
    for idx, card in enumerate(hand):
        if is_current_player and not is_ai:
            result.append({
                "id": f"hand_{idx}",
                "card": card,
                "image": card_image_path(card),
                "color": card.split("_")[0],
                "value": card.split("_")[1],
                "is_investment": is_investment(card),
                "number": card_number(card),
                "face_up": True,
            })
        else:
            result.append({
                "id": f"hand_{idx}",
                "card": card,
                "image": card_back_path(),
                "face_up": False,
            })
    return result


def serialize_expedition(cards: list[str]) -> list[dict[str, Any]]:
    """Serialize an expedition (list of cards played)."""
    result = []
    for idx, card in enumerate(cards):
        result.append({
            "id": f"exp_{idx}",
            "card": card,
            "image": card_image_path(card),
            "color": card.split("_")[0],
            "value": card.split("_")[1],
            "is_investment": is_investment(card),
            "number": card_number(card),
        })
    return result


def serialize_discard_pile(cards: list[str]) -> dict[str, Any]:
    """Serialize a discard pile (only top card fully visible)."""
    if not cards:
        return {
            "cards": [],
            "top_card": None,
            "count": 0,
        }
    top = cards[-1]
    return {
        "cards": cards,
        "top_card": {
            "card": top,
            "image": card_image_path(top),
            "color": top.split("_")[0],
            "value": top.split("_")[1],
            "is_investment": is_investment(top),
            "number": card_number(top),
        },
        "count": len(cards),
    }


def serialize_game_data(game_data: dict[str, Any], current_player_id: str) -> dict[str, Any]:
    """Convert full game_data to screen-ready format."""
    player_hands = game_data.get("player_hands", {})
    expeditions = game_data.get("expeditions", {})
    discard_piles = game_data.get("discard_piles", {})
    draw_pile = game_data.get("draw_pile", [])

    # Serialize hands
    serialized_hands = {}
    for pid, hand in player_hands.items():
        is_current = (pid == current_player_id)
        is_ai = (pid == "player_2")  # player_2 is always AI in this implementation
        serialized_hands[pid] = serialize_hand(hand, is_current, is_ai)

    # Serialize expeditions
    serialized_expeditions = {}
    for pid, exps in expeditions.items():
        serialized_expeditions[pid] = {}
        for color in COLORS:
            serialized_expeditions[pid][color] = serialize_expedition(exps.get(color, []))

    # Serialize discard piles
    serialized_discards = {}
    for color in COLORS:
        serialized_discards[color] = serialize_discard_pile(discard_piles.get(color, []))

    # Calculate current scores (for display during game)
    current_scores = {}
    for pid in ["player_1", "player_2"]:
        current_scores[pid] = _calculate_player_score(expeditions.get(pid, {}))

    return {
        "player_hands": serialized_hands,
        "expeditions": serialized_expeditions,
        "discard_piles": serialized_discards,
        "draw_pile": {
            "count": len(draw_pile),
            "image": card_back_path(),
        },
        "current_phase": game_data.get("current_phase", "play_a_card"),
        "current_player": game_data.get("current_player", "player_1"),
        "last_discarded": game_data.get("last_discarded"),
        "round": game_data.get("round", 1),
        "scores": game_data.get("scores", {"player_1": 0, "player_2": 0}),
        "current_scores": current_scores,
        "game_over": game_data.get("game_over", False),
        "round_over": game_data.get("round_over", False),
        "pending_draw": game_data.get("pending_draw", False),
    }


def state_response(
    game_data: dict[str, Any],
    winner: str | None = None,
    current_player_id: str | None = None,
) -> dict[str, Any]:
    """Convert game state to the response format the frontend play page expects."""
    if current_player_id is None:
        current_player_id = game_data.get("current_player", "player_1")

    return {
        "game_data": serialize_game_data(game_data, current_player_id),
        "winner": winner,
        "current_player_id": current_player_id,
    }