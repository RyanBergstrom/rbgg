"""Baseline policy and Gymnasium env tests for Twilight Struggle."""
from __future__ import annotations

import random

import pytest

from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv
from app.games.twilight_struggle.rl_adapter import TwilightStruggleReferenceEnv
from app.games.twilight_struggle.rl_policies import FIXED_POLICIES


@pytest.mark.parametrize("name", sorted(FIXED_POLICIES))
def test_fixed_policies_only_choose_unmasked_actions(name):
    env = TwilightStruggleReferenceEnv()
    obs = env.reset(11)
    rng = random.Random(1)
    for _ in range(400):
        if env.is_terminal():
            break
        obs = env.observe(env.current_player)
        if not any(obs["action_mask"]):
            break
        action = FIXED_POLICIES[name](env, obs, rng)
        assert obs["action_mask"][action] == 1
        env.step(action)


def _run_episode(env, seed, rng_seed=0):
    obs, info = env.reset(seed=seed)
    rng = random.Random(rng_seed)
    total, last = 0.0, {}
    for _ in range(env.max_episode_steps + 5):
        legal = [i for i, f in enumerate(env.action_masks()) if f]
        assert legal
        obs, reward, terminated, truncated, last = env.step(rng.choice(legal))
        total += reward
        if terminated or truncated:
            return total, terminated, truncated, last, info
    raise AssertionError("episode did not end")


@pytest.mark.parametrize("faction", ["us", "ussr"])
def test_rewards_sum_to_scaled_final_margin(faction):
    env = TwilightStruggleGymEnv(seed=3, learner_faction=faction, opponents={"random": 1.0}, curriculum_stage=0)
    total, terminated, truncated, last, info = _run_episode(env, seed=3)
    assert info["faction"] == faction
    if terminated:
        # Total reward = VP margin delta * scale + win_reward (if win) - win_reward (if loss) - defcon_penalty (if DEFCON-1 loss)
        expected = env.reward_scale * last["vp_margin"]
        terminal = last.get("terminal_result") or {}
        winner = last.get("winner")  # winner is in the step info, not reset info
        learner = last.get("learner")
        if winner is not None and learner is not None:
            expected += env.win_reward if winner == learner else -env.win_reward
        if terminal.get("reason") == "defcon_1" and winner is not None and learner is not None and winner != learner:
            expected -= 2.0  # DEFCON-1 penalty
        assert total == pytest.approx(expected)


def test_env_spaces_and_reset_variation():
    env = TwilightStruggleGymEnv(seed=5)
    obs, info = env.reset(seed=5)
    assert obs.shape == env.observation_space.shape and env.observation_space.contains(obs)
    assert env.action_masks().shape == (env.action_space.n,) and env.action_masks().any()
    factions = set()
    for seed in range(8):
        _, info = env.reset(seed=seed)
        factions.add(info["faction"])
    assert factions == {"us", "ussr"}


def test_env_rejects_bad_config():
    with pytest.raises(ValueError):
        TwilightStruggleGymEnv(opponents={"nope": 1.0})
    with pytest.raises(ValueError):
        TwilightStruggleGymEnv(learner_faction="x")
