"""Serialization helpers for converting Santorini GameState to API responses."""
from __future__ import annotations

from app.games.santorini.validator import GameState, Player


def board_to_dict(state: GameState) -> dict:
    """Convert a GameState to the board dict the frontend expects.

    Returns:
        {
            "height": {"(r,c)": h, ...},
            "workers": {
                "one": {"worker1": {"row": r, "col": c}, ...},
                "two": {"worker1": {"row": r, "col": c}, ...},
            },
            "player_turn": "one" | "two",
            "moved_workers": [...],
        }
    """
    height = {}
    for pos, h in state.board.height.items():
        height[f"({pos.row},{pos.col})"] = h

    workers = {}
    for player in Player:
        workers[player.value] = {}
        for wid, wpos in state.board.workers[player].items():
            workers[player.value][wid] = {"row": wpos.row, "col": wpos.col}

    return {
        "height": height,
        "workers": workers,
        "player_turn": state.player_turn.value,
        "moved_workers": sorted(state.moved_workers),
    }


def state_response(state: GameState, game_id: str = "santorini", game_name: str = "Santorini") -> dict:
    """Convert a GameState to the full response the frontend play page expects.

    Returns:
        {
            "id": "santorini",
            "name": "Santorini",
            "type": "santorini",
            "state": {"player_turn": "one", "winner": None},
            "turn": {"actions_remaining": 3},
        }
    """
    winner = None
    from app.games.santorini.validator import check_win
    w = check_win(state)
    if w is not None:
        winner = w.value

    return {
        "id": game_id,
        "name": game_name,
        "type": game_id,
        "state": {
            "player_turn": state.player_turn.value,
            "winner": winner,
        },
        "turn": {
            "actions_remaining": 3,
        },
    }
