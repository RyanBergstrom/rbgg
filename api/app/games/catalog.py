"""Game catalog — registry of available games.

Provides a simple in-memory catalog of games that the frontend can list
and look up.  Each game entry contains the fields the frontend expects:
id, name, type, min_players, max_players.
"""
from __future__ import annotations

from typing import Dict, List

GAME_CATALOG: Dict[str, dict] = {}


def register_game(game_id: str, name: str, game_type: str, min_players: int = 2, max_players: int = 2, cover_image: str | None = None, difficulty: dict | None = None) -> None:
    """Register a game in the catalog."""
    GAME_CATALOG[game_id] = {
        "id": game_id,
        "name": name,
        "type": game_type,
        "min_players": min_players,
        "max_players": max_players,
        "cover_image": cover_image,
        "difficulty": difficulty,
    }


def list_games() -> List[dict]:
    """Return all games in the catalog."""
    return list(GAME_CATALOG.values())


def get_game(game_id: str) -> dict | None:
    """Return a single game entry, or None if not found."""
    return GAME_CATALOG.get(game_id)
