"""Cached inference bridge from live Lost Cities states to MaskablePPO."""
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import random
from typing import Any

from app.games.lost_cities.rl_adapter import (
    OBSERVATION_SIZES,
    encode_live_state,
    moves_by_action_id,
)

DIFFICULTY_RANDOM_ACTION_PROBABILITIES = {
    "hard": 0.0,
    "medium": 0.15,
    "easy": 0.5,
}


def configured_model_path() -> Path:
    """Return the configured model path (defaulting to the selected lower-LR model)."""
    configured = os.environ.get("RBGG_LOST_CITIES_PPO_MODEL")
    api_root = Path(__file__).resolve().parents[3]
    if not configured:
        return api_root / "runtime" / "lc-v2-low-lr-2m.zip"
    path = Path(configured).expanduser()
    return path if path.is_absolute() else api_root / path


@lru_cache(maxsize=2)
def load_model(model_path: str):
    """Load an optional SB3-contrib model once per path, on CPU."""
    from sb3_contrib import MaskablePPO

    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"Lost Cities PPO model not found: {path}")
    return MaskablePPO.load(str(path), device="cpu")


def _same_action(candidate: dict[str, Any], live_move: dict[str, Any]) -> bool:
    """Compare action meaning, deliberately ignoring hand indices and move IDs."""
    keys = ("type", "card", "color", "source")
    return all(candidate.get(key) == live_move.get(key) for key in keys)


def choose_live_move(
    state: dict[str, Any],
    player_id: str,
    validator,
    model=None,
    difficulty: str = "hard",
    rng=None,
) -> dict[str, Any]:
    """Choose a legal live move while keeping canonical v2 slots aligned.

    The encoder uses a copied, canonically sorted state. Its action ID is mapped
    back to the original legal move by action meaning, never by sorted hand index.
    Hard uses the model's highest-probability action; medium and easy sample the
    model policy and increasingly often substitute a uniformly random legal move.
    Raises on any mismatch so the API can safely fall back to MCTS.
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
    version = next(version for version, size in OBSERVATION_SIZES.items() if size == input_size)
    encoded, canonical_moves = encode_live_state(state, player_id, live_moves, version, validator)
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
    selected = moves_by_action_id(canonical_moves).get(action_id)
    if selected is None:
        raise ValueError(f"PPO selected masked or unmapped action {action_id}")
    live_move = next((move for move in live_moves if _same_action(selected, move)), None)
    if live_move is None:
        raise ValueError(f"PPO action does not map to a live legal move: {selected!r}")
    return live_move
