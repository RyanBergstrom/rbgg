"""Process-local cache for SQLite-backed session state.

Entries are keyed by opaque database session IDs, never by game type. SQLite
is the authoritative store; this module only avoids repeatedly parsing the
same session JSON during one request flow.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class GameEntry:
    """Active game with its DB session reference."""
    state: Any
    session_id: int | None = None


_store: Dict[int, GameEntry] = {}
_undo_store: Dict[int, Any] = {}  # session_id -> serialized state snapshot


def get_state(session_id: int) -> Any:
    """Return the cached state for *session_id*, or None."""
    entry = _store.get(session_id)
    return entry.state if entry else None


def get_entry(session_id: int) -> Optional[GameEntry]:
    """Return the full cached entry for *session_id*, or None."""
    return _store.get(session_id)


def set_state(session_id: int, state: Any) -> None:
    """Cache a state for *session_id*."""
    _store[session_id] = GameEntry(state=state, session_id=session_id)


def clear_state(session_id: int) -> None:
    """Remove the cached state for *session_id*."""
    _store.pop(session_id, None)


def clear_all() -> None:
    """Clear all stored states (for testing)."""
    _store.clear()
    _undo_store.clear()


def push_undo(session_id: int, state: Any) -> None:
    """Save a state snapshot for undo. Only one level of undo is stored."""
    import json
    snapshot = json.loads(state.model_dump_json())
    _undo_store[session_id] = snapshot


def pop_undo(session_id: int) -> Any | None:
    """Retrieve and remove the undo snapshot. Returns None if no undo available."""
    return _undo_store.pop(session_id, None)


def has_undo(session_id: int) -> bool:
    """Check if an undo snapshot exists."""
    return session_id in _undo_store


def clear_undo(session_id: int) -> None:
    """Clear the undo snapshot for a session."""
    _undo_store.pop(session_id, None)
