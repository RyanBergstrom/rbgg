"""Validator registry for move pipelines.

Stores per-game validator instances keyed by game ID.  Returns a 501
``NotImplementedError`` when a validator has not been registered for the
requested game, which the route handlers convert to an explicit HTTP 501
response.
"""

VALIDATOR_REGISTRY: dict[str, object] = {}


def register_validator(game_id: str, validator: object) -> None:
    """Register a move validator for *game_id*."""
    VALIDATOR_REGISTRY[game_id] = validator


def get_validator(game_id: str) -> object | None:
    """Return the registered validator for *game_id*, or ``None``."""
    return VALIDATOR_REGISTRY.get(game_id)


def ensure_validator(game_id: str) -> object:
    """Return the validator for *game_id*, raising if absent."""
    validator = get_validator(game_id)
    if validator is None:
        raise RuntimeError(f"validator not registered for game: {game_id}")
    return validator
