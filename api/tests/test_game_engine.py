"""Tests for GameEngine — phase-aware engine with config-driven round/turn/phase tracking."""

import pytest
from unittest.mock import MagicMock

from app.core.engine import GameEngine
from app.core.legal_move_interface import LegalMoveValidator
from app.core.game_state import GameState, PlayerInfo, TurnInfo, Topology


class _StubValidator(LegalMoveValidator):
    """Test validator that supports basic checkers-like moves."""

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
        return {"board": []}


def _make_state(**overrides) -> GameState:
    """Create a minimal GameState for testing."""
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
        game_data={},
        current_round_index=0,
        current_turn_index=0,
        current_phase_index=0,
    )
    defaults.update(overrides)
    return GameState(**defaults)


# ── Config lookups ─────────────────────────────────────────────────────

def test_engine_loads_checkers_config():
    engine = GameEngine("checkers", _StubValidator())
    assert engine.config is not None
    assert len(engine.config.rounds) == 1
    assert engine.config.rounds[0].name == "Main Game"


def test_engine_get_phase_info_returns_current_phase():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state()
    info = engine.get_phase_info(state)
    assert info["phase_name"] == "Player_Turn"
    assert info["phase_text"] == "Make your move"
    assert info["confirm_required"] is False
    assert info["round_name"] == "Main Game"
    assert info["turn_name"] == "Player Turn"


def test_engine_get_phase_info_pass_turn():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state(current_phase_index=1)
    info = engine.get_phase_info(state)
    assert info["phase_name"] == "Pass_Turn"
    assert info["confirm_required"] is True
    assert info["confirm_name"] == "Confirm"
    assert info["confirm_description"] == "End your turn"


# ── Should show confirm ───────────────────────────────────────────────

def test_should_show_confirm_false_for_player_turn():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state(current_phase_index=0)
    assert engine.should_show_confirm(state) is False


def test_should_show_confirm_true_for_pass_turn():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state(current_phase_index=1)
    assert engine.should_show_confirm(state) is True


# ── Phase advancement ─────────────────────────────────────────────────

def test_advance_phase_moves_to_next_phase():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state(current_phase_index=0)
    engine.advance_phase(state)
    assert state.current_phase_index == 1


def test_advance_phase_from_last_phase_advances_player():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state(current_phase_index=1)  # last phase
    engine.advance_phase(state)
    # Should reset phase and advance player
    assert state.current_phase_index == 0
    assert state.current_player_index == 1  # player_2
    assert state.turn.player_id == "player_2"


def test_advance_phase_wraps_player_index():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state(
        current_phase_index=1,
        current_player_index=1,  # player_2's turn
    )
    engine.advance_phase(state)
    assert state.current_player_index == 0  # back to player_1


# ── Submit move ────────────────────────────────────────────────────────

def test_submit_move_with_no_legal_moves_advances_phase():
    """When no more legal moves and confirm not required, auto-advance."""
    engine = GameEngine("checkers", _StubValidator(moves=[]))
    state = _make_state(current_phase_index=0)  # Player_Turn (confirm=false)
    move = {"move_id": "m1", "type": "move", "from_row": 5, "from_col": 0,
            "to_row": 4, "to_col": 1, "player_id": "player_1"}
    result = engine.submit_move(state, move)
    # Should auto-advance since confirm=false and no more moves
    assert state.current_phase_index == 1  # advanced to Pass_Turn
    assert result["status"] == "accepted"
    # Phase info now shows confirm required for the new phase
    assert result["phase_info"]["confirm_required"] is True


def test_submit_move_with_more_moves_stays_in_phase():
    """When multi-jump continuation exists (must_jump_from set), stay in current phase."""
    class _MultiJumpValidator(LegalMoveValidator):
        def __init__(self):
            self._call_count = 0
        def validate_move(self, state, move):
            return True
        def get_legal_moves(self, state, player_id):
            return [{"move_id": "jump2"}]
        def apply_move(self, state, move):
            new_data = dict(state.get("game_data", {}))
            new_data["last_move"] = move.get("move_id")
            self._call_count += 1
            # Simulate multi-jump: set must_jump_from on first call only
            if self._call_count == 1:
                new_data["must_jump_from"] = {"row": 4, "col": 1}
            else:
                new_data.pop("must_jump_from", None)
            return {**state, "game_data": new_data}
        def check_win(self, state):
            return None
        def initial_game_data(self):
            return {"board": []}

    engine = GameEngine("checkers", _MultiJumpValidator())
    state = _make_state(current_phase_index=0)
    move = {"move_id": "m1", "type": "jump", "from_row": 5, "from_col": 0,
            "to_row": 4, "to_col": 1, "player_id": "player_1"}
    result = engine.submit_move(state, move)
    assert state.current_phase_index == 0  # stayed in Player_Turn
    assert result["status"] == "accepted"


def test_submit_move_with_winner():
    engine = GameEngine("checkers", _StubValidator(winner="player_1"))
    state = _make_state()
    move = {"move_id": "m1", "type": "move", "player_id": "player_1"}
    result = engine.submit_move(state, move)
    assert result["winner"] == "player_1"
    assert state.winner == "player_1"


# ── Confirm turn ───────────────────────────────────────────────────────

def test_confirm_turn_advances_to_next_player():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state(current_phase_index=1)  # Pass_Turn
    result = engine.confirm_turn(state)
    assert result["status"] == "turn_complete"
    assert state.current_player_index == 1
    assert state.current_phase_index == 0


def test_confirm_turn_when_not_required():
    engine = GameEngine("checkers", _StubValidator())
    state = _make_state(current_phase_index=0)  # Player_Turn (no confirm)
    result = engine.confirm_turn(state)
    assert result["status"] == "no_confirm_needed"


# ── Get legal moves ────────────────────────────────────────────────────

def test_get_legal_moves_delegates_to_validator():
    moves = [{"move_id": "m1"}, {"move_id": "m2"}]
    engine = GameEngine("checkers", _StubValidator(moves=moves))
    state = _make_state()
    result = engine.get_legal_moves(state, "player_1")
    assert len(result) == 2


# ── Phase info in result ──────────────────────────────────────────────

def test_submit_move_returns_phase_info():
    engine = GameEngine("checkers", _StubValidator(moves=[]))
    state = _make_state(current_phase_index=0)
    move = {"move_id": "m1", "type": "move", "player_id": "player_1"}
    result = engine.submit_move(state, move)
    assert "phase_info" in result
    assert "phase_name" in result["phase_info"]
