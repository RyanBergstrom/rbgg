"""Tests for games and sessions route contracts."""

from fastapi.testclient import TestClient
from app import app
from app.core.game_store import clear_all
from app.games.catalog import register_game


def setup_function():
    clear_all()
    register_game("test_game", "Test Game", "test_game", min_players=2, max_players=4)


def test_get_games_returns_catalog():
    """Verify that GET /api/v1/games/ returns the game catalog."""
    client = TestClient(app)
    response = client.get("/api/v1/games/")
    assert response.status_code == 200
    games = response.json()
    assert isinstance(games, list)
    assert len(games) >= 1
    test_game = [g for g in games if g["id"] == "test_game"]
    assert len(test_game) == 1
    assert test_game[0]["name"] == "Test Game"


def test_get_game_by_id_returns_game():
    """Verify that GET /api/v1/games/test_game returns game details."""
    client = TestClient(app)
    response = client.get("/api/v1/games/test_game")
    assert response.status_code == 200
    data = response.json()
    assert data["id"] == "test_game"
    assert data["name"] == "Test Game"


def test_bus_catalog_uses_and_serves_its_cover_art():
    client = TestClient(app)

    game_response = client.get("/api/v1/games/bus")
    assert game_response.status_code == 200
    assert game_response.json()["cover_image"] == "bus/bus-boxart.webp"

    image_response = client.get("/api/v1/img/bus/bus-boxart.webp")
    assert image_response.status_code == 200
    assert image_response.headers["content-type"] == "image/webp"


def test_get_game_by_id_404_for_unknown():
    """Verify that GET /api/v1/games/{game_id} returns 404 for unknown games."""
    client = TestClient(app)
    response = client.get("/api/v1/games/nonexistent-id")
    assert response.status_code == 404


def test_get_sessions_returns_list():
    """Verify that GET /api/v1/sessions/ returns a list."""
    client = TestClient(app)
    response = client.get("/api/v1/sessions/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_get_sessions_filtered():
    """Verify that sessions can be filtered by game_id."""
    client = TestClient(app)
    response = client.get("/api/v1/sessions/filter?game_id=test_game")
    assert response.status_code == 200
    assert isinstance(response.json(), list)
