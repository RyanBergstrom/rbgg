import random

import pytest

from app.core.rl_runner import run_episodes
from app.games.lost_cities.rl_adapter import LEGACY_OBSERVATION_SIZE, OBSERVATION_SIZE, LostCitiesReferenceEnv
from app.games.lost_cities.rl_policies import (
    FIXED_POLICIES,
    make_seat_selector,
    observation_version_for_size,
)


@pytest.mark.parametrize("name", sorted(FIXED_POLICIES))
def test_fixed_policies_finish_games_with_legal_actions(name):
    statistics = run_episodes(
        lambda seed: LostCitiesReferenceEnv(seed=seed),
        episodes=2,
        seed=31,
        action_selector=FIXED_POLICIES[name],
        max_steps_per_episode=3000,
    )

    assert statistics.winners.get("unfinished", 0) == 0


def test_never_play_scores_exactly_zero():
    statistics = run_episodes(
        lambda seed: LostCitiesReferenceEnv(seed=seed),
        episodes=2,
        seed=32,
        action_selector=FIXED_POLICIES["never_play"],
    )

    assert statistics.as_dict()["average_final_scores"] == {"player_1": 0.0, "player_2": 0.0}
    assert statistics.as_dict()["average_steps_per_episode"] == 264


def test_rule_policy_outscores_random_baseline():
    rule = run_episodes(
        lambda seed: LostCitiesReferenceEnv(seed=seed), episodes=10, seed=33,
        action_selector=FIXED_POLICIES["rule"],
    ).as_dict()["average_final_scores"]
    rand = run_episodes(
        lambda seed: LostCitiesReferenceEnv(seed=seed), episodes=10, seed=33,
    ).as_dict()["average_final_scores"]

    assert sum(rule.values()) > sum(rand.values()) + 100


def test_seat_selector_routes_by_current_player():
    env = LostCitiesReferenceEnv(seed=34)
    observation = env.reset()
    selector = make_seat_selector("player_1", lambda *_: "mine", lambda *_: "theirs")

    assert selector(env, observation, random.Random(0)) == "mine"


def test_observation_version_inference():
    assert observation_version_for_size(LEGACY_OBSERVATION_SIZE) == 1
    assert observation_version_for_size(OBSERVATION_SIZE) == 2
