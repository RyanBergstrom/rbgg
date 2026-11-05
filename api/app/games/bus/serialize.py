"""Screen serialization helpers for Bus public game state."""
from __future__ import annotations

from copy import deepcopy
from typing import Any


def adjusted_score(player: dict[str, Any]) -> int:
    """Return Bus final-score value before ranking tie breakers."""
    return player["score"] - player["time_stones"]


def ranked_player_ids(players: dict[str, dict[str, Any]]) -> list[str]:
    """Return final ranking in official Bus tie-break order."""
    return sorted(
        players,
        key=lambda player_id: (
            adjusted_score(players[player_id]),
            players[player_id]["time_stones"],
            -players[player_id]["score_stack_order"],
        ),
        reverse=True,
    )


def serialize_game_data(
    game_data: dict[str, Any], *, nodes: dict[str, Any], building_sites: dict[str, Any],
    edges: dict[str, Any], route_ends: dict[str, list[str]],
) -> dict[str, Any]:
    """Return an explicit public view without server-only or search metadata."""
    players = {
        player_id: {
            "action_markers": player["action_markers"],
            "buses": player["buses"],
            "time_stones": player["time_stones"],
            "score": player["score"],
            "adjusted_score": adjusted_score(player),
            "route_edges": list(player["route_edges"]),
            "route_anchor": player.get("route_anchor"),
            "route_ends": route_ends[player_id],
        }
        for player_id, player in game_data["players"].items()
    }
    return {
        "rules_edition": game_data["rules_edition"],
        "current_phase": game_data["current_phase"],
        "current_player": game_data["current_player"],
        "round_number": game_data["round_number"],
        "starting_player": game_data["starting_player"],
        "players": players,
        "buildings": deepcopy(game_data["buildings"]),
        "building_tiles_remaining": deepcopy(game_data["building_tiles_remaining"]),
        "passengers": deepcopy(game_data["passengers"]),
        "passenger_supply": game_data["passenger_supply"],
        "clock": game_data["clock"],
        "time_stones_remaining": game_data["time_stones_remaining"],
        "action_spaces": deepcopy(game_data["action_spaces"]),
        "passed_this_round": list(game_data["passed_this_round"]),
        "resolution": deepcopy(game_data["resolution"]),
        "terminal_reason": game_data["terminal_reason"],
        "game_over": game_data["game_over"],
        "final_ranking": ranked_player_ids(game_data["players"]) if game_data["game_over"] else [],
        "topology": {
            "nodes": deepcopy(nodes),
            "building_sites": deepcopy(building_sites),
            "edges": deepcopy(edges),
        },
    }