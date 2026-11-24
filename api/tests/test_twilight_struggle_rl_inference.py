"""Tests for the production Twilight Struggle PPO inference bridge."""
from __future__ import annotations

from types import SimpleNamespace

import numpy as np
import pytest

from app.games.twilight_struggle.rl_adapter import (
    ACTION_COUNT_V2,
    OBSERVATION_SIZE_V2,
    TwilightStruggleReferenceEnv,
)
from app.games.twilight_struggle.rl_inference import choose_live_move


class FirstLegalModel:
    """Tiny deterministic stand-in for MaskablePPO used to test live action mapping."""

    observation_space = SimpleNamespace(shape=(OBSERVATION_SIZE_V2,))
    action_space = SimpleNamespace(n=ACTION_COUNT_V2)

    def predict(self, observation, action_masks, deterministic=True):
        assert observation.shape == (OBSERVATION_SIZE_V2,)
        legal = np.flatnonzero(action_masks)
        assert legal.size
        return np.asarray(legal[0]), None


def test_choose_live_move_maps_schema2_prediction_to_authoritative_legal_move():
    validator = TwilightStruggleReferenceEnv().validator
    game_data = validator.initial_game_data(20261114, ["player_1", "player_2"])
    state = {
        "players": [{"player_id": "player_1"}, {"player_id": "player_2"}],
        "current_player_index": 1,
        "game_data": game_data,
        "version": 0,
        "rng_seed": game_data["rng_seed"],
        "rng_state_json": game_data["rng_state_json"],
    }
    player_id = game_data["current_player"]
    legal_before = validator.get_legal_moves(state, player_id)

    selected = choose_live_move(state, player_id, validator, model=FirstLegalModel())

    assert selected in legal_before
    assert validator.validate_move(state, selected)
    # The in-memory adapter used for staged model decisions must not mutate the live session state.
    assert state["game_data"]["current_phase"] == "headline"
    assert state["game_data"]["headline_cards"] == {"us": None, "ussr": None}


def test_choose_live_move_fails_closed_for_wrong_model_schema():
    class OldSchemaModel(FirstLegalModel):
        observation_space = SimpleNamespace(shape=(1092,))
        action_space = SimpleNamespace(n=781)

    adapter = TwilightStruggleReferenceEnv()
    adapter.reset(7)

    with pytest.raises(ValueError, match="Schema 2"):
        choose_live_move(
            adapter.state,
            adapter.current_player,
            adapter.validator,
            model=OldSchemaModel(),
        )
