"""Cached inference bridge from live Bus states to MaskablePPO.

Unlike Lost Cities, Bus has no hidden per-player information and action IDs
are derived from fixed game constants (edge/site/passenger identifiers), not
from hand order, so no canonicalization step is needed before encoding: the
live state can be passed to ``encode_observation`` directly.
"""
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import random
from typing import Any

from app.games.bus.rl_adapter import OBSERVATION_SIZES, encode_observation, moves_by_action_id

DIFFICULTY_RANDOM_ACTION_PROBABILITIES = {
    "hard": 0.0,
    "medium": 0.15,
    "easy": 0.5,
}


def configured_model_path() -> Path:
    """Return the configured model path (defaulting to the selected 1M-step model)."""
    configured = os.environ.get("RBGG_BUS_PPO_MODEL")
    api_root = Path(__file__).resolve().parents[3]
    if not configured:
        return api_root / "runtime" / "bus-v2-2.5m.zip"
    path = Path(configured).expanduser()
    return path if path.is_absolute() else api_root / path


@lru_cache(maxsize=2)
def load_model(model_path: str):
    """Load an optional SB3-contrib model once per path, on CPU."""
    from sb3_contrib import MaskablePPO

    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"Bus PPO model not found: {path}")
    return MaskablePPO.load(str(path), device="cpu")


def choose_live_move(
    state: dict[str, Any],
    player_id: str,
    validator,
    model=None,
    difficulty: str = "hard",
    rng=None,
) -> dict[str, Any]:
    """Choose a legal live move for ``player_id`` using a MaskablePPO model.

    Hard uses the model's highest-probability action; medium and easy sample
    the model policy and increasingly often substitute a uniformly random
    legal move. Raises on any mismatch so the API can safely fall back to
    MCTS/the built-in bot.
    """
    import numpy as np

    if not isinstance(difficulty, str) or difficulty not in DIFFICULTY_RANDOM_ACTION_PROBABILITIES:
        raise ValueError(f"unsupported PPO difficulty: {difficulty}")
    live_moves = validator.get_legal_moves(state, player_id)
    if not live_moves:
        raise ValueError(f"no legal moves available for {player_id}")
    active_model = model or load_model(str(configured_model_path()))
    input_size = active_model.observation_space.shape[0]
    if input_size not in OBSERVATION_SIZES.values():
        raise ValueError(f"unsupported PPO observation size: {input_size}")
    version = next(ver for ver, size in OBSERVATION_SIZES.items() if size == input_size)
    encoded = encode_observation(state, player_id, live_moves, version)
    vector = np.asarray(encoded["observation"], dtype=np.float32)
    mask = np.asarray(encoded["action_mask"], dtype=bool)
    if not mask.any():
        raise ValueError("PPO observation has no legal actions")
    rng = rng or random
    random_action_probability = DIFFICULTY_RANDOM_ACTION_PROBABILITIES[difficulty]
    if random_action_probability and rng.random() < random_action_probability:
        action_id = int(rng.choice(np.flatnonzero(mask)))
    else:
        action, _ = active_model.predict(
            vector,
            action_masks=mask,
            deterministic=difficulty == "hard",
        )
        action_id = int(np.asarray(action).item())
    live_move = moves_by_action_id(live_moves).get(action_id)
    if live_move is None:
        raise ValueError(f"PPO selected masked or unmapped action {action_id}")
    return live_move
