"""Shared contract for game-specific reinforcement-learning adapters.

The contract intentionally contains no PettingZoo, Gymnasium, or ML dependency.
Game adapters remain responsible for their own state encoding, action mapping,
visibility rules, and rewards.
"""
from __future__ import annotations

from typing import Any, Protocol, TypeAlias, runtime_checkable

Observation: TypeAlias = dict[str, Any]
StepResult: TypeAlias = tuple[Observation, float, bool, dict[str, Any]]


@runtime_checkable
class RLAdapter(Protocol):
    """Minimal headless environment surface shared by game adapters."""

    @property
    def action_count(self) -> int:
        """Number of fixed action IDs exposed by the adapter."""
        ...

    @property
    def observation_size(self) -> int:
        """Length of the numeric observation vector."""
        ...

    @property
    def current_player(self) -> str:
        """Stable agent ID whose turn is active."""
        ...

    def reset(self, seed: int | None = None) -> Observation:
        """Start a new in-memory episode."""
        ...

    def observe(self, player_id: str) -> Observation:
        """Return a player-relative observation and action mask."""
        ...

    def legal_moves(self, player_id: str | None = None) -> list[dict[str, Any]]:
        """Return validator-backed legal move payloads."""
        ...

    def step(self, action_id: int) -> StepResult:
        """Apply one action and return observation, reward, terminal, metadata."""
        ...
