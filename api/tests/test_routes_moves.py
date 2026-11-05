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


def test_new_lost_cities_sessions_receive_fresh_deals(monkeypatch):
    from app.core.game_store import get_state

    generated_seeds = iter((123456789, 987654321))
    monkeypatch.setattr("secrets.randbits", lambda bits: next(generated_seeds))
    client = TestClient(app)

    first = client.post("/api/v1/moves/start-session/lost_cities").json()
    second = client.post("/api/v1/moves/start-session/lost_cities").json()

    first_state = get_state(first["session_id"])
    second_state = get_state(second["session_id"])
    assert first["rng_seed"] == 123456789
    assert second["rng_seed"] == 987654321
    assert first_state.game_data["player_hands"]["player_1"] != second_state.game_data["player_hands"]["player_1"]


def test_all_games_use_consistent_bot_names():
    from app.core.game_store import get_state

    client = TestClient(app)
    for game_id, player_count in (("checkers", 2), ("lost_cities", 2), ("bus", 5)):
        response = client.post(
            f"/api/v1/moves/start-session/{game_id}",
            json={"playerName": "Alex", "playerCount": player_count},
        )
        assert response.status_code == 200
        state = get_state(response.json()["session_id"])
        assert [player.name for player in state.players] == [
            "Alex", "Stacy", "Trey", "Bella", "Stitch"
        ][:player_count]


def test_start_bus_session_uses_requested_three_to_five_player_count():
    """Bus starts with one human and the selected number of total seats."""
    client = TestClient(app)
    response = client.post("/api/v1/moves/start-session/bus", json={"playerCount": 4})
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    state = client.get(f"/api/v1/games/bus?session_id={session_id}").json()["state"]
    assert state["game_data"]["current_phase"] == "SETUP_BUILDINGS"
    assert len(state["game_data"]["players"]) == 4

    assert response.json()["screen_state"]["legal_moves"]
    assert response.json()["screen_state"]["legal_moves"][0]["type"] == "setup_building"


def test_bus_initial_screen_state_includes_current_actor_legal_moves():
    client = TestClient(app)
    response = client.post("/api/v1/moves/start-session/bus", json={"playerCount": 3})
    assert response.status_code == 200
    screen_state = response.json()["screen_state"]
    assert screen_state["current_player"] in {"player_1", "player_2", "player_3"}
    assert screen_state["legal_moves"]


def test_three_player_bus_session_creates_red_green_and_blue_seats():
    from app.core.game_store import get_state

    client = TestClient(app)
    response = client.post("/api/v1/moves/start-session/bus", json={"playerCount": 3})
    assert response.status_code == 200
    session_id = response.json()["session_id"]
    state = get_state(session_id)
    assert [player.player_id for player in state.players] == ["player_1", "player_2", "player_3"]
    assert [player.color for player in state.players] == ["#cc0000", "#3b8d3b", "#1d70b8"]


def test_bus_session_api_completes_setup_and_a_bot_selection_turn():
    """Bus route APIs preserve validator-owned actors through setup and bot play."""
    client = TestClient(app)
    started = client.post(
        "/api/v1/moves/start-session/bus",
        json={"playerCount": 3, "rng_seed": 13579},
    )
    assert started.status_code == 200
    session_id = started.json()["session_id"]

    # Six buildings and two route segments for each player complete setup.
    for _ in range(12):
        legal_response = client.post(
            "/api/v1/moves/legal-moves", json={"session_id": session_id}
        )
        assert legal_response.status_code == 200
        legal_moves = legal_response.json()["legal_moves"]
        assert legal_moves
        submitted = client.post(
            f"/api/v1/moves/{session_id}/move", json=legal_moves[0]
        )
        assert submitted.status_code == 200

    setup_state = client.get(
        f"/api/v1/games/bus?session_id={session_id}"
    ).json()["state"]
    setup_data = setup_state["game_data"]
    assert setup_data["current_phase"] == "ACTION_SELECTION"
    assert setup_state["player_turn"] == setup_data["current_player"]

    actor = setup_data["current_player"]
    for _ in range(7):
        ai_response = client.post("/api/v1/moves/ai", json={"sessionId": session_id})
        assert ai_response.status_code == 200
        assert ai_response.json()["status"] == "ok"
    ai_data = ai_response.json()["screen_state"]["game_data"]
    assert ai_data["players"][actor]["action_markers"] <= 18
    # The bot now picks a random legal action (and voluntarily passes after
    # three selections) instead of always selecting line_expansion then
    # passing immediately, so it may have advanced into a resolution
    # sub-phase rather than looping straight back to ACTION_SELECTION.
    assert ai_data["current_phase"] == "ACTION_SELECTION" or ai_data["current_phase"].startswith("RESOLVE_")
    assert ai_data["current_player"] in {"player_1", "player_2", "player_3"}


def test_bus_ai_route_consumes_consecutive_bot_turns_before_returning_to_human():
    from app.core.game_store import get_state

    client = TestClient(app)
    started = client.post(
        "/api/v1/moves/start-session/bus",
        json={"playerCount": 3, "rng_seed": 24680},
    )
    assert started.status_code == 200
    session_id = started.json()["session_id"]

    state = get_state(session_id)
    game_data = state.game_data
    game_data["current_phase"] = "ACTION_SELECTION"
    game_data["current_player"] = "player_2"
    game_data["action_spaces"] = {action: [] for action in game_data["action_spaces"]}
    game_data["passed_this_round"] = []
    game_data["resolution"] = None
    game_data["players"]["player_1"]["action_markers"] = 20
    game_data["players"]["player_2"]["action_markers"] = 20
    game_data["players"]["player_3"]["action_markers"] = 20

    debug = client.post(
        f"/api/v1/moves/debug-load/{session_id}",
        json={"game_data": game_data, "current_player_index": 1},
    )
    assert debug.status_code == 200

    response = client.post("/api/v1/moves/ai", json={"sessionId": session_id})
    assert response.status_code == 200
    screen_state = response.json()["screen_state"]
    assert screen_state["current_player"] == "player_1"


def test_get_sessions_returns_list():
    """Verify that GET /api/v1/sessions/ returns a list."""
    client = TestClient(app)
    response = client.get("/api/v1/sessions/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


def test_post_move_without_game_returns_404():
    """Verify that POST /api/v1/moves/{session_id}/move rejects an unknown session."""
    client = TestClient(app)
    response = client.post("/api/v1/moves/999999/move", json={"move_id": "m1"})
    assert response.status_code == 404


def test_ai_move_without_game_returns_no_legal_moves():
    """Verify that POST /api/v1/moves/ai rejects an unknown session."""
    client = TestClient(app)
    response = client.post("/api/v1/moves/ai", json={"sessionId": 999999})
    assert response.status_code == 404


def test_legal_moves_without_game_returns_empty():
    """Verify that POST /api/v1/moves/legal-moves rejects an unknown session."""
    client = TestClient(app)
    response = client.post("/api/v1/moves/legal-moves", json={"session_id": 999999})
    assert response.status_code == 404


def test_stateful_routes_require_session_id():
    """Stateful routes must not fall back to a game-type-global state."""
    client = TestClient(app)
    assert client.post("/api/v1/moves/legal-moves", json={"game_id": "checkers"}).status_code == 422
    assert client.post("/api/v1/moves/ai", json={"gameId": "checkers"}).status_code == 422


def test_two_sessions_for_one_game_keep_independent_state():
    """Interleaved requests to two same-game sessions do not overwrite state."""
    client = TestClient(app)
    first = client.post("/api/v1/moves/start-session/checkers").json()
    second = client.post("/api/v1/moves/start-session/checkers").json()
    first_id = first["session_id"]
    second_id = second["session_id"]
    assert first_id != second_id

    first_moves = client.post(
        "/api/v1/moves/legal-moves", json={"session_id": first_id}
    ).json()["legal_moves"]
    first_move = first_moves[0]
    moved = client.post(f"/api/v1/moves/{first_id}/move", json=first_move)
    assert moved.status_code == 200

    first_state = client.get(f"/api/v1/games/checkers?session_id={first_id}").json()
    second_state = client.get(f"/api/v1/games/checkers?session_id={second_id}").json()
    assert first_state["state"]["game_data"] != second_state["state"]["game_data"]


def test_two_lost_cities_sessions_keep_independent_state():
    """Lost Cities sessions also remain isolated when the game type matches."""
    client = TestClient(app)
    first = client.post("/api/v1/moves/start-session/lost_cities").json()
    second = client.post("/api/v1/moves/start-session/lost_cities").json()
    first_id = first["session_id"]
    second_id = second["session_id"]

    first_move = client.post(
        "/api/v1/moves/legal-moves", json={"session_id": first_id}
    ).json()["legal_moves"][0]
    moved = client.post(f"/api/v1/moves/{first_id}/move", json=first_move)
    assert moved.status_code == 200

    first_state = client.get(
        f"/api/v1/games/lost_cities?session_id={first_id}"
    ).json()
    second_state = client.get(
        f"/api/v1/games/lost_cities?session_id={second_id}"
    ).json()
    assert first_state["state"]["game_data"] != second_state["state"]["game_data"]


def test_terminal_human_move_completes_lost_cities_session_and_stats():
    from app.core.game_store import get_state

    client = TestClient(app)
    started = client.post("/api/v1/moves/start-session/lost_cities").json()
    session_id = started["session_id"]
    state = get_state(session_id)
    state.game_data["current_phase"] = "draw_a_card"
    state.game_data["pending_draw"] = True
    state.game_data["draw_pile"] = ["b_5"]
    state.game_data["round"] = 3
    from app.core.engine import GameEngine
    from app.games.registry import ensure_validator
    engine = GameEngine("lost_cities", ensure_validator("lost_cities"))
    legal_move = engine.get_legal_moves(state, "player_1")[0]

    response = client.post(
        f"/api/v1/moves/{session_id}/move",
        json=legal_move,
    )

    assert response.status_code == 200
    assert response.json()["winner"] in {"player_1", "player_2", "draw"}
    sessions = client.get("/api/v1/sessions/filter?game_id=lost_cities").json()
    completed = next(session for session in sessions if session["id"] == session_id)
    assert completed["finished_at"]
    assert completed["winner"] == response.json()["winner"]
    assert completed["result_summary_json"]


def test_lost_cities_ai_route_can_use_ppo_provider(monkeypatch):
    requested_difficulties = []

    def choose_move(state, player_id, validator, difficulty="hard"):
        requested_difficulties.append(difficulty)
        return validator.get_legal_moves(state, player_id)[0]

    monkeypatch.setattr(
        "app.games.lost_cities.rl_inference.choose_live_move",
        choose_move,
    )
    client = TestClient(app)
    started = client.post("/api/v1/moves/start-session/lost_cities").json()

    response = client.post(
        "/api/v1/moves/ai",
        json={"sessionId": started["session_id"], "provider": "ppo", "aiDifficulty": "medium"},
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["ai_provider"] == "ppo"
    assert response.json()["ai_difficulty"] == "medium"
    assert requested_difficulties and set(requested_difficulties) == {"medium"}
    assert response.json()["move"]


def test_lost_cities_ai_route_defaults_to_ppo(monkeypatch):
    monkeypatch.delenv("RBGG_LOST_CITIES_AI_PROVIDER", raising=False)
    requested_difficulties = []

    def choose_move(state, player_id, validator, difficulty="hard"):
        requested_difficulties.append(difficulty)
        return validator.get_legal_moves(state, player_id)[0]

    monkeypatch.setattr(
        "app.games.lost_cities.rl_inference.choose_live_move",
        choose_move,
    )
    client = TestClient(app)
    started = client.post("/api/v1/moves/start-session/lost_cities").json()

    response = client.post(
        "/api/v1/moves/ai",
        json={"sessionId": started["session_id"]},
    )

    assert response.status_code == 200
    assert response.json()["ai_provider"] == "ppo"
    assert requested_difficulties and set(requested_difficulties) == {"hard"}


def test_lost_cities_ppo_route_rejects_unknown_difficulty():
    client = TestClient(app)
    started = client.post("/api/v1/moves/start-session/lost_cities").json()

    response = client.post(
        "/api/v1/moves/ai",
        json={"sessionId": started["session_id"], "provider": "ppo", "aiDifficulty": "expert"},
    )

    assert response.status_code == 422


def test_lost_cities_ppo_failure_falls_back_to_mcts(monkeypatch):
    from types import SimpleNamespace

    def fail_inference(*args, **kwargs):
        raise RuntimeError("simulated PPO failure")

    class FakeMCTS:
        def __init__(self, validator, config):
            self.validator = validator

        def search(self, state, player_id):
            move = self.validator.get_legal_moves(state, player_id)[0]
            return SimpleNamespace(move=move)

    monkeypatch.setattr("app.games.lost_cities.rl_inference.choose_live_move", fail_inference, raising=False)
    monkeypatch.setattr("app.core.mcts.MCTSEngine", FakeMCTS)
    client = TestClient(app)
    started = client.post("/api/v1/moves/start-session/lost_cities").json()

    response = client.post(
        "/api/v1/moves/ai",
        json={"sessionId": started["session_id"], "provider": "ppo"},
    )

    assert response.status_code == 200
    assert response.json()["ai_provider"] == "mcts"
    assert response.json()["move"]


def test_session_state_is_reloaded_from_sqlite_after_cache_clear():
    """A process restart/cache loss does not discard the active session."""
    client = TestClient(app)
    started = client.post("/api/v1/moves/start-session/checkers").json()
    session_id = started["session_id"]
    move = client.post(
        "/api/v1/moves/legal-moves", json={"session_id": session_id}
    ).json()["legal_moves"][0]
    client.post(f"/api/v1/moves/{session_id}/move", json=move)

    clear_all()

    restored = client.get(
        f"/api/v1/games/checkers?session_id={session_id}"
    ).json()
    assert restored["state"]["game_data"] != started["screen_state"].get("game_data", {})
