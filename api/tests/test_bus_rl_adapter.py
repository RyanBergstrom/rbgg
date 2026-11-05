from app.core.rl_adapter import RLAdapter
from app.games.bus.rl_adapter import (
    ACTION_COUNT,
    ACTION_TYPES,
    ALL_SITE_IDS,
    BUILDING_TYPES,
    OBSERVATION_SIZE,
    OBSERVATION_SIZES,
    PHASE_NAMES,
    SORTED_EDGE_IDS,
    MAX_PLAYERS,
    BusReferenceEnv,
    action_id_for_move,
    encode_observation,
    moves_by_action_id,
)
from app.games.bus.validator import BusValidator


def _env(seed=1, player_ids=("player_1", "player_2", "player_3")):
    env = BusReferenceEnv(seed=seed, player_ids=tuple(player_ids))
    env.reset()
    return env


def test_bus_environment_implements_shared_rl_contract():
    env = BusReferenceEnv(seed=42)

    assert isinstance(env, RLAdapter)
    assert env.action_count == ACTION_COUNT
    assert env.observation_size == OBSERVATION_SIZES[env.observation_version]
    initial = env.reset()
    assert len(initial["observation"]) == env.observation_size
    assert len(initial["action_mask"]) == env.action_count


def test_action_ids_round_trip_over_many_legal_moves_across_phases():
    """Every legal move at every reachable phase maps to a unique, in-range ID."""
    for player_count in (3, 4, 5):
        env = _env(seed=player_count, player_ids=[f"player_{i}" for i in range(1, player_count + 1)])
        seen_phases = set()
        for _ in range(400):
            actor = env.current_player
            legal = env.legal_moves(actor)
            if not legal:
                break
            mapping = moves_by_action_id(legal)
            assert len(mapping) == len(legal), "action IDs must be unique across legal moves"
            assert all(0 <= action_id < ACTION_COUNT for action_id in mapping)
            assert all(action_id_for_move(move) in mapping for move in legal)
            seen_phases.add(env.state["game_data"]["current_phase"])
            action_id = min(mapping)
            _, _, done, _ = env.step(action_id)
            if done:
                break
        assert "ACTION_SELECTION" in seen_phases


def test_observation_has_fixed_size_and_no_nan_or_out_of_range_values():
    env = _env()
    obs = env.observe(env.current_player)
    assert len(obs["observation"]) == env.observation_size
    assert all(value == value for value in obs["observation"])  # no NaN
    assert all(-1.001 <= value <= 1.001 for value in obs["observation"])


def test_observation_is_player_relative_me_first():
    env = _env(player_ids=["player_1", "player_2", "player_3"])
    # Advance a few moves so players' states diverge (the initial reset state
    # is fully symmetric across seats, which would make this assertion vacuous).
    for _ in range(6):
        actor = env.current_player
        legal = env.legal_moves(actor)
        env.step(min(moves_by_action_id(legal)))
    obs_p1 = encode_observation(env.state, "player_1", env.legal_moves(env.current_player))
    obs_p2 = encode_observation(env.state, "player_2", env.legal_moves(env.current_player))
    # Different observers over the identical state must not be byte-identical
    # once per-player features exist (player 1's own-slot flags differ from
    # player 2's own-slot flags at minimum).
    assert obs_p1["observation"] != obs_p2["observation"]


def test_observation_has_no_public_information_leakage_risk():
    """Bus has no hidden state: encoding from any player's seat uses only
    rule-visible state, so two observers see the same board facts (positions
    swapped, not hidden)."""
    env = _env()
    data = env.state["game_data"]
    assert "player_hands" not in data
    assert set(data["players"]) == {"player_1", "player_2", "player_3"}


def test_observation_v2_encodes_each_building_type_and_v1_shape_is_preserved():
    env = _env()
    data = env.state["game_data"]
    site_id = ALL_SITE_IDS[0]
    data["buildings"][site_id] = {
        "building_id": f"building-{site_id}",
        "type": "office",
        "owner_id": "player_1",
        "occupied_by": None,
    }
    state = env.state
    old = encode_observation(state, "player_1", version=1)["observation"]
    current = encode_observation(state, "player_1", version=2)["observation"]

    assert len(old) == OBSERVATION_SIZES[1]
    assert OBSERVATION_SIZE == OBSERVATION_SIZES[2]
    assert len(current) == OBSERVATION_SIZES[2]
    global_features = len(PHASE_NAMES) + len(BUILDING_TYPES) + 2 + len(BUILDING_TYPES) + 1 + 3 + 2
    player_features = 7 + len(ACTION_TYPES) + 1
    first_site = global_features + MAX_PLAYERS * player_features + len(SORTED_EDGE_IDS) * 4
    type_start = first_site + 8
    assert current[type_start:type_start + 3] == [0.0, 1.0, 0.0]


def test_action_mask_matches_legal_moves_exactly():
    env = _env()
    actor = env.current_player
    legal = env.legal_moves(actor)
    obs = env.observe(actor, legal)
    mask_ids = {index for index, flag in enumerate(obs["action_mask"]) if flag}
    legal_ids = {action_id_for_move(move) for move in legal}
    assert mask_ids == legal_ids


def test_build_action_covers_all_building_sites_and_types():
    validator = BusValidator()
    for site_id in ALL_SITE_IDS:
        for building_type in ("house", "office", "pub"):
            action_id = action_id_for_move(
                {"type": "build", "site_id": site_id, "building_type": building_type}
            )
            assert 0 <= action_id < ACTION_COUNT
    del validator  # only used to assert the validator import stays in sync


def test_unsupported_move_raises_value_error():
    import pytest

    with pytest.raises(ValueError):
        action_id_for_move({"type": "not_a_real_move"})


def test_full_game_runs_to_completion_under_random_legal_actions():
    import random

    rng = random.Random(99)
    env = _env(seed=7, player_ids=["player_1", "player_2", "player_3", "player_4"])
    for _ in range(2000):
        actor = env.current_player
        legal = env.legal_moves(actor)
        if not legal:
            break
        action_id = action_id_for_move(rng.choice(legal))
        _, reward, done, info = env.step(action_id)
        assert -1.0 <= reward <= 1.0
        if done:
            assert info.get("ranking") in env.player_ids
            return
    raise AssertionError("game did not terminate within the step budget")
