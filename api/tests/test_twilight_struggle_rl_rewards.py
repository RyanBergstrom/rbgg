"""Tests for potential-based reward shaping in Twilight Struggle."""
from __future__ import annotations

import math
import random
import pytest

from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv
from app.games.twilight_struggle.rl_rewards import PotentialRewardShaper, compute_state_potential


def test_compute_state_potential_bounds_and_terminal_zero():
    env = TwilightStruggleGymEnv(seed=123)
    env.reset(seed=123)
    gd = env.adapter.game_data

    # Initial non-terminal potential is strictly bounded in [-0.25, 0.25]
    pot_us = compute_state_potential(gd, "us")
    pot_ussr = compute_state_potential(gd, "ussr")

    assert -0.25 <= pot_us <= 0.25
    assert -0.25 <= pot_ussr <= 0.25

    # Simulated terminal state must yield exactly 0.0
    terminal_gd = {**gd, "terminal_result": {"winner": "us", "reason": "twenty_vp"}}
    assert compute_state_potential(terminal_gd, "us") == 0.0
    assert compute_state_potential(terminal_gd, "ussr") == 0.0


def test_reward_shaper_telescoping_property():
    """Verify mathematical telescoping property of PotentialRewardShaper:
    sum_t (gamma^t * r'_t) == sum_t (gamma^t * r_t) - Phi(s_0).
    """
    gamma = 0.99
    shaper = PotentialRewardShaper(gamma=gamma)

    env = TwilightStruggleGymEnv(seed=77)
    env.reset(seed=77)
    learner = env.learner_faction
    initial_gd = env.adapter.game_data
    shaper.reset(initial_gd, learner)
    initial_phi = shaper.last_potential

    rng = random.Random(77)
    base_rewards = []
    shaped_rewards = []

    for step_idx in range(30):
        legal = [i for i, f in enumerate(env.action_masks()) if f]
        if not legal:
            break
        action = rng.choice(legal)
        _, base_reward, terminated, truncated, _ = env.step(action)
        is_term = terminated or (step_idx == 29)
        shaped_r = shaper.shape_reward(base_reward, env.adapter.game_data, learner, is_terminal=is_term)

        base_rewards.append(base_reward)
        shaped_rewards.append(shaped_r)
        if is_term:
            break

    # Calculate discounted returns
    discounted_base = sum((gamma ** t) * r for t, r in enumerate(base_rewards))
    discounted_shaped = sum((gamma ** t) * r for t, r in enumerate(shaped_rewards))

    # Because terminal Phi(s_T) = 0.0, discounted_shaped must equal discounted_base - initial_phi
    expected_shaped = discounted_base - initial_phi
    assert discounted_shaped == pytest.approx(expected_shaped, abs=1e-5)
