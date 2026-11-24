"""Live MaskablePPO inference for the production Twilight Struggle Schema 2 model.

The PPO policy selects from the staged reference adapter's fixed action space. This
bridge replays those staged decisions against a cloned live state until they form one
complete validator move, then returns that move without mutating the session state.
"""
from __future__ import annotations

from functools import lru_cache
import os
from pathlib import Path
import random
from typing import Any

import numpy as np

from app.games.twilight_struggle.rl_adapter import (
    ACTION_COUNT_V2,
    OBSERVATION_SIZE_V2,
    TwilightStruggleReferenceEnv,
)
from app.games.twilight_struggle.rl_strategy import filter_safe_actions
from app.games.twilight_struggle.state_clone import clone_envelope

MODEL_OBSERVATION_SIZE = OBSERVATION_SIZE_V2
MODEL_ACTION_COUNT = ACTION_COUNT_V2
MAX_STAGED_DECISIONS = 128
DIFFICULTY_RANDOM_ACTION_PROBABILITIES = {
    "hard": 0.0,
    "medium": 0.15,
    "easy": 0.5,
}


def configured_model_path() -> Path:
    """Use an optional explicit path or the promoted production model."""
    configured = os.environ.get("RBGG_TWILIGHT_PPO_MODEL")
    api_root = Path(__file__).resolve().parents[3]
    if not configured:
        return api_root / "runtime" / "twilight-ppo-v2-safe-500k.zip"
    path = Path(configured).expanduser()
    return path if path.is_absolute() else api_root / path


@lru_cache(maxsize=2)
def load_model(model_path: str):
    """Load and validate a Schema 2 MaskablePPO model once per path."""
    from sb3_contrib import MaskablePPO

    path = Path(model_path)
    if not path.is_file():
        raise FileNotFoundError(f"Twilight Struggle PPO model not found: {path}")
    model = MaskablePPO.load(str(path), device="cpu")
    observation_size = getattr(model.observation_space, "shape", None)
    action_count = getattr(model.action_space, "n", None)
    if observation_size != (MODEL_OBSERVATION_SIZE,) or action_count != MODEL_ACTION_COUNT:
        raise ValueError(
            "Twilight Struggle PPO model schema mismatch: expected "
            f"observation ({MODEL_OBSERVATION_SIZE},) and {MODEL_ACTION_COUNT} actions, "
            f"got observation {observation_size} and {action_count} actions"
        )
    return model


def _build_adapter(state: dict[str, Any], validator) -> TwilightStruggleReferenceEnv:
    if not isinstance(state, dict) or not isinstance(state.get("game_data"), dict):
        raise ValueError("Twilight PPO requires a complete live game-state envelope")
    adapter = TwilightStruggleReferenceEnv(
        validator=validator,
        state=clone_envelope(state),
        schema_version=2,
    )
    adapter.pending = None
    adapter._touch()
    return adapter


def choose_live_move(
    state: dict[str, Any],
    player_id: str,
    validator,
    model=None,
    difficulty: str = "hard",
    rng=None,
) -> dict[str, Any]:
    """Select one complete, validator-legal move for a live Twilight session.

    PPO's sub-action sequence is evaluated on a cloned in-memory state. The live
    session changes only when the returned complete move is submitted by GameEngine.
    Hard uses masked argmax; medium/easy sample the distribution with an optional
    legal-random-action mixture. The safety filter is applied before every staged
    policy decision to match safety-masked training.
    """
    if not isinstance(difficulty, str) or difficulty not in DIFFICULTY_RANDOM_ACTION_PROBABILITIES:
        raise ValueError(f"unsupported Twilight PPO difficulty: {difficulty}")
    if state.get("game_data", {}).get("current_player") != player_id:
        raise ValueError("Twilight PPO can only act for the current player")

    active_model = model or load_model(str(configured_model_path()))
    observation_size = getattr(active_model.observation_space, "shape", None)
    action_count = getattr(active_model.action_space, "n", None)
    if observation_size != (MODEL_OBSERVATION_SIZE,) or action_count != MODEL_ACTION_COUNT:
        raise ValueError(
            "Twilight PPO requires Schema 2 model dimensions "
            f"({MODEL_OBSERVATION_SIZE}, {MODEL_ACTION_COUNT}); got ({observation_size}, {action_count})"
        )

    adapter = _build_adapter(state, validator)
    random_source = rng or random.Random()
    random_action_probability = DIFFICULTY_RANDOM_ACTION_PROBABILITIES[difficulty]

    for _ in range(MAX_STAGED_DECISIONS):
        if adapter.is_terminal():
            raise ValueError("Twilight PPO reached a terminal state before completing a move")
        if adapter.current_player != player_id:
            raise ValueError("Twilight PPO staged decision changed actor before producing a move")

        observation = adapter.observe(player_id)
        legal_ids = [index for index, legal in enumerate(observation["action_mask"]) if legal]
        if not legal_ids:
            raise ValueError("Twilight PPO adapter has no representable legal actions for this phase")
        safe_ids = filter_safe_actions(adapter, legal_ids)
        action_mask = np.zeros(MODEL_ACTION_COUNT, dtype=bool)
        action_mask[safe_ids] = True
        vector = np.asarray(observation["observation"], dtype=np.float32)

        if random_action_probability and random_source.random() < random_action_probability:
            action_id = int(random_source.choice(safe_ids))
        else:
            prediction, _ = active_model.predict(
                vector,
                action_masks=action_mask,
                deterministic=difficulty == "hard",
            )
            action_id = int(np.asarray(prediction).item())
        if action_id not in safe_ids:
            raise ValueError(f"Twilight PPO selected masked or unsafe action {action_id}")

        _, _, terminated, info = adapter.step(action_id)
        if info.get("rejected"):
            raise ValueError(f"Twilight PPO staged action was rejected: {info.get('move')!r}")
        completed_move = info.get("move")
        if completed_move is None:
            if terminated:
                raise ValueError("Twilight PPO terminated before completing its selected move")
            continue
        if not validator.validate_move(state, completed_move):
            raise ValueError(f"Twilight PPO move is not legal in the live state: {completed_move!r}")
        return completed_move

    raise ValueError(f"Twilight PPO exceeded {MAX_STAGED_DECISIONS} staged decisions without a complete move")
