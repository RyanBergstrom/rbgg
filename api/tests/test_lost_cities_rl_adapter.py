from copy import deepcopy

import pytest

from app.games.lost_cities.rl_adapter import (
    ACTION_COUNT,
    HAND_SIZE,
    HAND_SLOT_FEATURES,
    LEGACY_OBSERVATION_SIZE,
    LostCitiesReferenceEnv,
    OBSERVATION_SIZE,
    action_id_for_move,
    encode_observation,
    encode_live_state,
    hand_sort_key,
    moves_by_action_id,
)
from app.core.rl_adapter import RLAdapter
from app.games.lost_cities.validator import LostCitiesValidator


def _state(game_data):
    return {
        "game_data": game_data,
        "players": [{"player_id": "player_1"}, {"player_id": "player_2"}],
        "current_player_index": 0,
    }


def test_action_mapping_has_fixed_shape_and_covers_initial_legal_moves():
    validator = LostCitiesValidator()
    data = validator.initial_game_data(rng_seed=123)
    state = _state(data)
    legal = validator.get_legal_moves(state, "player_1")

    mapping = moves_by_action_id(legal)

    assert ACTION_COUNT == 22
    assert len(mapping) == len(legal)
    assert all(0 <= action < ACTION_COUNT for action in mapping)
    assert all(action_id_for_move(move) in mapping for move in legal)


def test_lost_cities_environment_implements_shared_rl_contract():
    env = LostCitiesReferenceEnv(seed=123)

    assert isinstance(env, RLAdapter)
    assert env.action_count == ACTION_COUNT
    assert env.observation_size == OBSERVATION_SIZE
    initial = env.reset()
    assert len(initial["observation"]) == env.observation_size
    assert len(initial["action_mask"]) == env.action_count


def test_starting_player_can_be_seat_swapped_deterministically():
    first = LostCitiesReferenceEnv(seed=704, starting_player="player_2")
    second = LostCitiesReferenceEnv(seed=704, starting_player="player_2")

    first.reset()
    second.reset()

    assert first.current_player == "player_2"
    assert first.state == second.state
    assert first.state["game_data"]["player_hands"]["player_1"] == second.state["game_data"]["player_hands"]["player_1"]


def test_observation_is_fixed_shape_and_redacts_opponent_hand():
    validator = LostCitiesValidator()
    data = validator.initial_game_data(rng_seed=123)
    state = _state(data)
    observation = encode_observation(state, "player_1", validator.get_legal_moves(state, "player_1"))

    assert observation["schema_version"] == 2
    assert len(observation["observation"]) == OBSERVATION_SIZE
    assert len(observation["action_mask"]) == ACTION_COUNT

    # Changing hidden opponent cards must not change player 1's observation.
    hidden_state = deepcopy(state)
    hidden_state["game_data"]["player_hands"]["player_2"] = ["b_10"] * HAND_SIZE
    hidden_observation = encode_observation(
        hidden_state,
        "player_1",
        validator.get_legal_moves(hidden_state, "player_1"),
    )
    assert hidden_observation == observation


def test_reference_environment_is_deterministic_and_does_not_mutate_input():
    first = LostCitiesReferenceEnv(seed=77)
    second = LostCitiesReferenceEnv(seed=77)
    first.reset()
    second.reset()

    assert first.state == second.state
    before = deepcopy(first.state)
    action = next(
        index
        for index, enabled in enumerate(first.observe("player_1")["action_mask"])
        if enabled
    )
    first.step(action)

    assert before != first.state
    assert second.state != first.state
    assert second.state["game_data"]["round"] == 1


def test_illegal_action_fails_closed():
    env = LostCitiesReferenceEnv(seed=1)
    env.reset()
    with pytest.raises(ValueError, match="illegal"):
        env.step(21)


def test_environment_trajectory_matches_direct_validator_transitions():
    validator = LostCitiesValidator()
    # Legacy schema keeps validator hand order, so states compare exactly.
    env = LostCitiesReferenceEnv(seed=901, validator=validator, observation_version=1)
    env.reset()

    initial_data = validator.initial_game_data(rng_seed=901)
    direct_state = _state(initial_data)
    direct_state["rng_seed"] = 901
    direct_state["rng_state_json"] = direct_state["game_data"].pop(
        "_rng_state_json", "{}"
    )

    for _ in range(20):
        actor = direct_state["game_data"]["current_player"]
        direct_legal = validator.get_legal_moves(direct_state, actor)
        assert direct_legal
        selected = direct_legal[0]
        action_id = action_id_for_move(selected)

        _, _, done, info = env.step(action_id)

        direct_next = deepcopy(direct_state)
        direct_next.update(validator.apply_move(direct_next, selected))
        direct_next["current_player_index"] = (
            0 if direct_next["game_data"]["current_player"] == "player_1" else 1
        )
        direct_state = direct_next

        assert info["move"] == selected
        assert env.state["game_data"] == direct_state["game_data"]
        assert env.current_player == direct_state["game_data"]["current_player"]
        if done:
            break


def test_step_does_not_mutate_the_previous_game_data_object():
    env = LostCitiesReferenceEnv(seed=902)
    env.reset()
    previous_data = env.state["game_data"]
    previous_snapshot = deepcopy(previous_data)
    action = next(
        index
        for index, enabled in enumerate(env.observe("player_1")["action_mask"])
        if enabled
    )

    env.step(action)

    assert previous_data == previous_snapshot
    assert env.state["game_data"] is not previous_data


def test_legacy_observation_schema_is_still_available():
    env = LostCitiesReferenceEnv(seed=903, observation_version=1)

    observation = env.reset()

    assert env.observation_size == LEGACY_OBSERVATION_SIZE == 133
    assert observation["schema_version"] == 1
    assert len(observation["observation"]) == LEGACY_OBSERVATION_SIZE


def test_unknown_observation_version_is_rejected():
    with pytest.raises(ValueError, match="observation version"):
        LostCitiesReferenceEnv(seed=1, observation_version=9)


def test_v2_hands_stay_canonically_sorted_through_a_game():
    env = LostCitiesReferenceEnv(seed=904)
    observation = env.reset()
    for _ in range(200):
        for cards in env.state["game_data"]["player_hands"].values():
            assert cards == sorted(cards, key=hand_sort_key)
        action = next(index for index, enabled in enumerate(observation["action_mask"]) if enabled)
        observation, _, done, _ = env.step(action)
        if done:
            break


def test_v2_hand_slot_features_describe_playability_and_score_change():
    validator = LostCitiesValidator()
    data = validator.initial_game_data(rng_seed=5)
    data["player_hands"]["player_1"] = ["b_i", "b_4", "y_2", "y_9"]
    data["expeditions"]["player_1"]["yellow"] = ["y_5"]
    state = _state(data)

    values = encode_observation(state, "player_1", validator.get_legal_moves(state, "player_1"))["observation"]
    slot = lambda index: values[index * HAND_SLOT_FEATURES:(index + 1) * HAND_SLOT_FEATURES]
    playable, started, gap, delta = 8, 9, 10, 11

    assert slot(1)[playable] == 1.0 and slot(1)[started] == 0.0
    assert slot(1)[delta] == pytest.approx((4 - 20) / 50)
    assert slot(2)[playable] == 0.0 and slot(2)[delta] == 0.0
    assert slot(3)[playable] == 1.0 and slot(3)[gap] == pytest.approx(0.4)
    assert slot(3)[delta] == pytest.approx(9 / 50)
    assert slot(0)[delta] == pytest.approx(-40 / 50)  # investment doubles the -20 start cost
    assert slot(4) == [0.0] * HAND_SLOT_FEATURES


def test_live_encoding_canonicalizes_a_copy_and_aligns_legal_actions():
    validator = LostCitiesValidator()
    data = validator.initial_game_data(rng_seed=919)
    data["player_hands"]["player_1"] = list(reversed(data["player_hands"]["player_1"]))
    state = _state(data)
    original_hand = list(data["player_hands"]["player_1"])
    live_moves = validator.get_legal_moves(state, "player_1")

    encoded, canonical_moves = encode_live_state(
        state, "player_1", live_moves, version=2, validator=validator,
    )

    assert state["game_data"]["player_hands"]["player_1"] == original_hand
    canonical_ids = moves_by_action_id(canonical_moves)
    assert encoded["action_mask"] == [
        int(action_id in canonical_ids) for action_id in range(ACTION_COUNT)
    ]
    canonical_hand = sorted(original_hand, key=hand_sort_key)
    assert [move["card"] for move in canonical_moves if move["type"] == "discard"] == canonical_hand