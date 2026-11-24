"""Tests for tactical safety guards and strategic adviser for Twilight Struggle."""
from __future__ import annotations

import random
import pytest

from app.games.twilight_struggle import rl_adapter as ra
from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv
from app.games.twilight_struggle.rl_policies import FIXED_POLICIES
from app.games.twilight_struggle.rl_strategy import (
    adviser_policy,
    filter_safe_actions,
    is_defcon_suicide_action,
    make_adviser_wrapped_selector,
)


def test_adviser_policy_selects_legal_unmasked_actions():
    env = TwilightStruggleGymEnv(seed=42)
    obs, info = env.reset(seed=42)
    rng = random.Random(42)

    for _ in range(50):
        if not env.action_masks().any():
            break
        action = adviser_policy(env, env.adapter_observation, rng)
        assert env.action_masks()[action], f"Action {action} ({ra.describe_action(action)}) must be unmasked"
        _, _, terminated, truncated, _ = env.step(action)
        if terminated or truncated:
            break


def test_defcon_suicide_guard_identifies_defcon_2_battleground_coup():
    env = TwilightStruggleGymEnv(seed=10)
    env.reset(seed=10)
    gd = env.adapter.game_data
    # Set DEFCON to 2 and ensure no Nuclear Subs active
    gd["tracks"]["defcon"] = 2
    gd["persistent_events"] = {}

    # Find a battleground country ID and non-battleground country ID
    data = env.adapter._data["countries"]
    bg_country = next(name for name, info in data.items() if info.get("battleground") and name in ra.COUNTRY_INDEX)
    non_bg_country = next(name for name, info in data.items() if not info.get("battleground") and name in ra.COUNTRY_INDEX)

    bg_action = ra.COUNTRY_BASE + ra.COUNTRY_INDEX[bg_country]
    non_bg_action = ra.COUNTRY_BASE + ra.COUNTRY_INDEX[non_bg_country]

    # Simulate being in COUP stage
    env.adapter.pending = ra._Pending(stage=ra.STAGE_COUP)

    assert is_defcon_suicide_action(env, bg_action) is True
    assert is_defcon_suicide_action(env, non_bg_action) is False

    # Filter safe actions
    safe = filter_safe_actions(env, [bg_action, non_bg_action])
    assert bg_action not in safe
    assert non_bg_action in safe


def test_make_adviser_wrapped_selector_intercepts_suicide_coup():
    env = TwilightStruggleGymEnv(seed=15)
    env.reset(seed=15)
    gd = env.adapter.game_data
    gd["tracks"]["defcon"] = 2
    gd["persistent_events"] = {}

    data = env.adapter._data["countries"]
    bg_country = next(name for name, info in data.items() if info.get("battleground") and name in ra.COUNTRY_INDEX)
    non_bg_country = next(name for name, info in data.items() if not info.get("battleground") and name in ra.COUNTRY_INDEX)

    bg_action = ra.COUNTRY_BASE + ra.COUNTRY_INDEX[bg_country]
    non_bg_action = ra.COUNTRY_BASE + ra.COUNTRY_INDEX[non_bg_country]

    env.adapter.pending = ra._Pending(stage=ra.STAGE_COUP)

    # Base selector intentionally chooses the suicidal battleground coup
    def suicide_selector(e, obs, rng):
        return bg_action

    wrapped = make_adviser_wrapped_selector(suicide_selector, safety_only=True)
    mask = [0] * ra.ACTION_COUNT
    mask[bg_action] = 1
    mask[non_bg_action] = 1
    obs = {"observation": [0.0] * ra.OBSERVATION_SIZE, "action_mask": mask}

    chosen = wrapped(env, obs, random.Random(1))
    assert chosen == non_bg_action, "Wrapped selector must intercept suicide coup and pick safe action"


def test_adviser_registered_in_fixed_policies():
    assert "adviser" in FIXED_POLICIES
    env = TwilightStruggleGymEnv(seed=20)
    env.reset(seed=20)
    action = FIXED_POLICIES["adviser"](env, env.adapter_observation, random.Random(20))
    assert env.action_masks()[action]
