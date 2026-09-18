from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from app.core.db import get_connection, init_db

DB_PATH = Path("rbgg.db")


def create_session(profile_id: str, game_id: str = "santorini", state_id: str | None = None, game_state_json: str | None = None) -> dict:
    """Create a new game session scoped to a profile."""
    conn = get_connection(str(DB_PATH))
    init_db(conn)
    now = datetime.now(timezone.utc).isoformat()
    cur = conn.cursor()
    cur.execute(
        "INSERT INTO game_sessions (profile_id, game_id, started_at, state_id, game_state_json) VALUES (?, ?, ?, ?, ?)",
        (profile_id, game_id, now, state_id, game_state_json),
    )
    conn.commit()
    rowid = cur.lastrowid
    session = {
        "id": rowid,
        "profile_id": profile_id,
        "game_id": game_id,
        "started_at": now,
        "finished_at": None,
        "state_id": state_id,
    }
    conn.close()
    return session


def get_session(session_id: int) -> dict | None:
    """Retrieve a session by its auto-increment ID."""
    conn = get_connection(str(DB_PATH))
    init_db(conn)
    cur = conn.cursor()
    cur.execute(
        "SELECT id, profile_id, game_id, started_at, finished_at, state_id, game_state_json, expected_version FROM game_sessions WHERE id = ?",
        (session_id,),
    )
    row = cur.fetchone()
    conn.close()
    if row is None:
        return None
    return {
        "id": row[0],
        "profile_id": row[1],
        "game_id": row[2],
        "started_at": row[3],
        "finished_at": row[4],
        "state_id": row[5],
        "game_state_json": row[6],
        "expected_version": row[7],
    }


def save_session(session_id: int, expected_version: int, state_id: str | None = None, game_state_json: str | None = None) -> bool:
    """Save a session with optimistic concurrency.

    Returns True if the update succeeded (version matched and was bumped).
    Returns False if the version was stale (did not match).
    """
    conn = get_connection(str(DB_PATH))
    init_db(conn)
    cur = conn.cursor()

    cur.execute("SELECT expected_version FROM game_sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()

    if row is None:
        conn.close()
        return False

    current_version = row[0]

    if current_version == 0:
        cur.execute(
            "UPDATE game_sessions SET expected_version = ?, state_id = COALESCE(?, state_id), game_state_json = COALESCE(?, game_state_json) WHERE id = ?",
            (expected_version + 1, state_id, game_state_json, session_id),
        )
        conn.commit()
        conn.close()
        return True

    if current_version != expected_version:
        conn.close()
        return False

    cur.execute(
        "UPDATE game_sessions SET expected_version = ?, state_id = COALESCE(?, state_id), game_state_json = COALESCE(?, game_state_json) WHERE id = ? AND expected_version = ?",
        (expected_version + 1, state_id, game_state_json, session_id, expected_version),
    )
    conn.commit()
    conn.close()
    return True


def save_game_state(session_id: int, game_state_json: str) -> bool:
    """Save just the game state JSON for a session (bumps version)."""
    conn = get_connection(str(DB_PATH))
    init_db(conn)
    cur = conn.cursor()

    cur.execute("SELECT expected_version FROM game_sessions WHERE id = ?", (session_id,))
    row = cur.fetchone()
    if row is None:
        conn.close()
        return False

    current_version = row[0]
    cur.execute(
        "UPDATE game_sessions SET expected_version = ?, game_state_json = ? WHERE id = ? AND expected_version = ?",
        (current_version + 1, game_state_json, session_id, current_version),
    )
    conn.commit()
    updated = cur.rowcount > 0
    conn.close()
    return updated


def list_sessions(profile_id: str | None = None, game_id: str | None = None) -> list[dict]:
    """List sessions, optionally filtered by profile_id and/or game_id."""
    conn = get_connection(str(DB_PATH))
    init_db(conn)
    cur = conn.cursor()

    query = "SELECT id, profile_id, game_id, started_at, finished_at, state_id FROM game_sessions WHERE 1=1"
    params: list = []

    if profile_id is not None:
        query += " AND profile_id = ?"
        params.append(profile_id)

    if game_id is not None:
        query += " AND game_id = ?"
        params.append(game_id)

    query += " ORDER BY started_at DESC"
    cur.execute(query, params)
    rows = cur.fetchall()
    conn.close()

    return [
        {
            "id": row[0],
            "profile_id": row[1],
            "game_id": row[2],
            "started_at": row[3],
            "finished_at": row[4],
            "state_id": row[5],
        }
        for row in rows
    ]


def delete_session(session_id: int) -> bool:
    """Delete a session by its ID. Returns True if deleted, False if not found."""
    conn = get_connection(str(DB_PATH))
    init_db(conn)
    cur = conn.cursor()
    cur.execute("DELETE FROM game_sessions WHERE id = ?", (session_id,))
    conn.commit()
    deleted = cur.rowcount > 0
    conn.close()
    return deleted


def load_game_state(session_id: int):
    """Load the full GameState object from a session's saved JSON.

    Returns a GameState instance, or None if the session has no saved state.
    """
    from app.core.game_state import GameState
    session = get_session(session_id)
    if session is None:
        return None
    raw = session.get("game_state_json")
    if not raw:
        return None
    return GameState.model_validate_json(raw)


def record_stats(profile_id: str, total_moves: int = 0, total_turns: int = 0) -> dict:
    """Insert a row into game_stats and return the created record."""
    conn = get_connection(str(DB_PATH))
    init_db(conn)
    cur = conn.cursor()
    now = datetime.now(timezone.utc).isoformat()
    cur.execute(
        "INSERT INTO game_stats (profile_id, total_moves, total_turns, updated_at) VALUES (?, ?, ?, ?)",
        (profile_id, total_moves, total_turns, now),
    )
    conn.commit()
    rowid = cur.lastrowid
    record = {
        "id": rowid,
        "profile_id": profile_id,
        "total_moves": total_moves,
        "total_turns": total_turns,
        "updated_at": now,
    }
    conn.close()
    return record
