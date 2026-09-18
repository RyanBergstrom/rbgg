"""Tests for move flow routes and registry."""

from fastapi.testclient import TestClient
from app import app
from app.core.game_store import clear_all


def setup_function():
    clear_all()


def test_start_session_for_unknown_game_returns_404():
    """Verify that POST /api/v1/moves/start-session/{game_id} returns 404 for unknown games."""
    client = TestClient(app)
    response = client.post("/api/v1/moves/start-session/unknown-game")
    assert response.status_code == 404


def test_start_session_without_validator_returns_501():
    """Verify that POST /api/v1/moves/start-session/{game_id} returns 501 when no validator registered."""
    from app.games.catalog import register_game
    register_game("no-validator-game", "No Validator", "no-validator-game")
    client = TestClient(app)
    response = client.post("/api/v1/moves/start-session/no-validator-game")
    assert response.status_code == 501


def test_get_sessions_returns_list():
    """Verify that GET /api/v1/sessions/ returns a list."""
    client = TestClient(app)
    response = client.get("/api/v1/sessions/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_post_move_without_game_returns_404():
    """Verify that POST /api/v1/moves/{game_id}/move returns 404 when no game is active."""
    client = TestClient(app)
    response = client.post("/api/v1/moves/test_game/move", json={"move_id": "m1"})
    assert response.status_code == 404


def test_ai_move_without_game_returns_no_legal_moves():
    """Verify that POST /api/v1/moves/ai returns no_legal_moves when no game is active."""
    client = TestClient(app)
    response = client.post("/api/v1/moves/ai", json={"gameId": "test_game"})
    assert response.status_code == 200
    assert response.json()["status"] == "no_legal_moves"


def test_legal_moves_without_game_returns_empty():
    """Verify that POST /api/v1/moves/legal-moves returns empty when no game is active."""
    client = TestClient(app)
    response = client.post("/api/v1/moves/legal-moves", json={"game_id": "test_game"})
    assert response.status_code == 200
    assert response.json()["legal_moves"] == []
