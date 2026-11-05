import random

from app.games.bus.rl_adapter import ACTION_COUNT, BusReferenceEnv, OBSERVATION_SIZES
from app.games.bus.rl_adapter import action_id_for_move
from app.games.bus.rl_policies import (
    choose_null,
    choose_random,
    choose_rule,
    observation_version_for_size,
)


def _run_episode(policy, seed, player_ids=("player_1", "player_2", "player_3"), max_steps=2000):
    env = BusReferenceEnv(seed=seed, player_ids=tuple(player_ids))
    obs = env.reset()
    rng = random.Random(seed)
    for _ in range(max_steps):
        legal = env.legal_moves(env.current_player)
        if not legal:
            break
        action_id = policy(env, obs, rng)
        assert 0 <= action_id < ACTION_COUNT
        assert obs["action_mask"][action_id], "policy must only choose masked-in actions"
        obs, _, done, info = env.step(action_id)
        if done:
            return info
    raise AssertionError("episode did not terminate within the step budget")


def test_random_policy_only_chooses_masked_in_actions_over_full_games():
    for seed in (1, 2, 3):
        info = _run_episode(choose_random, seed)
        assert info.get("ranking") is not None


def test_null_policy_only_chooses_masked_in_actions_over_full_games():
    for seed in (1, 2, 3):
        info = _run_episode(choose_null, seed)
        assert info.get("ranking") is not None


def test_rule_policy_only_chooses_masked_in_actions_over_full_games():
    for seed in (1, 2, 3):
        info = _run_episode(choose_rule, seed)
        assert info.get("ranking") is not None


def test_rule_policy_scores_at_least_as_well_as_null_policy_on_average():
    """A cheap regression gate: the rule policy must not be worse than doing
    nothing (the null floor), per the playbook's baseline-quality guidance."""
    rule_scores = []
    null_scores = []
    for seed in range(5):
        rule_info = _run_episode(choose_rule, seed + 100)
        null_info = _run_episode(choose_null, seed + 100)
        rule_scores.append(rule_info["final_scores"]["player_1"])
        null_scores.append(null_info["final_scores"]["player_1"])
    assert sum(rule_scores) >= sum(null_scores)


def test_rule_policy_prefers_immediate_transport_when_available():
    class FakeAdapter:
        def __init__(self):
            self.current_player = "player_1"
            self.state = {
                "game_data": {
                    "current_phase": "ACTION_SELECTION",
                    "current_player": "player_1",
                    "clock": "house",
                    "passenger_supply": 11,
                    "buildings": {
                        "building_d_01": {
                            "building_id": "building-building_d_01",
                            "type": "house",
                            "owner_id": "player_2",
                            "occupied_by": None,
                        }
                    },
                    "passengers": {"central_park_1": "c1"},
                    "players": {
                        "player_1": {
                            "action_markers": 20,
                            "buses": 1,
                            "time_stones": 0,
                            "score": 0,
                            "score_stack_order": 0,
                            "route_anchor": "c1",
                            "route_edges": ["e1"],
                        },
                        "player_2": {
                            "action_markers": 20,
                            "buses": 1,
                            "time_stones": 0,
                            "score": 0,
                            "score_stack_order": 1,
                            "route_anchor": None,
                            "route_edges": [],
                        },
                        "player_3": {
                            "action_markers": 20,
                            "buses": 1,
                            "time_stones": 0,
                            "score": 0,
                            "score_stack_order": 2,
                            "route_anchor": None,
                            "route_edges": [],
                        },
                    },
                }
            }

        def legal_moves(self, player_id):
            assert player_id == "player_1"
            return [
                {
                    "move_id": "select-vrrooomm-A",
                    "type": "select_action",
                    "player_id": "player_1",
                    "action_type": "vrrooomm",
                    "slot": "A",
                },
                {
                    "move_id": "select-line_expansion-B",
                    "type": "select_action",
                    "player_id": "player_1",
                    "action_type": "line_expansion",
                    "slot": "B",
                },
            ]

    adapter = FakeAdapter()
    observation = {"action_mask": [False] * ACTION_COUNT}
    observation["action_mask"][action_id_for_move(adapter.legal_moves("player_1")[0])] = True
    observation["action_mask"][action_id_for_move(adapter.legal_moves("player_1")[1])] = True

    chosen = choose_rule(adapter, observation, random.Random(0))

    assert chosen == action_id_for_move(adapter.legal_moves("player_1")[0])


def test_observation_version_inference_round_trips():
    for version, size in OBSERVATION_SIZES.items():
        assert observation_version_for_size(size) == version


def test_observation_version_inference_rejects_unknown_size():
    import pytest

    with pytest.raises(ValueError):
        observation_version_for_size(-1)
