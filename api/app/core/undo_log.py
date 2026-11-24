"""File-backed undo history stored under ``api/runtime/undo/undo_<session_id>.txt``.

Each line is one serialized GameState snapshot (JSON). The file is the durable
source of truth so undo history survives process restarts and can be resumed on
a later request. Any game can build on this: push a snapshot before every
state-changing action, pop on undo.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

# Resolve against the repository root so it works regardless of CWD.
UNDO_DIR = Path(__file__).resolve().parents[2] / "runtime" / "undo"


def _ensure_dir() -> None:
    UNDO_DIR.mkdir(parents=True, exist_ok=True)


def _path(session_id: int) -> Path:
    _ensure_dir()
    return UNDO_DIR / f"undo_{session_id}.txt"


def append_undo(session_id: int, snapshot: Any) -> None:
    """Append one serialized state snapshot to the session's undo log."""
    _ensure_dir()
    with open(_path(session_id), "a", encoding="utf-8") as fh:
        fh.write(json.dumps(snapshot, sort_keys=True) + "\n")


def load_stack(session_id: int) -> list[Any]:
    """Read all undo snapshots from the file (oldest first). Returns [] if empty."""
    path = _path(session_id)
    if not path.exists():
        return []
    snapshots: list[Any] = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line:
                snapshots.append(json.loads(line))
    return snapshots


def rewrite_stack(session_id: int, stack: list[Any]) -> None:
    """Rewrite the undo file to exactly *stack* (oldest first)."""
    _ensure_dir()
    path = _path(session_id)
    if stack:
        with open(path, "w", encoding="utf-8") as fh:
            for snapshot in stack:
                fh.write(json.dumps(snapshot, sort_keys=True) + "\n")
    else:
        path.unlink(missing_ok=True)


def pop_undo_file(session_id: int) -> Any | None:
    """Remove and return the most recent undo snapshot from the file."""
    path = _path(session_id)
    if not path.exists():
        return None
    with open(path, "r", encoding="utf-8") as fh:
        lines = fh.readlines()
    if not lines:
        return None
    last = lines.pop()
    rewrite_stack(session_id, [json.loads(l) for l in lines if l.strip()])
    return json.loads(last)


def has_undo_file(session_id: int) -> bool:
    path = _path(session_id)
    return path.exists() and path.stat().st_size > 0


def clear_undo_file(session_id: int) -> None:
    path = _path(session_id)
    if path.exists():
        path.unlink()
