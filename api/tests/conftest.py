"""conftest.py ensures api package is importable from tests and DB is initialized."""
import sys
import os
import pytest
from pathlib import Path

_test_db_path = Path(__file__).resolve().parent / "test-runtime.db"

# Ensure the project root is on the path so api package is importable
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Exclude JS test files misfiled with .py extension
collect_ignore_glob = ["test_santorini_end_to_end.py"]


def _init_test_db():
    """Initialize the test database with required tables."""
    from app.core.db import get_connection, init_db
    conn = get_connection(str(_test_db_path))
    init_db(conn)
    conn.close()


@pytest.fixture(autouse=True)
def ensure_db(monkeypatch):
    """Provide an isolated test database without touching runtime data."""
    import app.core.db as db
    import app.core.repository as repository
    monkeypatch.setattr(db, "DB_PATH", _test_db_path)
    monkeypatch.setattr(repository, "DB_PATH", _test_db_path)
    _test_db_path.unlink(missing_ok=True)
    _init_test_db()
    yield


@pytest.fixture(scope="session", autouse=True)
def cleanup_test_db():
    yield
    _test_db_path.unlink(missing_ok=True)
