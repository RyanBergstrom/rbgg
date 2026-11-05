from __future__ import annotations

from typing import Any

from app.games.fields_of_fire.terrain import terrain_card


def serialize_game_data(game_data: dict[str, Any]) -> dict[str, Any]:
    map_data = game_data.get("map", {}) or {}
    cards = []
    for c in map_data.get("cards", []) or []:
        if c is None:
            cards.append(None)
        elif isinstance(c, dict):
            cards.append(c)
        elif isinstance(c, str):
            cards.append(terrain_card(c))
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
        "map": {"rows": map_data.get("rows", 0), "cols": map_data.get("cols", 0), "cards": cards},
        "markers": game_data.get("markers", []),
        "enemy": game_data.get("enemy", []),
        "enemy_packages": game_data.get("enemy_packages", []),
        "vof_markers": game_data.get("vof_markers", []),
        "pdf_markers": game_data.get("pdf_markers", []),
        "smoke_markers": game_data.get("smoke_markers", []),
        "pc_markers": game_data.get("pc_markers", []),
        "contact_level": game_data.get("contact_level", "no_contact"),
        "visibility": game_data.get("visibility", {}),
        "urban": game_data.get("urban", {}),
        "campaign": game_data.get("campaign", {}),
        "game_over": game_data.get("phase") == "game_over",
        "winner": game_data.get("current_player") if game_data.get("phase") == "game_over" else None,
    }

