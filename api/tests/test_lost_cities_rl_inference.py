from copy import deepcopy
from types import SimpleNamespace

import numpy as np
from pathlib import Path

from app.games.lost_cities.rl_adapter import hand_sort_key
from app.games.lost_cities.rl_inference import choose_live_move, configured_model_path
from app.games.lost_cities.validator import LostCitiesValidator


class _FirstDiscardModel:
    observation_space = SimpleNamespace(shape=(252,))

    def predict(self, observation, action_masks, deterministic):
        assert observation.shape == (252,)
        assert action_masks.shape == (22,)
        assert deterministic is True
        assert action_masks[8]
        return np.asarray(8), None


class _RecordingModel:
    observation_space = SimpleNamespace(shape=(252,))

    def __init__(self):
        self.deterministic_values = []

    def predict(self, observation, action_masks, deterministic):
        self.deterministic_values.append(deterministic)
        return np.asarray(8), None


def _make_live_state():
    validator = LostCitiesValidator()
    game_data = validator.initial_game_data(rng_seed=20261015)
    game_data["player_hands"]["player_1"] = list(
        reversed(game_data["player_hands"]["player_1"])
    )
    state = {
        "game_data": game_data,
        "players": [{"player_id": "player_1"}, {"player_id": "player_2"}],
        "current_player_index": 0,
        "version": 0,
        "rng_seed": 20261015,
        "rng_state_json": "{}",
    }
    return validator, state


def test_live_inference_maps_sorted_slot_back_to_original_move_without_mutation():
    validator, state = _make_live_state()
    game_data = state["game_data"]
    before = deepcopy(state)
    original_legal = validator.get_legal_moves(state, "player_1")
    expected_card = sorted(game_data["player_hands"]["player_1"], key=hand_sort_key)[0]

    selected = choose_live_move(state, "player_1", validator, model=_FirstDiscardModel())

    assert selected in original_legal
    assert selected["type"] == "discard"
    assert selected["card"] == expected_card
    assert state == before


def test_medium_difficulty_samples_the_masked_model_policy():
    validator, state = _make_live_state()
    model = _RecordingModel()

    selected = choose_live_move(
        state,
        "player_1",
        validator,
        model=model,
        difficulty="medium",
        rng=SimpleNamespace(random=lambda: 0.99),
    )

    assert selected in validator.get_legal_moves(state, "player_1")
    assert model.deterministic_values == [False]


def test_easy_difficulty_can_choose_a_random_legal_masked_action():
    validator, state = _make_live_state()

    class RandomOnlyRng:
        @staticmethod
        def random():
            return 0.0

        @staticmethod
        def choice(actions):
            assert 8 in actions
            return 8

    class ModelMustNotBeUsed(_RecordingModel):
        def predict(self, observation, action_masks, deterministic):
            raise AssertionError("easy random branch should not call the model")

    selected = choose_live_move(
        state,
        "player_1",
        validator,
        model=ModelMustNotBeUsed(),
        difficulty="easy",
        rng=RandomOnlyRng(),
    )

    assert selected in validator.get_legal_moves(state, "player_1")
    assert selected["type"] == "discard"


def test_unknown_ppo_difficulty_is_rejected():
    validator, state = _make_live_state()

    try:
        choose_live_move(state, "player_1", validator, model=_RecordingModel(), difficulty="expert")
    except ValueError as exc:
        assert "unsupported PPO difficulty" in str(exc)
    else:
        raise AssertionError("unsupported difficulty should fail closed")


def test_configured_model_path_resolves_relative_paths_from_api_root(monkeypatch, tmp_path):
    api_root = Path(__file__).resolve().parents[1]
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("RBGG_LOST_CITIES_PPO_MODEL", raising=False)
    assert configured_model_path() == api_root / "runtime" / "lc-v2-low-lr-2m.zip"

    monkeypatch.setenv("RBGG_LOST_CITIES_PPO_MODEL", "runtime/custom-model.zip")
    assert configured_model_path() == api_root / "runtime" / "custom-model.zip"
