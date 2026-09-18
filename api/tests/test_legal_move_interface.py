"""Tests for LegalMoveValidator interface and domain errors."""

from app.core.legal_move_interface import (
    IllegalMoveError,
    ValidatorConsistencyError,
    LegalMoveValidator,
)


class _ConcreteLegalMoveValidator(LegalMoveValidator):
    """Test validator that accepts all moves and has simple win logic."""

    def validate_move(self, state, move):
        return True

    def get_legal_moves(self, state, player_id):
        return [{"move_id": "m1", "player_id": player_id, "action": "move"}]

    def apply_move(self, state, move):
        new_data = dict(state.get("game_data", {}))
        new_data["last_move"] = move.get("move_id")
        return {**state, "game_data": new_data}

    def check_win(self, state):
        return None


class _ErrorRaisingValidator(LegalMoveValidator):
    """Test validator that raises IllegalMoveError for all moves."""

    def validate_move(self, state, move):
        raise IllegalMoveError("Move is illegal")

    def get_legal_moves(self, state, player_id):
        return []

    def apply_move(self, state, move):
        raise IllegalMoveError("Cannot apply")

    def check_win(self, state):
        return None


class _WinnerValidator(LegalMoveValidator):
    """Test validator that declares a winner when game_data has 'game_over'."""

    def validate_move(self, state, move):
        return True

    def get_legal_moves(self, state, player_id):
        return [{"move_id": "m1", "player_id": player_id}]

    def apply_move(self, state, move):
        new_data = dict(state.get("game_data", {}))
        new_data["game_over"] = True
        return {**state, "game_data": new_data}

    def check_win(self, state):
        if state.get("game_data", {}).get("game_over"):
            return "player_red"
        return None


def test_validate_move_returns_bool():
    """Verify validate_move returns True for legal moves."""
    validator = _ConcreteLegalMoveValidator()
    state = {"game_data": {}, "players": [], "current_player_index": 0}
    assert validator.validate_move(state, {"move_id": "m1"}) is True


def test_get_legal_moves_returns_list():
    """Verify get_legal_moves returns a list of move dicts."""
    validator = _ConcreteLegalMoveValidator()
    state = {"game_data": {}, "players": [], "current_player_index": 0}
    moves = validator.get_legal_moves(state, "player_red")
    assert isinstance(moves, list)
    assert len(moves) == 1
    assert moves[0]["move_id"] == "m1"
    assert moves[0]["player_id"] == "player_red"


def test_apply_move_returns_new_state():
    """Verify apply_move returns a new state dict with updated game_data."""
    validator = _ConcreteLegalMoveValidator()
    state = {"game_data": {"count": 0}, "players": [], "current_player_index": 0}
    move = {"move_id": "m1", "action": "move"}
    new_state = validator.apply_move(state, move)
    assert new_state["game_data"]["last_move"] == "m1"
    assert "count" in new_state["game_data"]


def test_check_win_returns_none_or_player_id():
    """Verify check_win returns None when no winner, or player_id when winner."""
    validator = _ConcreteLegalMoveValidator()
    state = {"game_data": {}}
    assert validator.check_win(state) is None

    winner_validator = _WinnerValidator()
    assert winner_validator.check_win({"game_data": {}}) is None
    assert winner_validator.check_win({"game_data": {"game_over": True}}) == "player_red"


def test_recommend_ai_move_picks_first_candidate():
    """Verify default recommend_ai_move returns the first candidate."""
    validator = _ConcreteLegalMoveValidator()
    state = {"game_data": {}}
    candidates = [
        {"move_id": "m1", "action": "move_forward"},
        {"move_id": "m2", "action": "move_backward"},
    ]
    result = validator.recommend_ai_move(state, candidates)
    assert result is not None
    assert result["move_id"] == "m1"


def test_recommend_ai_move_returns_none_for_empty_list():
    """Verify recommend_ai_move returns None for empty candidates."""
    validator = _ConcreteLegalMoveValidator()
    state = {"game_data": {}}
    result = validator.recommend_ai_move(state, [])
    assert result is None


def test_abstract_class_cannot_be_instantiated_directly():
    """Verify that LegalMoveValidator ABC cannot be instantiated."""
    try:
        LegalMoveValidator()  # type: ignore[abstract]
        assert False, "Should have raised TypeError"
    except TypeError:
        pass
