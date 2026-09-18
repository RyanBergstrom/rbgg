"""Tests for WI-005 sqlite schema with profile-scoped session tables."""

from pathlib import Path

from app.core.db import get_connection, init_db


def test_init_db_creates_tables():
    """Verify that init_db creates the game_sessions and game_stats tables."""
    db_path = Path(".tmp_test.db")
    try:
        conn = get_connection(str(db_path))
        init_db(conn)

        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        tables = {row["name"] for row in cur.fetchall()}

        assert "game_sessions" in tables, "game_sessions table should exist"
        assert "game_stats" in tables, "game_stats table should exist"

        # Verify profile_id columns exist
        cur.execute("PRAGMA table_info(game_sessions)")
        session_cols = {row["name"] for row in cur.fetchall()}
        assert "profile_id" in session_cols, "game_sessions should have profile_id column"

        cur.execute("PRAGMA table_info(game_stats)")
        stats_cols = {row["name"] for row in cur.fetchall()}
        assert "profile_id" in stats_cols, "game_stats should have profile_id column"

        conn.close()
    finally:
        if db_path.exists():
            db_path.unlink()


def test_init_db_is_idempotent():
    """Verify that running init_db twice does not raise an error."""
    db_path = Path(".tmp_test2.db")
    try:
        # First init
        conn1 = get_connection(str(db_path))
        init_db(conn1)
        conn1.close()

        # Second init (idempotent)
        conn2 = get_connection(str(db_path))
        init_db(conn2)
        conn2.close()
    finally:
        if db_path.exists():
            db_path.unlink()