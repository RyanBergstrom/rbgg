"""Tests for RNG persistence and deterministic replay coverage."""

from app.core.engine import MovePipeline
from app.games.lost_cities.validator import LostCitiesValidator, _initial_game_data


def test_same_seed_same_move_sequence_same_outcome():
    """Verify that identical seeds and move sequences produce identical outcomes."""
    pipeline = MovePipeline()

    state1 = {"rng_seed": 123, "rng_state_json": "{}", "game_data": {}, "version": 0}
    state2 = {"rng_seed": 123, "rng_state_json": "{}", "game_data": {}, "version": 0}

    move = {"move_id": "m1", "action": "move_forward"}

    result1 = pipeline.submit_move(state1, move)
    result2 = pipeline.submit_move(state2, move)

    # RNG state should be the same after the same move from the same seed
    assert result1["new_state"]["rng_state_json"] == result2["new_state"]["rng_state_json"]

    # Second move with the same seed and same move should produce the same result
    state1_2 = {"rng_seed": 123, "rng_state_json": "{}", "game_data": {}, "version": 0}
    state2_2 = {"rng_seed": 123, "rng_state_json": "{}", "game_data": {}, "version": 0}
    result1_2 = pipeline.submit_move(state1_2, move)
    result2_2 = pipeline.submit_move(state2_2, move)

    assert result1_2["new_state"]["rng_state_json"] == result2_2["new_state"]["rng_state_json"]


def test_rng_state_persists_after_each_move():
    """Verify that rng_state_json is persisted after each move submission."""
    pipeline = MovePipeline()

    state = {"rng_seed": 42, "rng_state_json": "{}", "game_data": {}, "version": 0}
    move = {"move_id": "m1", "action": "move_forward"}

    # First move
    result1 = pipeline.submit_move(state, move)
    rng1 = result1["new_state"]["rng_state_json"]
    assert isinstance(rng1, str)
    assert rng1 != "{}"

    # Second move - state should persist and advance
    move2 = {"move_id": "m2", "action": "move_backward"}
    result2 = pipeline.submit_move(result1["new_state"], move2)
    rng2 = result2["new_state"]["rng_state_json"]
    assert isinstance(rng2, str)
    assert rng2 != rng1  # should have advanced

    # Third move
    move3 = {"move_id": "m3", "action": "move_forward"}
    result3 = pipeline.submit_move(result2["new_state"], move3)
    rng3 = result3["new_state"]["rng_state_json"]
    assert isinstance(rng3, str)
    assert rng3 != rng2  # should have advanced again


def test_different_seeds_produce_different_states():
    """Verify that different seeds produce different RNG states after same move."""
    pipeline = MovePipeline()

    state1 = {"rng_seed": 1, "rng_state_json": "{}", "game_data": {}, "version": 0}
    state2 = {"rng_seed": 2, "rng_state_json": "{}", "game_data": {}, "version": 0}
    move = {"move_id": "m1"}

    r1 = pipeline.submit_move(state1, move)
    r2 = pipeline.submit_move(state2, move)

    assert r1["new_state"]["rng_state_json"] != r2["new_state"]["rng_state_json"]


def test_lost_cities_initial_deal_is_seed_deterministic():
    first = _initial_game_data(123)
    replay = _initial_game_data(123)
    different = _initial_game_data(124)

    assert first["player_hands"] == replay["player_hands"]
    assert first["draw_pile"] == replay["draw_pile"]
    assert first["_rng_state_json"] == replay["_rng_state_json"]
    assert first["player_hands"] != different["player_hands"]


def test_lost_cities_subsequent_round_deal_is_seed_deterministic():
    validator = LostCitiesValidator()
    first = _initial_game_data(987)
    second = _initial_game_data(987)

    for game_data in (first, second):
        game_data["current_phase"] = "draw_a_card"
        game_data["pending_draw"] = True
        game_data["draw_pile"] = ["b_5"]

    move = {"type": "draw", "source": "draw_pile", "player_id": "player_1"}
    state_one = {
        "game_data": first,
        "rng_seed": 987,
        "rng_state_json": first.pop("_rng_state_json"),
    }
    state_two = {
        "game_data": second,
        "rng_seed": 987,
        "rng_state_json": second.pop("_rng_state_json"),
    }

    result_one = validator.apply_move(state_one, move)
    result_two = validator.apply_move(state_two, move)

    assert result_one["game_data"]["player_hands"] == result_two["game_data"]["player_hands"]
    assert result_one["rng_state_json"] == result_two["rng_state_json"]
