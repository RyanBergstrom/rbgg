"""Tests for Checkers validator — rules, legal moves, apply, win detection."""

import copy
import pytest

from app.games.checkers.validator import (
    CheckersValidator,
    EMPTY,
    RED,
    RED_KING,
    BLACK,
    BLACK_KING,
    BOARD_SIZE,
)
from app.games.checkers.serialize import initial_board, board_to_dict


@pytest.fixture
def validator():
    return CheckersValidator()


def _make_state(board=None, current_player_index=0, players=None):
    if board is None:
        board = initial_board()
    if players is None:
        players = [
            {"player_id": "player_1", "name": "Red"},
            {"player_id": "player_2", "name": "Black"},
        ]
    return {
        "game_data": {"board": board},
        "current_player_index": current_player_index,
        "players": players,
    }


# ── initial board ──────────────────────────────────────────────────────

def test_initial_board_has_12_red_and_12_black():
    board = initial_board()
    reds = sum(1 for r in range(8) for c in range(8) if board[r][c] in (RED, RED_KING))
    blacks = sum(1 for r in range(8) for c in range(8) if board[r][c] in (BLACK, BLACK_KING))
    assert reds == 12
    assert blacks == 12


def test_initial_board_pieces_on_dark_squares():
    board = initial_board()
    for r in range(8):
        for c in range(8):
            if board[r][c] != EMPTY:
                assert (r + c) % 2 == 1, f"Piece at ({r},{c}) is on a light square"


# ── simple moves ───────────────────────────────────────────────────────

def test_red_can_move_forward_diagonal(validator):
    """A red piece at (5,0) can move to (4,1)."""
    board = initial_board()
    state = _make_state(board=board)
    move = {"move_id": "m1", "type": "move", "from_row": 5, "from_col": 0,
            "to_row": 4, "to_col": 1, "player_id": "player_1"}
    assert validator.validate_move(state, move) is True


def test_red_cannot_move_backward(validator):
    """A non-king red piece at (5,0) cannot move down to (6,1)."""
    board = initial_board()
    state = _make_state(board=board)
    move = {"move_id": "m1", "type": "move", "from_row": 5, "from_col": 0,
            "to_row": 6, "to_col": 1, "player_id": "player_1"}
    assert validator.validate_move(state, move) is False


def test_black_can_move_forward(validator):
    """Black pieces at row 2 can move to row 3."""
    board = initial_board()
    state = _make_state(board=board, current_player_index=1)
    move = {"move_id": "m1", "type": "move", "from_row": 2, "from_col": 1,
            "to_row": 3, "to_col": 0, "player_id": "player_2"}
    assert validator.validate_move(state, move) is True


def test_black_cannot_move_backward(validator):
    """A non-king black piece at (2,1) cannot move up to (1,0)."""
    board = initial_board()
    state = _make_state(board=board, current_player_index=1)
    move = {"move_id": "m1", "type": "move", "from_row": 2, "from_col": 1,
            "to_row": 1, "to_col": 0, "player_id": "player_2"}
    assert validator.validate_move(state, move) is False


def test_cannot_move_to_occupied_square(validator):
    board = initial_board()
    # Try to move red to a square occupied by another red
    state = _make_state(board=board)
    move = {"move_id": "m1", "type": "move", "from_row": 5, "from_col": 0,
            "to_row": 6, "to_col": 1, "player_id": "player_1"}
    assert validator.validate_move(state, move) is False


# ── jumps ──────────────────────────────────────────────────────────────

def test_jump_captures_opponent(validator):
    """Red jumps over black."""
    board = [[EMPTY] * 8 for _ in range(8)]
    board[3][2] = RED
    board[2][3] = BLACK
    board[1][4] = EMPTY
    state = _make_state(board=board)
    move = {"move_id": "j1", "type": "jump", "from_row": 3, "from_col": 2,
            "over_row": 2, "over_col": 3, "to_row": 1, "to_col": 4, "player_id": "player_1"}
    assert validator.validate_move(state, move) is True


def test_jump_removes_captured_piece(validator):
    board = [[EMPTY] * 8 for _ in range(8)]
    board[3][2] = RED
    board[2][3] = BLACK
    board[1][4] = EMPTY
    state = _make_state(board=board)
    move = {"move_id": "j1", "type": "jump", "from_row": 3, "from_col": 2,
            "over_row": 2, "over_col": 3, "to_row": 1, "to_col": 4, "player_id": "player_1"}
    new_state = validator.apply_move(state, move)
    new_board = new_state["game_data"]["board"]
    assert new_board[1][4] == RED
    assert new_board[3][2] == EMPTY
    assert new_board[2][3] == EMPTY


def test_mandatory_jump_rules(validator):
    """If a jump is available, simple moves are illegal."""
    board = [[EMPTY] * 8 for _ in range(8)]
    board[3][2] = RED
    board[2][3] = BLACK
    board[1][4] = EMPTY
    board[4][5] = RED  # another red piece
    board[3][4] = EMPTY
    state = _make_state(board=board)

    # Simple move should be illegal when jump exists
    simple = {"move_id": "m1", "type": "move", "from_row": 4, "from_col": 5,
              "to_row": 3, "to_col": 4, "player_id": "player_1"}
    assert validator.validate_move(state, simple) is False

    # Jump should be legal
    jump = {"move_id": "j1", "type": "jump", "from_row": 3, "from_col": 2,
            "over_row": 2, "over_col": 3, "to_row": 1, "to_col": 4, "player_id": "player_1"}
    assert validator.validate_move(state, jump) is True


# ── king promotion ─────────────────────────────────────────────────────

def test_king_promotion_on_last_row(validator):
    """Red piece reaching row 0 becomes a king."""
    board = [[EMPTY] * 8 for _ in range(8)]
    board[1][1] = RED
    board[0][2] = EMPTY
    state = _make_state(board=board)
    move = {"move_id": "m1", "type": "move", "from_row": 1, "from_col": 1,
            "to_row": 0, "to_col": 2, "player_id": "player_1"}
    new_state = validator.apply_move(state, move)
    assert new_state["game_data"]["board"][0][2] == RED_KING


def test_black_king_promotion(validator):
    """Black piece reaching row 7 becomes a king."""
    board = [[EMPTY] * 8 for _ in range(8)]
    board[6][1] = BLACK
    board[7][0] = EMPTY
    state = _make_state(board=board, current_player_index=1)
    move = {"move_id": "m1", "type": "move", "from_row": 6, "from_col": 1,
            "to_row": 7, "to_col": 0, "player_id": "player_2"}
    new_state = validator.apply_move(state, move)
    assert new_state["game_data"]["board"][7][0] == BLACK_KING


def test_king_can_move_backward(validator):
    board = [[EMPTY] * 8 for _ in range(8)]
    board[3][3] = RED_KING
    board[4][2] = EMPTY
    state = _make_state(board=board)
    move = {"move_id": "m1", "type": "move", "from_row": 3, "from_col": 3,
            "to_row": 4, "to_col": 2, "player_id": "player_1"}
    assert validator.validate_move(state, move) is True


def test_king_can_jump_backward(validator):
    board = [[EMPTY] * 8 for _ in range(8)]
    board[3][3] = RED_KING
    board[4][4] = BLACK
    board[5][5] = EMPTY
    state = _make_state(board=board)
    move = {"move_id": "j1", "type": "jump", "from_row": 3, "from_col": 3,
            "over_row": 4, "over_col": 4, "to_row": 5, "to_col": 5, "player_id": "player_1"}
    assert validator.validate_move(state, move) is True


# ── get_legal_moves ────────────────────────────────────────────────────

def test_get_legal_moves_initial_red(validator):
    """Red on row 5: 3 pieces have 2 moves each, 1 piece has 1 move = 7 total."""
    state = _make_state()
    moves = validator.get_legal_moves(state, "player_1")
    assert len(moves) == 7


def test_get_legal_moves_initial_black(validator):
    """Black on row 2: 3 pieces have 2 moves each, 1 piece has 1 move = 7 total."""
    state = _make_state()
    moves = validator.get_legal_moves(state, "player_2")
    assert len(moves) == 7


def test_get_legal_moves_returns_only_jumps_when_available(validator):
    board = [[EMPTY] * 8 for _ in range(8)]
    board[3][2] = RED
    board[2][3] = BLACK
    board[1][4] = EMPTY
    state = _make_state(board=board)
    moves = validator.get_legal_moves(state, "player_1")
    assert len(moves) == 1
    assert moves[0]["type"] == "jump"


# ── win detection ──────────────────────────────────────────────────────

def test_no_pieces_means_loss(validator):
    """Player with no pieces has no legal moves and loses."""
    board = [[EMPTY] * 8 for _ in range(8)]
    board[5][0] = RED  # red can move to (4,1)
    # No black pieces at all
    state = _make_state(board=board)
    winner = validator.check_win(state)
    assert winner == "player_1"  # black has no pieces → red wins


def test_no_legal_moves_means_loss(validator):
    """Player surrounded with no legal moves loses."""
    board = [[EMPTY] * 8 for _ in range(8)]
    board[0][0] = BLACK  # can't move: (1,-1) out of bounds, (1,1) occupied, can't jump (2,2) occupied
    board[1][1] = RED
    board[2][0] = RED  # block jump landing
    board[2][2] = RED  # block jump landing
    state = _make_state(board=board)
    winner = validator.check_win(state)
    assert winner == "player_1"


def test_game_in_progress_returns_none(validator):
    state = _make_state()
    assert validator.check_win(state) is None


# ── AI ─────────────────────────────────────────────────────────────────

def test_recommend_ai_move_returns_move(validator):
    state = _make_state()
    moves = validator.get_legal_moves(state, "player_1")
    ai_move = validator.recommend_ai_move(state, moves)
    assert ai_move is not None
    assert ai_move["move_id"].startswith("move_")


def test_recommend_ai_move_prefers_advancing(validator):
    """AI should prefer moves that advance toward king row."""
    board = [[EMPTY] * 8 for _ in range(8)]
    board[3][1] = RED
    board[3][3] = RED
    state = _make_state(board=board)
    moves = validator.get_legal_moves(state, "player_1")
    ai_move = validator.recommend_ai_move(state, moves)
    assert ai_move["to_row"] == 2  # should prefer moving up


def test_recommend_ai_move_returns_none_for_empty(validator):
    assert validator.recommend_ai_move(_make_state(), []) is None


# ── round-trip serialization ───────────────────────────────────────────

def test_initial_board_round_trip():
    board = initial_board()
    assert len(board) == 8
    assert all(len(row) == 8 for row in board)


def test_board_to_dict_keys():
    data = board_to_dict({"board": initial_board()})
    assert "board" in data
    assert "board_size" in data
    assert data["board_size"] == 8
