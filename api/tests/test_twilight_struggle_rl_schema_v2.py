"""Tests for Schema Version 2 in Twilight Struggle RL Adapter."""
from __future__ import annotations

import random
import pytest

from app.games.twilight_struggle import rl_adapter as ra
from app.games.twilight_struggle.cards import load_standard_card_catalog
from app.games.twilight_struggle.gym_env import TwilightStruggleGymEnv
from app.games.twilight_struggle.rl_adapter import (
    ACTION_COUNT,
    ACTION_COUNT_V2,
    CRISIS_CANCEL_BASE,
    CRISIS_CANCEL_COUNTRIES,
    OBSERVATION_SIZE,
    OBSERVATION_SIZE_V2,
    SPACE_BASE,
    TwilightStruggleReferenceEnv,
    card_index,
    describe_action,
)


def test_schema_v1_and_v2_shapes_and_constants():
    assert ACTION_COUNT == 781
    assert ACTION_COUNT_V2 == 894
    assert OBSERVATION_SIZE == 1092
    assert OBSERVATION_SIZE_V2 == 1104
    assert SPACE_BASE == 781
    assert CRISIS_CANCEL_BASE == 781 + 110  # 891
    assert len(CRISIS_CANCEL_COUNTRIES) == 3

    # V1 defaults
    env_v1 = TwilightStruggleReferenceEnv(schema_version=1)
    obs_v1 = env_v1.reset(seed=1)
    assert env_v1.action_count == 781
    assert env_v1.observation_size == 1092
    assert len(obs_v1["observation"]) == 1092
    assert len(obs_v1["action_mask"]) == 781
    assert obs_v1["schema_version"] == 1

    # V2
    env_v2 = TwilightStruggleReferenceEnv(schema_version=2)
    obs_v2 = env_v2.reset(seed=1)
    assert env_v2.action_count == 894
    assert env_v2.observation_size == 1104
    assert len(obs_v2["observation"]) == 1104
    assert len(obs_v2["action_mask"]) == 894
    assert obs_v2["schema_version"] == 2

    # Observations in v1 and v2 match on the first 1092 features
    assert obs_v1["observation"] == obs_v2["observation"][:1092]


def test_describe_action_v2():
    assert describe_action(SPACE_BASE) == "space:card1"
    assert describe_action(SPACE_BASE + 109) == "space:card110"
    assert describe_action(CRISIS_CANCEL_BASE) == "cancel_crisis:Cuba"
    assert describe_action(CRISIS_CANCEL_BASE + 1) == "cancel_crisis:W. Germany"
    assert describe_action(CRISIS_CANCEL_BASE + 2) == "cancel_crisis:Turkey"


def test_space_race_action_available_and_playable_in_v2():
    env = TwilightStruggleReferenceEnv(schema_version=2)
    env.reset(seed=5)
    gd = env.game_data
    gd["current_phase"] = "action_round"
    gd["current_player"] = "player_1"
    gd["current_player_faction"] = "us"
    gd["actions_taken"] = {"us": 0, "ussr": 0}

    # Give US a 2-Ops non-scoring card (e.g. Card 25 Containment)
    catalog = {c["id"]: c for c in load_standard_card_catalog()}
    card_25 = catalog[25]
    gd["hands"]["us"] = [card_25]
    env._touch()

    space_action = SPACE_BASE + card_index(25)
    mask = env.action_mask("player_1")
    assert mask[space_action] == 1, "Space Race action must be unmasked for 2-ops card"

    obs, reward, terminated, info = env.step(space_action)
    assert info["move"] is not None
    assert info["move"]["type"] == "play_card"
    assert info["move"]["card_id"] == 25
    assert info["move"]["operations_action"]["type"] == "space_race"
    assert card_25 not in env.game_data["hands"]["us"]


def test_crisis_cancellation_action_available_and_playable_in_v2():
    env = TwilightStruggleReferenceEnv(schema_version=2)
    env.reset(seed=8)
    gd = env.game_data
    gd["current_phase"] = "action_round"
    gd["current_player"] = "player_1"
    gd["current_player_faction"] = "us"
    turn = gd["turn"]

    # Active Cuban Missile Crisis on US
    gd["persistent_events"]["cuban_missile_crisis"] = {"faction": "us", "expires_turn": turn}
    # Put 2 US influence in W. Germany
    gd["countries"]["W. Germany"]["us"] = 3
    env._touch()

    cancel_wg = CRISIS_CANCEL_BASE + CRISIS_CANCEL_COUNTRIES.index("W. Germany")
    mask = env.action_mask("player_1")
    assert mask[cancel_wg] == 1, "W. Germany crisis cancellation must be legal"

    obs, reward, terminated, info = env.step(cancel_wg)
    assert info["move"] is not None
    assert info["move"]["type"] == "cancel_cuban_missile_crisis"
    assert info["move"]["country"] == "W. Germany"
    assert "cuban_missile_crisis" not in env.game_data.get("persistent_events", {})
    assert env.game_data["countries"]["W. Germany"]["us"] == 1


def test_gym_env_v2_spaces_and_step():
    gym_env = TwilightStruggleGymEnv(schema_version=2, seed=99)
    obs, info = gym_env.reset(seed=99)

    assert gym_env.action_space.n == 894
    assert gym_env.observation_space.shape == (1104,)
    assert obs.shape == (1104,)
    assert gym_env.action_masks().shape == (894,)

    # Take a step
    legal = [i for i, f in enumerate(gym_env.action_masks()) if f]
    next_obs, r, term, trunc, _ = gym_env.step(legal[0])
    assert next_obs.shape == (1104,)


def test_transferred_v2_model_loads_and_predicts():
    from pathlib import Path
    import numpy as np
    from sb3_contrib import MaskablePPO

    model_path = Path("api/runtime/twilight/twilight-ppo-v2-transferred.zip")
    if not model_path.is_file():
        pytest.skip("Transferred model not found")

    model = MaskablePPO.load(str(model_path), device="cpu")
    gym_env = TwilightStruggleGymEnv(schema_version=2, seed=101)
    obs, info = gym_env.reset(seed=101)

    masks = gym_env.action_masks()
    action, _ = model.predict(obs, action_masks=masks, deterministic=True)
    assert 0 <= int(action) < 894
    assert masks[action] == 1, "Predicted action must be unmasked in Schema 2"
