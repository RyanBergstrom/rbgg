"""Checkers (draughts) validator — implements LegalMoveValidator.

American checkers rules:
- 8×8 board, 12 pieces per player on dark squares
- Regular pieces move forward-diagonal 1 square
- Kings move forward or backward diagonal 1 square
- Mandatory capture: must jump if a jump is available
- Multi-jump: if after a jump another jump is available, must continue
- King promotion: piece reaching the far row becomes a king
- Win: opponent has no pieces or no legal moves
"""

from __future__ import annotations

from typing import Any

from app.core.legal_move_interface import IllegalMoveError, LegalMoveValidator
from app.core.mcts import MCTSConfig
from app.games.checkers.serialize import initial_board


# Board cell constants
EMPTY = 0
RED = 1
RED_KING = 2
BLACK = 3
BLACK_KING = 4

BOARD_SIZE = 8


def _opponent(player_id: str) -> str:
    """Return the opponent's player_id."""
    return "player_2" if player_id == "player_1" else "player_1"


def _piece_owner(cell: int) -> str | None:
    """Return the player_id that owns a cell, or None if empty."""
    if cell in (RED, RED_KING):
        return "player_1"
    if cell in (BLACK, BLACK_KING):
        return "player_2"
    return None


def _is_king(cell: int) -> bool:
    return cell in (RED_KING, BLACK_KING)


def _is_red(cell: int) -> bool:
    return cell in (RED, RED_KING)


def _is_black(cell: int) -> bool:
    return cell in (BLACK, BLACK_KING)


def _promote(cell: int) -> int:
    """Promote a piece to king."""
    if cell == RED:
        return RED_KING
    if cell == BLACK:
        return BLACK_KING
    return cell


def _is_forward(from_row: int, to_row: int, player_id: str) -> bool:
    """Check if the move is in the forward direction for the player."""
    if player_id == "player_1":
        return to_row < from_row  # red moves toward row 0
    return to_row > from_row  # black moves toward row 7


def _in_bounds(row: int, col: int) -> bool:
    return 0 <= row < BOARD_SIZE and 0 <= col < BOARD_SIZE


def _board_from_game_data(game_data: dict[str, Any]) -> list[list[int]]:
    """Extract the 8×8 board from game_data."""
    return game_data.get("board", [[EMPTY] * BOARD_SIZE for _ in range(BOARD_SIZE)])


def _find_jumps(
    board: list[list[int]], row: int, col: int, player_id: str
) -> list[dict[str, Any]]:
    """Find all jump moves for the piece at (row, col)."""
    cell = board[row][col]
    if cell == EMPTY:
        return []

    is_k = _is_king(cell)
    jumps: list[dict[str, Any]] = []

    # Directions: red (player_1) moves toward row 0, black (player_2) toward row 7
    if player_id == "player_1":
        directions = [(-1, -1), (-1, 1)]  # forward (up)
        if is_k:
            directions += [(1, -1), (1, 1)]  # backward too
    else:
        directions = [(1, -1), (1, 1)]  # forward (down)
        if is_k:
            directions += [(-1, -1), (-1, 1)]  # backward too

    for dr, dc in directions:
        mid_r, mid_c = row + dr, col + dc
        land_r, land_c = row + 2 * dr, col + 2 * dc

        if not _in_bounds(land_r, land_c):
            continue

        mid_cell = board[mid_r][mid_c]
        land_cell = board[land_r][land_c]

        # Must jump over an opponent piece onto an empty square
        if mid_cell != EMPTY and _piece_owner(mid_cell) != player_id and land_cell == EMPTY:
            jumps.append({
                "move_id": f"jump_{row}_{col}_{land_r}_{land_c}",
                "type": "jump",
                "from_row": row,
                "from_col": col,
                "over_row": mid_r,
                "over_col": mid_c,
                "to_row": land_r,
                "to_col": land_c,
                "player_id": player_id,
            })

    return jumps


def _find_double_jumps(
    board: list[list[int]], row: int, col: int, player_id: str
) -> list[dict[str, Any]]:
    """Find double-jump combos: single jump followed by another jump from the landing square.

    Returns compound moves with type="double_jump" representing the full sequence.
    """
    first_jumps = _find_jumps(board, row, col, player_id)
    doubles: list[dict[str, Any]] = []

    for fj in first_jumps:
        # Simulate the first jump on a temp board
        temp_board = [r[:] for r in board]
        temp_board[row][col] = EMPTY
        temp_board[fj["over_row"]][fj["over_col"]] = EMPTY
        temp_board[fj["to_row"]][fj["to_col"]] = board[row][col]

        # Check for a second jump from the landing position
        second_jumps = _find_jumps(temp_board, fj["to_row"], fj["to_col"], player_id)
        for sj in second_jumps:
            doubles.append({
                "move_id": f"double_jump_{row}_{col}_{sj['to_row']}_{sj['to_col']}",
                "type": "double_jump",
                "from_row": row,
                "from_col": col,
                "to_row": sj["to_row"],
                "to_col": sj["to_col"],
                "first_jump": fj,
                "second_jump": sj,
                "player_id": player_id,
            })

    return doubles


def _find_simple_moves(
    board: list[list[int]], row: int, col: int, player_id: str
) -> list[dict[str, Any]]:
    """Find all simple (non-jump) moves for the piece at (row, col)."""
    cell = board[row][col]
    if cell == EMPTY:
        return []

    is_k = _is_king(cell)
    moves: list[dict[str, Any]] = []

    if player_id == "player_1":
        directions = [(-1, -1), (-1, 1)]  # forward (up)
        if is_k:
            directions += [(1, -1), (1, 1)]
    else:
        directions = [(1, -1), (1, 1)]  # forward (down)
        if is_k:
            directions += [(-1, -1), (-1, 1)]

    for dr, dc in directions:
        to_r, to_c = row + dr, col + dc
        if not _in_bounds(to_r, to_c):
            continue
        if board[to_r][to_c] != EMPTY:
            continue
        # For non-kings, enforce forward direction
        if not is_k and not _is_forward(row, to_r, player_id):
            continue

        moves.append({
            "move_id": f"move_{row}_{col}_{to_r}_{to_c}",
            "type": "move",
            "from_row": row,
            "from_col": col,
            "to_row": to_r,
            "to_col": to_c,
            "player_id": player_id,
        })

    return moves


def _apply_move_to_board(
    board: list[list[int]], move: dict[str, Any]
) -> list[list[int]]:
    """Apply a single move or jump to the board, returning a new board."""
    import copy
    new_board = copy.deepcopy(board)

    fr, fc = move["from_row"], move["from_col"]
    tr, tc = move["to_row"], move["to_col"]
    cell = new_board[fr][fc]
    new_board[fr][fc] = EMPTY
    new_board[tr][tc] = cell

    # Remove jumped piece
    if move["type"] == "jump":
        new_board[move["over_row"]][move["over_col"]] = EMPTY

    # King promotion
    if cell == RED and tr == 0:
        new_board[tr][tc] = RED_KING
    elif cell == BLACK and tr == BOARD_SIZE - 1:
        new_board[tr][tc] = BLACK_KING

    return new_board


def _has_legal_moves(board: list[list[int]], player_id: str) -> bool:
    """Check if the player has any legal moves (simple or jump)."""
    for r in range(BOARD_SIZE):
        for c in range(BOARD_SIZE):
            cell = board[r][c]
            if _piece_owner(cell) != player_id:
                continue
            if _find_jumps(board, r, c, player_id):
                return True
            if _find_simple_moves(board, r, c, player_id):
                return True
    return False


class CheckersValidator(LegalMoveValidator):
    """Implements LegalMoveValidator for American checkers."""

    _mcts_init_args: tuple = ()  # no-arg constructor for MCTS workers

    def validate_move(self, state: dict[str, Any], move: dict[str, Any]) -> bool:
        game_data = state.get("game_data", {})
        board = _board_from_game_data(game_data)
        player_id = move.get("player_id")

        if not player_id:
            return False

        # Must be this player's turn
        current_idx = state.get("current_player_index", 0)
        players = state.get("players", [])
        if current_idx < len(players) and players[current_idx].get("player_id") != player_id:
            return False

        # Check if the piece belongs to this player
        fr, fc = move.get("from_row"), move.get("from_col")
        if fr is None or fc is None:
            return False
        if not _in_bounds(fr, fc):
            return False
        if _piece_owner(board[fr][fc]) != player_id:
            return False

        # During multi-jump continuation, must jump from must_jump_from
        must_jump_from = game_data.get("must_jump_from")
        if must_jump_from:
            if move.get("type") not in ("jump", "double_jump"):
                return False
            if fr != must_jump_from["row"] or fc != must_jump_from["col"]:
                return False
            jumps = _find_jumps(board, fr, fc, player_id)
            for j in jumps:
                if (j["to_row"] == move.get("to_row") and
                        j["to_col"] == move.get("to_col")):
                    return True
            return False

        # Double jump: validate both jumps are legal
        if move.get("type") == "double_jump":
            fj = move.get("first_jump")
            sj = move.get("second_jump")
            if not fj or not sj:
                return False
            # First jump must be a valid jump from the piece's current position
            first_jumps = _find_jumps(board, fr, fc, player_id)
            if not any(j["to_row"] == fj["to_row"] and j["to_col"] == fj["to_col"]
                       for j in first_jumps):
                return False
            # Simulate first jump and check second jump is valid from there
            temp_board = [r[:] for r in board]
            temp_board[fr][fc] = EMPTY
            temp_board[fj["over_row"]][fj["over_col"]] = EMPTY
            temp_board[fj["to_row"]][fj["to_col"]] = board[fr][fc]
            second_jumps = _find_jumps(temp_board, fj["to_row"], fj["to_col"], player_id)
            return any(j["to_row"] == sj["to_row"] and j["to_col"] == sj["to_col"]
                       for j in second_jumps)

        # Mandatory jump rule: if any jump exists, must jump
        all_jumps = []
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if _piece_owner(board[r][c]) == player_id:
                    all_jumps.extend(_find_jumps(board, r, c, player_id))

        if move.get("type") == "jump":
            # Verify this specific jump is legal
            jumps = _find_jumps(board, fr, fc, player_id)
            for j in jumps:
                if (j["to_row"] == move.get("to_row") and
                        j["to_col"] == move.get("to_col")):
                    return True
            return False
        else:
            # Simple move: only allowed if no jumps available anywhere
            if all_jumps:
                return False
            moves = _find_simple_moves(board, fr, fc, player_id)
            for m in moves:
                if (m["to_row"] == move.get("to_row") and
                        m["to_col"] == move.get("to_col")):
                    return True
            return False

    def get_legal_moves(self, state: dict[str, Any], player_id: str) -> list[dict[str, Any]]:
        game_data = state.get("game_data", {})
        board = _board_from_game_data(game_data)

        # During multi-jump continuation, only jumps from must_jump_from are legal
        must_jump_from = game_data.get("must_jump_from")
        if must_jump_from:
            r, c = must_jump_from["row"], must_jump_from["col"]
            return _find_jumps(board, r, c, player_id)

        # Collect all jumps
        all_jumps: list[dict[str, Any]] = []
        all_doubles: list[dict[str, Any]] = []
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if _piece_owner(board[r][c]) == player_id:
                    all_jumps.extend(_find_jumps(board, r, c, player_id))
                    all_doubles.extend(_find_double_jumps(board, r, c, player_id))

        # Mandatory jump: if any jumps exist, return single jumps + double jump combos
        if all_jumps:
            return all_jumps + all_doubles

        # Otherwise, simple moves only
        all_moves: list[dict[str, Any]] = []
        for r in range(BOARD_SIZE):
            for c in range(BOARD_SIZE):
                if _piece_owner(board[r][c]) == player_id:
                    all_moves.extend(_find_simple_moves(board, r, c, player_id))

        return all_moves

    def apply_move(self, state: dict[str, Any], move: dict[str, Any]) -> dict[str, Any]:
        game_data = dict(state.get("game_data", {}))
        board = _board_from_game_data(game_data)

        # Double jump: apply both jumps atomically
        if move["type"] == "double_jump":
            board = _apply_move_to_board(board, move["first_jump"])
            board = _apply_move_to_board(board, move["second_jump"])
            game_data["board"] = board
            game_data.pop("must_jump_from", None)
            return {"game_data": game_data}

        new_board = _apply_move_to_board(board, move)

        # Check for multi-jump continuation
        tr, tc = move["to_row"], move["to_col"]
        player_id = move["player_id"]
        cell = new_board[tr][tc]
        if move["type"] == "jump":
            more_jumps = _find_jumps(new_board, tr, tc, player_id)
            if more_jumps:
                game_data["board"] = new_board
                game_data["must_jump_from"] = {"row": tr, "col": tc}
                return {"game_data": game_data}

        # No multi-jump: clear continuation flag
        game_data["board"] = new_board
        game_data.pop("must_jump_from", None)
        return {"game_data": game_data}

    def check_win(self, state: dict[str, Any]) -> str | None:
        game_data = state.get("game_data", {})
        board = _board_from_game_data(game_data)
        players = state.get("players", [])

        if not players:
            return None

        for p in players:
            pid = p.get("player_id", "")
            if not _has_legal_moves(board, pid):
                # This player has no moves — opponent wins
                return _opponent(pid)

        return None

    def recommend_ai_move(
        self, state: dict[str, Any], candidate_moves: list[dict[str, Any]]
    ) -> dict[str, Any] | None:
        if not candidate_moves:
            return None

        # Prefer jumps (captures), then prefer moves that advance toward promotion
        jumps = [m for m in candidate_moves if m.get("type") == "jump"]
        if jumps:
            # Among jumps, prefer ones that land closer to king row
            player_id = jumps[0].get("player_id")
            if player_id == "player_1":
                return max(jumps, key=lambda m: m["to_row"])
            return min(jumps, key=lambda m: m["to_row"])

        # Among simple moves, prefer advancing toward king row
        player_id = candidate_moves[0].get("player_id")
        if player_id == "player_1":
            return max(candidate_moves, key=lambda m: m["to_row"])
        return min(candidate_moves, key=lambda m: m["to_row"])

    def ai_config(self) -> MCTSConfig:
        """Return MCTS config tuned for checkers."""
        return MCTSConfig(
            iterations=500,
            exploration_constant=1.414,
            max_depth=64,
        )

    def initial_game_data(self) -> dict[str, Any]:
        """Return the initial checkers board state."""
        return {"board": initial_board()}

    def serialize_for_screen(self, game_data: dict[str, Any]) -> dict[str, Any]:
        """Convert checkers game_data to screen-ready format with cells."""
        from app.games.checkers.serialize import board_to_cells
        board = game_data.get("board", initial_board())
        return {
            "board": board,
            "cells": board_to_cells(board),
            "must_jump_from": game_data.get("must_jump_from"),
        }
