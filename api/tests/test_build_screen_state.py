"""Tests for screen state JSON — board_to_cells and GameEngine.build_screen_state."""

import pytest
from app.games.checkers.serialize import board_to_cells, initial_board
from app.core.engine import GameEngine
from app.core.legal_move_interface import LegalMoveValidator
from app.core.game_state import GameState, PlayerInfo, TurnInfo, Topology


class _StubValidator(LegalMoveValidator):
    """Test validator for screen state tests."""

    def __init__(self, moves: list[dict] | None = None, winner: str | None = None):
        self._moves = moves or []
        self._winner = winner

    def validate_move(self, state, move):
        return True

    def get_legal_moves(self, state, player_id):
        return list(self._moves)

    def apply_move(self, state, move):
        new_data = dict(state.get("game_data", {}))
        new_data["last_move"] = move.get("move_id")
        return {**state, "game_data": new_data}

    def check_win(self, state):
        return self._winner

    def initial_game_data(self):
        from app.games.checkers.serialize import initial_board
        return {"board": initial_board()}

    def serialize_for_screen(self, game_data):
        from app.games.checkers.serialize import board_to_cells
        board = game_data.get("board", [])
        return {
            "board": board,
            "cells": board_to_cells(board),
            "must_jump_from": game_data.get("must_jump_from"),
        }


def _make_state(**overrides) -> GameState:
    defaults = dict(
        state_id="test-state",
        game_type="checkers",
        topology=Topology.grid,
        rng_seed=42,
        players=[
            PlayerInfo(player_id="player_1", name="Red", color="#cc0000"),
            PlayerInfo(player_id="player_2", name="Black", color="#222222"),
        ],
        current_player_index=0,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
        game_data={"board": initial_board()},
        current_round_index=0,
        current_turn_index=0,
        current_phase_index=0,
    )
    defaults.update(overrides)
    return GameState(**defaults)


# ── board_to_cells tests ──────────────────────────────────────────────

def test_board_to_cells_returns_8_rows():
    board = initial_board()
    cells = board_to_cells(board)
    assert len(cells) == 8


def test_board_to_cells_returns_8_columns_per_row():
    board = initial_board()
    cells = board_to_cells(board)
    for row in cells:
        assert len(row) == 8


def test_board_to_cells_empty_square():
    board = [[0] * 8 for _ in range(8)]
    cells = board_to_cells(board)
    # Top-left (0,0) is light square, empty
    assert cells[0][0] == {"color": "#f0d9b5", "piece": None}


def test_board_to_cells_dark_square_empty():
    board = [[0] * 8 for _ in range(8)]
    cells = board_to_cells(board)
    # (0,1) is dark square, empty
    assert cells[0][1] == {"color": "#b58863", "piece": None}


def test_board_to_cells_red_piece():
    board = [[0] * 8 for _ in range(8)]
    board[5][0] = 1  # red piece
    cells = board_to_cells(board)
    piece = cells[5][0]["piece"]
    assert piece is not None
    assert piece["type"] == "red"
    assert piece["color"] == "#cc0000"
    assert piece["king"] is False
    assert piece["id"] == "r5c0"


def test_board_to_cells_red_king():
    board = [[0] * 8 for _ in range(8)]
    board[5][0] = 2  # red king
    cells = board_to_cells(board)
    piece = cells[5][0]["piece"]
    assert piece is not None
    assert piece["type"] == "red"
    assert piece["king"] is True


def test_board_to_cells_black_piece():
    board = [[0] * 8 for _ in range(8)]
    board[0][1] = 3  # black piece
    cells = board_to_cells(board)
    piece = cells[0][1]["piece"]
    assert piece is not None
    assert piece["type"] == "black"
    assert piece["color"] == "#222222"
    assert piece["king"] is False


def test_board_to_cells_black_king():
    board = [[0] * 8 for _ in range(8)]
    board[0][1] = 4  # black king
    cells = board_to_cells(board)
    piece = cells[0][1]["piece"]
    assert piece is not None
    assert piece["type"] == "black"
    assert piece["king"] is True


def test_board_to_cells_initial_board_has_correct_positions():
    board = initial_board()
    cells = board_to_cells(board)
    # Black pieces on rows 0-2, dark squares
    assert cells[0][1]["piece"]["type"] == "black"
    assert cells[2][1]["piece"]["type"] == "black"
    # Red pieces on rows 5-7, dark squares
    assert cells[5][0]["piece"]["type"] == "red"
    assert cells[7][0]["piece"]["type"] == "red"
    # Light squares are empty
    assert cells[0][0]["piece"] is None
    assert cells[4][4]["piece"] is None


# ── build_screen_state tests ──────────────────────────────────────────

def test_build_screen_state_has_panels():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state()
    result = engine.build_screen_state(state)
    assert "panels" in result
    assert len(result["panels"]) == 2  # game_progress + main_board


def test_build_screen_state_panel_ids():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state()
    result = engine.build_screen_state(state)
    panel_ids = [p["id"] for p in result["panels"]]
    assert "game_progress" in panel_ids
    assert "main_board" in panel_ids


def test_build_screen_state_main_board_has_board_component():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state()
    result = engine.build_screen_state(state)
    main_board = next(p for p in result["panels"] if p["id"] == "main_board")
    comp_ids = [c["id"] for c in main_board["components"]]
    assert "board" in comp_ids


def test_build_screen_state_board_has_grid():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state()
    result = engine.build_screen_state(state)
    main_board = next(p for p in result["panels"] if p["id"] == "main_board")
    board_comp = next(c for c in main_board["components"] if c["id"] == "board")
    assert "grid" in board_comp
    assert board_comp["grid"]["rows"] == 8
    assert board_comp["grid"]["columns"] == 8


def test_build_screen_state_board_has_cells():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state()
    result = engine.build_screen_state(state)
    main_board = next(p for p in result["panels"] if p["id"] == "main_board")
    board_comp = next(c for c in main_board["components"] if c["id"] == "board")
    cells = board_comp["grid"]["cells"]
    assert len(cells) == 8
    assert len(cells[0]) == 8
    # Check a piece exists
    assert cells[0][1]["piece"]["type"] == "black"
    assert cells[5][0]["piece"]["type"] == "red"


def test_build_screen_state_has_phase():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state()
    result = engine.build_screen_state(state)
    assert "phase" in result
    assert result["phase"]["phase_name"] == "Player_Turn"


def test_build_screen_state_has_legal_moves():
    moves = [{"move_id": "m1"}, {"move_id": "m2"}]
    engine = GameEngine("checkers", _StubValidator(moves=moves))
    state = _make_state()
    result = engine.build_screen_state(state, legal_moves=moves)
    assert len(result["legal_moves"]) == 2


def test_build_screen_state_has_current_player():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state()
    result = engine.build_screen_state(state)
    assert result["current_player"] == "player_1"


def test_build_screen_state_has_winner():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state(winner="player_1")
    result = engine.build_screen_state(state)
    assert result["winner"] == "player_1"


def test_build_screen_state_has_game_data():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state()
    result = engine.build_screen_state(state)
    assert "game_data" in result
    assert "board" in result["game_data"]


def test_build_screen_state_component_properties():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state()
    result = engine.build_screen_state(state)
    main_board = next(p for p in result["panels"] if p["id"] == "main_board")
    board_comp = next(c for c in main_board["components"] if c["id"] == "board")
    assert board_comp["shape"] == "rectangle"
    assert board_comp["color"] == "#b58863"
    assert board_comp["z_index"] == 0
    assert board_comp["clickable"] is False


def test_build_screen_state_empty_legal_moves_default():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state()
    result = engine.build_screen_state(state)
    assert result["legal_moves"] == []
