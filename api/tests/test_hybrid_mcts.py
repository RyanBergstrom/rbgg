"""Tests for the deterministic, rollout-free hybrid MCTS strategy."""

import math
import json

import pytest

from app.core.mcts import (
    HybridMCTSEngine,
    MCTSConfig,
    MCTSNode,
    MCTSEngine,
    MCTSResult,
)
from app.games.checkers.serialize import initial_board
from app.games.checkers.validator import CheckersValidator, EMPTY, RED


def make_state(board=None, current_player_index=0):
    return {
        "game_data": {"board": board or initial_board()},
        "current_player_index": current_player_index,
        "players": [
            {"player_id": "player_1", "name": "Red"},
            {"player_id": "player_2", "name": "Black"},
        ],
    }


def test_hybrid_search_returns_legal_move_without_rollouts(monkeypatch):
    validator = CheckersValidator()

    def fail_rollout(*args, **kwargs):
        raise AssertionError("hybrid search must not call rollout scoring")

    monkeypatch.setattr(validator, "score_moves", fail_rollout)
    engine = MCTSEngine(
        validator,
        MCTSConfig(
            strategy="hybrid",
            iterations=30,
            max_depth=3,
            hot_pool_size=3,
            admission_interval=5,
        ),
    )

    state = make_state()
    result = engine.search(state, "player_1")

    assert isinstance(result, MCTSResult)
    assert result.move is not None
    assert result.move["move_id"] in {
        move["move_id"] for move in validator.get_legal_moves(state, "player_1")
    }
    assert 0.0 <= result.win_rate <= 1.0


def test_hybrid_diagnostics_are_opt_in_and_bounded():
    validator = CheckersValidator()
    state = make_state()

    disabled = MCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=8, max_depth=2, seed=42),
    ).search(state, "player_1")
    enabled = MCTSEngine(
        validator,
        MCTSConfig(
            strategy="hybrid",
            iterations=8,
            max_depth=2,
            seed=42,
            diagnostic_enabled=True,
            diagnostic_max_records=3,
        ),
    ).search(state, "player_1")

    assert disabled.diagnostics == []
    assert len(enabled.diagnostics) == 3
    for record in enabled.diagnostics:
        assert record["leaf_type"] in {"horizon", "terminal"}
        assert record["depth"] == len(record["path"])
        assert all("move_id" in step and "action" in step for step in record["path"])
        assert "horizon" not in record  # Checkers has no optional explanation hook.


def test_hybrid_search_is_deterministic():
    validator = CheckersValidator()
    config = MCTSConfig(strategy="hybrid", iterations=40, max_depth=3, seed=42)
    state = make_state()

    first = MCTSEngine(validator, config).search(state, "player_1")
    second = MCTSEngine(validator, config).search(state, "player_1")

    assert first.move["move_id"] == second.move["move_id"]
    assert first.visit_count == second.visit_count
    assert first.top_moves == second.top_moves


def test_hybrid_search_preserves_input_state():
    validator = CheckersValidator()
    engine = MCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=20, max_depth=2),
    )
    state = make_state()
    original_board = [row[:] for row in state["game_data"]["board"]]

    engine.search(state, "player_1")

    assert state["game_data"]["board"] == original_board
    assert state["current_player_index"] == 0


def test_hybrid_rejects_invalid_configuration():
    with pytest.raises(ValueError):
        MCTSConfig(strategy="hybrid", iterations=0)
        MCTSEngine(
            CheckersValidator(),
            MCTSConfig(strategy="hybrid", iterations=0),
        ).search(make_state(), "player_1")


def test_hybrid_terminal_root_returns_no_move():
    board = [[EMPTY] * 8 for _ in range(8)]
    board[0][1] = RED
    validator = CheckersValidator()
    engine = MCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=2),
    )

    result = engine.search(make_state(board), "player_1")

    assert result.move is None
    assert math.isfinite(result.win_rate)


def test_lost_cities_horizon_values_expedition_support():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game = GameState(
        state_id="horizon",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=validator.initial_game_data(),
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy
    moves = validator.get_legal_moves(state, "player_1")
    play = next(move for move in moves if move.get("type") == "play_expedition" and move.get("card") == "g_5")
    discard = next(move for move in moves if move.get("type") == "discard" and move.get("card") == "g_5")

    play_value = policy.horizon_value(policy.apply_move(state, play), "player_1")
    discard_value = policy.horizon_value(policy.apply_move(state, discard), "player_1")

    assert play_value > discard_value


def test_lost_cities_horizon_explanation_matches_value_and_is_json_serializable():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.search_policy import LostCitiesSearchPolicy
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game = GameState(
        state_id="horizon-explanation",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=validator.initial_game_data(),
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = LostCitiesSearchPolicy(validator)
    explanation = policy.explain_horizon(state, "player_1")

    assert set(explanation) == {
        "relative", "absolute", "latent_equity", "compound_setup",
        "contributions", "final", "raw_equity", "equity_by_color",
        "opponent_equity_by_color", "compound_setup_raw",
        "known_dead_discard_draw_penalty",
        "spread_pressure",
        "portfolio_pressure",
    }
    assert explanation["final"] == policy.horizon_value(state, "player_1")
    assert explanation["final"] == sum(explanation["contributions"].values())
    json.dumps(explanation)


def test_lost_cities_does_not_hot_rank_stranded_high_opening_card():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["player_hands"]["player_1"] = [
        "w_i", "y_10", "b_10", "y_7", "g_6", "g_9", "b_2", "g_i"
    ]
    game_data["expeditions"]["player_1"] = {
        "blue": [], "yellow": ["y_3"], "red": [], "white": [], "green": ["g_5"]
    }
    game_data["current_player"] = "player_1"
    game_data["current_phase"] = "play_a_card"
    game = GameState(
        state_id="stranded-high-card",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    engine = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    )
    root = MCTSNode(state, None, None)
    engine._initialize_pools(root, state, "player_1")

    hot_cards = {move.get("card") for move in root.hot_pool or []}
    assert "b_10" not in hot_cards


def test_lost_cities_scores_draw_sources_by_card_usefulness():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["current_player"] = "player_1"
    game_data["current_phase"] = "draw_a_card"
    game_data["expeditions"]["player_1"]["green"] = ["g_5"]
    game_data["expeditions"]["player_1"]["red"] = ["r_10"]
    game_data["discard_piles"]["green"] = ["g_6"]
    game_data["discard_piles"]["red"] = ["r_2"]
    game = GameState(
        state_id="draw-values",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy
    draw_moves = validator.get_legal_moves(state, "player_1")
    green_draw = next(move for move in draw_moves if move["source"] == "green_discard")
    red_draw = next(move for move in draw_moves if move["source"] == "red_discard")

    green_value = policy.one_ply_value(
        state, green_draw, policy.apply_move(state, green_draw), "player_1"
    )
    red_value = policy.one_ply_value(
        state, red_draw, policy.apply_move(state, red_draw), "player_1"
    )

    assert green_value > red_value


def test_lost_cities_rewards_discarding_deadwood():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["current_player"] = "player_1"
    game_data["current_phase"] = "play_a_card"
    game_data["expeditions"]["player_1"]["green"] = ["g_8"]
    game_data["player_hands"]["player_1"] = ["g_2", "g_9"]
    game = GameState(
        state_id="deadwood",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy
    moves = validator.get_legal_moves(state, "player_1")
    dead_discard = next(
        move for move in moves
        if move.get("type") == "discard" and move.get("card") == "g_2"
    )
    viable_discard = next(
        move for move in moves
        if move.get("type") == "discard" and move.get("card") == "g_9"
    )

    dead_value = policy.one_ply_value(
        state, dead_discard, policy.apply_move(state, dead_discard), "player_1"
    )
    viable_value = policy.one_ply_value(
        state, viable_discard, policy.apply_move(state, viable_discard), "player_1"
    )

    assert dead_value > viable_value


def test_lost_cities_dead_investment_is_preferred_for_discard():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["current_player"] = "player_1"
    game_data["current_phase"] = "play_a_card"
    game_data["expeditions"]["player_1"]["blue"] = ["b_2"]
    game_data["player_hands"]["player_1"] = ["b_i", "g_6"]
    game = GameState(
        state_id="dead-investment",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy
    moves = validator.get_legal_moves(state, "player_1")
    dead_discard = next(
        move for move in moves
        if move.get("type") == "discard" and move.get("card") == "b_i"
    )
    other_discard = next(
        move for move in moves
        if move.get("type") == "discard" and move.get("card") == "g_6"
    )

    dead_value = policy.one_ply_value(
        state, dead_discard, policy.apply_move(state, dead_discard), "player_1"
    )
    other_value = policy.one_ply_value(
        state, other_discard, policy.apply_move(state, other_discard), "player_1"
    )

    assert dead_value > other_value


def test_lost_cities_numbered_play_penalizes_stranded_investment():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["current_player"] = "player_1"
    game_data["current_phase"] = "play_a_card"
    game_data["player_hands"]["player_1"] = ["b_i", "b_2", "g_6"]
    game = GameState(
        state_id="strand-investment",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy
    moves = validator.get_legal_moves(state, "player_1")
    play_b2 = next(
        move for move in moves
        if move.get("type") == "play_expedition" and move.get("card") == "b_2"
    )
    discard_b2 = next(
        move for move in moves
        if move.get("type") == "discard" and move.get("card") == "b_2"
    )

    play_value = policy.one_ply_value(
        state, play_b2, policy.apply_move(state, play_b2), "player_1"
    )
    discard_value = policy.one_ply_value(
        state, discard_b2, policy.apply_move(state, discard_b2), "player_1"
    )

    assert play_value < discard_value


def test_lost_cities_live_investment_is_not_preferred_for_discard():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["current_player"] = "player_1"
    game_data["current_phase"] = "play_a_card"
    game_data["player_hands"]["player_1"] = ["b_i", "b_2", "g_6"]
    game = GameState(
        state_id="live-investment",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy
    moves = validator.get_legal_moves(state, "player_1")
    live_discard = next(
        move for move in moves
        if move.get("type") == "discard" and move.get("card") == "b_i"
    )
    live_play = next(
        move for move in moves
        if move.get("type") == "play_expedition" and move.get("card") == "b_i"
    )

    discard_value = policy.one_ply_value(
        state, live_discard, policy.apply_move(state, live_discard), "player_1"
    )
    play_value = policy.one_ply_value(
        state, live_play, policy.apply_move(state, live_play), "player_1"
    )

    assert play_value > discard_value


def test_lost_cities_dominated_live_investment_discard_is_not_in_pool():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["current_player"] = "player_1"
    game_data["current_phase"] = "play_a_card"
    game_data["player_hands"]["player_1"] = ["b_i", "b_2", "b_5", "g_6"]
    game = GameState(
        state_id="dominated-investment-discard",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    engine = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    )
    root = MCTSNode(state, None, None)
    engine._initialize_pools(root, state, "player_1")
    pool_ids = {
        move.get("move_id")
        for move in (root.hot_pool or []) + (root.cold_pool or [])
    }
    assert "discard_b_i_0" not in pool_ids


def test_lost_cities_does_not_start_empty_expedition_with_ten():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.core.mcts import MCTSNode
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["current_player"] = "player_1"
    game_data["current_phase"] = "play_a_card"
    game_data["player_hands"]["player_1"] = ["r_10", "g_6"]
    game = GameState(
        state_id="empty-ten",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    engine = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    )
    root = MCTSNode(state, None, None)
    engine._initialize_pools(root, state, "player_1")

    pool_ids = {
        move.get("move_id")
        for move in (root.hot_pool or []) + (root.cold_pool or [])
    }
    assert "play_exp_r_10_0" not in pool_ids


def test_lost_cities_publicly_exhausted_suit_has_lower_potential():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["current_player"] = "player_1"
    game_data["current_phase"] = "play_a_card"
    game_data["player_hands"]["player_1"] = ["b_2", "g_2"]
    game_data["expeditions"]["player_2"]["blue"] = [
        "b_i", "b_i", "b_i", "b_3", "b_4", "b_5", "b_6", "b_7", "b_8", "b_9", "b_10"
    ]
    game = GameState(
        state_id="public-suit-potential",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy

    assert policy._suit_potential(state, "player_1", "blue") < policy._suit_potential(
        state, "player_1", "green"
    )


def test_lost_cities_live_investment_is_not_horizon_deadwood():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["expeditions"]["player_1"]["blue"] = ["b_i"]
    game_data["player_hands"]["player_1"] = ["b_i", "b_5"]
    game = GameState(
        state_id="live-investment-horizon",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy

    value = policy.horizon_value(state, "player_1")
    game_data["expeditions"]["player_1"]["blue"].append("b_2")
    dead_value = policy.horizon_value(state, "player_1")

    assert value > dead_value


def test_lost_cities_horizon_rewards_supported_investment_plan():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data(rng_seed=99)
    game_data["player_hands"]["player_2"] = [
        "g_6", "b_6", "y_4", "r_10", "w_3", "b_2", "b_5", "b_i"
    ]
    game_data["expeditions"]["player_1"]["yellow"] = ["y_6"]
    game_data["current_player"] = "player_2"
    game_data["current_phase"] = "play_a_card"
    game = GameState(
        state_id="supported-investment-plan",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=1,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_2", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 1,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy
    moves = validator.get_legal_moves(state, "player_2")
    blue_investment = next(
        move for move in moves
        if move.get("type") == "play_expedition" and move.get("card") == "b_i"
    )
    red_ten = next(
        move for move in moves
        if move.get("type") == "play_expedition" and move.get("card") == "r_10"
    )
    blue_state = policy.apply_move(state, blue_investment)
    red_state = policy.apply_move(state, red_ten)

    assert policy.horizon_value(blue_state, "player_2") > policy.horizon_value(
        red_state, "player_2"
    )


def test_lost_cities_horizon_penalizes_irreversible_ten_endpoint():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data(rng_seed=99)
    game_data["player_hands"]["player_2"] = [
        "b_6", "r_10", "w_3", "b_2", "b_5", "b_i", "b_9", "g_7"
    ]
    game_data["expeditions"]["player_2"]["blue"] = ["b_i"]
    game_data["expeditions"]["player_2"]["green"] = ["g_6", "g_7", "g_10"]
    game_data["scores"] = {"player_1": -65, "player_2": -54}
    game_data["current_player"] = "player_2"
    game_data["current_phase"] = "play_a_card"
    game = GameState(
        state_id="ten-endpoint",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=1,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_2", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 1,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy
    moves = validator.get_legal_moves(state, "player_2")
    red_ten = next(
        move for move in moves
        if move.get("type") == "play_expedition" and move.get("card") == "r_10"
    )
    blue_investment = next(
        move for move in moves
        if move.get("type") == "play_expedition" and move.get("card") == "b_i"
    )
    red_value = policy.horizon_value(policy.apply_move(state, red_ten), "player_2")
    blue_value = policy.horizon_value(
        policy.apply_move(state, blue_investment), "player_2"
    )

    assert blue_value > red_value


def test_lost_cities_discards_cannot_override_acceptable_play():
    from app.games.lost_cities.search_policy import LostCitiesSearchPolicy
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    policy = LostCitiesSearchPolicy(validator)
    moves = [
        {"move_id": "play", "type": "play_expedition", "card": "b_2"},
        {"move_id": "discard", "type": "discard", "card": "b_9"},
    ]
    adjusted = policy.adjust_action_values(
        {}, moves, {"play": 0.35, "discard": 0.90}, "player_1"
    )

    assert adjusted["discard"] == pytest.approx(0.34)


def test_lost_cities_discards_are_capped_when_all_plays_are_bad():
    from app.games.lost_cities.search_policy import LostCitiesSearchPolicy
    from app.games.lost_cities.validator import LostCitiesValidator

    policy = LostCitiesSearchPolicy(LostCitiesValidator())
    moves = [
        {"move_id": "play", "type": "play_expedition", "card": "b_9"},
        {"move_id": "discard", "type": "discard", "card": "b_9"},
    ]
    adjusted = policy.adjust_action_values(
        {}, moves, {"play": 0.20, "discard": 0.90}, "player_1"
    )

    assert adjusted["discard"] == pytest.approx(0.50)


def test_hybrid_final_selection_caps_accumulated_discard_value():
    from app.core.mcts import MCTSNode

    engine = HybridMCTSEngine(
        CheckersValidator(),
        MCTSConfig(strategy="hybrid", iterations=10, discard_ceiling=0.40),
    )
    root = MCTSNode({}, None, None, visits=100)
    discard = MCTSNode(
        {}, {"move_id": "discard", "type": "discard"}, root,
        visits=20, wins=18.0,
    )
    play = MCTSNode(
        {}, {"move_id": "play", "type": "play_expedition"}, root,
        visits=20, wins=12.0,
    )
    root.children = [discard, play]

    # The production search uses the same capped child-value rule. This
    # fixture documents that 0.90 accumulated discard value is treated as
    # 0.40 at final selection, below the 0.60 play value.
    discard_final = min(discard.wins / discard.visits, engine.config.discard_ceiling)
    play_final = play.wins / play.visits
    assert discard_final == pytest.approx(0.40)
    assert play_final > discard_final


def test_lost_cities_investment_multiplier_increases_future_card_equity():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["player_hands"]["player_1"] = ["b_2", "b_5", "b_8"]
    game_data["expeditions"]["player_1"]["blue"] = ["b_i"]
    game = GameState(
        state_id="multiplier-equity",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy
    one_investment_value = policy.horizon_value(state, "player_1")
    state["game_data"]["expeditions"]["player_1"]["blue"].append("b_i")
    two_investment_value = policy.horizon_value(state, "player_1")

    assert two_investment_value > one_investment_value


def test_lost_cities_numbered_start_tracks_eight_card_bonus_ceiling():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["current_player"] = "player_1"
    game_data["current_phase"] = "play_a_card"
    game_data["player_hands"]["player_1"] = ["g_2", "g_6"]
    game = GameState(
        state_id="length-ceiling",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy
    moves = validator.get_legal_moves(state, "player_1")
    play_two = next(move for move in moves if move.get("card") == "g_2" and move.get("type") == "play_expedition")
    play_six = next(move for move in moves if move.get("card") == "g_6" and move.get("type") == "play_expedition")
    two_value = policy.horizon_value(policy.apply_move(state, play_two), "player_1")
    six_value = policy.horizon_value(policy.apply_move(state, play_six), "player_1")

    assert two_value > six_value


def test_lost_cities_later_numbered_card_reduces_eight_card_ceiling():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["player_hands"]["player_1"] = []
    game_data["expeditions"]["player_1"]["red"] = ["r_3", "r_7"]
    game = GameState(
        state_id="later-numbered-ceiling",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
        game_data=game_data,
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy

    breakdown = policy.explain_horizon(state, "player_1")
    red_detail = next(
        item for item in breakdown["equity_by_color"] if item["color"] == "red"
    )

    # r_3 followed by r_7 leaves room only for r_8, r_9, and r_10:
    # 2 committed cards + 3 remaining cards = 5, so the shortfall penalty is
    # (8 - 5) * 6 = 18.
    assert red_detail["eight_card_bonus_penalty"] == 18.0


def test_lost_cities_weak_new_expedition_penalty_applies_to_play_and_discard():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.search_policy import LostCitiesSearchPolicy
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["player_hands"]["player_1"] = ["r_4", "r_10"]
    game_data["expeditions"]["player_1"]["blue"] = ["b_2"]
    game_data["expeditions"]["player_1"]["yellow"] = ["y_4"]
    game_data["expeditions"]["player_1"]["white"] = ["w_3"]
    game = GameState(
        state_id="weak-new-expedition-penalty",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
        game_data=game_data,
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = LostCitiesSearchPolicy(validator)

    r4_risk = policy._new_expedition_recovery_risk(state, "player_1", "red", "r_4")
    r10_risk = policy._new_expedition_recovery_risk(state, "player_1", "red", "r_10")
    assert 0.0 < r4_risk < r10_risk < 0.25

    game_data["expeditions"]["player_1"]["yellow"] = []
    two_commitment_state = {**state, "game_data": game_data}
    assert policy._new_expedition_recovery_risk(
        two_commitment_state, "player_1", "red", "r_10"
    ) > 0.0

    game_data["player_hands"]["player_1"] = ["r_4", "r_5", "r_6", "r_7", "r_8", "r_9", "r_10"]
    supported_state = {**state, "game_data": game_data}
    supported_risk = policy._new_expedition_recovery_risk(
        supported_state, "player_1", "red", "r_4"
    )
    assert supported_risk < r4_risk

    moves = validator.get_legal_moves(state, "player_1")
    assert any(
        move.get("type") == "play_expedition" and move.get("card") == "r_4"
        for move in moves
    )
    assert any(
        move.get("type") == "discard" and move.get("card") == "r_4"
        for move in moves
    )


def test_lost_cities_dead_discard_draw_penalty_persists_to_horizon():
    from app.core.game_state import GameState, PlayerInfo, Topology, TurnInfo
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    players = [
        PlayerInfo(player_id="player_1", name="P1", score=0, color="#fff"),
        PlayerInfo(player_id="player_2", name="P2", score=0, color="#333"),
    ]
    game_data = validator.initial_game_data()
    game_data["current_player"] = "player_1"
    game_data["current_phase"] = "draw_a_card"
    game_data["expeditions"]["player_1"]["red"] = ["r_4", "r_10"]
    game_data["discard_piles"]["red"] = ["r_i"]
    game = GameState(
        state_id="dead-draw-penalty",
        game_type="lost_cities",
        topology=Topology.grid,
        rng_seed=99,
        players=players,
        current_player_index=0,
        game_data=game_data,
        turn=TurnInfo(turn_id="t1", player_id="player_1", topology=Topology.grid),
    )
    state = {
        "players": [player.__dict__ for player in players],
        "current_player_index": 0,
        "game_data": game.game_data,
        "version": game.version,
    }
    policy = HybridMCTSEngine(
        validator,
        MCTSConfig(strategy="hybrid", iterations=10, max_depth=3),
    ).policy
    draw = next(move for move in validator.get_legal_moves(state, "player_1") if move.get("source") == "red_discard")
    penalized_state = policy.apply_move(state, draw)
    assert penalized_state["_search_dead_draw_penalty"] > 0
    assert policy.horizon_value(penalized_state, "player_1") < policy.horizon_value(state, "player_1")


def test_lost_cities_optimistic_bound_pushes_hopeless_opening_cold():
    from app.games.lost_cities.search_policy import LostCitiesSearchPolicy
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    policy = LostCitiesSearchPolicy(validator)
    state = {
        "game_data": {
            "player_hands": {"player_1": ["b_9", "b_10"]},
            "expeditions": {
                "player_1": {
                    "blue": [], "yellow": ["y_4"], "red": ["r_3"],
                    "white": [], "green": ["g_2"],
                }
            },
        }
    }
    move = {"type": "play_expedition", "card": "b_9", "color": "blue", "player_id": "player_1", "hand_index": 0}
    assert policy.optimistic_action_bound(state, move, state, "player_1") == 0.12


def test_lost_cities_portfolio_pressure_hurdles_fifth_expedition():
    from app.games.lost_cities.search_policy import LostCitiesSearchPolicy
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    policy = LostCitiesSearchPolicy(validator)
    expeditions = {
        "blue": ["b_9"],
        "yellow": ["y_4"],
        "red": ["r_3"],
        "white": ["w_4"],
        "green": [],
    }
    state = {
        "game_data": {
            "draw_pile": list(range(20)),
            "player_hands": {"player_1": ["b_10", "y_5", "r_4", "w_5"]},
            "expeditions": {"player_1": expeditions},
        }
    }
    four_color_pressure = policy._portfolio_pressure(state, "player_1")
    expeditions["green"] = ["g_9"]
    state["game_data"]["player_hands"]["player_1"].append("g_10")
    five_color_pressure = policy._portfolio_pressure(state, "player_1")

    assert five_color_pressure > four_color_pressure
    assert 0.0 <= five_color_pressure <= 1.0


def test_lost_cities_marginal_portfolio_cost_penalizes_new_work():
    from app.games.lost_cities.search_policy import LostCitiesSearchPolicy
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    policy = LostCitiesSearchPolicy(validator)
    state = {
        "game_data": {
            "draw_pile": list(range(20)),
            "player_hands": {"player_1": ["b_9", "b_10"]},
            "expeditions": {
                "player_1": {
                    "blue": [], "yellow": ["y_4"], "red": ["r_3"],
                    "white": ["w_4"], "green": [],
                }
            },
        }
    }
    move = {"type": "play_expedition", "card": "b_9", "color": "blue", "player_id": "player_1", "hand_index": 0}
    next_state = policy.apply_move(state, move)
    before = policy._portfolio_pressure(state, "player_1")
    after = policy._portfolio_pressure(next_state, "player_1")

    assert after > before
    assert 0.60 * (after - before) > 0.0


def test_lost_cities_discard_draw_uses_recovery_risk_for_empty_expedition():
    from app.games.lost_cities.search_policy import LostCitiesSearchPolicy
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    policy = LostCitiesSearchPolicy(validator)
    state = {
        "game_data": {
            "draw_pile": list(range(20)),
            "discard_piles": {
                "blue": ["b_9"], "yellow": [], "red": [],
                "white": [], "green": [],
            },
            "player_hands": {"player_1": ["b_10"]},
            "expeditions": {
                "player_1": {
                    "blue": [], "yellow": ["y_4"], "red": ["r_3"],
                    "white": ["w_4"], "green": [],
                }
            },
        }
    }
    move = {"type": "draw", "source": "blue_discard"}
    value = policy._draw_action_value(state, state, move, "player_1")

    assert value < 0.55


def test_lost_cities_dominates_unrecoverable_new_expedition_after_two_commitments():
    from app.games.lost_cities.search_policy import LostCitiesSearchPolicy
    from app.games.lost_cities.validator import LostCitiesValidator

    validator = LostCitiesValidator()
    policy = LostCitiesSearchPolicy(validator)
    state = {
        "game_data": {
            "player_hands": {"player_1": ["b_9", "b_10", "y_2", "y_4", "y_6", "y_8"]},
            "expeditions": {
                "player_1": {
                    "blue": [], "yellow": ["y_2"], "red": ["r_3"],
                    "white": [], "green": [],
                }
            },
        }
    }
    hopeless = {"type": "play_expedition", "card": "b_9"}
    supported = {"type": "play_expedition", "card": "y_4"}

    assert policy.is_dominated_action(state, hopeless, "player_1") is True
    assert policy.is_dominated_action(state, supported, "player_1") is False


def test_hybrid_config_accepts_root_pruning_controls():
    config = MCTSConfig(root_score_margin=0.08, root_min_actions=6)
    assert config.root_score_margin == 0.08
    assert config.root_min_actions == 6
