"""conftest.py ensures api package is importable from tests and DB is initialized."""
import sys
import os
import pytest

# Ensure the project root is on the path so api package is importable
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# Exclude JS test files misfiled with .py extension
collect_ignore_glob = ["test_santorini_end_to_end.py"]


def _init_test_db():
    """Initialize the test database with required tables."""
    from app.core.db import get_connection, init_db
    conn = get_connection()
    init_db(conn)
    conn.close()


# Initialize DB at import time
_init_test_db()


@pytest.fixture(autouse=True)
def ensure_db():
    """Re-initialize DB before each test in case a prior test deleted it."""
    _init_test_db()
    yield
