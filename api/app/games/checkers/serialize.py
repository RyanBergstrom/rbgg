"""Serialization helpers for converting checkers board state to API responses."""
from __future__ import annotations

from typing import Any


def initial_board() -> list[list[int]]:
    """Create the standard 8×8 checkers starting board.

    Piece codes:
        0 = empty, 1 = red, 2 = red king, 3 = black, 4 = black king

    Layout (rows 0–2 = black, rows 5–7 = red):
        Row 0: B . B . B . B .
        Row 1: . B . B . B . B
        Row 2: B . B . B . B .
        Row 5: . R . R . R . R
        Row 6: R . R . R . R .
        Row 7: . R . R . R . R
    """
    board: list[list[int]] = [[0] * 8 for _ in range(8)]

    for r in range(8):
        for c in range(8):
            if (r + c) % 2 == 1:
                if r < 3:
                    board[r][c] = 3  # black
                elif r > 4:
                    board[r][c] = 1  # red

    return board


def board_to_dict(game_data: dict[str, Any]) -> dict[str, Any]:
    """Convert game_data to a frontend-friendly dict.

    Returns:
        {
            "board": [[0,3,0,...], ...],  # 8×8 grid
            "board_size": 8,
            "must_jump_from": {"row": r, "col": c} | null,
        }
    """
    board = game_data.get("board", initial_board())
    return {
        "board": board,
        "board_size": 8,
        "must_jump_from": game_data.get("must_jump_from"),
    }


def state_response(
    game_data: dict[str, Any],
    winner: str | None = None,
    current_player_id: str | None = None,
) -> dict[str, Any]:
    """Convert game state to the response format the frontend play page expects."""
    return {
        "board": board_to_dict(game_data),
        "winner": winner,
        "current_player_id": current_player_id,
    }


# ── Piece lookup for screen state ──────────────────────────────────────

_PIECE_MAP: dict[int, dict[str, Any] | None] = {
    0: None,
    1: {"type": "red", "color": "#cc0000", "king": False},
    2: {"type": "red", "color": "#cc0000", "king": True},
    3: {"type": "black", "color": "#222222", "king": False},
    4: {"type": "black", "color": "#222222", "king": True},
}

_LIGHT_SQUARE = "#f0d9b5"
_DARK_SQUARE = "#b58863"


def board_to_cells(board: list[list[int]]) -> list[list[dict[str, Any]]]:
    """Convert 8×8 int array to [[{color, piece}]] for screen state.

    Piece codes:
        0 = empty, 1 = red, 2 = red king, 3 = black, 4 = black king

    Returns list of rows, each row a list of cell dicts:
        {"color": "#f0d9b5"|"#b58863", "piece": {"id", "type", "color", "king"} | null}
    """
    cells: list[list[dict[str, Any]]] = []
    for r, row in enumerate(board):
        row_cells: list[dict[str, Any]] = []
        for c, val in enumerate(row):
            is_dark = (r + c) % 2 == 1
            bg = _DARK_SQUARE if is_dark else _LIGHT_SQUARE
            piece_info = _PIECE_MAP.get(val)
            piece = None
            if piece_info is not None:
                piece = {"id": f"r{r}c{c}", **piece_info}
            row_cells.append({"color": bg, "piece": piece})
        cells.append(row_cells)
    return cells
