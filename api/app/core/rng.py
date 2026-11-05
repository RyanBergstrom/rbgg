from __future__ import annotations

import json
import random
from typing import Any


def _to_tuple(obj: Any) -> Any:
    """Recursively convert lists back to tuples (JSON returns lists)."""
    if isinstance(obj, list):
        return tuple(_to_tuple(x) for x in obj)
    return obj


# Parsed RNG states keyed by their JSON text. Validators rebuild the same RNG
# many times per move, and parsing the 625-word Mersenne state dominates that.
# Parsed states are immutable tuples, so sharing them is safe.
_STATE_CACHE: dict[str, Any] = {}
_STATE_CACHE_LIMIT = 4096


def _parsed_state(state_json: str) -> Any:
    cached = _STATE_CACHE.get(state_json)
    if cached is None:
        cached = _to_tuple(json.loads(state_json))
        if len(_STATE_CACHE) >= _STATE_CACHE_LIMIT:
            _STATE_CACHE.clear()
        _STATE_CACHE[state_json] = cached
    return cached


def create_rng(seed: int, state_json: str | None = None) -> random.Random:
    """Create a deterministic RNG from a seed and optional persisted state.

    Args:
        seed: The deterministic seed.
        state_json: Previously serialized RNG state (from ``serialize_rng``).

    Returns:
        A ``random.Random`` instance in the correct state.
    """
    rng = random.Random(seed)
    if state_json and state_json != "{}":
        try:
            rng.setstate(_parsed_state(state_json))
        except (json.JSONDecodeError, ValueError, TypeError):
            pass
    return rng


def serialize_rng(rng: random.Random) -> str:
    """Serialize an RNG instance's state to a JSON string.

    Returns:
        A JSON string suitable for storage in ``rng_state_json``.
    """
    return json.dumps(rng.getstate())


def serialize_rng_state(rng_seed: int, rng_state_json: str | None = None) -> dict[str, Any]:
    """Serialize the RNG state into a dictionary for storage or transmission.

    Returns:
        A dict with ``"seed"`` and ``"state"`` keys.
    """
    if rng_state_json is None:
        rng_state_json = "{}"
    return {"seed": rng_seed, "state": rng_state_json}


def deserialize_rng_state(data: dict[str, Any]) -> tuple[int, str]:
    """Deserialize a previously-serialized RNG state dictionary.

    Returns:
        A ``(seed, state_json)`` tuple.
    """
    seed: int = int(data["seed"])
    state_json: str = str(data["state"])
    return seed, state_json
