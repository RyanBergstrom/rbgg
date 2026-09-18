"""In-memory game state store for active games.

Stores GameState objects keyed by game_id.  Also tracks the DB session_id
so state can be persisted after each move.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class GameEntry:
    """Active game with its DB session reference."""
    state: Any
    session_id: int | None = None


_store: Dict[str, GameEntry] = {}
_undo_store: Dict[str, Any] = {}  # game_id -> serialized state snapshot for undo


def get_state(game_id: str) -> Any:
    """Return the current state for *game_id*, or None."""
    entry = _store.get(game_id)
    return entry.state if entry else None


def get_entry(game_id: str) -> Optional[GameEntry]:
    """Return the full GameEntry for *game_id*, or None."""
    return _store.get(game_id)


def set_state(game_id: str, state: Any, session_id: int | None = None) -> None:
    """Store a state for *game_id*."""
    existing = _store.get(game_id)
    if existing is not None and session_id is None:
        session_id = existing.session_id
    _store[game_id] = GameEntry(state=state, session_id=session_id)


def clear_state(game_id: str) -> None:
    """Remove the state for *game_id*."""
    _store.pop(game_id, None)


def clear_all() -> None:
    """Clear all stored states (for testing)."""
    _store.clear()
    _undo_store.clear()


def push_undo(game_id: str, state: Any) -> None:
    """Save a state snapshot for undo. Only one level of undo is stored."""
    import json
    snapshot = json.loads(state.model_dump_json())
    _undo_store[game_id] = snapshot


def pop_undo(game_id: str) -> Any | None:
    """Retrieve and remove the undo snapshot. Returns None if no undo available."""
    return _undo_store.pop(game_id, None)


def has_undo(game_id: str) -> bool:
    """Check if an undo snapshot exists."""
    return game_id in _undo_store


def clear_undo(game_id: str) -> None:
    """Clear undo snapshot for a game."""
    _undo_store.pop(game_id, None)
