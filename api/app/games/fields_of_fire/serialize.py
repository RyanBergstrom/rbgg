from __future__ import annotations

from typing import Any

from app.games.fields_of_fire.terrain import terrain_card


def _top_discard_card(game_data: dict[str, Any]) -> dict[str, Any] | None:
    deck = game_data.get("action_deck") or {}
    discard = deck.get("discard") or []
    if not discard:
        return None
    top_id = discard[-1]
    try:
        from app.games.fields_of_fire.action_deck import get_action_card, RESHUFFLE_CARD
        if top_id == RESHUFFLE_CARD:
            return {"card": top_id, "image_url": None}
        rec = get_action_card(top_id)
    except (KeyError, ImportError):
        return {"card": top_id, "image_url": None}
    ad = rec.get("action_details") or {}
    num = ad.get("card_number")
    image_url = None
    if isinstance(num, int) and num > 0:
        image_url = f"/api/v1/img/fof/cards/A{str(num).zfill(2)}.jpg"
    return {
        "card": top_id,
        "card_number": num,
        "action_attempt": ad.get("action_attempt"),
        "commands": ad.get("commands"),
        "image_url": image_url,
    }


def serialize_game_data(game_data: dict[str, Any]) -> dict[str, Any]:
    map_data = game_data.get("map", {}) or {}
    cards = []
    for c in map_data.get("cards", []) or []:
        if c is None:
            cards.append(None)
        elif isinstance(c, dict):
            card = dict(c)
            card_id = card.get("card_id") or card.get("id")
            if card_id and not str(card_id).startswith("DZ_"):
                try:
                    from app.games.fields_of_fire.terrain import get_card

                    fresh = get_card(str(card_id))
                    if fresh and fresh.get("image"):
                        card["image"] = fresh["image"]
                except Exception:
                    pass
            cards.append(card)
        elif isinstance(c, str):
            if c.startswith("DZ_"):
                cards.append({"id": c, "card_id": c, "deployment_zone": True})
            else:
                card = terrain_card(c, c)
                card["id"] = c
                cards.append(card)
        else:
            cards.append(terrain_card(str(c), None))
    return {
        "game": game_data.get("game"),
        "edition": game_data.get("edition"),
        "phase": game_data.get("phase"),
        "current_player": game_data.get("current_player"),
        "turn": game_data.get("turn"),
        "players": game_data.get("players", {}),
        "company": game_data.get("company", {}),
        "map": {
            **map_data,
            "rows": map_data.get("rows", 0),
            "cols": map_data.get("cols", 0),
            "cards": cards,
        },
        "markers": game_data.get("markers", []),
        "enemy": game_data.get("enemy", []),
        "enemy_packages": game_data.get("enemy_packages", []),
        "vof_markers": game_data.get("vof_markers", []),
        "pdf_markers": game_data.get("pdf_markers", []),
        "smoke_markers": game_data.get("smoke_markers", []),
        "pc_markers": game_data.get("pc_markers", []),
        "action_deck": game_data.get("action_deck"),
        "top_discard": _top_discard_card(game_data),
        "contact_level": game_data.get("contact_level", "no_contact"),
        "visibility": game_data.get("visibility", {}),
        "urban": game_data.get("urban", {}),
        "campaign": game_data.get("campaign", {}),
        "deployment_zones": game_data.get("deployment_zones", []),
        "scenario_id": game_data.get("scenario_id"),
        "victory_conditions": game_data.get("victory_conditions"),
        "game_over": game_data.get("phase") == "game_over",
        "winner": game_data.get("current_player") if game_data.get("phase") == "game_over" else None,
    }

