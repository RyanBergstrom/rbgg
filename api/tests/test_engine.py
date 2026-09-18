"""Tests for core defense-in-depth move pipeline."""

from app.core.engine import MovePipeline
from app.core.legal_move_interface import IllegalMoveError, LegalMoveValidator


def test_submit_move_happy_path():
    """Verify that a valid move submits successfully through the pipeline."""
    pipeline = MovePipeline()
    state = {"game_data": {}, "version": 0}
    move = {"move_id": "m1", "action": "move_forward"}

    result = pipeline.submit_move(state, move)
    assert result["move_id"] == "m1"
    assert result["status"] == "accepted"
    assert result["winner"] is None
    assert result["new_state"] is state


def test_submit_move_applies_move_and_checks_win():
    """Verify submit_move applies the move and checks for winner."""
    class WinOnMoveValidator(LegalMoveValidator):
        def validate_move(self, state, move):
            return True
        def get_legal_moves(self, state, player_id):
            return []
        def apply_move(self, state, move):
            return {**state, "game_data": {"moved": True}}
        def check_win(self, state):
            if state.get("game_data", {}).get("moved"):
                return "player_red"
            return None

    pipeline = MovePipeline(validator=WinOnMoveValidator())
    state = {"game_data": {}, "version": 0}
    move = {"move_id": "m1"}

    result = pipeline.submit_move(state, move)
    assert result["winner"] == "player_red"
    assert result["new_state"]["game_data"]["moved"] is True


def test_payload_schema_invalid_returns_illegal_move():
    """Verify that an invalid payload raises IllegalMoveError."""
    pipeline = MovePipeline()

    try:
        pipeline.submit_move({"game_data": {}}, {})
        assert False, "Should have raised IllegalMoveError"
    except IllegalMoveError:
        pass

    try:
        pipeline.submit_move({"game_data": {}}, "not_a_dict")  # type: ignore[arg-type]
        assert False, "Should have raised IllegalMoveError"
    except IllegalMoveError:
        pass


def test_move_not_in_legal_set_returns_illegal_move():
    """Verify that a move not in the legal set raises IllegalMoveError."""
    class StrictValidator(LegalMoveValidator):
        def validate_move(self, state, move):
            return False
        def get_legal_moves(self, state, player_id):
            return []
        def apply_move(self, state, move):
            return state
        def check_win(self, state):
            return None

    pipeline = MovePipeline(validator=StrictValidator())
    state = {"game_data": {}}
    move = {"move_id": "m1", "action": "illegal"}

    try:
        pipeline.submit_move(state, move)
        assert False, "Should have raised IllegalMoveError"
    except IllegalMoveError:
        pass


def test_version_conflict_raises_value_error():
    """Verify that a version conflict raises ValueError."""
    pipeline = MovePipeline()
    state = {"game_data": {}, "version": 5}
    move = {"move_id": "m1"}

    try:
        pipeline.submit_move(state, move, expected_version=3)
        assert False, "Should have raised ValueError"
    except ValueError as exc:
        assert "version conflict" in str(exc).lower()


def test_version_match_succeeds():
    """Verify that matching version passes the check."""
    pipeline = MovePipeline()
    state = {"game_data": {}, "version": 5}
    move = {"move_id": "m1"}

    result = pipeline.submit_move(state, move, expected_version=5)
    assert result["status"] == "accepted"


def test_get_legal_moves_for_player_delegates_to_validator():
    """Verify get_legal_moves_for_player delegates to the validator."""
    class ListValidator(LegalMoveValidator):
        def validate_move(self, state, move):
            return True
        def get_legal_moves(self, state, player_id):
            return [{"move_id": "m1", "player_id": player_id}]
        def apply_move(self, state, move):
            return state
        def check_win(self, state):
            return None

    pipeline = MovePipeline(validator=ListValidator())
    state = {"game_data": {}}
    moves = pipeline.get_legal_moves_for_player(state, "player_red")
    assert len(moves) == 1
    assert moves[0]["player_id"] == "player_red"


def test_get_ai_move_delegates_to_validator():
    """Verify get_ai_move delegates to validator.recommend_ai_move."""
    pipeline = MovePipeline()
    state = {"game_data": {}}
    candidates = [{"move_id": "m1"}, {"move_id": "m2"}]
    result = pipeline.get_ai_move(state, candidates)
    assert result == {"move_id": "m1"}
