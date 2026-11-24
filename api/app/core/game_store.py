"""Process-local cache for SQLite-backed session state.

Entries are keyed by opaque database session IDs, never by game type. SQLite
is the authoritative store; this module only avoids repeatedly parsing the
same session JSON during one request flow.

Undo history is durable: every pushed snapshot is also appended to
``api/runtime/undo/undo_<session_id>.txt`` so it survives process restarts and
can be resumed on a later request.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional

from app.core.undo_log import (
    append_undo,
    clear_undo_file,
    has_undo_file,
    load_stack,
    pop_undo_file,
    rewrite_stack,
)


@dataclass
class GameEntry:
    """Active game with its DB session reference."""

    state: Any
    session_id: int | None = None


_store: Dict[int, GameEntry] = {}
_undo_store: Dict[int, List[Any]] = {}  # session_id -> stack of serialized state snapshots


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


def _ensure_loaded(session_id: int) -> List[Any]:
    """Ensure the in-memory undo stack is loaded from the durable file."""
    stack = _undo_store.get(session_id)
    if stack is None:
        stack = load_stack(session_id)
        _undo_store[session_id] = stack
    return stack


def push_undo(session_id: int, state: Any) -> None:
    """Save a state snapshot for undo. Snapshots accumulate as a stack and are
    appended to the durable per-session undo log."""
    import json

    snapshot = json.loads(state.model_dump_json())
    stack = _ensure_loaded(session_id)
    stack.append(snapshot)
    append_undo(session_id, snapshot)


def pop_undo(session_id: int) -> Any | None:
    """Retrieve and remove the most recent undo snapshot. Returns None if empty."""
    stack = _ensure_loaded(session_id)
    if not stack:
        return None
    snapshot = stack.pop()
    rewrite_stack(session_id, stack)
    return snapshot


def has_undo(session_id: int) -> bool:
    """Check if an undo snapshot exists."""
    stack = _ensure_loaded(session_id)
    return bool(stack) or has_undo_file(session_id)


def clear_undo(session_id: int) -> None:
    """Clear all undo snapshots for a session (memory + durable file)."""
    _undo_store.pop(session_id, None)
    clear_undo_file(session_id)


def load_undo_stack(session_id: int) -> List[Any]:
    """Public helper to load the durable undo stack into memory for a session."""
    return _ensure_loaded(session_id)
