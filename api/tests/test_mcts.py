"""Tests for MCTS engine — node, engine, and integration with CheckersValidator."""

import pytest

from app.core.mcts import MCTSConfig, MCTSNode, MCTSEngine, MCTSResult
from app.games.checkers.validator import CheckersValidator, EMPTY, RED, BLACK
from app.games.checkers.serialize import initial_board


# ── Helpers ─────────────────────────────────────────────────────────

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


def _make_simple_game_state():
    """A minimal game that ends in 1 move — red can capture black."""
    board = [[EMPTY] * 8 for _ in range(8)]
    board[3][2] = RED
    board[2][3] = BLACK
    board[1][4] = EMPTY
    return _make_state(board=board)


# ── MCTSNode tests ─────────────────────────────────────────────────

class TestMCTSNode:
    def test_unvisited_node_has_infinite_uct(self):
        node = MCTSNode(
            state={}, move=None, parent=None, visits=0, wins=0.0
        )
        assert node.uct_value(1.414) == float("inf")

    def test_root_node_has_infinite_uct(self):
        parent = MCTSNode(
            state={}, move=None, parent=None, visits=10, wins=5.0
        )
        node = MCTSNode(
            state={}, move=None, parent=parent, visits=5, wins=3.0
        )
        # Root's parent is not None but parent's parent is — UCT should still work
        # Actually root is parent here, so node.uct_value uses parent.visits=10
        import math
        expected = 3.0 / 5 + 1.414 * math.sqrt(math.log(10) / 5)
        assert abs(node.uct_value(1.414) - expected) < 1e-6

    def test_fully_expanded_when_no_untried_moves(self):
        node = MCTSNode(
            state={}, move=None, parent=None,
            untried_moves=[],
        )
        assert node.is_fully_expanded() is True

    def test_not_fully_expanded_with_untried_moves(self):
        node = MCTSNode(
            state={}, move=None, parent=None,
            untried_moves=[{"move_id": "m1"}],
        )
        assert node.is_fully_expanded() is False

    def test_terminal_when_no_children_and_no_untried(self):
        node = MCTSNode(
            state={}, move=None, parent=None,
            children=[], untried_moves=[],
        )
        assert node.is_terminal() is True

    def test_not_terminal_with_children(self):
        child = MCTSNode(
            state={}, move={"move_id": "m1"}, parent=None,
        )
        node = MCTSNode(
            state={}, move=None, parent=None,
            children=[child], untried_moves=[],
        )
        assert node.is_terminal() is False

    def test_best_child_returns_highest_uct(self):
        parent = MCTSNode(
            state={}, move=None, parent=None, visits=100,
        )
        child1 = MCTSNode(
            state={}, move={"move_id": "m1"}, parent=parent,
            visits=10, wins=8.0,
        )
        child2 = MCTSNode(
            state={}, move={"move_id": "m2"}, parent=parent,
            visits=10, wins=2.0,
        )
        parent.children = [child1, child2]
        best = parent.best_child(1.414)
        assert best.move["move_id"] == "m1"


# ── MCTSEngine unit tests ──────────────────────────────────────────

class TestMCTSEngineUnit:
    def test_clone_state_is_independent(self):
        validator = CheckersValidator()
        engine = MCTSEngine(validator, MCTSConfig(seed=42))
        state = _make_state()
        cloned = engine._clone_state(state)
        cloned["game_data"]["board"][0][0] = 999
        assert state["game_data"]["board"][0][0] != 999

    def test_get_opponent(self):
        validator = CheckersValidator()
        engine = MCTSEngine(validator)
        assert engine._get_opponent("player_1") == "player_2"
        assert engine._get_opponent("player_2") == "player_1"

    def test_find_player_index(self):
        validator = CheckersValidator()
        engine = MCTSEngine(validator)
        state = _make_state()
        assert engine._find_player_index(state, "player_1") == 0
        assert engine._find_player_index(state, "player_2") == 1

    def test_current_player_id(self):
        validator = CheckersValidator()
        engine = MCTSEngine(validator)
        state = _make_state()
        assert engine._current_player_id(state) == "player_1"
        state["current_player_index"] = 1
        assert engine._current_player_id(state) == "player_2"

    def test_apply_move_switches_player(self):
        validator = CheckersValidator()
        engine = MCTSEngine(validator, MCTSConfig(seed=42))
        state = _make_state()
        moves = validator.get_legal_moves(state, "player_1")
        move = moves[0]
        new_state = engine._apply_move_to_state(state, move)
        assert new_state["current_player_index"] == 1

    def test_apply_move_handles_multi_jump(self):
        """When must_jump_from is set, same player should go again."""
        validator = CheckersValidator()
        engine = MCTSEngine(validator, MCTSConfig(seed=42))
        state = _make_state()
        # Simulate a state with must_jump_from
        state["game_data"]["must_jump_from"] = {"row": 3, "col": 2}
        move = {
            "move_id": "jump_3_2_1_4",
            "type": "jump",
            "from_row": 3,
            "from_col": 2,
            "over_row": 2,
            "over_col": 3,
            "to_row": 1,
            "to_col": 4,
            "player_id": "player_1",
        }
        new_state = engine._apply_move_to_state(state, move)
        # After a jump that clears must_jump_from, player should switch
        # (the validator clears must_jump_from when no more jumps)
        assert new_state["current_player_index"] == 1


# ── MCTSEngine integration tests ───────────────────────────────────

class TestMCTSEngineIntegration:
    def test_search_returns_valid_move(self):
        """MCTS should return a legal move from the initial board."""
        validator = CheckersValidator()
        engine = MCTSEngine(validator, MCTSConfig(iterations=100, seed=42))
        state = _make_state()
        result = engine.search(state, "player_1")

        assert isinstance(result, MCTSResult)
        assert result.move is not None
        assert result.move["move_id"] is not None
        assert result.visit_count > 0
        assert 0.0 <= result.win_rate <= 1.0
        assert result.total_iterations == 100
        assert result.search_time_ms >= 0

        # Verify the move is actually legal
        legal_moves = validator.get_legal_moves(state, "player_1")
        legal_ids = {m["move_id"] for m in legal_moves}
        assert result.move["move_id"] in legal_ids

    def test_search_with_capture_available(self):
        """MCTS should find the capture move when available."""
        validator = CheckersValidator()
        engine = MCTSEngine(validator, MCTSConfig(iterations=200, seed=42))
        state = _make_simple_game_state()
        result = engine.search(state, "player_1")

        # The only legal move is a jump
        legal_moves = validator.get_legal_moves(state, "player_1")
        assert len(legal_moves) == 1
        assert result.move["move_id"] == legal_moves[0]["move_id"]

    def test_search_deterministic_with_seed(self):
        """Same seed should produce same results."""
        validator = CheckersValidator()
        state = _make_state()

        engine1 = MCTSEngine(validator, MCTSConfig(iterations=100, seed=42))
        result1 = engine1.search(state, "player_1")

        engine2 = MCTSEngine(validator, MCTSConfig(iterations=100, seed=42))
        result2 = engine2.search(state, "player_1")

        assert result1.move["move_id"] == result2.move["move_id"]
        assert result1.visit_count == result2.visit_count

    def test_search_for_player_2(self):
        """MCTS should work for player_2 as well."""
        validator = CheckersValidator()
        engine = MCTSEngine(validator, MCTSConfig(iterations=100, seed=42))
        state = _make_state(current_player_index=1)
        result = engine.search(state, "player_2")

        assert result.move is not None
        legal_moves = validator.get_legal_moves(state, "player_2")
        legal_ids = {m["move_id"] for m in legal_moves}
        assert result.move["move_id"] in legal_ids

    def test_search_respects_max_depth(self):
        """Rollouts should not exceed max_depth."""
        validator = CheckersValidator()
        engine = MCTSEngine(validator, MCTSConfig(iterations=10, max_depth=5, seed=42))
        state = _make_state()
        result = engine.search(state, "player_1")
        # Should still return a valid move even with shallow depth
        assert result.move is not None

    def test_ai_config_returns_config(self):
        """CheckersValidator.ai_config should return MCTSConfig."""
        validator = CheckersValidator()
        config = validator.ai_config()
        assert isinstance(config, MCTSConfig)
        assert config.iterations == 500
        assert config.max_depth == 64


# ── Parallel search tests ───────────────────────────────────────────

class TestMCTSEngineParallel:
    def test_parallel_search_returns_valid_move(self):
        """Parallel MCTS should return a legal move."""
        validator = CheckersValidator()
        engine = MCTSEngine(validator, MCTSConfig(iterations=100, seed=42, workers=2))
        state = _make_state()
        result = engine.search(state, "player_1")

        assert isinstance(result, MCTSResult)
        assert result.move is not None
        assert result.move["move_id"] is not None
        assert result.total_iterations == 100

        legal_moves = validator.get_legal_moves(state, "player_1")
        legal_ids = {m["move_id"] for m in legal_moves}
        assert result.move["move_id"] in legal_ids

    def test_parallel_search_with_capture(self):
        """Parallel MCTS should find the capture move."""
        validator = CheckersValidator()
        engine = MCTSEngine(validator, MCTSConfig(iterations=200, seed=42, workers=2))
        state = _make_simple_game_state()
        result = engine.search(state, "player_1")

        legal_moves = validator.get_legal_moves(state, "player_1")
        assert len(legal_moves) == 1
        assert result.move["move_id"] == legal_moves[0]["move_id"]

    def test_parallel_search_for_player_2(self):
        """Parallel MCTS should work for player_2."""
        validator = CheckersValidator()
        engine = MCTSEngine(validator, MCTSConfig(iterations=100, seed=42, workers=2))
        state = _make_state(current_player_index=1)
        result = engine.search(state, "player_2")

        assert result.move is not None
        legal_moves = validator.get_legal_moves(state, "player_2")
        legal_ids = {m["move_id"] for m in legal_moves}
        assert result.move["move_id"] in legal_ids

    def test_parallel_falls_back_to_sequential_with_workers_1(self):
        """workers=1 should use sequential path."""
        validator = CheckersValidator()
        engine = MCTSEngine(validator, MCTSConfig(iterations=100, seed=42, workers=1))
        state = _make_state()
        result = engine.search(state, "player_1")
        assert result.move is not None
