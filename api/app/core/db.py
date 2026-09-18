from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Optional


DB_PATH = Path("rbgg.db")


def get_connection(path: Optional[str] = None) -> sqlite3.Connection:
    """Return a sqlite3 Connection positioned at the project DB."""
    target = Path(path) if path else DB_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(target))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Initialise the schema: create tables if they do not exist."""
    cur = conn.cursor()

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS game_sessions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL,
            game_id TEXT NOT NULL DEFAULT 'santorini',
            started_at TEXT NOT NULL DEFAULT (datetime('now')),
            finished_at TEXT,
            state_id TEXT,
            game_state_json TEXT,
            expected_version INTEGER NOT NULL DEFAULT 1
        )
        """
    )

    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS game_stats (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            profile_id TEXT NOT NULL,
            total_moves INTEGER NOT NULL DEFAULT 0,
            total_turns INTEGER NOT NULL DEFAULT 0,
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )

    conn.commit()
