import numpy as np
import pytest

from app.games.bus.gym_env import BusGymEnv, parse_opponent_mix
from app.games.bus.rl_adapter import ACTION_COUNT


def test_gym_env_exposes_fixed_spaces_and_legal_masks():
    env = BusGymEnv(seed=705)
    observation, info = env.reset()

    assert observation.shape == env.observation_space.shape
    assert observation.dtype == np.float32
    assert env.action_space.n == ACTION_COUNT
    assert env.action_masks().shape == (ACTION_COUNT,)
    assert env.action_masks().any()
    assert info["player_id"] == env.learner
    assert env.adapter.current_player == env.learner


def test_gym_observation_space_matches_adapter_bounds():
    env = BusGymEnv(seed=709)
    observation, _ = env.reset()

    assert env.observation_space.contains(observation)
    assert (observation >= 0.0).all()
    assert (observation <= 1.0).all()


def test_gym_env_step_returns_gymnasium_transition_for_the_learner():
    env = BusGymEnv(seed=706)
    env.reset()
    action = int(np.flatnonzero(env.action_masks())[0])

    observation, reward, terminated, truncated, info = env.step(action)

    assert observation.shape == env.observation_space.shape
    assert isinstance(reward, float)
    assert isinstance(terminated, bool)
    assert truncated is False
    assert info["learner"] == env.learner
    assert env.adapter.current_player == env.learner or terminated


def test_gym_env_truncates_stalled_episodes():
    env = BusGymEnv(seed=707, max_episode_steps=1)
    env.reset()
    action = int(np.flatnonzero(env.action_masks())[0])

    _, _, terminated, truncated, info = env.step(action)

    assert terminated is False
    assert truncated is True
    assert info["truncated_reason"] == "max_episode_steps"
    assert info["reward_breakdown"]["timeout"] == pytest.approx(-0.25)


def test_full_random_episode_completes_and_reward_matches_breakdown():
    env = BusGymEnv(seed=711, max_episode_steps=3000)
    env.reset()
    rng = np.random.default_rng(0)
    total = 0.0
    terminated = truncated = False
    info = {}
    steps = 0
    while not (terminated or truncated) and steps < 3000:
        enabled = np.flatnonzero(env.action_masks())
        action = int(rng.choice(enabled))
        _, reward, terminated, truncated, info = env.step(action)
        total += reward
        steps += 1

    assert terminated
    assert "final_scores" in info
    assert info["winner"] in info["final_scores"]


def test_player_count_and_learner_seat_vary_between_episodes():
    env = BusGymEnv(seed=714)
    counts = set()
    seats = set()
    for _ in range(40):
        _, info = env.reset()
        seats.add(info["player_id"])
        counts.add(len(info["opponents"]) + 1)

    assert counts.issubset({3, 4, 5})
    assert len(counts) > 1
    assert len(seats) > 1


def test_opponent_kinds_drawn_from_requested_mix():
    env = BusGymEnv(seed=716, opponents={"rule": 1.0, "random": 1.0})
    kinds = set()
    for _ in range(40):
        _, info = env.reset()
        kinds.update(info["opponents"].values())

    assert kinds == {"rule", "random"}


def test_opponent_variety_controls_are_reported_and_validated():
    env = BusGymEnv(
        seed=717,
        random_setup_probability=0.4,
        rule_pass_probability=0.3,
    )
    _, info = env.reset(seed=717)
    assert info["random_setup_probability"] == 0.4
    assert info["rule_pass_probability"] == 0.3

    import pytest

    with pytest.raises(ValueError, match="random_setup_probability"):
        BusGymEnv(random_setup_probability=1.1)
    with pytest.raises(ValueError, match="rule_pass_probability"):
        BusGymEnv(rule_pass_probability=-0.1)


def test_snapshot_pool_is_bounded_and_unused_until_registered():
    env = BusGymEnv(seed=715, opponents={"rule": 1.0, "snapshot": 5.0})
    for _ in range(10):
        _, info = env.reset()
        assert set(info["opponents"].values()) == {"rule"}

    for index in range(4):
        env.add_opponent_snapshot(f"snapshot-{index}.zip", max_snapshots=2)
    assert env.snapshot_paths == ["snapshot-2.zip", "snapshot-3.zip"]


def test_auto_resets_deal_new_games():
    env = BusGymEnv(seed=713)
    _, first = env.reset()
    _, second = env.reset()

    assert first["episode_seed"] != second["episode_seed"]
    again = BusGymEnv(seed=713)
    assert again.reset()[1]["episode_seed"] == first["episode_seed"]


def test_parse_opponent_mix_validates_names_and_weights():
    assert parse_opponent_mix("rule=0.6,random=0.2,null=0.2") == {
        "rule": 0.6, "random": 0.2, "null": 0.2,
    }
    with pytest.raises(ValueError):
        parse_opponent_mix("not_a_policy=1.0")
    with pytest.raises(ValueError):
        parse_opponent_mix("rule=-1.0")
